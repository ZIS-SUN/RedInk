"""
额度与性能修复回归测试（审查编号 S2 / S12 / S11）

S2 服务端「进行中任务」去重（防同页双倍扣费总闸门）：
- _generate_single_image 对同一 (task_id, 页 index) 的并发请求只放行一个，
  后到者跳过上游调用并返回哨兵消息（IN_FLIGHT_MESSAGE）
- 注册/清除发生在实际执行生成的线程内，成功/失败/异常一律 finally 清除；
  跳过分支不会误清他人的注册
- 生成流 / 批量重试流遇到在途页：改发 progress 事件（status=generating +
  in_flight 标记），不计失败、不写任务失败表；finish/retry_finish 以
  纯增量字段 in_flight_indices 透出被跳过的页
- GET /api/task/<task_id> 返回 in_flight 页列表（纯增量字段）

S12 缓存回放校验磁盘文件：
- get_cached_generation_events 回放前逐页校验磁盘：记录中的文件缺失时
  回退磁盘上该页的最新版本文件（复用 merger 的目录扫描，兼容版本化文件名），
  磁盘也没有则发可重试 error 事件，不再回放指向 404 图片的 complete

S11 索引写放大与详情页扫盘：
- merge_generated_image(defer_index_sync=True) 只写记录 JSON 不动索引，
  每累计 INDEX_SYNC_BATCH_SIZE 次自动补写一次，流收尾 flush_record_index
  兜底（含 GeneratorExit 中断路径）
- update_record 全量索引同步后清空攒批计数，避免重复补写
- get_record(sync_images=True) 仅对 draft/generating/partial（及缺状态的
  老数据）执行目录同步，completed 记录直接返回

不发起任何真实网络请求：生成器均为假实现（内存字节/受控阻塞/受控失败）。
"""
import json
import re
import threading

from backend.routes import image_routes
from backend.services.history import HistoryService
from backend.services.image import ImageService
from backend.services.image_rate_limiter import ImageRateLimiter


# ==================== 测试辅助 ====================

def make_history_service(tmp_path) -> HistoryService:
    service = HistoryService.__new__(HistoryService)
    service.history_dir = str(tmp_path)
    service.index_file = str(tmp_path / "index.json")
    service._init_index()
    return service


class RecordingGenerator:
    """记录调用的假生成器：返回固定图片字节"""

    def __init__(self):
        self.calls = []

    def generate_image(self, prompt=None, **kwargs):
        self.calls.append(prompt)
        return b"image-bytes"


class FailingGenerator(RecordingGenerator):
    """总是失败的假生成器"""

    def generate_image(self, prompt=None, **kwargs):
        self.calls.append(prompt)
        raise Exception("HTTP 500: upstream exploded")


class GatedGenerator(RecordingGenerator):
    """受控阻塞的假生成器：进入后置位 entered，等待 release 放行"""

    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def generate_image(self, prompt=None, **kwargs):
        self.calls.append(prompt)
        self.entered.set()
        assert self.release.wait(timeout=10), "测试闸门等待超时"
        return b"gated-image-bytes"


def make_image_service(
    tmp_path, history_service=None, generator=None, worker_count: int = 1
) -> ImageService:
    """绕过 __init__（避免读取真实配置/API Key），手工装配依赖"""
    service = ImageService.__new__(ImageService)
    service.generator = generator or RecordingGenerator()
    service.provider_config = {"type": "image_api", "model": "fake-model"}
    service.use_short_prompt = False
    service.prompt_template = "{page_content}"
    service.prompt_template_short = ""
    service.history_root_dir = str(tmp_path)
    service.current_task_dir = None
    service.rate_limiter = ImageRateLimiter(
        max_concurrent=max(worker_count, 1), interval_seconds=0
    )
    service.worker_count = worker_count
    service.history_service = history_service
    service._task_states = {}
    return service


PAGE_0 = {"index": 0, "type": "cover", "content": "封面"}
PAGE_1 = {"index": 1, "type": "content", "content": "内容一"}
PAGE_2 = {"index": 2, "type": "content", "content": "内容二"}

TWO_PAGE_OUTLINE = {
    "raw": "raw",
    "pages": [
        {"index": 0, "type": "cover", "content": "封面"},
        {"index": 1, "type": "content", "content": "内容"},
    ],
}


