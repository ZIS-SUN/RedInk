"""
后端稳定性修复回归测试

覆盖审查确认的三组行为（均不发起真实网络请求）：

- S6 上游重试白名单：backend/utils/genai_client.retry_on_429 仅对
  429/配额、5xx、超时、网络连接类错误重试，其余（认证/参数/安全拦截/
  代码错误）直接抛出；流式拼接跳过 text 为 None 的 chunk；
  backend/utils/text_client 的限流判定不再被 "generateContent" 之类
  含 "rate" 子串的文本误命中
- S9 排队超时语义：ImageRateLimiter 排队超时抛 ImageQueueTimeoutError
  （消息带"图片生成排队超时"专属语义，分类为 QUEUE_TIMEOUT 而非
  NETWORK_TIMEOUT，分类断言见 errors_test.py）
- S5 重绘版本化文件名：单张重试/重新生成写入 {index}_v{毫秒时间戳}.png
  新文件名（immutable 长缓存下同名覆盖会让用户跨会话看到旧图），
  历史记录/SSE 返回/目录扫描同步拿到新名，旧版本文件被清理，
  重绘后的封面仍可作为后续重试的参考图
"""
import os
import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.services.history import HistoryService
from backend.services.history_image_merger import HistoryImageMerger
from backend.services.image import ImageService
from backend.services.image_rate_limiter import ImageQueueTimeoutError, ImageRateLimiter
from backend.utils import genai_client
from backend.utils import text_client as text_client_module
from backend.utils.genai_client import GenAIClient


# ==================== S6: genai 重试白名单 ====================

