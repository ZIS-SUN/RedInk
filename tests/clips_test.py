"""
剪藏收件箱（ClipsService + /api/clips）测试

不动真实数据：
- 服务层：用临时目录装配服务（__new__ 绕过 __init__，与 idea_library_test 同法），
  覆盖 CRUD / 字段归一化 / 50 条滚动上限 / 字段校验 / 损坏文件不覆盖
- 路由层：复用 conftest 的完整 app（顺带验证蓝图已注册），
  monkeypatch get_clips_service 指向临时服务；另验证插件来源的 CORS 放行
"""
import json
from pathlib import Path

import pytest

from backend.routes import clips_routes
from backend.services.clips import (
    ClipsService,
    ClipStoreCorruptedError,
    DEFAULT_SOURCE,
    MAX_CLIPS,
    MAX_CONTENT_CHARS,
    MAX_TAGS,
    MAX_TITLE_CHARS,
)


# ==================== 测试工具 ====================

def make_service(tmp_path: Path) -> ClipsService:
    """绕过 __init__，把存储指向临时目录（不触碰真实数据根目录）"""
    service = ClipsService.__new__(ClipsService)
    service.clips_dir = str(tmp_path)
    service.store_file = str(tmp_path / "clips.json")
    service._init_store()
    return service


@pytest.fixture
def service(tmp_path):
    return make_service(tmp_path)


# ==================== 创建与归一化 ====================

def test_create_clip_full_fields(service):
    clip = service.create_clip({
        "source": "xiaohongshu",
        "url": "https://www.xiaohongshu.com/explore/abc123",
        "title": "  秋季穿搭合集  ",
        "author": "穿搭博主",
        "content": "第一条：基础款……",
        "tags": ["#穿搭", "秋季", "", None],
        "stats": {"likes": 1200, "collects": "340", "comments": 56.0},
    })

    assert clip["source"] == "xiaohongshu"
    assert clip["url"] == "https://www.xiaohongshu.com/explore/abc123"
    assert clip["title"] == "秋季穿搭合集"
    assert clip["author"] == "穿搭博主"
    assert clip["content"] == "第一条：基础款……"
    # 标签去 # 前缀、丢弃空项
    assert clip["tags"] == ["穿搭", "秋季"]
    # 互动数：字符串数字解析为整数
    assert clip["stats"] == {"likes": 1200, "collects": 340, "comments": 56}
    assert clip["id"]
    assert clip["created_at"]


def test_create_clip_defaults_and_fallbacks(service):
    """来源非法回退 other；未提供的字段给默认值"""
    clip = service.create_clip({"title": "只有标题", "source": "weibo"})

    assert clip["source"] == DEFAULT_SOURCE
    assert clip["url"] == ""
    assert clip["author"] == ""
    assert clip["content"] == ""
    assert clip["tags"] == []
    assert clip["stats"] is None


def test_create_clip_content_only(service):
    """只有正文没有标题也允许（抖音纯文案场景）"""
    clip = service.create_clip({"content": "只有文案没有标题", "source": "douyin"})
    assert clip["title"] == ""
    assert clip["content"] == "只有文案没有标题"


def test_create_clip_both_empty_raises(service):
    with pytest.raises(ValueError):
        service.create_clip({"title": "   ", "content": ""})


def test_create_clip_content_too_long_raises(service):
    with pytest.raises(ValueError):
        service.create_clip({"content": "长" * (MAX_CONTENT_CHARS + 1)})


def test_create_clip_boundary_content_length_ok(service):
    """正文正好达到上限时应被接收（边界值）"""
    clip = service.create_clip({"content": "长" * MAX_CONTENT_CHARS})
    assert len(clip["content"]) == MAX_CONTENT_CHARS


def test_create_clip_truncates_long_short_fields(service):
    """标题等短字段超长时截断而非报错（网页 DOM 内容不可控）"""
    clip = service.create_clip({"title": "题" * (MAX_TITLE_CHARS + 50)})
    assert len(clip["title"]) == MAX_TITLE_CHARS


def test_create_clip_tags_capped(service):
    clip = service.create_clip({
        "title": "标签上限",
        "tags": [f"标签{i}" for i in range(MAX_TAGS + 10)],
    })
    assert len(clip["tags"]) == MAX_TAGS