def count_index_saves(history: HistoryService):
    """包装 _save_index 统计索引写盘次数，返回计数列表"""
    calls = []
    original = history._save_index

    def counting(index):
        calls.append(True)
        return original(index)

    history._save_index = counting
    return calls


# ==================== S2：in-flight 注册表核心语义 ====================

def test_generate_single_image_skips_when_page_in_flight(tmp_path):
    """同页已在生成中：跳过上游调用，返回哨兵消息，不误清他人的注册"""
    service = make_image_service(tmp_path)
    (tmp_path / "task_1").mkdir()
    assert service._try_begin_in_flight("task_1", 1) is True  # 模拟另一请求在途

    result = service._generate_single_image(PAGE_1, "task_1")

    assert result == (1, False, None, ImageService.IN_FLIGHT_MESSAGE)
    assert service.generator.calls == []  # 未调上游 = 未扣费
    # 跳过分支不得清除「另一请求」的注册
    assert service.get_in_flight_pages("task_1") == [1]


def test_in_flight_cleared_after_success_and_failure(tmp_path):
    """成功与失败路径都必须清除在途标记（finally 兜底）"""
    service = make_image_service(tmp_path)
    (tmp_path / "task_1").mkdir()

    result = service._generate_single_image(PAGE_1, "task_1")
    assert result[1] is True
    assert service.get_in_flight_pages("task_1") == []

    failing = make_image_service(tmp_path, generator=FailingGenerator())
    result = failing._generate_single_image(PAGE_2, "task_1")
    assert result[1] is False
    assert failing.get_in_flight_pages("task_1") == []


def test_concurrent_same_page_only_one_upstream_call(tmp_path):
    """并发生成同一页：检查+注册原子化，恰好一次上游调用"""
    generator = GatedGenerator()
    service = make_image_service(tmp_path, generator=generator)
    (tmp_path / "task_1").mkdir()

    results = {}

    def first_call():
        results["first"] = service._generate_single_image(PAGE_1, "task_1")

    worker = threading.Thread(target=first_call)
    worker.start()
    assert generator.entered.wait(timeout=10), "首个生成请求未进入生成器"

    # 首个请求阻塞在上游期间，第二个请求必须跳过
    second = service._generate_single_image(PAGE_1, "task_1")
    assert second == (1, False, None, ImageService.IN_FLIGHT_MESSAGE)

    generator.release.set()
    worker.join(timeout=10)

    assert results["first"][1] is True
    assert len(generator.calls) == 1
    assert service.get_in_flight_pages("task_1") == []


def test_in_flight_pages_listed_and_cleaned(tmp_path):
    """注册表按任务聚合、升序透出；清空后条目移除防泄漏"""
    service = make_image_service(tmp_path)
    assert service._try_begin_in_flight("task_a", 3)
    assert service._try_begin_in_flight("task_a", 1)
    assert service._try_begin_in_flight("task_b", 0)

    assert service.get_in_flight_pages("task_a") == [1, 3]
    assert service.get_in_flight_pages("task_b") == [0]
    assert service.get_in_flight_pages("task_missing") == []

    service._end_in_flight("task_a", 1)
    service._end_in_flight("task_a", 3)
    assert service.get_in_flight_pages("task_a") == []
    # 空集合的 task 条目被移除
    assert "task_a" not in service.__dict__.get("_in_flight", {})


# ==================== S2：生成流对在途页发 progress 而非 error ====================

def test_generate_stream_emits_in_flight_progress_for_content_page(tmp_path):
    service = make_image_service(tmp_path)
    task_id = "task_stream"
    assert service._try_begin_in_flight(task_id, 1)  # 模拟另一窗口正在生成第 1 页

    events = list(service.generate_images([PAGE_0, PAGE_1], task_id=task_id))

    names = [e["event"] for e in events]
    assert "error" not in names, "在途页不得发 error 事件"

    in_flight_events = [
        e for e in events
        if e["event"] == "progress" and e["data"].get("in_flight")
    ]
    assert len(in_flight_events) == 1
    data = in_flight_events[0]["data"]
    assert data["index"] == 1
    assert data["status"] == "generating"  # 沿用现有 progress 语义
    assert data["message"] == ImageService.IN_FLIGHT_MESSAGE
    assert data["phase"] == "content"

    finish = events[-1]["data"]
    assert finish["success"] is True  # 无真实失败
    assert finish["completed"] == 1  # 只有封面真正生成
    assert finish["failed"] == 0
    assert finish["failed_indices"] == []
    assert finish["in_flight_indices"] == [1]

    # 在途页不得写入任务失败表（否则前端恢复时会被标成 error）
    assert service.get_task_state(task_id)["failed"] == {}
    # 只有封面调了上游
    assert len(service.generator.calls) == 1


