"""
审查修复的回归测试

覆盖：
- P1-1 任务状态字典读写竞态（重试路径在状态被并发淘汰时不抛 KeyError）
- P1-2 配置文件原子写入与并发保存
- P2-1 开发/打包模式下 API 404 统一返回结构化 JSON
- P2-2 重试时封面参考图按封面页 index 推导（不硬编码 0.png）
- P2-3 图片文件原子写入
- P2-5 /api/images 按扩展名推断 mimetype
- P2-7 服务单例惰性初始化的双检查锁定
"""
import threading
import time
from pathlib import Path

import yaml

from backend.services.history import HistoryService
from backend.services.image import ImageService
from backend.services.image_rate_limiter import ImageRateLimiter


# ==================== 测试辅助 ====================

class RecordingGenerator:
    """记录调用参数的假生成器"""

    def __init__(self):
        self.calls = []

    def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return b"image-bytes"


class EvictingDict(dict):
    """
    模拟「membership 检查通过后、取值前条目被并发容量淘汰」的字典。

    只要重试路径重新引入 "if task_id in ...: dict[task_id]" 的
    check-then-use 模式，本字典就会让它抛出 KeyError。
    """

    def __contains__(self, key):
        present = super().__contains__(key)
        if present:
            # 模拟检查后立即被 _set_task_state 的容量淘汰移除
            super().pop(key)
        return present


def make_history_service(tmp_path: Path) -> HistoryService:
    service = HistoryService.__new__(HistoryService)
    service.history_dir = str(tmp_path)
    service.index_file = str(tmp_path / "index.json")
    service._init_index()
    return service


def make_image_service(tmp_path: Path, history_service=None, generator=None) -> ImageService:
    image_service = ImageService.__new__(ImageService)
    image_service.generator = generator or RecordingGenerator()
    image_service.provider_config = {"type": "image_api", "model": "gpt-image-2"}
    image_service.use_short_prompt = False
    image_service.prompt_template = "{page_content}"
    image_service.prompt_template_short = ""
    image_service.history_root_dir = str(tmp_path)
    image_service.rate_limiter = ImageRateLimiter(max_concurrent=1, interval_seconds=0)
    image_service.history_service = history_service or make_history_service(tmp_path / "records")
    image_service.worker_count = 1
    image_service._task_states = {}
    return image_service


def make_task_state(pages, cover_image=None):
    return {
        "pages": pages,
        "generated": {},
        "failed": {},
        "cover_image": cover_image,
        "full_outline": "",
        "user_images": None,
        "user_topic": "",
        "style_prompt": "",
    }


# ==================== P1-1 任务状态读写竞态 ====================

def test_retry_single_image_survives_concurrent_state_eviction(tmp_path):
    """状态在 membership 检查后被并发淘汰时，重试不抛 KeyError（500）"""
    image_service = make_image_service(tmp_path)
    page = {"index": 1, "type": "content", "content": "content"}
    image_service._task_states = EvictingDict({
        "task_1": make_task_state([page], cover_image=b"cover-bytes"),
    })

    result = image_service.retry_single_image("task_1", page, use_reference=True)

    assert result["success"] is True
    assert result["index"] == 1


def test_retry_failed_images_survives_concurrent_state_eviction(tmp_path):
    """批量重试流在状态被并发淘汰时不抛 KeyError，正常产出事件"""
    image_service = make_image_service(tmp_path)
    pages = [
        {"index": 0, "type": "cover", "content": "cover"},
        {"index": 1, "type": "content", "content": "content"},
    ]
    image_service._task_states = EvictingDict({
        "task_1": make_task_state(pages, cover_image=b"cover-bytes"),
    })

    events = list(image_service.retry_failed_images("task_1", [pages[1]]))

    assert [event["event"] for event in events] == [
        "retry_start", "complete", "retry_finish",
    ]
    assert events[-1]["data"]["success"] is True


