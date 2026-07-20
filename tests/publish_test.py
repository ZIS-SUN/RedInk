"""
发布助手（publish 服务 + /api/publish/* 路由）测试

用 tmp_path + monkeypatch 隔离 get_data_root 与历史服务，
不读写真实数据目录，不发起任何子进程调用（open-folder 只测拒绝分支）。

覆盖：
- 账号 CRUD：增改删查、platform 白名单 400、nickname 空 400、404
- 平台清单接口
- 一键备料：无 record 404 / 无图 400 / 正常导出文件与「发布文案.txt」内容
- 打开文件夹：目录穿越 400（/etc 与 ../ 均被拒）、导出目录内不存在的文件夹不报错
"""
from pathlib import Path

import pytest

from backend.services import publish as publish_module
from backend.services.history import HistoryService


# ==================== 隔离环境 ====================

@pytest.fixture
def publish_env(tmp_path, monkeypatch):
    """数据根目录指向 tmp_path，历史服务落到 tmp_path/history，重置单例。"""
    monkeypatch.setattr(publish_module, "get_data_root", lambda: tmp_path)
    monkeypatch.setattr(publish_module, "_service_instance", None)

    history_dir = tmp_path / "history"
    history_dir.mkdir()
    history_service = HistoryService.__new__(HistoryService)
    history_service.history_dir = str(history_dir)
    history_service.index_file = str(history_dir / "index.json")
    history_service._init_index()
    monkeypatch.setattr(
        publish_module, "get_history_service", lambda: history_service
    )

    return tmp_path, history_service


SAMPLE_OUTLINE = {
    "raw": "原始大纲文本",
    "pages": [
        {"index": 0, "type": "cover", "content": "封面"},
        {"index": 1, "type": "content", "content": "内容"},
    ],
}

SAMPLE_CONTENT = {
    "titles": ["推荐标题", "备选标题"],
    "copywriting": "正文文案第一段\n第二段",
    "tags": ["穿搭", "秋季"],
}


def _make_record_with_images(history_service: HistoryService, tmp_path: Path) -> str:
    """建一条带 2 张原图 + 1 张缩略图的完整历史记录，返回 record_id。"""
    record_id = history_service.create_record(
        "测试主题", SAMPLE_OUTLINE, task_id="task_pub_1", content=SAMPLE_CONTENT
    )

    task_dir = tmp_path / "history" / "task_pub_1"
    task_dir.mkdir()
    (task_dir / "0.png").write_bytes(b"png-0")
    (task_dir / "1.png").write_bytes(b"png-1")
    (task_dir / "thumb_0.png").write_bytes(b"thumb")

    history_service.update_record(
        record_id,
        images={"task_id": "task_pub_1", "generated": ["0.png", "1.png"]},
        status="completed",
    )
    return record_id


# ==================== 账号 CRUD ====================

def test_account_crud_full_cycle(client, publish_env):
    # 初始为空
    resp = client.get("/api/publish/accounts")
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "accounts": []}

    # 新建
    resp = client.post("/api/publish/accounts", json={
        "platform": "douyin", "nickname": "我的抖音号", "notes": "主账号",
    })
    assert resp.status_code == 200
    account = resp.get_json()["account"]
    assert len(account["id"]) == 8
    assert account["platform"] == "douyin"
    assert account["nickname"] == "我的抖音号"
    assert account["notes"] == "主账号"
    assert account["created_at"] and account["updated_at"]
    # 绝不出现任何凭证字段
    assert not any(k in account for k in ("password", "cookie", "session", "token"))

    account_id = account["id"]

    # 列表可见
    resp = client.get("/api/publish/accounts")
    accounts = resp.get_json()["accounts"]
    assert [a["id"] for a in accounts] == [account_id]

    # 部分更新：只改昵称与备注，platform 保持不变
    resp = client.put(f"/api/publish/accounts/{account_id}", json={
        "nickname": "新昵称", "notes": "",
    })
    assert resp.status_code == 200
    updated = resp.get_json()["account"]
    assert updated["nickname"] == "新昵称"
    assert updated["notes"] == ""
    assert updated["platform"] == "douyin"

    # 改平台
    resp = client.put(f"/api/publish/accounts/{account_id}", json={
        "platform": "kuaishou",
    })
    assert resp.status_code == 200
    assert resp.get_json()["account"]["platform"] == "kuaishou"

    # 删除
    resp = client.delete(f"/api/publish/accounts/{account_id}")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    resp = client.get("/api/publish/accounts")
    assert resp.get_json()["accounts"] == []


def test_create_account_rejects_bad_platform(client, publish_env):
    resp = client.post("/api/publish/accounts", json={
        "platform": "weibo", "nickname": "微博号",
    })
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_create_account_rejects_empty_nickname(client, publish_env):
    for nickname in ("", "   ", None):
        resp = client.post("/api/publish/accounts", json={
            "platform": "xiaohongshu", "nickname": nickname,
        })
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False


def test_update_account_validates_fields(client, publish_env):
    account_id = client.post("/api/publish/accounts", json={
        "platform": "bilibili", "nickname": "B站号",
    }).get_json()["account"]["id"]

    resp = client.put(f"/api/publish/accounts/{account_id}", json={"nickname": " "})
    assert resp.status_code == 400

    resp = client.put(f"/api/publish/accounts/{account_id}", json={"platform": "youtube"})
    assert resp.status_code == 400

    # 校验失败不落库
    accounts = client.get("/api/publish/accounts").get_json()["accounts"]
    assert accounts[0]["nickname"] == "B站号"
    assert accounts[0]["platform"] == "bilibili"