def test_generate_stream_cover_in_flight_skip_degrades_gracefully(tmp_path):
    """封面在途被跳过：内容页照常生成（与封面失败的降级路径一致）"""
    service = make_image_service(tmp_path)
    task_id = "task_cover_busy"
    assert service._try_begin_in_flight(task_id, 0)

    events = list(service.generate_images([PAGE_0, PAGE_1], task_id=task_id))

    names = [e["event"] for e in events]
    assert "error" not in names
    assert names.count("complete") == 1  # 内容页正常完成

    in_flight_events = [
        e for e in events
        if e["event"] == "progress" and e["data"].get("in_flight")
    ]
    assert [e["data"]["index"] for e in in_flight_events] == [0]
    assert in_flight_events[0]["data"]["phase"] == "cover"

    finish = events[-1]["data"]
    assert finish["completed"] == 1
    assert finish["failed"] == 0
    assert finish["in_flight_indices"] == [0]
    assert len(service.generator.calls) == 1


def test_two_overlapping_streams_generate_page_exactly_once(tmp_path):
    """双开窗口对同一任务点生成：在途页只有一次上游调用（真实并发时序）"""
    generator = GatedGenerator()
    service = make_image_service(tmp_path, generator=generator)
    task_id = "task_dual"
    pages = [PAGE_0]

    events_a = []

    def run_stream_a():
        events_a.extend(service.generate_images(pages, task_id=task_id))

    stream_a = threading.Thread(target=run_stream_a)
    stream_a.start()
    assert generator.entered.wait(timeout=10), "流 A 未进入生成器"

    # 流 A 阻塞在上游期间，流 B（第二个窗口）对同一任务发起生成
    events_b = list(service.generate_images(pages, task_id=task_id))

    generator.release.set()
    stream_a.join(timeout=10)

    # 上游只被调用一次（B 跳过了在途页）
    assert len(generator.calls) == 1

    b_in_flight = [
        e for e in events_b
        if e["event"] == "progress" and e["data"].get("in_flight")
    ]
    assert [e["data"]["index"] for e in b_in_flight] == [0]
    assert events_b[-1]["data"]["in_flight_indices"] == [0]
    assert events_b[-1]["data"]["completed"] == 0

    # 流 A 正常完成该页
    a_completes = [e for e in events_a if e["event"] == "complete"]
    assert [e["data"]["index"] for e in a_completes] == [0]
    assert service.get_in_flight_pages(task_id) == []


# ==================== S2：批量重试流与单张重试 ====================

def test_retry_failed_stream_skips_in_flight_page(tmp_path):
    service = make_image_service(tmp_path)
    task_id = "task_retry_busy"
    service._set_task_state(task_id, {
        "pages": [PAGE_0, PAGE_1, PAGE_2],
        "generated": {0: "0.png"},
        "failed": {1: "boom", 2: "boom"},
        "cover_image": b"cover-bytes",
        "full_outline": "",
        "user_images": None,
        "user_topic": "",
        "style_prompt": "",
    })
    assert service._try_begin_in_flight(task_id, 2)  # 第 2 页仍在原请求中生成

    events = list(service.retry_failed_images(task_id, [PAGE_1, PAGE_2]))

    assert [e["event"] for e in events] == [
        "retry_start", "complete", "progress", "retry_finish",
    ]
    progress = events[2]["data"]
    assert progress["index"] == 2
    assert progress["status"] == "generating"
    assert progress["in_flight"] is True
    assert progress["message"] == ImageService.IN_FLIGHT_MESSAGE

    retry_finish = events[-1]["data"]
    assert retry_finish["success"] is True  # 跳过不算失败
    assert retry_finish["completed"] == 1
    assert retry_finish["failed"] == 0
    assert retry_finish["in_flight_indices"] == [2]

    # 上游只为第 1 页调用；第 2 页的失败标记不被本次重试清除或改写
    assert len(service.generator.calls) == 1
    state = service.get_task_state(task_id)
    assert 1 not in state["failed"]
    assert state["failed"][2] == "boom"