def test_retry_single_image_updates_state_when_present(tmp_path):
    """状态存在时，重试成功后 generated/failed 正常更新（行为不回退）"""
    image_service = make_image_service(tmp_path)
    page = {"index": 1, "type": "content", "content": "content"}
    state = make_task_state([page])
    state["failed"][1] = "上次失败"
    image_service._task_states = {"task_1": state}

    result = image_service.retry_single_image("task_1", page)

    assert result["success"] is True
    assert state["generated"][1] == "1.png"
    assert 1 not in state["failed"]


def test_retry_single_image_with_fully_evicted_state(tmp_path):
    """状态完全被淘汰（字典中无此 task）时重试仍可用"""
    image_service = make_image_service(tmp_path)
    page = {"index": 2, "type": "content", "content": "content"}

    result = image_service.retry_single_image("task_gone", page, use_reference=True)

    assert result["success"] is True
    assert (tmp_path / "task_gone" / "2.png").exists()


# ==================== P2-2 封面参考图按封面页 index 推导 ====================

def test_resolve_cover_filename_prefers_cover_page():
    image_service = ImageService.__new__(ImageService)
    pages = [
        {"index": 0, "type": "content", "content": "content"},
        {"index": 1, "type": "cover", "content": "cover"},
    ]
    assert image_service._resolve_cover_filename(pages) == "1.png"


def test_resolve_cover_filename_falls_back_to_first_page():
    image_service = ImageService.__new__(ImageService)
    pages = [
        {"index": 3, "type": "content", "content": "content"},
        {"index": 4, "type": "summary", "content": "summary"},
    ]
    assert image_service._resolve_cover_filename(pages) == "3.png"


def test_resolve_cover_filename_defaults_to_zero_when_unknown(tmp_path):
    image_service = make_image_service(tmp_path)
    assert image_service._resolve_cover_filename(None) == "0.png"
    assert image_service._resolve_cover_filename([]) == "0.png"


def test_retry_loads_cover_reference_by_cover_index(tmp_path):
    """封面页 index=1 且大对象已释放时，磁盘回退读 1.png 而不是 0.png"""
    generator = RecordingGenerator()
    image_service = make_image_service(tmp_path, generator=generator)
    pages = [
        {"index": 0, "type": "content", "content": "content"},
        {"index": 1, "type": "cover", "content": "cover"},
    ]
    # 模拟 _release_task_heavy_data 后的状态：pages 保留、cover_image 已释放
    image_service._task_states = {"task_1": make_task_state(pages, cover_image=None)}

    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    (task_dir / "1.png").write_bytes(b"cover-at-index-1")

    result = image_service.retry_single_image(
        "task_1", pages[0], use_reference=True
    )

    assert result["success"] is True
    assert generator.calls[0]["reference_images"] == [b"cover-at-index-1"]


def test_retry_failed_stream_loads_cover_reference_by_cover_index(tmp_path):
    generator = RecordingGenerator()
    image_service = make_image_service(tmp_path, generator=generator)
    pages = [
        {"index": 0, "type": "content", "content": "content"},
        {"index": 1, "type": "cover", "content": "cover"},
    ]
    image_service._task_states = {"task_1": make_task_state(pages, cover_image=None)}

    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    (task_dir / "1.png").write_bytes(b"cover-at-index-1")

    events = list(image_service.retry_failed_images("task_1", [pages[0]]))

    assert events[-1]["data"]["success"] is True
    assert generator.calls[0]["reference_images"] == [b"cover-at-index-1"]


# ==================== P2-3 图片文件原子写入 ====================

def test_save_image_is_atomic_and_leaves_no_temp_files(tmp_path):
    image_service = make_image_service(tmp_path)
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()

    filepath = image_service._save_image(b"image-bytes", "0.png", str(task_dir))

    assert Path(filepath).read_bytes() == b"image-bytes"
    assert (task_dir / "thumb_0.png").read_bytes() == b"image-bytes"
    assert not list(task_dir.glob(".tmp_*"))


