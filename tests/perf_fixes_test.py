"""
性能修复回归测试：

问题 1：历史扫描 O(任务数×记录数) 全量读盘
- scan_all_tasks / scan_and_sync_task_images 通过索引冗余的 task_id 字段
  构建映射直接定位记录，扫描结果与旧实现等价
- 索引条目缺少 task_id 字段（极老数据）时回退为读取记录文件
- 扫描期间不再逐记录读盘（get_record 调用次数有界）
- 扫描过程中的索引更新攒批，最后一次性写盘

问题 2：图片响应无缓存头
- /api/images 响应携带 Cache-Control: public, max-age=31536000, immutable
- 404 错误响应不带长缓存头
"""
import json
from pathlib import Path

from backend.services.history import HistoryService


def make_history_service(tmp_path: Path) -> HistoryService:
    service = HistoryService.__new__(HistoryService)
    service.history_dir = str(tmp_path)
    service.index_file = str(tmp_path / "index.json")
    service._init_index()
    return service


SAMPLE_OUTLINE = {
    "raw": "raw",
    "pages": [
        {"index": 0, "type": "cover", "content": "封面"},
        {"index": 1, "type": "content", "content": "内容"},
    ],
}


def _make_task_dir(tmp_path: Path, task_id: str, filenames) -> None:
    task_dir = tmp_path / task_id
    task_dir.mkdir()
    for name in filenames:
        (task_dir / name).write_bytes(b"png-bytes")


# ==================== 问题 1：扫描走 task_id 映射 ====================

def test_scan_all_tasks_syncs_records_via_index_mapping(tmp_path):
    """有 task_id 的索引条目走映射：扫描结果与旧实现等价"""
    service = make_history_service(tmp_path)

    # 记录 A：任务目录里有全部 2 张图 -> completed
    record_a = service.create_record("话题A", SAMPLE_OUTLINE, task_id="task_a")
    _make_task_dir(tmp_path, "task_a", ["0.png", "1.png", "thumb_0.png"])

    # 记录 B：任务目录里只有 1 张图 -> partial
    record_b = service.create_record("话题B", SAMPLE_OUTLINE, task_id="task_b")
    _make_task_dir(tmp_path, "task_b", ["1.png"])

    # 孤立任务目录：无关联记录
    _make_task_dir(tmp_path, "task_orphan", ["0.png"])

    result = service.scan_all_tasks()

    assert result["success"] is True
    assert result["total_tasks"] == 3
    assert result["synced"] == 2
    assert result["failed"] == 0
    assert result["orphan_tasks"] == ["task_orphan"]

    by_task = {r["task_id"]: r for r in result["results"]}
    assert by_task["task_a"]["record_id"] == record_a
    assert by_task["task_a"]["images"] == ["0.png", "1.png"]
    assert by_task["task_a"]["status"] == "completed"
    assert by_task["task_b"]["record_id"] == record_b
    assert by_task["task_b"]["images"] == ["", "1.png"]
    assert by_task["task_b"]["status"] == "partial"
    assert by_task["task_orphan"].get("no_record") is True

    # 记录文件已更新
    detail_a = service.get_record(record_a)
    assert detail_a["images"]["generated"] == ["0.png", "1.png"]
    assert detail_a["status"] == "completed"
    assert detail_a["thumbnail"] == "0.png"

    detail_b = service.get_record(record_b)
    assert detail_b["images"]["generated"] == ["", "1.png"]
    assert detail_b["status"] == "partial"
    assert detail_b["thumbnail"] == "1.png"

    # 索引也同步更新
    index_by_id = {r["id"]: r for r in service._load_index()["records"]}
    assert index_by_id[record_a]["status"] == "completed"
    assert index_by_id[record_a]["thumbnail"] == "0.png"
    assert index_by_id[record_b]["status"] == "partial"
    assert index_by_id[record_b]["thumbnail"] == "1.png"