def test_retry_finish_has_no_in_flight_field_when_nothing_skipped(tmp_path):
    """无跳过时 retry_finish 不携带增量字段（向后兼容旧前端契约）"""
    service = make_image_service(tmp_path)

    events = list(service.retry_failed_images("task_plain", [PAGE_1]))

    retry_finish = events[-1]["data"]
    assert retry_finish == {
        "success": True, "total": 1, "completed": 1, "failed": 0,
    }


def test_retry_single_image_skips_in_flight_page(tmp_path):
    """单张重试/重绘遇到在途页：跳过上游，返回可重试的提示"""
    service = make_image_service(tmp_path)
    assert service._try_begin_in_flight("task_1", 1)

    result = service.retry_single_image("task_1", PAGE_1, use_reference=False)

    assert result["success"] is False
    assert result["error"] == ImageService.IN_FLIGHT_MESSAGE
    assert result["retryable"] is True
    assert service.generator.calls == []


# ==================== S2：/api/task/<task_id> 增量字段 ====================

def test_task_state_route_returns_in_flight_pages(client, tmp_path, monkeypatch):
    service = make_image_service(tmp_path)
    monkeypatch.setattr(image_routes, "get_image_service", lambda: service)

    service._set_task_state("task_api", {
        "pages": [PAGE_0, PAGE_1],
        "generated": {0: "0.png"},
        "failed": {},
        "cover_image": None,
        "full_outline": "",
        "user_images": None,
        "user_topic": "",
        "style_prompt": "",
    })
    assert service._try_begin_in_flight("task_api", 1)

    resp = client.get("/api/task/task_api")

    assert resp.status_code == 200
    state = resp.get_json()["state"]
    assert state["generated"] == {"0": "0.png"}
    assert state["in_flight"] == [1]

    # 生成结束后增量字段回落为空列表
    service._end_in_flight("task_api", 1)
    resp = client.get("/api/task/task_api")
    assert resp.get_json()["state"]["in_flight"] == []


# ==================== S12：缓存回放校验磁盘文件 ====================

def _make_replay_env(tmp_path, generated, status="completed"):
    """构造带历史记录的回放环境，返回 (image_service, record_id)"""
    history = make_history_service(tmp_path)
    record_id = history.create_record("topic", TWO_PAGE_OUTLINE, task_id="task_1")
    history.update_record(
        record_id,
        images={"task_id": "task_1", "generated": generated},
        status=status,
    )
    service = make_image_service(tmp_path, history_service=history)
    return service, record_id


REPLAY_PAGES = TWO_PAGE_OUTLINE["pages"]


def test_cached_replay_missing_file_yields_retryable_error(tmp_path):
    """记录里有文件名但磁盘文件已被删：该页发可重试 error 而非 404 complete"""
    service, record_id = _make_replay_env(tmp_path, ["0.png", "1.png"])
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    (task_dir / "0.png").write_bytes(b"png")  # 只有第 0 页真实存在

    events = service.get_cached_generation_events(record_id, REPLAY_PAGES)

    assert [e["event"] for e in events] == ["complete", "error", "finish"]
    assert events[0]["data"]["image_url"] == "/api/images/task_1/0.png"

    error_data = events[1]["data"]
    assert error_data["index"] == 1
    assert error_data["retryable"] is True
    assert error_data["cached"] is True
    assert "丢失" in error_data["message"]

    finish = events[-1]["data"]
    assert finish["success"] is False
    assert finish["failed_indices"] == [1]
    assert finish["completed"] == 1
    assert finish["images"] == ["0.png", ""]  # images 列表与事件一致