# ==================== P1-2 配置文件原子写入与并发保存 ====================

def test_write_config_atomic_and_parseable(tmp_path):
    from backend.routes import config_routes

    path = tmp_path / "text_providers.yaml"
    config = {"active_provider": "p1", "providers": {"p1": {"api_key": "key-1"}}}
    config_routes._write_config(path, config)

    assert yaml.safe_load(path.read_text(encoding="utf-8")) == config
    assert not list(tmp_path.glob(".tmp_*"))


def test_concurrent_config_saves_keep_yaml_valid(tmp_path):
    """并发保存配置后文件必须是完整可解析的 YAML（不被交叉写坏）"""
    from backend.routes import config_routes

    path = tmp_path / "text_providers.yaml"
    worker_count = 16
    errors = []

    def save(i: int):
        try:
            config_routes._update_provider_config(path, {
                "active_provider": f"provider_{i}",
                "providers": {
                    f"provider_{i}": {
                        "api_key": f"key-{i}",
                        "model": "m" * 500,  # 加大写入量，放大交叉写入的窗口
                    }
                },
            })
        except Exception as e:  # noqa: BLE001 - 测试中收集所有异常
            errors.append(e)

    threads = [threading.Thread(target=save, args=(i,)) for i in range(worker_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert data["active_provider"] in {f"provider_{i}" for i in range(worker_count)}
    # 每次保存都会整体替换 providers，最终应恰好剩最后一次写入的那一个
    assert len(data["providers"]) == 1
    assert not list(tmp_path.glob(".tmp_*"))


# ==================== P2-1 API 404 返回结构化 JSON ====================

def test_api_404_returns_structured_json(client):
    resp = client.get("/api/definitely-not-exists")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body is not None, "API 404 必须返回 JSON 而不是 HTML"
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


# ==================== P2-5 /api/images 按扩展名推断 mimetype ====================

def test_get_image_mimetype_inferred_from_extension(client, tmp_path, monkeypatch):
    from backend.routes import image_routes

    history_dir = tmp_path / "history" / "task_mime"
    history_dir.mkdir(parents=True)
    (history_dir / "0.jpg").write_bytes(b"jpg-bytes")
    (history_dir / "0.png").write_bytes(b"png-bytes")

    monkeypatch.setattr(image_routes, "get_data_root", lambda: tmp_path)

    resp = client.get("/api/images/task_mime/0.jpg?thumbnail=false")
    assert resp.status_code == 200
    assert resp.content_type.startswith("image/jpeg")

    resp = client.get("/api/images/task_mime/0.png?thumbnail=false")
    assert resp.status_code == 200
    assert resp.content_type.startswith("image/png")


# ==================== P2-7 服务单例双检查初始化 ====================

def _assert_singleton_under_concurrency(module, class_attr: str, getter_name: str, monkeypatch):
    created = []

    class SlowService:
        def __init__(self):
            time.sleep(0.05)  # 放大初始化窗口，暴露并发重复构造
            created.append(self)

    monkeypatch.setattr(module, class_attr, SlowService)
    monkeypatch.setattr(module, "_service_instance", None)

    getter = getattr(module, getter_name)
    results = []
    threads = [
        threading.Thread(target=lambda: results.append(getter()))
        for _ in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(created) == 1, "并发首次获取时只能构造一个实例"
    assert all(instance is results[0] for instance in results)


def test_get_history_service_singleton_under_concurrency(monkeypatch):
    import backend.services.history as history_module
    _assert_singleton_under_concurrency(
        history_module, "HistoryService", "get_history_service", monkeypatch
    )


def test_get_image_service_singleton_under_concurrency(monkeypatch):
    import backend.services.image as image_module
    _assert_singleton_under_concurrency(
        image_module, "ImageService", "get_image_service", monkeypatch
    )
