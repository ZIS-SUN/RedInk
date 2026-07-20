"""
图片生成 SSE 流式协议测试（POST /api/generate 与 POST /api/retry-failed）

为后端 event-stream 生成器补齐协议回归保护，对应前端
frontend/src/api/__tests__/sseParser.test.ts 与 src/api/image.ts 的消费契约：

- 事件序列与字段完整性：progress → complete/error → finish；
  retry_start → complete/error → retry_finish
- 参数校验：非法请求返回 400 JSON（application/json，非 SSE）
- 断连清理：客户端提前断开（GeneratorExit）时线程池取消尚未开始的任务
- 线格式：每个事件符合 `event: X\\ndata: {json}\\n\\n` 且 data 可被 json.loads

不发起任何真实网络请求：
- 多数用例在生成器工厂层注入 FakeImageGenerator（_generate_single_image
  真实执行，覆盖保存图片/缩略图路径），失败注入通过页面内容里的
  FAIL_MARKER 触发；
- 断连用例在 _generate_single_image 层打桩，以便精确控制并发时序。

任务状态隔离：每个测试用 ImageService.__new__ 装配独立实例
（history_root_dir 指向 tmp_path），并把路由层 get_image_service
monkeypatch 到该实例，不触碰全局单例，测试之间无状态串扰。
"""
import json
import os
import re
import threading
import time

import pytest

from backend.routes import image_routes
from backend.services.image import ImageService
from backend.services.image_rate_limiter import ImageRateLimiter


# ==================== 测试工具 ====================

FAIL_MARKER = "[[FAIL]]"

# 与前端 readSseResponse 注册的 handler 一致的事件名集合
GENERATE_EVENTS = {"progress", "complete", "error", "finish"}
RETRY_EVENTS = {"retry_start", "complete", "error", "retry_finish"}


def parse_sse_events(body: str):
    """把 SSE 响应体解析为 (event, data_dict) 列表（与大纲流式测试同款）"""
    events = []
    for block in body.split('\n\n'):
        if not block.strip():
            continue
        event_type = 'message'
        data = None
        for line in block.split('\n'):
            if line.startswith('event: '):
                event_type = line[len('event: '):]
            elif line.startswith('data: '):
                data = json.loads(line[len('data: '):])
        events.append((event_type, data))
    return events


class FakeImageGenerator:
    """假图片生成器：prompt 含 FAIL_MARKER 时抛错，其余返回固定图片字节"""

    def __init__(self, error_message="HTTP 429: rate limit exceeded"):
        self.calls = []
        self.error_message = error_message

    def generate_image(self, prompt=None, **kwargs):
        self.calls.append(prompt)
        if prompt and FAIL_MARKER in prompt:
            raise Exception(self.error_message)
        return b"fake-image-bytes"


def make_image_service(tmp_path, worker_count: int = 1) -> ImageService:
    """绕过 __init__（避免读取真实配置/API Key），手工装配依赖"""
    service = ImageService.__new__(ImageService)
    service.generator = FakeImageGenerator()
    service.provider_name = "fake_provider"
    service.provider_config = {"type": "image_api", "model": "fake-model"}
    service.use_short_prompt = False
    service.prompt_template = "{page_content}"
    service.prompt_template_short = ""
    service.history_root_dir = str(tmp_path / "history")
    os.makedirs(service.history_root_dir, exist_ok=True)
    service.current_task_dir = None
    service.rate_limiter = ImageRateLimiter(
        max_concurrent=max(worker_count, 1), interval_seconds=0
    )
    service.worker_count = worker_count
    # record_id 均不传，历史服务不会被触达
    service.history_service = None
    service._task_states = {}
    return service


@pytest.fixture
def image_env(tmp_path, monkeypatch):
    """构造独立 ImageService 并接管路由层的 get_image_service"""
    def _build(worker_count: int = 1) -> ImageService:
        service = make_image_service(tmp_path, worker_count=worker_count)
        monkeypatch.setattr(image_routes, "get_image_service", lambda: service)
        return service
    return _build


