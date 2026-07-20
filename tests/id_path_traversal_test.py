"""record_id / task_id 路径遍历防护测试（修复 1：服务层统一校验）"""
import uuid
from pathlib import Path

import pytest

from backend.errors import AppErrorException, ensure_app_error
from backend.services.history import HistoryService, validate_safe_id
from backend.services.image import ImageService


def make_history_service(tmp_path: Path) -> HistoryService:
    service = HistoryService.__new__(HistoryService)
    service.history_dir = str(tmp_path)
    service.index_file = str(tmp_path / "index.json")
    service._init_index()
    return service


def make_image_service(tmp_path: Path) -> ImageService:
    image_service = ImageService.__new__(ImageService)
    image_service.history_root_dir = str(tmp_path)
    return image_service


# ==================== validate_safe_id 本体 ====================

def test_validate_safe_id_accepts_existing_id_formats():
    # 兼容存量数据格式：uuid4 的 record_id、"task_" 前缀短 hex 的 task_id
    assert validate_safe_id(str(uuid.uuid4()), "record_id")
    assert validate_safe_id(f"task_{uuid.uuid4().hex[:8]}", "task_id")
    assert validate_safe_id("test-record-001", "record_id")


@pytest.mark.parametrize("bad_id", [
    "../evil",
    "..",
    "a/b",
    "a\\b",
    "task_1/../../x",
    "",
    "x" * 65,
    None,
    123,
])
def test_validate_safe_id_rejects_illegal_values(bad_id):
    with pytest.raises(AppErrorException) as exc_info:
        validate_safe_id(bad_id, "task_id")

    app_error = ensure_app_error(exc_info.value)
    assert app_error.status == 400
    assert app_error.code == "INVALID_REQUEST"


# ==================== HistoryService 入口 ====================

def test_history_service_rejects_traversal_record_id(tmp_path):
    service = make_history_service(tmp_path)

    with pytest.raises(AppErrorException):
        service.get_record("../../etc/passwd")
    with pytest.raises(AppErrorException):
        service.update_record("../evil", status="draft")
    with pytest.raises(AppErrorException):
        service.record_exists("../evil")


def test_history_service_rejects_traversal_task_id_in_scan(tmp_path):
    service = make_history_service(tmp_path)

    with pytest.raises(AppErrorException):
        service.scan_and_sync_task_images("../outside")


def test_scan_all_tasks_skips_unsafe_dir_names(tmp_path):
    service = make_history_service(tmp_path)
    # 合法任务目录 + 名字含非法字符的目录（非本应用生成）
    (tmp_path / "task_ok123").mkdir()
    (tmp_path / "bad name!").mkdir()

    result = service.scan_all_tasks()

    assert result["success"] is True
    assert result["total_tasks"] == 1


# ==================== ImageService 写入侧入口 ====================

def test_generate_images_rejects_bad_task_id_before_streaming(tmp_path, sample_pages):
    image_service = make_image_service(tmp_path)

    # 校验发生在返回生成器之前（调用即抛错，路由层可返回 400 而非流中断）
    with pytest.raises(AppErrorException):
        image_service.generate_images(sample_pages, task_id="../evil")

    # 未在历史根目录外创建任何目录
    assert not (tmp_path.parent / "evil").exists()


def test_retry_single_image_rejects_bad_task_id(tmp_path):
    image_service = make_image_service(tmp_path)

    with pytest.raises(AppErrorException):
        image_service.retry_single_image(
            "../../evil", {"index": 0, "type": "cover", "content": "c"}
        )

    assert not (tmp_path.parent / "evil").exists()


def test_retry_failed_images_rejects_bad_task_id(tmp_path):
    image_service = make_image_service(tmp_path)

    with pytest.raises(AppErrorException):
        image_service.retry_failed_images(
            "..", [{"index": 0, "type": "cover", "content": "c"}]
        )


def test_get_image_path_rejects_bad_task_id(tmp_path):
    image_service = make_image_service(tmp_path)

    with pytest.raises(AppErrorException):
        image_service.get_image_path("../evil", "0.png")