def test_cached_replay_whole_task_dir_deleted_all_pages_retryable(tmp_path):
    """整个任务目录被手动删除：全部页发可重试 error，不再回放 404 图片"""
    service, record_id = _make_replay_env(tmp_path, ["0.png", "1.png"])
    # 不创建 task_1 目录，模拟手动删除

    events = service.get_cached_generation_events(record_id, REPLAY_PAGES)

    assert [e["event"] for e in events] == ["error", "error", "finish"]
    assert all(e["data"]["retryable"] for e in events[:2])
    finish = events[-1]["data"]
    assert finish["success"] is False
    assert finish["completed"] == 0
    assert finish["failed"] == 2
    assert finish["failed_indices"] == [0, 1]
    assert finish["images"] == ["", ""]


def test_cached_replay_falls_back_to_latest_version_on_disk(tmp_path):
    """记录中的文件名失真但磁盘有该页版本化文件：回退最新版本（复用 merger 规则）"""
    service, record_id = _make_replay_env(tmp_path, ["0.png", "1.png"])
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    (task_dir / "0.png").write_bytes(b"png")
    # 第 1 页原名文件不在，只剩重绘产生的版本化文件（清理竞态残留场景）
    (task_dir / "1_v1721470000000.png").write_bytes(b"png-v2")

    events = service.get_cached_generation_events(record_id, REPLAY_PAGES)

    assert [e["event"] for e in events] == ["complete", "complete", "finish"]
    assert events[1]["data"]["image_url"] == "/api/images/task_1/1_v1721470000000.png"
    finish = events[-1]["data"]
    assert finish["success"] is True
    assert finish["images"] == ["0.png", "1_v1721470000000.png"]


def test_cached_replay_intact_files_unchanged(tmp_path):
    """文件齐全时回放行为与协议不变（回归保护）"""
    service, record_id = _make_replay_env(tmp_path, ["0.png", "1.png"])
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    (task_dir / "0.png").write_bytes(b"png")
    (task_dir / "1.png").write_bytes(b"png")

    events = service.get_cached_generation_events(record_id, REPLAY_PAGES)

    assert [e["event"] for e in events] == ["complete", "complete", "finish"]
    finish = events[-1]["data"]
    assert finish["success"] is True
    assert finish["completed"] == 2
    assert finish["images"] == ["0.png", "1.png"]
    assert finish["cached"] is True


# ==================== S11：merge 延后索引 + 攒批 + flush ====================

def test_merge_deferred_writes_record_but_not_index(tmp_path):
    history = make_history_service(tmp_path)
    record_id = history.create_record("topic", {
        "raw": "raw",
        "pages": [
            {"index": i, "type": "content", "content": f"第{i}页"}
            for i in range(3)
        ],
    })
    saves = count_index_saves(history)

    for i in range(3):
        assert history.merge_generated_image(
            record_id, "task_1", i, f"{i}.png", defer_index_sync=True
        )

    # 记录文件实时更新
    record = history.get_record(record_id)
    assert record["images"]["generated"] == ["0.png", "1.png", "2.png"]
    assert record["status"] == "completed"
    # 索引一次都没写（3 < INDEX_SYNC_BATCH_SIZE）
    assert len(saves) == 0
    entry = next(r for r in history._load_index()["records"] if r["id"] == record_id)
    assert entry["status"] == "draft"  # 索引仍是旧状态（滞后是攒批的预期代价）

    # 流收尾 flush：一次写盘补齐索引
    assert history.flush_record_index(record_id) is True
    assert len(saves) == 1
    entry = next(r for r in history._load_index()["records"] if r["id"] == record_id)
    assert entry["status"] == "completed"
    assert entry["thumbnail"] == "0.png"

    # 无挂账时 flush 零成本返回，不重复写盘
    assert history.flush_record_index(record_id) is False
    assert len(saves) == 1


def test_merge_deferred_autoflushes_every_batch(tmp_path):
    """延后合并每累计 INDEX_SYNC_BATCH_SIZE 次自动补写一次索引"""
    batch = HistoryService.INDEX_SYNC_BATCH_SIZE
    page_count = batch + 2
    history = make_history_service(tmp_path)
    record_id = history.create_record("topic", {
        "raw": "raw",
        "pages": [
            {"index": i, "type": "content", "content": f"第{i}页"}
            for i in range(page_count)
        ],
    })
    saves = count_index_saves(history)

    for i in range(batch):
        history.merge_generated_image(
            record_id, "task_1", i, f"{i}.png", defer_index_sync=True
        )
    # 第 batch 次触发自动补写
    assert len(saves) == 1
    entry = next(r for r in history._load_index()["records"] if r["id"] == record_id)
    assert entry["status"] == "partial"

    for i in range(batch, page_count):
        history.merge_generated_image(
            record_id, "task_1", i, f"{i}.png", defer_index_sync=True
        )
    assert len(saves) == 1  # 未再攒满一批，不写

    assert history.flush_record_index(record_id) is True
    assert len(saves) == 2
    entry = next(r for r in history._load_index()["records"] if r["id"] == record_id)
    assert entry["status"] == "completed"