def post_generate(client, pages, task_id="task_sse_test", **extra):
    payload = {"pages": pages, "task_id": task_id}
    payload.update(extra)
    return client.post("/api/generate", json=payload)


# ==================== /api/generate 事件序列 ====================

def test_generate_all_success_event_sequence(client, image_env, sample_pages):
    service = image_env(worker_count=1)
    task_id = "task_all_ok"

    response = post_generate(client, sample_pages, task_id=task_id)

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-cache"

    events = parse_sse_events(response.get_data(as_text=True))
    # 顺序模式（worker_count=1）：封面 → batch_start → 逐页 progress/complete → finish
    assert [e[0] for e in events] == [
        "progress", "complete",           # 封面
        "progress",                       # batch_start
        "progress", "complete",           # 第 1 页
        "progress", "complete",           # 第 2 页
        "progress", "complete",           # 第 3 页
        "finish",
    ]

    # 封面 progress：进度计数从 1 开始
    cover_progress = events[0][1]
    assert cover_progress["index"] == 0
    assert cover_progress["status"] == "generating"
    assert cover_progress["current"] == 1
    assert cover_progress["total"] == 4
    assert cover_progress["phase"] == "cover"

    # 封面 complete：index/status/image_url（image_url 内嵌 task_id 与文件名）
    cover_complete = events[1][1]
    assert cover_complete["index"] == 0
    assert cover_complete["status"] == "done"
    assert cover_complete["image_url"] == f"/api/images/{task_id}/0.png"

    # batch_start：已完成 1 张（封面）
    batch_start = events[2][1]
    assert batch_start["status"] == "batch_start"
    assert batch_start["current"] == 1
    assert batch_start["total"] == 4

    # 逐页 progress 的进度计数单调递增（current = 已生成数 + 1）
    page_progress = [events[i][1] for i in (3, 5, 7)]
    assert [p["index"] for p in page_progress] == [1, 2, 3]
    assert [p["current"] for p in page_progress] == [2, 3, 4]
    assert all(p["total"] == 4 for p in page_progress)

    # 逐页 complete 的 image_url 以对应文件名结尾
    page_complete = [events[i][1] for i in (4, 6, 8)]
    for expected_index, data in zip((1, 2, 3), page_complete):
        assert data["index"] == expected_index
        assert data["status"] == "done"
        assert data["image_url"] == f"/api/images/{task_id}/{expected_index}.png"

    # finish：task_id、images 列表按 index 对齐、统计字段完整
    finish = events[-1][1]
    assert finish["success"] is True
    assert finish["task_id"] == task_id
    assert finish["images"] == ["0.png", "1.png", "2.png", "3.png"]
    assert finish["total"] == 4
    assert finish["completed"] == 4
    assert finish["failed"] == 0
    assert finish["failed_indices"] == []

    # 生成路径真实执行：原图与缩略图都已落盘
    task_dir = os.path.join(service.history_root_dir, task_id)
    assert os.path.isfile(os.path.join(task_dir, "0.png"))
    assert os.path.isfile(os.path.join(task_dir, "thumb_0.png"))


def test_generate_partial_failure_error_and_finish_stats(client, image_env):
    image_env(worker_count=1)
    task_id = "task_partial_fail"
    pages = [
        {"index": 0, "type": "cover", "content": "封面"},
        {"index": 1, "type": "content", "content": "第一页"},
        {"index": 2, "type": "content", "content": f"第二页 {FAIL_MARKER}"},
        {"index": 3, "type": "content", "content": "第三页"},
    ]

    response = post_generate(client, pages, task_id=task_id)
    events = parse_sse_events(response.get_data(as_text=True))

    assert [e[0] for e in events] == [
        "progress", "complete",
        "progress",
        "progress", "complete",
        "progress", "error",
        "progress", "complete",
        "finish",
    ]

    # error 事件：结构化字段（经 _normalize_sse_error 归一化）
    error_data = events[6][1]
    assert error_data["index"] == 2
    assert error_data["status"] == "error"
    assert error_data["retryable"] is True
    assert error_data["phase"] == "content"
    assert isinstance(error_data["message"], str) and error_data["message"]
    assert isinstance(error_data["error"], dict)
    # "HTTP 429: rate limit exceeded" 应被分类为限流错误
    assert error_data["error"]["code"] == "RATE_LIMITED"
    assert error_data["error"]["status"] == 429
    assert error_data["error"]["retryable"] is True

    # finish：失败统计与 images 占位对齐
    finish = events[-1][1]
    assert finish["success"] is False
    assert finish["task_id"] == task_id
    assert finish["images"] == ["0.png", "1.png", "", "3.png"]
    assert finish["total"] == 4
    assert finish["completed"] == 3
    assert finish["failed"] == 1
    assert finish["failed_indices"] == [2]