def test_scan_and_sync_single_task_uses_mapping(tmp_path):
    """单任务扫描：通过映射定位记录并立即写回索引"""
    service = make_history_service(tmp_path)
    record_id = service.create_record("话题", SAMPLE_OUTLINE, task_id="task_1")
    _make_task_dir(tmp_path, "task_1", ["0.png", "1.png"])

    result = service.scan_and_sync_task_images("task_1")

    assert result["success"] is True
    assert result["record_id"] == record_id
    assert result["images"] == ["0.png", "1.png"]
    assert result["status"] == "completed"

    entry = next(
        r for r in service._load_index()["records"] if r["id"] == record_id
    )
    assert entry["status"] == "completed"
    assert entry["thumbnail"] == "0.png"


def test_scan_and_sync_task_without_record_reports_no_record(tmp_path):
    service = make_history_service(tmp_path)
    service.create_record("话题", SAMPLE_OUTLINE, task_id="task_other")
    _make_task_dir(tmp_path, "task_alone", ["0.png"])

    result = service.scan_and_sync_task_images("task_alone")

    assert result["success"] is True
    assert result["no_record"] is True
    assert result["images"] == ["0.png"]


def test_scan_and_sync_missing_task_dir_fails(tmp_path):
    service = make_history_service(tmp_path)

    result = service.scan_and_sync_task_images("task_missing")

    assert result["success"] is False
    assert "任务目录不存在" in result["error"]


# ==================== 问题 1：旧数据回退 ====================

def _strip_task_id_from_index(service: HistoryService, record_ids) -> None:
    """模拟极老索引数据：删除指定条目的 task_id 字段"""
    index_path = Path(service.index_file)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for entry in index["records"]:
        if entry["id"] in record_ids:
            entry.pop("task_id", None)
    index_path.write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8"
    )


def test_scan_falls_back_to_record_file_for_legacy_index_entries(tmp_path):
    """索引条目缺少 task_id 字段时回退读取记录文件，扫描结果不变"""
    service = make_history_service(tmp_path)
    legacy_id = service.create_record("旧记录", SAMPLE_OUTLINE, task_id="task_legacy")
    modern_id = service.create_record("新记录", SAMPLE_OUTLINE, task_id="task_modern")
    _make_task_dir(tmp_path, "task_legacy", ["0.png", "1.png"])
    _make_task_dir(tmp_path, "task_modern", ["0.png"])

    _strip_task_id_from_index(service, {legacy_id})

    result = service.scan_all_tasks()

    assert result["success"] is True
    assert result["synced"] == 2
    assert result["orphan_tasks"] == []

    by_task = {r["task_id"]: r for r in result["results"]}
    assert by_task["task_legacy"]["record_id"] == legacy_id
    assert by_task["task_legacy"]["status"] == "completed"
    assert by_task["task_modern"]["record_id"] == modern_id
    assert by_task["task_modern"]["status"] == "partial"

    assert service.get_record(legacy_id)["images"]["generated"] == ["0.png", "1.png"]


def test_legacy_fallback_only_reads_entries_missing_task_id(tmp_path):
    """回退只针对缺 task_id 字段的条目，不是全部条目"""
    service = make_history_service(tmp_path)
    legacy_id = service.create_record("旧记录", SAMPLE_OUTLINE, task_id="task_legacy")
    for i in range(5):
        service.create_record(f"新记录{i}", SAMPLE_OUTLINE, task_id=f"task_m{i}")

    _strip_task_id_from_index(service, {legacy_id})

    read_ids = []
    original_get_record = service.get_record

    def counting_get_record(record_id, sync_images=False):
        read_ids.append(record_id)
        return original_get_record(record_id, sync_images=sync_images)

    service.get_record = counting_get_record

    mapping = service._build_task_record_map(service._load_index())

    # 构建映射时只读了缺 task_id 的那一条记录文件
    assert read_ids == [legacy_id]
    assert mapping["task_legacy"] == legacy_id
    assert mapping["task_m0"] != legacy_id


# ==================== 问题 1：读盘次数与索引攒批 ====================

