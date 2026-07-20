"""
我的选题库（IdeaLibraryService + /api/ideas）测试

不动真实数据：
- 服务层：用临时目录装配服务（__new__ 绕过 __init__，与 preference_test 同法），
  覆盖 CRUD / 字段归一化 / 状态流转 / 过滤 / 损坏文件不覆盖
- 路由层：复用 conftest 的完整 app（顺带验证蓝图已注册），
  monkeypatch get_idea_library_service 指向临时服务
"""
import json
from pathlib import Path

import pytest

from backend.routes import idea_routes
from backend.services.idea_library import (
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    IdeaLibraryService,
    IdeaStoreCorruptedError,
)


# ==================== 测试工具 ====================

def make_service(tmp_path: Path) -> IdeaLibraryService:
    """绕过 __init__，把存储指向临时目录（不触碰真实数据根目录）"""
    service = IdeaLibraryService.__new__(IdeaLibraryService)
    service.idea_dir = str(tmp_path)
    service.store_file = str(tmp_path / "ideas.json")
    service._init_store()
    return service


@pytest.fixture
def service(tmp_path):
    return make_service(tmp_path)


# ==================== 创建与归一化 ====================

def test_create_idea_full_fields(service):
    idea = service.create_idea({
        "title": "  租房收纳选题  ",
        "angle": "反常识切入",
        "tags": ["#收纳", "租房", "", None],
        "source": "topic",
        "status": "todo",
        "niche": "家居收纳",
    })

    assert idea["title"] == "租房收纳选题"
    assert idea["angle"] == "反常识切入"
    # 标签去 # 前缀、丢弃空项
    assert idea["tags"] == ["收纳", "租房"]
    assert idea["source"] == "topic"
    assert idea["status"] == "todo"
    assert idea["niche"] == "家居收纳"
    assert idea["id"]
    assert idea["created_at"] == idea["updated_at"]


def test_create_idea_defaults_and_fallbacks(service):
    """创建入口宽松容错：非法 source/status 回退默认值"""
    idea = service.create_idea({
        "title": "只有标题",
        "source": "weibo",
        "status": "flying",
    })

    assert idea["source"] == DEFAULT_SOURCE
    assert idea["status"] == DEFAULT_STATUS
    assert idea["angle"] == ""
    assert idea["tags"] == []
    assert idea["niche"] == ""


def test_create_idea_empty_title_raises(service):
    with pytest.raises(ValueError):
        service.create_idea({"title": "   "})


def test_list_ideas_newest_first(service):
    service.create_idea({"title": "第一条"})
    service.create_idea({"title": "第二条"})

    ideas = service.list_ideas()
    assert [i["title"] for i in ideas] == ["第二条", "第一条"]


# ==================== 状态流转与更新 ====================

def test_status_transition_via_update(service):
    idea = service.create_idea({"title": "流转测试"})
    assert idea["status"] == "idea"

    # 想法 → 待做 → 已做 → 已爆
    for status in ("todo", "done", "viral"):
        updated = service.update_idea(idea["id"], {"status": status})
        assert updated["status"] == status

    # 落盘后重新读取仍是最终状态
    assert service.get_idea(idea["id"])["status"] == "viral"


def test_update_invalid_status_raises(service):
    idea = service.create_idea({"title": "非法状态"})
    with pytest.raises(ValueError):
        service.update_idea(idea["id"], {"status": "archived"})
    # 报错后原状态保持不变
    assert service.get_idea(idea["id"])["status"] == "idea"


def test_update_invalid_source_raises(service):
    idea = service.create_idea({"title": "非法来源"})
    with pytest.raises(ValueError):
        service.update_idea(idea["id"], {"source": "weibo"})


def test_update_partial_fields(service):
    idea = service.create_idea({"title": "部分更新", "angle": "旧角度"})
    updated = service.update_idea(idea["id"], {"angle": "新角度", "tags": ["a", "b"]})

    assert updated["title"] == "部分更新"
    assert updated["angle"] == "新角度"
    assert updated["tags"] == ["a", "b"]


def test_update_empty_title_raises(service):
    idea = service.create_idea({"title": "标题保护"})
    with pytest.raises(ValueError):
        service.update_idea(idea["id"], {"title": ""})


def test_update_missing_idea_returns_none(service):
    assert service.update_idea("no-such-id", {"status": "todo"}) is None


# ==================== 删除 ====================