def test_normalize_stats_invalid_values(service):
    """互动数：布尔/负数/解析不出的字符串丢弃；全无效时 stats 为 None"""
    clip = service.create_clip({
        "title": "互动数容错",
        "stats": {"likes": True, "collects": -5, "comments": "abc"},
    })
    assert clip["stats"] is None

    clip2 = service.create_clip({
        "title": "部分有效",
        "stats": {"likes": "1.2", "comments": 3, "extra": 99},
    })
    assert clip2["stats"] == {"likes": 1, "comments": 3}


def test_stats_non_dict_becomes_none(service):
    clip = service.create_clip({"title": "非对象互动数", "stats": [1, 2, 3]})
    assert clip["stats"] is None


# ==================== 列表与删除 ====================

def test_list_clips_newest_first(service):
    service.create_clip({"title": "第一条"})
    service.create_clip({"title": "第二条"})

    clips = service.list_clips()
    assert [c["title"] for c in clips] == ["第二条", "第一条"]


def test_get_clip(service):
    clip = service.create_clip({"title": "按 ID 取"})
    assert service.get_clip(clip["id"])["title"] == "按 ID 取"
    assert service.get_clip("no-such-id") is None


def test_delete_clip(service):
    clip = service.create_clip({"title": "待删除"})
    assert service.delete_clip(clip["id"]) is True
    assert service.get_clip(clip["id"]) is None
    assert service.delete_clip(clip["id"]) is False


def test_clear_clips(service):
    service.create_clip({"title": "A"})
    service.create_clip({"title": "B"})

    assert service.clear_clips() == 2
    assert service.list_clips() == []
    # 空库再清空返回 0
    assert service.clear_clips() == 0


# ==================== 50 条滚动上限 ====================

def test_rolling_limit_drops_oldest(service):
    for i in range(MAX_CLIPS + 5):
        service.create_clip({"title": f"第 {i} 条"})

    clips = service.list_clips()
    assert len(clips) == MAX_CLIPS
    # 最新的在队首，最早的 5 条已被滚动删除
    assert clips[0]["title"] == f"第 {MAX_CLIPS + 4} 条"
    assert clips[-1]["title"] == "第 5 条"
    titles = {c["title"] for c in clips}
    for i in range(5):
        assert f"第 {i} 条" not in titles


def test_rolling_limit_persisted(service):
    """滚动裁剪的结果要真实落盘，不只是内存视图"""
    for i in range(MAX_CLIPS + 3):
        service.create_clip({"title": f"第 {i} 条"})

    with open(service.store_file, "r", encoding="utf-8") as f:
        store = json.load(f)
    assert len(store["clips"]) == MAX_CLIPS


# ==================== 损坏文件保护 ====================

def test_corrupted_store_raises_and_preserves_file(service):
    service.create_clip({"title": "真实数据"})

    # 人为写坏数据文件
    with open(service.store_file, "w", encoding="utf-8") as f:
        f.write("{ 这不是合法 JSON")

    with pytest.raises(ClipStoreCorruptedError):
        service.list_clips()
    with pytest.raises(ClipStoreCorruptedError):
        service.create_clip({"title": "不应写入"})

    # 原文件内容被完整保留，未被空库覆盖
    with open(service.store_file, "r", encoding="utf-8") as f:
        assert f.read() == "{ 这不是合法 JSON"


def test_wrong_structure_raises(service):
    """结构异常（clips 不是列表）同样视为损坏，拒绝静默覆盖"""
    with open(service.store_file, "w", encoding="utf-8") as f:
        json.dump({"clips": "not-a-list"}, f)

    with pytest.raises(ClipStoreCorruptedError):
        service.list_clips()


def test_missing_file_returns_empty(service):
    """文件被删除时返回空库（首次使用场景），不报错"""
    import os
    os.remove(service.store_file)
    assert service.list_clips() == []


# ==================== 路由层 ====================

@pytest.fixture
def route_service(tmp_path, monkeypatch):
    """把路由使用的服务替换为临时目录服务"""
    service = make_service(tmp_path)
    monkeypatch.setattr(clips_routes, "get_clips_service", lambda: service)
    return service


def test_route_create_and_list(client, route_service):
    create_resp = client.post("/api/clips", json={
        "source": "douyin",
        "url": "https://www.douyin.com/video/123",
        "title": "路由新建",
        "content": "正文",
        "tags": ["测试"],
        "stats": {"likes": 10},
    })
    created = create_resp.get_json()

    assert create_resp.status_code == 200
    assert created["success"] is True
    assert created["clip"]["title"] == "路由新建"
    assert created["clip"]["source"] == "douyin"
    assert created["clip"]["stats"] == {"likes": 10}

    list_resp = client.get("/api/clips")
    data = list_resp.get_json()
    assert list_resp.status_code == 200
    assert data["success"] is True
    assert len(data["clips"]) == 1