def test_update_and_delete_missing_account_returns_404(client, publish_env):
    resp = client.put("/api/publish/accounts/deadbeef", json={"nickname": "x"})
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False

    resp = client.delete("/api/publish/accounts/deadbeef")
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


# ==================== 平台清单 ====================

def test_platforms_endpoint_returns_whitelist(client, publish_env):
    resp = client.get("/api/publish/platforms")
    assert resp.status_code == 200
    platforms = resp.get_json()["platforms"]

    keys = {p["key"] for p in platforms}
    assert keys == {
        "xiaohongshu", "douyin", "shipinhao",
        "bilibili", "gongzhonghao", "kuaishou",
    }
    by_key = {p["key"]: p for p in platforms}
    assert by_key["xiaohongshu"]["label"] == "小红书"
    assert by_key["xiaohongshu"]["creator_url"] == \
        "https://creator.xiaohongshu.com/publish/publish"
    assert all(p["creator_url"].startswith("https://") for p in platforms)


# ==================== 一键备料 ====================

def test_prepare_missing_record_returns_404(client, publish_env):
    resp = client.post("/api/publish/prepare", json={"record_id": "no-such-record"})
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_prepare_requires_record_id(client, publish_env):
    resp = client.post("/api/publish/prepare", json={})
    assert resp.status_code == 400


def test_prepare_record_without_images_returns_400(client, publish_env):
    _, history_service = publish_env
    record_id = history_service.create_record("无图主题", SAMPLE_OUTLINE)

    resp = client.post("/api/publish/prepare", json={"record_id": record_id})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "该作品还没有生成图片" in data["error"]["detail"]


def test_prepare_exports_images_and_publish_text(client, publish_env):
    tmp_path, history_service = publish_env
    record_id = _make_record_with_images(history_service, tmp_path)

    resp = client.post("/api/publish/prepare", json={"record_id": record_id})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True

    # 导出目录必须在 tmp_path/publish_exports 下，且以 record_id 开头
    folder = Path(data["folder"])
    assert folder.is_dir()
    assert folder.parent == (tmp_path / "publish_exports").resolve()
    assert folder.name.startswith(f"{record_id}_")

    # 文件清单：2 张原图 + 发布文案.txt，缩略图被跳过
    assert data["files"] == ["page_1.png", "page_2.png", "发布文案.txt"]
    assert (folder / "page_1.png").read_bytes() == b"png-0"
    assert (folder / "page_2.png").read_bytes() == b"png-1"
    assert not list(folder.glob("thumb_*"))

    # 发布文案.txt 内容与 zip 发布包同源
    text = (folder / "发布文案.txt").read_text(encoding="utf-8")
    # 首行是 AIGC 标注合规提醒（B1 合规护栏）
    assert "AI 辅助生成" in text.splitlines()[0]
    assert "AI 内容声明" in text.splitlines()[0]
    assert "【标题候选】\n推荐标题\n备选标题" in text
    assert "【正文文案】\n正文文案第一段\n第二段" in text
    assert "【标签】\n#穿搭 #秋季" in text
    assert "【大纲原文】\n原始大纲文本" in text

    # 结构化文案回传，供前端复制
    assert data["text"] == {
        "titles": ["推荐标题", "备选标题"],
        "copywriting": "正文文案第一段\n第二段",
        "tags": ["穿搭", "秋季"],
    }


def test_prepare_without_content_skips_text_sections(client, publish_env):
    """只有大纲无 content 的旧记录：仍导出图片，文案只含大纲小节"""
    tmp_path, history_service = publish_env
    record_id = history_service.create_record(
        "旧记录", SAMPLE_OUTLINE, task_id="task_pub_2"
    )
    task_dir = tmp_path / "history" / "task_pub_2"
    task_dir.mkdir()
    (task_dir / "0.png").write_bytes(b"png-0")
    history_service.update_record(
        record_id, images={"task_id": "task_pub_2", "generated": ["0.png"]}
    )

    resp = client.post("/api/publish/prepare", json={"record_id": record_id})
    assert resp.status_code == 200
    data = resp.get_json()

    text = (Path(data["folder"]) / "发布文案.txt").read_text(encoding="utf-8")
    assert "【标题候选】" not in text
    assert "【大纲原文】\n原始大纲文本" in text
    assert data["text"] == {"titles": [], "copywriting": "", "tags": []}


# ==================== 打开文件夹（安全校验） ====================

def test_open_folder_rejects_paths_outside_exports(client, publish_env):
    tmp_path, _ = publish_env

    bad_paths = [
        "/etc",
        "/tmp",
        str(tmp_path),  # 数据根目录本身也不行
        str(tmp_path / "history"),
        str(tmp_path / "publish_exports" / ".." / "history"),  # ../ 穿越
        "",
    ]
    for path in bad_paths:
        resp = client.post("/api/publish/open-folder", json={"path": path})
        assert resp.status_code == 400, f"应拒绝路径: {path!r}"
        assert resp.get_json()["success"] is False


def test_open_folder_missing_dir_inside_exports_is_soft_failure(client, publish_env):
    """导出目录内但不存在的文件夹：不抛异常，success:false + 提示"""
    tmp_path, _ = publish_env
    path = str(tmp_path / "publish_exports" / "not_exist_folder")

    resp = client.post("/api/publish/open-folder", json={"path": path})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is False
    assert data["message"]
