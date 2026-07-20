"""
数据管理中心测试：

- 备份导出 zip 结构与 manifest（数据目录/文件/前端 localStorage）
- include_keys 缺省不含 providers 配置，显式开启才带
- 导入的 zip slip 防护（../ 与绝对路径均 400）
- 导入前自动备份 .pre_import_backup_* 存在且内容完整
- 导入摘要（restored/skipped/local_storage 回传）
- 非法 zip / 缺 manifest / 超大文件返回 400
- 诊断包 zip：含日志与 diagnostics.json，绝不含任何 API Key 字符串
"""
import io
import json
import zipfile
from pathlib import Path

import pytest
import yaml

from backend.services import data_admin
from backend.services.data_admin import (
    build_diagnostics_zip,
    build_export_zip,
    import_backup_zip,
)
from backend.errors import AppErrorException


FAKE_TEXT_KEY = "sk-text-SECRET-abc123"
FAKE_IMAGE_KEY = "sk-image-SECRET-xyz789"


@pytest.fixture
def data_root(tmp_path):
    """构造一个带全套数据的临时 data_root"""
    (tmp_path / "history").mkdir()
    (tmp_path / "history" / "index.json").write_text(
        json.dumps({"records": []}), encoding="utf-8"
    )
    (tmp_path / "history" / "task_1").mkdir()
    (tmp_path / "history" / "task_1" / "0.png").write_bytes(b"png-data")

    (tmp_path / "brand_kits").mkdir()
    (tmp_path / "brand_kits" / "brand.json").write_text("{}", encoding="utf-8")

    (tmp_path / "content_calendar").mkdir()
    (tmp_path / "content_calendar" / "plan.json").write_text("{}", encoding="utf-8")

    (tmp_path / "analytics_data").mkdir()
    (tmp_path / "analytics_data" / "records.json").write_text("[]", encoding="utf-8")

    (tmp_path / "publish_accounts.json").write_text(
        json.dumps({"accounts": []}), encoding="utf-8"
    )

    (tmp_path / "text_providers.yaml").write_text(yaml.dump({
        "active_provider": "prov_a",
        "providers": {
            "prov_a": {
                "type": "openai_compatible",
                "api_key": FAKE_TEXT_KEY,
                "base_url": "https://api.text-example.com/v1/chat",
                "model": "m1",
            },
        },
    }), encoding="utf-8")
    (tmp_path / "image_providers.yaml").write_text(yaml.dump({
        "active_provider": "prov_b",
        "providers": {
            "prov_b": {
                "type": "image_api",
                "api_key": FAKE_IMAGE_KEY,
                "base_url": "https://api.image-example.com",
            },
        },
    }), encoding="utf-8")

    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "redink.log").write_text("启动完成\n", encoding="utf-8")
    return tmp_path


def _zip_names(buffer) -> list:
    with zipfile.ZipFile(buffer) as zf:
        return zf.namelist()


def _read_zip_entry(buffer, name: str) -> bytes:
    buffer.seek(0)
    with zipfile.ZipFile(buffer) as zf:
        return zf.read(name)


# ==================== 备份导出 ====================

def test_export_zip_structure_and_manifest(data_root):
    buffer = build_export_zip(data_root=data_root)
    names = _zip_names(buffer)

    assert "manifest.json" in names
    assert "history/index.json" in names
    assert "history/task_1/0.png" in names
    assert "brand_kits/brand.json" in names
    assert "content_calendar/plan.json" in names
    assert "analytics_data/records.json" in names
    assert "publish_accounts.json" in names
    # logs 不进备份包（属诊断包范畴）
    assert not any(n.startswith("logs/") for n in names)

    manifest = json.loads(_read_zip_entry(buffer, "manifest.json"))
    assert manifest["app"] == "RedInk"
    assert manifest["format"] == 1
    assert manifest["version"]
    assert manifest["exported_at"]
    assert manifest["platform"]["system"]
    assert manifest["include_keys"] is False
    assert "history" in manifest["items"]
    assert "publish_accounts.json" in manifest["items"]


def test_export_excludes_provider_keys_by_default(data_root):
    buffer = build_export_zip(data_root=data_root)
    names = _zip_names(buffer)
    assert "text_providers.yaml" not in names
    assert "image_providers.yaml" not in names

    # 整包字节里不出现任何 key 字符串
    buffer.seek(0)
    with zipfile.ZipFile(buffer) as zf:
        blob = b"".join(zf.read(n) for n in zf.namelist())
    assert FAKE_TEXT_KEY.encode() not in blob
    assert FAKE_IMAGE_KEY.encode() not in blob