def test_scan_all_tasks_record_reads_are_bounded(tmp_path):
    """扫描不再逐记录读盘：get_record 调用次数与任务数线性有界"""
    service = make_history_service(tmp_path)
    task_count = 6
    for i in range(task_count):
        service.create_record(f"话题{i}", SAMPLE_OUTLINE, task_id=f"task_{i}")
        _make_task_dir(tmp_path, f"task_{i}", ["0.png"])

    reads = []
    original_get_record = service.get_record

    def counting_get_record(record_id, sync_images=False):
        reads.append(record_id)
        return original_get_record(record_id, sync_images=sync_images)

    service.get_record = counting_get_record

    result = service.scan_all_tasks()

    assert result["success"] is True
    assert result["synced"] == task_count
    # 每个匹配任务最多 2 次读（合并前快照 + 记录更新），
    # 远小于旧实现的 任务数×记录数
    assert len(reads) <= 2 * task_count


def test_scan_all_tasks_writes_index_once(tmp_path):
    """扫描过程中的索引更新攒批：整个扫描只写一次索引"""
    service = make_history_service(tmp_path)
    for i in range(4):
        service.create_record(f"话题{i}", SAMPLE_OUTLINE, task_id=f"task_{i}")
        _make_task_dir(tmp_path, f"task_{i}", ["0.png", "1.png"])

    save_calls = []
    original_save_index = service._save_index

    def counting_save_index(index):
        save_calls.append(True)
        return original_save_index(index)

    service._save_index = counting_save_index

    result = service.scan_all_tasks()

    assert result["success"] is True
    assert result["synced"] == 4
    assert len(save_calls) == 1

    # 一次性写盘后索引内容仍然完整正确
    index_by_id = {r["id"]: r for r in service._load_index()["records"]}
    assert all(entry["status"] == "completed" for entry in index_by_id.values())


def test_scan_all_tasks_without_updates_does_not_write_index(tmp_path):
    """只有孤立任务时无索引更新，不写盘"""
    service = make_history_service(tmp_path)
    _make_task_dir(tmp_path, "task_orphan", ["0.png"])

    save_calls = []
    original_save_index = service._save_index

    def counting_save_index(index):
        save_calls.append(True)
        return original_save_index(index)

    service._save_index = counting_save_index

    result = service.scan_all_tasks()

    assert result["success"] is True
    assert result["orphan_tasks"] == ["task_orphan"]
    assert save_calls == []


# ==================== 问题 2：图片响应缓存头 ====================

def _setup_image_env(tmp_path, monkeypatch):
    from backend.routes import image_routes

    task_dir = tmp_path / "history" / "task_cache"
    task_dir.mkdir(parents=True)
    (task_dir / "0.png").write_bytes(b"png-bytes")
    (task_dir / "thumb_0.png").write_bytes(b"thumb-bytes")

    monkeypatch.setattr(image_routes, "get_data_root", lambda: tmp_path)


def test_get_image_has_immutable_cache_headers(client, tmp_path, monkeypatch):
    _setup_image_env(tmp_path, monkeypatch)

    resp = client.get("/api/images/task_cache/0.png?thumbnail=false")

    assert resp.status_code == 200
    cache_control = resp.headers.get("Cache-Control", "")
    assert "public" in cache_control
    assert "max-age=31536000" in cache_control
    assert "immutable" in cache_control


def test_get_image_thumbnail_has_immutable_cache_headers(client, tmp_path, monkeypatch):
    _setup_image_env(tmp_path, monkeypatch)

    resp = client.get("/api/images/task_cache/0.png")

    assert resp.status_code == 200
    assert resp.data == b"thumb-bytes"
    cache_control = resp.headers.get("Cache-Control", "")
    assert "max-age=31536000" in cache_control
    assert "immutable" in cache_control


def test_get_image_404_has_no_long_cache_header(client, tmp_path, monkeypatch):
    _setup_image_env(tmp_path, monkeypatch)

    resp = client.get("/api/images/task_cache/missing.png?thumbnail=false")

    assert resp.status_code == 404
    assert "immutable" not in resp.headers.get("Cache-Control", "")
