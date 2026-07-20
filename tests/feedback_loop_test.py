"""
输出质量反馈闭环（数据积累层）测试：

- 作品评分：set_rating 校验（1-5 / null）、持久化、清除、索引冗余
- PATCH /api/history/<id>/rating 路由：校验 400 / 404 / 成功
- 编辑留痕：update_record(edit_trace=...) 追加、坏结构静默忽略、
  50 条截断、旧记录向后兼容
- 详情响应对旧记录补 rating / edit_history 默认值
"""
import json
from pathlib import Path

import pytest

from backend.errors import AppErrorException, ensure_app_error
from backend.services.history import (
    MAX_EDIT_HISTORY,
    HistoryService,
    validate_rating,
)


def make_history_service(tmp_path: Path) -> HistoryService:
    service = HistoryService.__new__(HistoryService)
    service.history_dir = str(tmp_path)
    service.index_file = str(tmp_path / "index.json")
    service._init_index()
    return service


SAMPLE_OUTLINE = {
    "raw": "原始大纲文本",
    "pages": [
        {"index": 0, "type": "cover", "content": "封面"},
        {"index": 1, "type": "content", "content": "内容"},
    ],
}


def make_trace(page_index=0, original="AI 原文", edited="用户终稿", source="manual"):
    return {
        "page_index": page_index,
        "original_text": original,
        "edited_text": edited,
        "source": source,
    }


# ==================== validate_rating ====================

@pytest.mark.parametrize("rating", [1, 2, 3, 4, 5, None])
def test_validate_rating_accepts_valid_values(rating):
    assert validate_rating(rating) == rating


@pytest.mark.parametrize("bad", [0, 6, -1, "3", 2.5, True, False, [], {}])
def test_validate_rating_rejects_illegal_values(bad):
    with pytest.raises(AppErrorException) as exc_info:
        validate_rating(bad)

    app_error = ensure_app_error(exc_info.value)
    assert app_error.status == 400
    assert app_error.code == "INVALID_REQUEST"


# ==================== set_rating 服务层 ====================

def test_set_rating_persists_to_record_and_index(tmp_path):
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE, task_id="task_1")

    assert service.set_rating(record_id, 4)

    record = service.get_record(record_id)
    assert record["rating"] == 4

    entry = next(
        r for r in service._load_index()["records"] if r["id"] == record_id
    )
    assert entry["rating"] == 4
    # 索引原有字段不被评分更新破坏（task_id 映射逻辑依赖它）
    assert entry["task_id"] == "task_1"


def test_set_rating_none_clears_rating(tmp_path):
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    assert service.set_rating(record_id, 5)
    assert service.set_rating(record_id, None)

    assert service.get_record(record_id)["rating"] is None
    entry = next(
        r for r in service._load_index()["records"] if r["id"] == record_id
    )
    assert entry["rating"] is None


def test_set_rating_missing_record_returns_false(tmp_path):
    service = make_history_service(tmp_path)
    assert service.set_rating("no-such-record", 3) is False


def test_set_rating_rejects_illegal_value_before_write(tmp_path):
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    with pytest.raises(AppErrorException):
        service.set_rating(record_id, 6)

    assert "rating" not in service.get_record(record_id)


def test_unrated_records_keep_old_index_shape(tmp_path):
    """未评分记录的索引条目不新增 rating 键（向后兼容：缺字段=无评分）"""
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    # 常规更新（如生成图片）不应引入 rating 键
    service.update_record(record_id, status="generating")

    entry = next(
        r for r in service._load_index()["records"] if r["id"] == record_id
    )
    assert "rating" not in entry


def test_rating_survives_other_updates(tmp_path):
    """评分后其他字段更新不应丢失索引中的 rating"""
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    service.set_rating(record_id, 3)
    service.update_record(
        record_id,
        images={"task_id": "task_1", "generated": ["0.png", "1.png"]},
        status="completed",
        thumbnail="0.png",
    )

    entry = next(
        r for r in service._load_index()["records"] if r["id"] == record_id
    )
    assert entry["rating"] == 3
    assert entry["status"] == "completed"
    assert entry["task_id"] == "task_1"


# ==================== 编辑留痕 服务层 ====================

def test_update_record_appends_edit_trace(tmp_path):
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    assert service.update_record(record_id, edit_trace=make_trace())
    assert service.update_record(
        record_id, edit_trace=make_trace(page_index=1, source="polish")
    )

    traces = service.get_record(record_id)["edit_history"]
    assert len(traces) == 2
    assert traces[0]["page_index"] == 0
    assert traces[0]["source"] == "manual"
    assert traces[0]["original_text"] == "AI 原文"
    assert traces[0]["edited_text"] == "用户终稿"
    assert traces[0]["edited_at"]
    assert traces[1]["page_index"] == 1
    assert traces[1]["source"] == "polish"


def test_edit_trace_can_ride_along_outline_update(tmp_path):
    """编辑文案保存的真实调用：outline 覆写 + edit_trace 同一次请求落库"""
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    new_outline = {
        "raw": "改后的大纲",
        "pages": [
            {"index": 0, "type": "cover", "content": "改后的封面"},
            {"index": 1, "type": "content", "content": "内容"},
        ],
    }
    assert service.update_record(
        record_id,
        outline=new_outline,
        edit_trace=make_trace(original="封面", edited="改后的封面"),
    )

    record = service.get_record(record_id)
    assert record["outline"] == new_outline
    assert len(record["edit_history"]) == 1