def test_export_includes_provider_keys_when_opted_in(data_root):
    buffer = build_export_zip(include_keys=True, data_root=data_root)
    names = _zip_names(buffer)
    assert "text_providers.yaml" in names
    assert "image_providers.yaml" in names

    manifest = json.loads(_read_zip_entry(buffer, "manifest.json"))
    assert manifest["include_keys"] is True
    assert "text_providers.yaml" in manifest["items"]


def test_export_embeds_frontend_local_storage(data_root):
    local = {"redink_custom_styles": "[]", "redink_export_watermark": "{}"}
    buffer = build_export_zip(local_storage=local, data_root=data_root)

    stored = json.loads(_read_zip_entry(buffer, "frontend/local_storage.json"))
    assert stored == local

    manifest = json.loads(_read_zip_entry(buffer, "manifest.json"))
    assert "frontend/local_storage.json" in manifest["items"]


# ==================== 备份导入 ====================

def _make_backup_zip(entries: dict, manifest: dict = None) -> io.BytesIO:
    """构造一个测试备份 zip；manifest=None 时写入合法 manifest"""
    if manifest is None:
        manifest = {"app": "RedInk", "format": 1, "version": "0.1.0"}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
        if manifest is not False:
            zf.writestr("manifest.json", json.dumps(manifest))
    buffer.seek(0)
    return buffer


def test_import_roundtrip_restores_data(data_root, tmp_path_factory):
    exported = build_export_zip(
        local_storage={"redink_custom_styles": "[1]"}, data_root=data_root
    )

    target_root = tmp_path_factory.mktemp("target_root")
    (target_root / "history").mkdir()
    (target_root / "history" / "old.json").write_text("old", encoding="utf-8")

    exported.seek(0)
    summary = import_backup_zip(io.BytesIO(exported.read()), data_root=target_root)

    assert summary["success"] is True
    assert (target_root / "history" / "index.json").exists()
    assert (target_root / "history" / "task_1" / "0.png").read_bytes() == b"png-data"
    assert (target_root / "publish_accounts.json").exists()
    # 目录被整体替换：旧文件不残留
    assert not (target_root / "history" / "old.json").exists()
    # localStorage 数据回传给前端恢复
    assert summary["local_storage"] == {"redink_custom_styles": "[1]"}
    assert "history" in summary["restored"]


def test_import_creates_pre_import_backup(data_root):
    original_index = (data_root / "history" / "index.json").read_text(encoding="utf-8")
    backup = _make_backup_zip({
        "history/index.json": json.dumps({"records": [{"id": "new"}]}),
    })

    summary = import_backup_zip(backup, data_root=data_root)

    backup_dir = data_root / summary["pre_import_backup"]
    assert backup_dir.name.startswith(".pre_import_backup_")
    assert backup_dir.is_dir()
    # 覆盖前的现有数据被完整备份
    assert (backup_dir / "history" / "index.json").read_text(encoding="utf-8") == original_index
    assert (backup_dir / "publish_accounts.json").exists()
    assert (backup_dir / "text_providers.yaml").exists()
    # 数据已被 zip 内容覆盖
    new_index = json.loads((data_root / "history" / "index.json").read_text(encoding="utf-8"))
    assert new_index["records"][0]["id"] == "new"


def test_import_rejects_zip_slip_dotdot(data_root):
    backup = _make_backup_zip({"history/../../evil.txt": "pwned"})
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(backup, data_root=data_root)
    assert exc_info.value.app_error.status == 400
    assert not (data_root.parent / "evil.txt").exists()
    # 校验先于写入：不应产生导入前备份目录
    assert not list(data_root.glob(".pre_import_backup_*"))


def test_import_rejects_absolute_path_entry(data_root):
    backup = _make_backup_zip({"/tmp/evil.txt": "pwned"})
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(backup, data_root=data_root)
    assert exc_info.value.app_error.status == 400


def test_import_skips_unknown_toplevel_entries(data_root):
    backup = _make_backup_zip({
        "history/index.json": "{}",
        "unknown_dir/file.txt": "x",
    })
    summary = import_backup_zip(backup, data_root=data_root)
    assert summary["skipped"] == ["unknown_dir/file.txt"]
    assert not (data_root / "unknown_dir").exists()


def test_import_rejects_non_zip(data_root):
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(io.BytesIO(b"not a zip"), data_root=data_root)
    assert exc_info.value.app_error.status == 400


def test_import_rejects_missing_manifest(data_root):
    backup = _make_backup_zip({"history/index.json": "{}"}, manifest=False)
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(backup, data_root=data_root)
    assert exc_info.value.app_error.status == 400
    assert "manifest" in exc_info.value.app_error.detail