@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch):
    """重试退避不真实睡眠，加速测试"""
    monkeypatch.setattr(genai_client.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(text_client_module.time, "sleep", lambda seconds: None)


def _run_decorated(error: Exception, max_retries: int = 3):
    """用固定异常驱动装饰器，返回 (调用次数, 捕获到的最终异常)"""
    calls = {"count": 0}

    @genai_client.retry_on_429(max_retries=max_retries, base_delay=2)
    def always_fail():
        calls["count"] += 1
        raise error

    with pytest.raises(Exception) as exc_info:
        always_fail()
    return calls["count"], exc_info.value


class TestGenaiRetryWhitelist:
    def test_rate_limit_error_is_retried(self):
        count, _ = _run_decorated(Exception("429 RESOURCE_EXHAUSTED: quota exceeded"))
        assert count == 3

    def test_server_error_is_retried(self):
        count, _ = _run_decorated(Exception("HTTP 503 Service Unavailable"))
        assert count == 3

    def test_timeout_error_is_retried(self):
        count, _ = _run_decorated(Exception("Request timed out"))
        assert count == 3

    def test_connection_error_is_retried(self):
        count, _ = _run_decorated(Exception("Connection reset by peer"))
        assert count == 3

    def test_safety_error_not_retried(self):
        """安全拦截是确定性失败，重试只会重复扣费"""
        count, raised = _run_decorated(
            Exception("The response was blocked due to SAFETY")
        )
        assert count == 1
        assert "安全过滤" in str(raised)

    def test_invalid_argument_not_retried(self):
        count, _ = _run_decorated(Exception("400 INVALID_ARGUMENT: bad prompt"))
        assert count == 1

    def test_auth_error_not_retried(self):
        count, _ = _run_decorated(Exception("401 UNAUTHENTICATED"))
        assert count == 1

    def test_type_error_not_retried(self):
        """代码类错误（如历史上 chunk.text 为 None 的 TypeError）不再白跑重试"""
        count, _ = _run_decorated(
            TypeError('can only concatenate str (not "NoneType") to str')
        )
        assert count == 1

    def test_unknown_error_not_retried(self):
        """白名单之外的未知错误默认不重试（历史黑名单行为会重试 3 次）"""
        count, _ = _run_decorated(Exception("something completely unexpected"))
        assert count == 1

    def test_status_code_attribute_takes_priority_over_text(self):
        """异常携带明确状态码时以状态码为准：404 即使文案含 timeout 也不重试"""
        error = Exception("deadline timeout while fetching model")
        error.code = 404
        count, _ = _run_decorated(error)
        assert count == 1

    def test_retryable_status_code_attribute_is_retried(self):
        error = Exception("upstream hiccup")
        error.status_code = 429
        count, _ = _run_decorated(error)
        assert count == 3

    def test_success_returns_without_retry(self):
        calls = {"count": 0}

        @genai_client.retry_on_429(max_retries=3, base_delay=2)
        def succeed():
            calls["count"] += 1
            return "ok"

        assert succeed() == "ok"
        assert calls["count"] == 1


def _make_chunk(text, with_parts: bool = True):
    """构造最小化的流式 chunk（.text 属性可为 None，模拟纯 thought 部件）"""
    parts = [SimpleNamespace(text=text)] if with_parts else []
    candidate = SimpleNamespace(content=SimpleNamespace(parts=parts))
    return SimpleNamespace(candidates=[candidate], text=text)


def test_generate_text_skips_none_text_chunks():
    """思考模型 chunk 只含 thought 部件时 .text 为 None：跳过而不是 TypeError"""
    client = GenAIClient.__new__(GenAIClient)
    client.default_safety_settings = []

    stream_calls = {"count": 0}

    def fake_stream(model=None, contents=None, config=None):
        stream_calls["count"] += 1
        return iter([
            _make_chunk("你好"),
            _make_chunk(None),
            _make_chunk("，世界"),
            _make_chunk(None, with_parts=False),
        ])

    client.client = SimpleNamespace(
        models=SimpleNamespace(generate_content_stream=fake_stream)
    )

    result = client.generate_text("测试提示词", model="fake-model")

    assert result == "你好，世界"
    # 不再因 TypeError 被误判为可重试错误而重复调用（重复计费）
    assert stream_calls["count"] == 1


# ==================== S6: text_client 限流判定 ====================

class TestTextClientRateLimitDetection:
    def test_generatecontent_text_not_treated_as_rate_limit(self):
        """"generateContent" 含 "rate" 子串，历史实现会误判为限流重试"""
        error = Exception(
            "models/gemini-pro:generateContent failed with 400 INVALID_ARGUMENT"
        )
        assert text_client_module._is_rate_limited_error(error) is False

    def test_status_code_429_detected(self):
        error = text_client_module.ApiRateLimitError("限流", status_code=429)
        assert text_client_module._is_rate_limited_error(error) is True

    @pytest.mark.parametrize("message", [
        "HTTP 429 Too Many Requests",
        "rate limit exceeded",
        "rate_limit_exceeded",
        "RESOURCE_EXHAUSTED: quota exceeded",
    ])
    def test_explicit_rate_limit_phrases_detected(self, message):
        assert text_client_module._is_rate_limited_error(Exception(message)) is True

    def test_decorator_does_not_retry_non_rate_limit_error(self):
        calls = {"count": 0}

        @text_client_module.retry_on_429(max_retries=3, base_delay=2)
        def fail_with_generate_content():
            calls["count"] += 1
            raise Exception("generateContent: invalid request body")

        with pytest.raises(Exception):
            fail_with_generate_content()
        assert calls["count"] == 1

    def test_decorator_retries_rate_limit_error(self):
        calls = {"count": 0}

        @text_client_module.retry_on_429(max_retries=3, base_delay=2)
        def fail_with_429():
            calls["count"] += 1
            raise text_client_module.ApiRateLimitError("限流", status_code=429)

        with pytest.raises(Exception):
            fail_with_429()
        assert calls["count"] == 3


# ==================== S9: 限流器排队超时专属异常 ====================

class TestImageQueueTimeout:
    def test_acquire_timeout_raises_dedicated_error(self):
        limiter = ImageRateLimiter(max_concurrent=1, interval_seconds=0)
        with limiter.acquire():
            with pytest.raises(ImageQueueTimeoutError) as exc_info:
                with limiter.acquire(timeout=0.01):
                    pass  # pragma: no cover - 不应进入

        message = str(exc_info.value)
        assert "图片生成排队超时" in message
        # 保持 TimeoutError 子类，兼容既有 except TimeoutError 调用方
        assert isinstance(exc_info.value, TimeoutError)

    def test_acquire_succeeds_after_release(self):
        limiter = ImageRateLimiter(max_concurrent=1, interval_seconds=0)
        with limiter.acquire():
            pass
        with limiter.acquire(timeout=1):
            pass


# ==================== S5: 重绘版本化文件名 ====================

VERSIONED_URL_PATTERN = re.compile(r"^/api/images/task_1/1_v\d+\.png$")


def make_history_service(tmp_path: Path) -> HistoryService:
    service = HistoryService.__new__(HistoryService)
    service.history_dir = str(tmp_path)
    service.index_file = str(tmp_path / "index.json")
    service._init_index()
    return service


class RecordingGenerator:
    """记录调用参数的假生成器"""

    def __init__(self):
        self.calls = []

    def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return b"regenerated-image-bytes"


def make_image_service(tmp_path: Path, history_service=None) -> ImageService:
    service = ImageService.__new__(ImageService)
    service.generator = RecordingGenerator()
    service.provider_config = {"type": "image_api", "model": "fake-model"}
    service.use_short_prompt = False
    service.prompt_template = "{page_content}"
    service.prompt_template_short = ""
    service.history_root_dir = str(tmp_path)
    service.current_task_dir = None
    service.rate_limiter = ImageRateLimiter(max_concurrent=1, interval_seconds=0)
    service.worker_count = 1
    service.history_service = history_service
    service._task_states = {}
    return service


def _write_page_image(task_dir: Path, filename: str):
    (task_dir / filename).write_bytes(b"old-image-bytes")
    (task_dir / f"thumb_{filename}").write_bytes(b"old-thumb-bytes")


class TestVersionedRegenerate:
    def test_retry_single_image_writes_versioned_filename(self, tmp_path):
        history = make_history_service(tmp_path)
        record_id = history.create_record("topic", {
            "raw": "raw",
            "pages": [
                {"index": 0, "type": "cover", "content": "封面"},
                {"index": 1, "type": "content", "content": "内容"},
            ],
        })
        history.update_record(
            record_id,
            images={"task_id": "task_1", "generated": ["0.png", "1.png"]},
            status="completed",
        )

        service = make_image_service(tmp_path, history_service=history)
        task_dir = tmp_path / "task_1"
        task_dir.mkdir()
        _write_page_image(task_dir, "0.png")
        _write_page_image(task_dir, "1.png")

        result = service.retry_single_image(
            "task_1",
            {"index": 1, "type": "content", "content": "内容"},
            use_reference=False,
            record_id=record_id,
        )

        assert result["success"] is True
        assert VERSIONED_URL_PATTERN.match(result["image_url"]), result["image_url"]

        new_filename = result["image_url"].rsplit("/", 1)[-1]
        # 新文件与缩略图落盘
        assert (task_dir / new_filename).exists()
        assert (task_dir / f"thumb_{new_filename}").exists()
        # 旧版本文件（含缩略图）被清理，避免堆积和目录扫描回写旧名
        assert not (task_dir / "1.png").exists()
        assert not (task_dir / "thumb_1.png").exists()
        # 其他页面的文件不受影响
        assert (task_dir / "0.png").exists()

        # 历史记录同步为新文件名
        record = history.get_record(record_id)
        assert record["images"]["generated"] == ["0.png", new_filename]

    def test_repeated_regenerate_keeps_single_version(self, tmp_path):
        """连续重绘同一页只保留最新版本文件"""
        service = make_image_service(tmp_path)
        task_dir = tmp_path / "task_1"
        task_dir.mkdir()
        _write_page_image(task_dir, "1.png")
        page = {"index": 1, "type": "content", "content": "内容"}

        first = service.retry_single_image("task_1", page, use_reference=False)
        time.sleep(0.002)  # 确保毫秒时间戳前进，文件名不同
        second = service.retry_single_image("task_1", page, use_reference=False)

        assert first["success"] and second["success"]
        page_files = [
            name for name in os.listdir(task_dir)
            if not name.startswith("thumb_") and name.startswith("1")
        ]
        assert page_files == [second["image_url"].rsplit("/", 1)[-1]]

    def test_regenerated_cover_still_used_as_reference(self, tmp_path):
        """封面被重绘成版本化文件名后，后续重试仍能从磁盘找到参考图"""
        service = make_image_service(tmp_path)
        task_dir = tmp_path / "task_1"
        task_dir.mkdir()
        # 模拟封面重绘后的状态：只剩带版本的封面文件
        (task_dir / "0_v1721470000000.png").write_bytes(b"versioned-cover-bytes")

        result = service.retry_single_image(
            "task_1",
            {"index": 1, "type": "content", "content": "内容"},
            use_reference=True,
        )

        assert result["success"] is True
        assert service.generator.calls, "应调用生成器"
        reference = service.generator.calls[0].get("reference_images") or []
        assert b"versioned-cover-bytes" in reference

    def test_batch_generate_still_uses_plain_filenames(self, tmp_path):
        """整批生成协议不变：仍写 {index}.png（版本化仅限单张重绘路径）"""
        service = make_image_service(tmp_path)
        events = list(service.generate_images(
            [
                {"index": 0, "type": "cover", "content": "封面"},
                {"index": 1, "type": "content", "content": "内容"},
            ],
            task_id="task_1",
        ))

        finish = events[-1]
        assert finish["event"] == "finish"
        assert finish["data"]["images"] == ["0.png", "1.png"]


class TestVersionedFilenameCompatibility:
    def test_files_by_index_prefers_latest_version(self, tmp_path):
        task_dir = tmp_path / "task_1"
        task_dir.mkdir()
        for name in [
            "0.png", "0_v100.png", "0_v200.png",
            "1.png", "thumb_0_v200.png", "extra.txt", "abc.png",
        ]:
            (task_dir / name).write_bytes(b"x")

        files = HistoryImageMerger.files_by_index(str(tmp_path), "task_1")

        assert files == {0: "0_v200.png", 1: "1.png"}

    def test_sync_record_images_picks_versioned_file(self, tmp_path):
        """目录扫描同步能识别版本化文件名（不再要求纯数字文件名）"""
        history = make_history_service(tmp_path)
        record_id = history.create_record("topic", {
            "raw": "raw",
            "pages": [{"index": 0, "type": "cover", "content": "封面"}],
        })
        history.update_record(
            record_id,
            images={"task_id": "task_1", "generated": []},
        )
        task_dir = tmp_path / "task_1"
        task_dir.mkdir()
        (task_dir / "0_v1721470000000.png").write_bytes(b"x")

        result = history.sync_record_images(record_id)

        assert result["success"] is True
        record = history.get_record(record_id)
        assert record["images"]["generated"] == ["0_v1721470000000.png"]

    def test_image_routes_filename_pattern_accepts_versioned(self):
        from backend.routes.image_routes import _IMAGE_FILENAME_PATTERN

        assert _IMAGE_FILENAME_PATTERN.match("1_v1721470000000.png")
        assert _IMAGE_FILENAME_PATTERN.match("thumb_1_v1721470000000.png")
        # 路径遍历仍被拒绝
        assert not _IMAGE_FILENAME_PATTERN.match("../evil.png")
        assert not _IMAGE_FILENAME_PATTERN.match("1_v123/../../x.png")