def test_generate_invalid_page_yields_validate_error_first(client, image_env):
    """畸形页（缺 content）产出 phase=validate 的结构化 error，不中断整条流"""
    image_env(worker_count=1)
    pages = [
        {"index": 0, "type": "cover", "content": "封面"},
        {"index": 1, "type": "content"},  # 缺 content 字段
    ]

    response = post_generate(client, pages, task_id="task_bad_page")
    events = parse_sse_events(response.get_data(as_text=True))

    # 畸形页 error 在生成开始前先行发出
    assert [e[0] for e in events] == ["error", "progress", "complete", "finish"]

    error_data = events[0][1]
    assert error_data["index"] == 1
    assert error_data["status"] == "error"
    assert error_data["phase"] == "validate"
    assert error_data["retryable"] is False
    # 注意：_normalize_sse_error 会把 message 覆盖为归一化后的通用文案
    # （"操作失败：请稍后重试…"），原始校验原因保留在 error.detail 中
    assert isinstance(error_data["message"], str) and error_data["message"]
    assert isinstance(error_data["error"], dict)
    assert "content" in error_data["error"]["detail"]

    finish = events[-1][1]
    assert finish["success"] is False
    assert finish["failed"] == 1
    assert finish["failed_indices"] == [1]
    assert finish["completed"] == 1