@pytest.mark.parametrize("bad", [
    "not-a-dict",
    [],
    {},
    make_trace(page_index=-1),
    make_trace(page_index="0"),
    make_trace(page_index=True),
    make_trace(source="llm"),
    make_trace(source=None),
    {"page_index": 0, "original_text": 1, "edited_text": "x", "source": "manual"},
    {"page_index": 0, "original_text": "x", "edited_text": None, "source": "manual"},
])
def test_update_record_ignores_bad_edit_trace(tmp_path, bad):
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    # 更新本身成功（不报错），坏结构不写入
    assert service.update_record(record_id, edit_trace=bad)
    assert "edit_history" not in service.get_record(record_id)


def test_edit_trace_with_no_diff_is_skipped(tmp_path):
    """原文与新文相同（无 diff 价值）不落库"""
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    assert service.update_record(
        record_id, edit_trace=make_trace(original="一样", edited="一样")
    )
    assert "edit_history" not in service.get_record(record_id)


def test_edit_history_truncated_to_max(tmp_path):
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    total = MAX_EDIT_HISTORY + 10
    for i in range(total):
        assert service.update_record(
            record_id, edit_trace=make_trace(original=f"原文{i}", edited=f"终稿{i}")
        )

    traces = service.get_record(record_id)["edit_history"]
    assert len(traces) == MAX_EDIT_HISTORY
    # 保留的是最近 MAX_EDIT_HISTORY 条
    assert traces[0]["original_text"] == f"原文{total - MAX_EDIT_HISTORY}"
    assert traces[-1]["original_text"] == f"原文{total - 1}"


def test_edit_trace_on_legacy_record_with_bad_field_type(tmp_path):
    """edit_history 字段被外部写坏（非数组）时重置为新数组，不崩溃"""
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    record_path = Path(service._get_record_path(record_id))
    broken = json.loads(record_path.read_text(encoding="utf-8"))
    broken["edit_history"] = "corrupted"
    record_path.write_text(
        json.dumps(broken, ensure_ascii=False), encoding="utf-8"
    )

    assert service.update_record(record_id, edit_trace=make_trace())
    traces = service.get_record(record_id)["edit_history"]
    assert len(traces) == 1


# ==================== 路由层 ====================

@pytest.fixture
def history_env(tmp_path, monkeypatch):
    """把历史路由指向临时目录的服务实例"""
    from backend.routes import history_routes

    service = make_history_service(tmp_path)
    monkeypatch.setattr(history_routes, "get_history_service", lambda: service)
    return service


def test_patch_rating_persists(client, history_env):
    record_id = history_env.create_record("topic", SAMPLE_OUTLINE)

    response = client.patch(f"/api/history/{record_id}/rating", json={"rating": 5})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["rating"] == 5
    assert history_env.get_record(record_id)["rating"] == 5


def test_patch_rating_null_clears(client, history_env):
    record_id = history_env.create_record("topic", SAMPLE_OUTLINE)
    history_env.set_rating(record_id, 2)

    response = client.patch(f"/api/history/{record_id}/rating", json={"rating": None})
    assert response.status_code == 200
    assert response.get_json()["rating"] is None
    assert history_env.get_record(record_id)["rating"] is None


@pytest.mark.parametrize("bad", [0, 6, "3", 2.5, True])
def test_patch_rating_rejects_illegal_values(client, history_env, bad):
    record_id = history_env.create_record("topic", SAMPLE_OUTLINE)

    response = client.patch(f"/api/history/{record_id}/rating", json={"rating": bad})
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "INVALID_REQUEST"


def test_patch_rating_requires_rating_field(client, history_env):
    record_id = history_env.create_record("topic", SAMPLE_OUTLINE)

    response = client.patch(f"/api/history/{record_id}/rating", json={})
    assert response.status_code == 400


def test_patch_rating_missing_record_returns_404(client, history_env):
    response = client.patch("/api/history/no-such-id/rating", json={"rating": 3})
    assert response.status_code == 404


def test_set_rating_rejects_traversal_record_id(tmp_path):
    service = make_history_service(tmp_path)
    with pytest.raises(AppErrorException):
        service.set_rating("../evil", 3)


def test_detail_response_defaults_rating_and_edit_history(client, history_env):
    """旧记录（无新字段）详情响应显式补 rating=null / edit_history=[]"""
    record_id = history_env.create_record("topic", SAMPLE_OUTLINE)

    response = client.get(f"/api/history/{record_id}")
    assert response.status_code == 200
    record = response.get_json()["record"]
    assert record["rating"] is None
    assert record["edit_history"] == []


def test_list_response_carries_rating(client, history_env):
    rated_id = history_env.create_record("有评分", SAMPLE_OUTLINE)
    history_env.create_record("无评分", SAMPLE_OUTLINE)
    history_env.set_rating(rated_id, 4)

    response = client.get("/api/history")
    assert response.status_code == 200
    records = response.get_json()["records"]
    by_id = {r["id"]: r for r in records}
    assert by_id[rated_id]["rating"] == 4


def test_put_history_with_edit_trace(client, history_env):
    record_id = history_env.create_record("topic", SAMPLE_OUTLINE)

    response = client.put(
        f"/api/history/{record_id}",
        json={"edit_trace": make_trace(source="polish")},
    )
    assert response.status_code == 200
    traces = history_env.get_record(record_id)["edit_history"]
    assert len(traces) == 1
    assert traces[0]["source"] == "polish"