def test_merge_default_still_syncs_index_immediately(tmp_path):
    """默认（单张重试/重绘路径）行为不变：合并后立即同步索引"""
    history = make_history_service(tmp_path)
    record_id = history.create_record("topic", TWO_PAGE_OUTLINE)
    saves = count_index_saves(history)

    assert history.merge_generated_image(record_id, "task_1", 0, "0_v123.png")

    assert len(saves) == 1
    entry = next(r for r in history._load_index()["records"] if r["id"] == record_id)
    assert entry["status"] == "partial"
    assert entry["thumbnail"] == "0_v123.png"
    # 立即同步路径不留攒批挂账
    assert history.flush_record_index(record_id) is False


def test_full_update_record_resets_pending_batch(tmp_path):
    """全量 update_record 已刷新索引：清空攒批计数，收尾 flush 不再重复写"""
    history = make_history_service(tmp_path)
    record_id = history.create_record("topic", TWO_PAGE_OUTLINE)
    history.merge_generated_image(
        record_id, "task_1", 0, "0.png", defer_index_sync=True
    )

    assert history.update_record(record_id, status="partial")

    saves = count_index_saves(history)
    assert history.flush_record_index(record_id) is False
    assert len(saves) == 0


# ==================== S11：生成流收尾统一同步（含中断路径） ====================

def _make_stream_env(tmp_path, pages):
    history = make_history_service(tmp_path)
    record_id = history.create_record(
        "topic", {"raw": "raw", "pages": pages}, task_id="task_1"
    )
    service = make_image_service(tmp_path, history_service=history)
    return service, history, record_id


def test_generate_stream_writes_index_once_at_finish(tmp_path):
    """N 页生成的索引写盘从 N 次降到收尾 1 次（N < 攒批阈值时）"""
    pages = [PAGE_0, PAGE_1, PAGE_2]
    service, history, record_id = _make_stream_env(tmp_path, pages)
    saves = count_index_saves(history)

    events = list(service.generate_images(
        pages, task_id="task_1", record_id=record_id
    ))

    assert events[-1]["event"] == "finish"
    assert events[-1]["data"]["success"] is True
    # 3 页生成期间 0 次索引写 + 收尾 flush 1 次
    assert len(saves) == 1

    # 记录与索引最终一致
    record = history.get_record(record_id)
    assert record["images"]["generated"] == ["0.png", "1.png", "2.png"]
    assert record["status"] == "completed"
    entry = next(r for r in history._load_index()["records"] if r["id"] == record_id)
    assert entry["status"] == "completed"
    assert entry["thumbnail"] == "0.png"


def test_generate_stream_interrupted_still_flushes_index(tmp_path):
    """客户端断开（GeneratorExit）后 finally 仍补写索引，列表页不长期失真"""
    pages = [PAGE_0, PAGE_1, PAGE_2]
    service, history, record_id = _make_stream_env(tmp_path, pages)
    saves = count_index_saves(history)

    stream = service.generate_images(pages, task_id="task_1", record_id=record_id)
    for event in stream:
        if event["event"] == "complete":  # 封面完成后立刻断开
            break
    stream.close()  # 触发 GeneratorExit → finally 补写索引

    assert len(saves) == 1
    entry = next(r for r in history._load_index()["records"] if r["id"] == record_id)
    assert entry["status"] == "partial"
    assert entry["thumbnail"] == "0.png"