def test_generate_error_event_message_normalized(client, image_env):
    """error 事件的 message 被归一化为「标题：建议」的用户友好文案"""
    service = image_env(worker_count=1)
    service.generator.error_message = "HTTP 500: upstream exploded"
    pages = [{"index": 0, "type": "cover", "content": f"封面 {FAIL_MARKER}"}]

    response = post_generate(client, pages, task_id="task_err_norm")
    events = parse_sse_events(response.get_data(as_text=True))

    assert [e[0] for e in events] == ["progress", "error", "finish"]
    error_data = events[1][1]
    assert isinstance(error_data["error"], dict)
    assert error_data["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    # message 与 error.title/suggestion 一致（前端直接展示 message）
    assert error_data["message"].startswith(error_data["error"]["title"])


# ==================== /api/generate 参数校验（400 JSON，非 SSE） ====================

@pytest.mark.parametrize("payload", [
    {},
    {"pages": []},
    {"pages": None},
])
def test_generate_missing_or_empty_pages_returns_400_json(client, image_env, payload):
    image_env()
    response = client.post("/api/generate", json=payload)
    data = response.get_json()

    assert response.status_code == 400
    assert response.mimetype == "application/json"
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert data["error_message"]


def test_generate_malformed_json_body_returns_400(client, image_env):
    image_env()
    response = client.post(
        "/api/generate", data="{not valid json", content_type="application/json"
    )
    data = response.get_json()

    assert response.status_code == 400
    assert response.mimetype == "application/json"
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_generate_non_json_content_type_returns_400(client, image_env):
    image_env()
    response = client.post(
        "/api/generate", data="pages=1", content_type="text/plain"
    )
    data = response.get_json()

    assert response.status_code == 400
    assert response.mimetype == "application/json"
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_generate_user_images_must_be_list_returns_400(client, image_env, sample_pages):
    image_env()
    response = post_generate(client, sample_pages, user_images="not-a-list")
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_generate_too_many_user_images_returns_400(client, image_env, sample_pages):
    image_env()
    response = post_generate(client, sample_pages, user_images=["aGVsbG8="] * 6)
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_generate_invalid_base64_user_image_returns_400(client, image_env, sample_pages):
    image_env()
    response = post_generate(client, sample_pages, user_images=["!!!not-base64!!!"])
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_generate_illegal_task_id_returns_400(client, image_env, sample_pages):
    """路径遍历风格的 task_id 应在进入 SSE 流之前被拒绝（400 JSON 而非流中断）"""
    image_env()
    response = post_generate(client, sample_pages, task_id="../evil")
    data = response.get_json()

    assert response.status_code == 400
    assert response.mimetype == "application/json"
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_generate_null_json_body_should_return_400(client, image_env):
    image_env()
    response = client.post(
        "/api/generate", data="null", content_type="application/json"
    )
    assert response.status_code == 400


# ==================== /api/generate 断连清理 ====================

def test_generate_client_disconnect_cancels_pending_pool_tasks(app, image_env):
    """
    客户端提前断开（关闭响应迭代器触发 GeneratorExit）后，
    线程池中尚未开始的生成任务被 cancel_futures 取消，不再执行。
    """
    service = image_env(worker_count=2)
    gate = threading.Event()
    content_calls = []

    def fake_generate(page, task_id, reference_image=None, retry_count=0,
                      full_outline="", user_images=None, user_topic="",
                      record_id=None, total_count=None, style_prompt="",
                      retry_hint=False, defer_index_sync=False):
        index = page["index"]
        if page.get("type") == "cover":
            # 生成流会回读封面文件作为参考图，须真实落盘
            task_dir = os.path.join(service.history_root_dir, task_id)
            with open(os.path.join(task_dir, f"{index}.png"), "wb") as f:
                f.write(b"cover-bytes")
            return (index, True, f"{index}.png", None)
        content_calls.append(index)
        # 卡住已开始执行的 worker，模拟慢速上游
        gate.wait(timeout=10)
        return (index, True, f"{index}.png", None)

    service._generate_single_image = fake_generate

    content_total = 6
    pages = [{"index": 0, "type": "cover", "content": "封面"}] + [
        {"index": i, "type": "content", "content": f"第{i}页"}
        for i in range(1, content_total + 1)
    ]

    test_client = app.test_client()
    response = test_client.post(
        "/api/generate",
        json={"pages": pages, "task_id": "task_disconnect"},
        buffered=False,
    )

    # 消费到线程池阻塞前生成器主动推送的全部事件：
    # 封面 progress + 封面 complete + batch_start + 6 条逐页 progress = 9 个事件
    iterator = iter(response.response)
    data_chunks = 0
    while data_chunks < 3 + content_total:
        chunk = next(iterator)
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        if chunk.startswith("data: "):
            data_chunks += 1

    # close() 触发 GeneratorExit → shutdown(cancel_futures=True) 取消排队任务，
    # 随后 with 退出会等待 2 个已在执行的 worker，由后台定时器释放闸门
    releaser = threading.Timer(0.3, gate.set)
    releaser.start()
    try:
        response.close()
    finally:
        gate.set()
        releaser.cancel()

    # 已真正开始执行的最多 worker_count（2）个，其余排队任务被取消
    assert len(content_calls) <= 2
    assert len(content_calls) < content_total

    # finally 分支已释放任务状态中的大对象（断连也会清理）
    task_state = service._task_states.get("task_disconnect")
    assert task_state is not None
    assert task_state["cover_image"] is None
    assert task_state["user_images"] is None


# ==================== /api/retry-failed 事件序列 ====================

def test_retry_failed_success_event_sequence_and_state_update(client, image_env, sample_pages):
    service = image_env(worker_count=1)
    task_id = "task_retry_ok"
    # 预置任务状态：0 已生成，1/2 失败（cover_image 直接给内存值，避免读盘）
    service._set_task_state(task_id, {
        "pages": sample_pages,
        "generated": {0: "0.png"},
        "failed": {1: "boom", 2: "boom"},
        "cover_image": b"cover-bytes",
        "full_outline": "",
        "user_images": None,
        "user_topic": "",
        "style_prompt": "",
    })

    retry_pages = [
        {"index": 1, "type": "content", "content": "第一页"},
        {"index": 2, "type": "content", "content": "第二页"},
    ]
    response = client.post("/api/retry-failed", json={
        "task_id": task_id, "pages": retry_pages,
    })

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"

    events = parse_sse_events(response.get_data(as_text=True))
    assert [e[0] for e in events] == [
        "retry_start", "complete", "complete", "retry_finish",
    ]

    retry_start = events[0][1]
    assert retry_start["total"] == 2
    assert "2" in retry_start["message"]

    for expected_index, (_, data) in zip((1, 2), events[1:3]):
        assert data["index"] == expected_index
        assert data["status"] == "done"
        assert data["image_url"] == f"/api/images/{task_id}/{expected_index}.png"

    retry_finish = events[-1][1]
    assert retry_finish == {
        "success": True, "total": 2, "completed": 2, "failed": 0,
    }

    # 任务状态同步更新：失败清空、生成表补齐
    state = service.get_task_state(task_id)
    assert state["failed"] == {}
    assert state["generated"] == {0: "0.png", 1: "1.png", 2: "2.png"}


def test_retry_failed_partial_failure_sequence(client, image_env):
    image_env(worker_count=1)
    retry_pages = [
        {"index": 1, "type": "content", "content": "第一页"},
        {"index": 2, "type": "content", "content": f"第二页 {FAIL_MARKER}"},
    ]

    response = client.post("/api/retry-failed", json={
        "task_id": "task_retry_partial", "pages": retry_pages,
    })
    events = parse_sse_events(response.get_data(as_text=True))

    assert [e[0] for e in events] == [
        "retry_start", "complete", "error", "retry_finish",
    ]

    error_data = events[2][1]
    assert error_data["index"] == 2
    assert error_data["status"] == "error"
    assert error_data["retryable"] is True
    assert isinstance(error_data["message"], str) and error_data["message"]
    assert isinstance(error_data["error"], dict)
    assert error_data["error"]["code"] == "RATE_LIMITED"

    retry_finish = events[-1][1]
    assert retry_finish == {
        "success": False, "total": 2, "completed": 1, "failed": 1,
    }


def test_retry_failed_unknown_task_still_streams(client, image_env):
    """
    任务状态不存在（如后端重启后）时不报错：retry-failed 直接按无参考图
    重新生成并正常走完事件流（当前协议没有任务不存在的 404 分支）。
    """
    image_env(worker_count=1)
    response = client.post("/api/retry-failed", json={
        "task_id": "task_never_seen",
        "pages": [{"index": 1, "type": "content", "content": "第一页"}],
    })

    assert response.status_code == 200
    events = parse_sse_events(response.get_data(as_text=True))
    assert [e[0] for e in events] == ["retry_start", "complete", "retry_finish"]
    assert events[-1][1]["success"] is True


@pytest.mark.parametrize("payload", [
    {},
    {"task_id": "task_x"},
    {"pages": [{"index": 1, "type": "content", "content": "x"}]},
])
def test_retry_failed_missing_params_returns_400_json(client, image_env, payload):
    image_env()
    response = client.post("/api/retry-failed", json=payload)
    data = response.get_json()

    assert response.status_code == 400
    assert response.mimetype == "application/json"
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_retry_failed_empty_pages_returns_400(client, image_env):
    """无失败图片（pages 为空列表）时按参数校验拒绝，不进入 SSE 流"""
    image_env()
    response = client.post("/api/retry-failed", json={
        "task_id": "task_x", "pages": [],
    })
    data = response.get_json()

    assert response.status_code == 400
    assert response.mimetype == "application/json"
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_retry_failed_illegal_task_id_returns_400(client, image_env):
    image_env()
    response = client.post("/api/retry-failed", json={
        "task_id": "../evil",
        "pages": [{"index": 1, "type": "content", "content": "x"}],
    })
    data = response.get_json()

    assert response.status_code == 400
    assert response.mimetype == "application/json"
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_retry_failed_null_json_body_should_return_400(client, image_env):
    image_env()
    response = client.post(
        "/api/retry-failed", data="null", content_type="application/json"
    )
    assert response.status_code == 400


# ==================== SSE 线格式（前端 sseParser 的解析前提） ====================

def assert_sse_wire_format(body: str, allowed_events: set):
    """
    校验 SSE 响应体的线格式：
    每个事件块恰为 `event: X\\ndata: {json}` 两行，块之间以空行分隔，
    data 为单行且可被 json.loads —— 即前端 SseParser 的全部解析前提。
    """
    assert body.endswith("\n\n")
    blocks = [b for b in body.split("\n\n") if b]
    assert blocks
    for block in blocks:
        lines = block.split("\n")
        assert len(lines) == 2, f"事件块应恰为两行: {block!r}"
        assert lines[0].startswith("event: ")
        assert lines[1].startswith("data: ")
        event_name = lines[0][len("event: "):]
        assert re.fullmatch(r"[a-z_]+", event_name)
        assert event_name in allowed_events
        payload = json.loads(lines[1][len("data: "):])
        assert isinstance(payload, dict)


def test_generate_sse_wire_format(client, image_env):
    image_env(worker_count=1)
    pages = [
        {"index": 0, "type": "cover", "content": "封面"},
        {"index": 1, "type": "content", "content": "含冒号: 与换行\n的文案"},
        {"index": 2, "type": "content", "content": f"失败页 {FAIL_MARKER}"},
    ]

    response = post_generate(client, pages, task_id="task_wire_gen")

    assert response.mimetype == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["X-Accel-Buffering"] == "no"

    body = response.get_data(as_text=True)
    assert_sse_wire_format(body, GENERATE_EVENTS)
    # 成功与失败路径的事件均已覆盖到
    event_names = {e[0] for e in parse_sse_events(body)}
    assert {"progress", "complete", "error", "finish"} <= event_names


def test_retry_failed_sse_wire_format(client, image_env):
    image_env(worker_count=1)
    response = client.post("/api/retry-failed", json={
        "task_id": "task_wire_retry",
        "pages": [
            {"index": 1, "type": "content", "content": "正常页"},
            {"index": 2, "type": "content", "content": f"失败页 {FAIL_MARKER}"},
        ],
    })

    assert response.mimetype == "text/event-stream"
    body = response.get_data(as_text=True)
    assert_sse_wire_format(body, RETRY_EVENTS)
    event_names = {e[0] for e in parse_sse_events(body)}
    assert {"retry_start", "complete", "error", "retry_finish"} <= event_names


# ==================== SSE 心跳（慢生成期间保活，防前端空闲熔断） ====================

class SlowFakeImageGenerator(FakeImageGenerator):
    """模拟慢速上游：每张图阻塞 delay_seconds 秒"""

    def __init__(self, delay_seconds: float = 0.3):
        super().__init__()
        self.delay_seconds = delay_seconds

    def generate_image(self, prompt=None, **kwargs):
        time.sleep(self.delay_seconds)
        return super().generate_image(prompt=prompt, **kwargs)


def make_slow_service(image_env, worker_count: int = 1, delay_seconds: float = 0.3):
    """
    构造慢速生成的服务，并把心跳间隔压到 50ms 加速测试
    （实例属性覆盖类常量 HEARTBEAT_INTERVAL_SECONDS）
    """
    service = image_env(worker_count=worker_count)
    service.generator = SlowFakeImageGenerator(delay_seconds=delay_seconds)
    service.HEARTBEAT_INTERVAL_SECONDS = 0.05
    return service


def split_heartbeats(events):
    """把事件列表拆为 (业务事件, 心跳事件)"""
    business = [e for e in events if e[0] != "heartbeat"]
    heartbeats = [e for e in events if e[0] == "heartbeat"]
    return business, heartbeats


def test_generate_serial_slow_pages_emit_heartbeats(client, image_env):
    """顺序模式下单张图阻塞期间周期性下发 heartbeat，业务事件序列不变"""
    make_slow_service(image_env, worker_count=1)
    pages = [
        {"index": 0, "type": "cover", "content": "封面"},
        {"index": 1, "type": "content", "content": "第一页"},
    ]

    response = post_generate(client, pages, task_id="task_hb_serial")
    body = response.get_data(as_text=True)

    # 心跳是合法 SSE 事件（event: heartbeat\ndata: {json}\n\n）
    assert_sse_wire_format(body, GENERATE_EVENTS | {"heartbeat"})

    business, heartbeats = split_heartbeats(parse_sse_events(body))
    assert heartbeats, "阻塞生成期间应下发心跳事件"
    # 心跳携带毫秒时间戳，前端未注册该事件类型会安全忽略
    assert all(isinstance(hb[1].get("ts"), int) for hb in heartbeats)
    # 过滤心跳后，业务事件的语义与顺序与既有协议完全一致
    assert [e[0] for e in business] == [
        "progress", "complete",
        "progress",
        "progress", "complete",
        "finish",
    ]
    # 心跳出现在生成阻塞期间（第一个业务事件之后、最后一个之前）
    all_events = parse_sse_events(body)
    first_hb = next(i for i, e in enumerate(all_events) if e[0] == "heartbeat")
    assert 0 < first_hb < len(all_events) - 1


def test_generate_concurrent_slow_pages_emit_heartbeats(client, image_env):
    """高并发模式下等待批次完成期间同样下发心跳"""
    make_slow_service(image_env, worker_count=2)
    pages = [
        {"index": 0, "type": "cover", "content": "封面"},
        {"index": 1, "type": "content", "content": "第一页"},
        {"index": 2, "type": "content", "content": "第二页"},
    ]

    response = post_generate(client, pages, task_id="task_hb_parallel")
    body = response.get_data(as_text=True)

    assert_sse_wire_format(body, GENERATE_EVENTS | {"heartbeat"})

    business, heartbeats = split_heartbeats(parse_sse_events(body))
    assert heartbeats, "并发等待期间应下发心跳事件"
    # 封面 → batch_start → 2 条 progress → 2 条 complete → finish
    assert [e[0] for e in business] == [
        "progress", "complete",
        "progress",
        "progress", "progress",
        "complete", "complete",
        "finish",
    ]
    finish = business[-1][1]
    assert finish["success"] is True
    assert finish["completed"] == 3


def test_retry_failed_slow_pages_emit_heartbeats(client, image_env):
    """批量重试（顺序模式）阻塞期间同样下发心跳，业务事件序列不变"""
    make_slow_service(image_env, worker_count=1)

    response = client.post("/api/retry-failed", json={
        "task_id": "task_hb_retry",
        "pages": [{"index": 1, "type": "content", "content": "第一页"}],
    })
    body = response.get_data(as_text=True)

    assert_sse_wire_format(body, RETRY_EVENTS | {"heartbeat"})

    business, heartbeats = split_heartbeats(parse_sse_events(body))
    assert heartbeats, "阻塞生成期间应下发心跳事件"
    assert [e[0] for e in business] == ["retry_start", "complete", "retry_finish"]
    assert business[-1][1]["success"] is True


def test_generate_fast_pages_emit_no_heartbeat(client, image_env, sample_pages):
    """快速完成的生成不产生心跳：既有事件协议对旧前端完全兼容"""
    image_env(worker_count=1)

    response = post_generate(client, sample_pages, task_id="task_hb_none")
    events = parse_sse_events(response.get_data(as_text=True))

    assert all(e[0] != "heartbeat" for e in events)