def test_import_rejects_foreign_manifest(data_root):
    backup = _make_backup_zip(
        {"history/index.json": "{}"},
        manifest={"app": "Other", "format": 1},
    )
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(backup, data_root=data_root)
    assert exc_info.value.app_error.status == 400


def test_import_rejects_oversized_stream(data_root, monkeypatch):
    monkeypatch.setattr(data_admin, "MAX_IMPORT_SIZE", 1024)
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(io.BytesIO(b"a" * 2048), data_root=data_root)
    assert exc_info.value.app_error.status == 400
    assert "大小上限" in exc_info.value.app_error.detail


# ==================== 诊断包 ====================

def test_diagnostics_zip_contains_logs_and_report(data_root):
    buffer = build_diagnostics_zip(data_root=data_root)
    names = _zip_names(buffer)
    assert "logs/redink.log" in names
    assert "diagnostics.json" in names

    report = json.loads(_read_zip_entry(buffer, "diagnostics.json"))
    assert report["app"] == "RedInk"
    assert report["version"]
    assert report["platform"]["system"]

    text = report["providers"]["text"]
    assert text["exists"] is True
    assert text["active_provider"] == "prov_a"
    assert text["providers"]["prov_a"]["has_api_key"] is True
    # 只有域名，不含路径
    assert text["providers"]["prov_a"]["base_url_host"] == "api.text-example.com"

    image = report["providers"]["image"]
    assert image["providers"]["prov_b"]["has_api_key"] is True
    assert image["providers"]["prov_b"]["base_url_host"] == "api.image-example.com"


def test_diagnostics_zip_never_contains_api_keys(data_root):
    buffer = build_diagnostics_zip(data_root=data_root)
    buffer.seek(0)
    with zipfile.ZipFile(buffer) as zf:
        blob = b"".join(zf.read(n) for n in zf.namelist())
    assert FAKE_TEXT_KEY.encode() not in blob
    assert FAKE_IMAGE_KEY.encode() not in blob
    # 不存在原始 api_key 字段（脱敏报告里只有 has_api_key 布尔）
    assert b'"api_key"' not in blob
    assert b"sk-" not in blob


def test_diagnostics_handles_missing_configs(tmp_path):
    buffer = build_diagnostics_zip(data_root=tmp_path)
    report = json.loads(_read_zip_entry(buffer, "diagnostics.json"))
    assert report["providers"]["text"] == {"exists": False}


# ==================== 路由层 ====================

@pytest.fixture
def patched_root(data_root, monkeypatch):
    monkeypatch.setattr(data_admin, "get_data_root", lambda: data_root)
    return data_root


def test_export_endpoint_returns_zip(client, patched_root):
    response = client.get("/api/data/export")
    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    names = _zip_names(io.BytesIO(response.data))
    assert "manifest.json" in names
    assert "text_providers.yaml" not in names


def test_export_endpoint_include_keys_and_local_storage(client, patched_root):
    response = client.post(
        "/api/data/export?include_keys=true",
        json={"local_storage": {"redink_custom_styles": "[]", "bad": 123}},
    )
    assert response.status_code == 200
    buffer = io.BytesIO(response.data)
    names = _zip_names(buffer)
    assert "text_providers.yaml" in names
    stored = json.loads(_read_zip_entry(buffer, "frontend/local_storage.json"))
    # 非字符串值被丢弃
    assert stored == {"redink_custom_styles": "[]"}


def test_import_endpoint_requires_file(client, patched_root):
    response = client.post("/api/data/import", data={})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_REQUEST"


def test_import_endpoint_rejects_zip_slip_with_400(client, patched_root):
    backup = _make_backup_zip({"history/../../evil.txt": "pwned"})
    response = client.post(
        "/api/data/import",
        data={"file": (backup, "backup.zip")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_import_endpoint_happy_path(client, patched_root):
    backup = _make_backup_zip({
        "history/index.json": json.dumps({"records": []}),
        "frontend/local_storage.json": json.dumps({"redink_custom_styles": "[]"}),
    })
    response = client.post(
        "/api/data/import",
        data={"file": (backup, "backup.zip")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["restored"] == ["history"]
    assert data["local_storage"] == {"redink_custom_styles": "[]"}
    assert data["pre_import_backup"].startswith(".pre_import_backup_")


def test_diagnostics_endpoint_returns_zip_without_keys(client, patched_root):
    response = client.get("/api/data/diagnostics")
    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    assert FAKE_TEXT_KEY.encode() not in response.data
    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        blob = b"".join(zf.read(n) for n in zf.namelist())
    assert FAKE_TEXT_KEY.encode() not in blob
    assert FAKE_IMAGE_KEY.encode() not in blob