def test_retry_failed_stream_flushes_index_once(tmp_path):
    """批量重试流同样攒批 + 收尾统一同步"""
    pages = [PAGE_0, PAGE_1, PAGE_2]
    service, history, record_id = _make_stream_env(tmp_path, pages)
    saves = count_index_saves(history)

    events = list(service.retry_failed_images(
        "task_1", [PAGE_1, PAGE_2], record_id=record_id
    ))

    assert events[-1]["event"] == "retry_finish"
    assert events[-1]["data"]["success"] is True
    assert len(saves) == 1

    record = history.get_record(record_id)
    assert record["images"]["generated"] == ["", "1.png", "2.png"]
    entry = next(r for r in history._load_index()["records"] if r["id"] == record_id)
    assert entry["status"] == "partial"


def test_retry_single_image_keeps_immediate_index_sync(tmp_path):
    """单张重绘（无流收尾时机）：合并后索引立即同步，不留挂账"""
    pages = [PAGE_0]
    service, history, record_id = _make_stream_env(tmp_path, pages)
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()

    result = service.retry_single_image(
        "task_1", PAGE_0, use_reference=False, record_id=record_id
    )

    assert result["success"] is True
    new_filename = result["image_url"].rsplit("/", 1)[-1]
    assert re.fullmatch(r"0_v\d+\.png", new_filename)
    entry = next(r for r in history._load_index()["records"] if r["id"] == record_id)
    assert entry["status"] == "completed"
    assert entry["thumbnail"] == new_filename
    assert history.flush_record_index(record_id) is False


# ==================== S11：详情读取仅未完成状态才扫盘 ====================

def _count_sync_calls(history: HistoryService):
    calls = []
    original = history.sync_record_images

    def counting(record_id, record=None):
        calls.append(record_id)
        return original(record_id, record)

    history.sync_record_images = counting
    return calls


def test_get_record_skips_dir_sync_for_completed(tmp_path):
    history = make_history_service(tmp_path)
    record_id = history.create_record("topic", TWO_PAGE_OUTLINE, task_id="task_1")
    history.update_record(
        record_id,
        images={"task_id": "task_1", "generated": ["0.png", "1.png"]},
        status="completed",
    )
    calls = _count_sync_calls(history)

    record = history.get_record(record_id, sync_images=True)

    assert record["status"] == "completed"
    assert calls == []  # completed 记录不再 listdir 扫盘


def test_get_record_syncs_dir_for_unfinished_statuses(tmp_path):
    history = make_history_service(tmp_path)
    calls = _count_sync_calls(history)

    for status in ("draft", "generating", "partial"):
        record_id = history.create_record("topic", TWO_PAGE_OUTLINE, task_id="task_1")
        if status != "draft":
            history.update_record(record_id, status=status)
        history.get_record(record_id, sync_images=True)
        assert calls[-1] == record_id, f"{status} 状态应执行目录同步"

    assert len(calls) == 3


def test_get_record_syncs_when_status_missing_legacy(tmp_path):
    """缺 status 字段的老数据仍执行目录同步（兜底）"""
    history = make_history_service(tmp_path)
    record_id = history.create_record("topic", TWO_PAGE_OUTLINE, task_id="task_1")

    # 手动去掉 status 字段模拟老数据
    record_path = history._get_record_path(record_id)
    with open(record_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    raw.pop("status", None)
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)

    calls = _count_sync_calls(history)
    history.get_record(record_id, sync_images=True)
    assert calls == [record_id]


def test_history_detail_route_skips_sync_for_completed(client, tmp_path, monkeypatch):
    """GET /history/<id>：completed 记录直接返回，不触发目录扫描"""
    from backend.routes import history_routes

    history = make_history_service(tmp_path)
    record_id = history.create_record("topic", TWO_PAGE_OUTLINE, task_id="task_1")
    history.update_record(
        record_id,
        images={"task_id": "task_1", "generated": ["0.png", "1.png"]},
        status="completed",
    )
    monkeypatch.setattr(history_routes, "get_history_service", lambda: history)
    calls = _count_sync_calls(history)

    resp = client.get(f"/api/history/{record_id}")

    assert resp.status_code == 200
    assert resp.get_json()["record"]["status"] == "completed"
    assert calls == []

    # 未完成记录走原有同步路径（行为不回退）
    draft_id = history.create_record("topic2", TWO_PAGE_OUTLINE, task_id="task_2")
    resp = client.get(f"/api/history/{draft_id}")
    assert resp.status_code == 200
    assert calls == [draft_id]