def test_delete_idea(service):
    idea = service.create_idea({"title": "待删除"})
    assert service.delete_idea(idea["id"]) is True
    assert service.get_idea(idea["id"]) is None
    assert service.delete_idea(idea["id"]) is False


# ==================== 过滤 ====================

def test_list_filter_by_status_and_source(service):
    service.create_idea({"title": "A", "status": "todo", "source": "topic"})
    service.create_idea({"title": "B", "status": "todo", "source": "insight"})
    service.create_idea({"title": "C", "status": "viral", "source": "topic"})

    assert [i["title"] for i in service.list_ideas(status="todo")] == ["B", "A"]
    assert [i["title"] for i in service.list_ideas(source="topic")] == ["C", "A"]
    assert [i["title"] for i in service.list_ideas(status="todo", source="topic")] == ["A"]
    assert service.list_ideas(status="done") == []


# ==================== 损坏文件回退 ====================

def test_corrupted_store_raises_and_preserves_file(service):
    service.create_idea({"title": "真实数据"})

    # 人为写坏数据文件
    with open(service.store_file, "w", encoding="utf-8") as f:
        f.write("{ 这不是合法 JSON")

    with pytest.raises(IdeaStoreCorruptedError):
        service.list_ideas()
    with pytest.raises(IdeaStoreCorruptedError):
        service.create_idea({"title": "不应写入"})

    # 原文件内容被完整保留，未被空库覆盖
    with open(service.store_file, "r", encoding="utf-8") as f:
        assert f.read() == "{ 这不是合法 JSON"


def test_wrong_structure_raises(service):
    """结构异常（ideas 不是列表）同样视为损坏，拒绝静默覆盖"""
    with open(service.store_file, "w", encoding="utf-8") as f:
        json.dump({"ideas": "not-a-list"}, f)

    with pytest.raises(IdeaStoreCorruptedError):
        service.list_ideas()


def test_missing_file_returns_empty(service):
    """文件被删除时返回空库（首次使用场景），不报错"""
    import os
    os.remove(service.store_file)
    assert service.list_ideas() == []


# ==================== 路由层 ====================

@pytest.fixture
def route_service(tmp_path, monkeypatch):
    """把路由使用的服务替换为临时目录服务"""
    service = make_service(tmp_path)
    monkeypatch.setattr(idea_routes, "get_idea_library_service", lambda: service)
    return service


def test_route_create_and_list(client, route_service):
    create_resp = client.post("/api/ideas", json={
        "title": "路由新建",
        "angle": "角度",
        "tags": ["标签"],
        "source": "insight",
    })
    created = create_resp.get_json()

    assert create_resp.status_code == 200
    assert created["success"] is True
    assert created["idea"]["title"] == "路由新建"
    assert created["idea"]["source"] == "insight"

    list_resp = client.get("/api/ideas")
    data = list_resp.get_json()
    assert list_resp.status_code == 200
    assert data["success"] is True
    assert len(data["ideas"]) == 1


def test_route_create_requires_title(client, route_service):
    resp = client.post("/api/ideas", json={"angle": "只有角度"})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_route_list_filters(client, route_service):
    route_service.create_idea({"title": "A", "status": "todo", "source": "topic"})
    route_service.create_idea({"title": "B", "status": "viral", "source": "hotspot"})

    resp = client.get("/api/ideas?status=viral&source=hotspot")
    data = resp.get_json()
    assert [i["title"] for i in data["ideas"]] == ["B"]


def test_route_update_status(client, route_service):
    idea = route_service.create_idea({"title": "路由流转"})

    resp = client.put(f"/api/ideas/{idea['id']}", json={"status": "done"})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["idea"]["status"] == "done"


def test_route_update_invalid_status_returns_400(client, route_service):
    idea = route_service.create_idea({"title": "路由非法状态"})
    resp = client.put(f"/api/ideas/{idea['id']}", json={"status": "bad"})
    assert resp.status_code == 400


def test_route_update_missing_returns_404(client, route_service):
    resp = client.put("/api/ideas/no-such-id", json={"status": "todo"})
    assert resp.status_code == 404


def test_route_delete(client, route_service):
    idea = route_service.create_idea({"title": "路由删除"})

    resp = client.delete(f"/api/ideas/{idea['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    resp = client.delete(f"/api/ideas/{idea['id']}")
    assert resp.status_code == 404