def test_route_create_requires_title_or_content(client, route_service):
    resp = client.post("/api/clips", json={"url": "https://example.com"})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_route_create_rejects_oversized_content(client, route_service):
    resp = client.post("/api/clips", json={"content": "长" * (MAX_CONTENT_CHARS + 1)})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False
    # 超限请求不应写入
    assert route_service.list_clips() == []


def test_route_create_handles_non_json_body(client, route_service):
    """非 JSON 请求体按空请求处理，返回 400 而非 500"""
    resp = client.post("/api/clips", data="not json", content_type="text/plain")
    assert resp.status_code == 400


def test_route_delete_one(client, route_service):
    clip = route_service.create_clip({"title": "路由删除"})

    resp = client.delete(f"/api/clips/{clip['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    resp = client.delete(f"/api/clips/{clip['id']}")
    assert resp.status_code == 404


def test_route_clear_all(client, route_service):
    route_service.create_clip({"title": "A"})
    route_service.create_clip({"title": "B"})

    resp = client.delete("/api/clips")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["success"] is True
    assert data["removed"] == 2
    assert route_service.list_clips() == []


# ==================== CORS：插件来源放行 ====================

def test_cors_allows_extension_origin_on_clips(client, route_service):
    """chrome-extension:// 来源在 /api/clips 上放行（含预检与实际请求）"""
    origin = "chrome-extension://abcdefghijklmnop"

    # 预检请求
    preflight = client.options("/api/clips", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type, X-Access-Token",
    })
    assert preflight.headers.get("Access-Control-Allow-Origin") == origin
    allow_headers = preflight.headers.get("Access-Control-Allow-Headers", "")
    assert "X-Access-Token" in allow_headers

    # 实际 POST
    resp = client.post("/api/clips", json={"title": "跨源剪藏"}, headers={"Origin": origin})
    assert resp.status_code == 200
    assert resp.headers.get("Access-Control-Allow-Origin") == origin

    # Firefox 的 moz-extension:// 同样放行
    moz = client.get("/api/clips", headers={"Origin": "moz-extension://xyz"})
    assert moz.headers.get("Access-Control-Allow-Origin") == "moz-extension://xyz"


def test_cors_extension_origin_not_allowed_elsewhere(client):
    """插件来源的放行仅限 /api/clips*，其他 /api/* 路径不受影响"""
    origin = "chrome-extension://abcdefghijklmnop"
    resp = client.get("/api/brands", headers={"Origin": origin})
    assert resp.headers.get("Access-Control-Allow-Origin") is None

    # 原白名单来源在其他路径继续生效
    resp2 = client.get("/api/brands", headers={"Origin": "http://localhost:5173"})
    assert resp2.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"


# ==================== 令牌鉴权场景（REDINK_ACCESS_TOKEN） ====================

def test_clips_with_access_token_auth(tmp_path, monkeypatch):
    """启用访问令牌后：预检放行、无令牌 401、插件带 X-Access-Token 可正常剪藏"""
    monkeypatch.setenv("REDINK_ACCESS_TOKEN", "secret-token")

    from backend.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    token_client = app.test_client()

    service = make_service(tmp_path)
    monkeypatch.setattr(clips_routes, "get_clips_service", lambda: service)

    origin = "chrome-extension://abcdefghijklmnop"

    # CORS 预检不受鉴权影响（浏览器预检不带自定义头）
    preflight = token_client.options("/api/clips", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type, X-Access-Token",
    })
    assert preflight.headers.get("Access-Control-Allow-Origin") == origin

    # 未带令牌 → 401，且未写入数据
    resp = token_client.post("/api/clips", json={"title": "无令牌"}, headers={"Origin": origin})
    assert resp.status_code == 401
    assert service.list_clips() == []

    # 带 X-Access-Token（插件设置项的请求头）→ 剪藏成功
    resp2 = token_client.post(
        "/api/clips",
        json={"title": "带令牌"},
        headers={"Origin": origin, "X-Access-Token": "secret-token"},
    )
    assert resp2.status_code == 200
    assert resp2.get_json()["success"] is True
    assert len(service.list_clips()) == 1
