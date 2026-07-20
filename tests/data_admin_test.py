"""
数据管理中心测试：

- 备份导出 zip 结构与 manifest v2（数据目录/文件/前端 localStorage/
  逐文件 sha256/空目录列表）
- include_keys 缺省不含 providers 配置，显式开启才带
- 导入的 zip slip 防护（../ 与绝对路径均 400）
- 导入前自动备份 .pre_import_backup_* 存在且内容完整
- 导入摘要（restored/skipped/local_storage 回传）
- 非法 zip / 缺 manifest / 超大文件 / 条目数超限 / 解压总大小超限返回 400
- v2 导入按注册表全量替换（源端已删除的数据不复活）；v1 旧包按宽松语义兼容导入
- 篡改校验和被拒且现有数据不被修改
- 诊断包 zip：含日志与 diagnostics.json，绝不含任何 API Key 字符串
"""
import hashlib
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
    # 空目录：v2 备份必须显式记录并在恢复时重建
    (tmp_path / "history" / "task_empty").mkdir()

    (tmp_path / "brand_kits").mkdir()
    (tmp_path / "brand_kits" / "brand.json").write_text("{}", encoding="utf-8")

    (tmp_path / "content_calendar").mkdir()
    (tmp_path / "content_calendar" / "plan.json").write_text("{}", encoding="utf-8")

    (tmp_path / "analytics_data").mkdir()
    (tmp_path / "analytics_data" / "records.json").write_text("[]", encoding="utf-8")

    (tmp_path / "idea_library").mkdir()
    (tmp_path / "idea_library" / "ideas.json").write_text(
        json.dumps({"ideas": [{"id": "idea_1"}]}), encoding="utf-8"
    )

    (tmp_path / "clips").mkdir()
    (tmp_path / "clips" / "clips.json").write_text(
        json.dumps({"clips": [{"id": "clip_1"}]}), encoding="utf-8"
    )

    (tmp_path / "custom_prompts").mkdir()
    (tmp_path / "custom_prompts" / "image_prompt.txt").write_text(
        "自定义提示词", encoding="utf-8"
    )

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
    # 历史上漏备份的三个 store 必须进包
    assert "idea_library/ideas.json" in names
    assert "clips/clips.json" in names
    assert "custom_prompts/image_prompt.txt" in names
    assert "publish_accounts.json" in names
    # logs 不进备份包（属诊断包范畴）
    assert not any(n.startswith("logs/") for n in names)

    manifest = json.loads(_read_zip_entry(buffer, "manifest.json"))
    assert manifest["app"] == "RedInk"
    assert manifest["format"] == 2
    assert manifest["version"]
    assert manifest["exported_at"]
    assert manifest["platform"]["system"]
    assert manifest["include_keys"] is False
    assert "history" in manifest["items"]
    assert "idea_library" in manifest["items"]
    assert "publish_accounts.json" in manifest["items"]


def test_export_manifest_v2_records_checksums_and_empty_dirs(data_root):
    buffer = build_export_zip(data_root=data_root)
    manifest = json.loads(_read_zip_entry(buffer, "manifest.json"))

    files = {f["path"]: f for f in manifest["files"]}
    # zip 内每个数据文件都有逐文件记录（manifest.json 自身除外）
    buffer.seek(0)
    with zipfile.ZipFile(buffer) as zf:
        data_entries = [
            n for n in zf.namelist()
            if n != "manifest.json" and not n.endswith("/")
        ]
    assert set(files) == set(data_entries)

    entry = files["history/task_1/0.png"]
    assert entry["size"] == len(b"png-data")
    assert entry["sha256"] == hashlib.sha256(b"png-data").hexdigest()

    # 空目录被显式记录
    assert "history/task_empty" in manifest["empty_dirs"]


def test_export_includes_existing_but_empty_toplevel_dir(tmp_path):
    (tmp_path / "clips").mkdir()  # 存在但为空
    buffer = build_export_zip(data_root=tmp_path)
    manifest = json.loads(_read_zip_entry(buffer, "manifest.json"))
    assert "clips" in manifest["empty_dirs"]
    assert "clips" in manifest["items"]


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

# 注册表内的全部 core_data 资产（用于快照对比）
_CORE_ASSETS = (
    "history", "brand_kits", "content_calendar", "analytics_data",
    "idea_library", "clips", "custom_prompts", "publish_accounts.json",
)


def _make_backup_zip(entries: dict, manifest: dict = None) -> io.BytesIO:
    """构造一个测试备份 zip；manifest=None 时写入合法 v1 manifest"""
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


def _tamper_zip_entry(buffer: io.BytesIO, name: str, new_bytes: bytes) -> io.BytesIO:
    """重建 zip 并替换指定 entry 的内容（manifest 保持原样，用于模拟篡改）"""
    buffer.seek(0)
    out = io.BytesIO()
    with zipfile.ZipFile(buffer) as src, zipfile.ZipFile(out, "w") as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == name:
                data = new_bytes
            dst.writestr(info.filename, data)
    out.seek(0)
    return out


def _snapshot_files(root: Path) -> dict:
    """root 下全部文件的 相对路径 -> 内容 快照（含隐藏目录）"""
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _snapshot_core_assets(root: Path) -> dict:
    """仅核心数据资产的 相对路径 -> 内容 快照"""
    snap = {}
    for name in _CORE_ASSETS:
        path = root / name
        if path.is_file():
            snap[name] = path.read_bytes()
        elif path.is_dir():
            for file_path in sorted(path.rglob("*")):
                if file_path.is_file():
                    snap[file_path.relative_to(root).as_posix()] = file_path.read_bytes()
    return snap


def test_import_full_asset_roundtrip_file_by_file(data_root, tmp_path_factory):
    """全资产往返：导出 → 新目录导入 → 逐文件一致（含空目录）"""
    exported = build_export_zip(data_root=data_root)

    target_root = tmp_path_factory.mktemp("fresh_root")
    exported.seek(0)
    summary = import_backup_zip(io.BytesIO(exported.read()), data_root=target_root)

    assert summary["success"] is True
    assert _snapshot_core_assets(target_root) == _snapshot_core_assets(data_root)
    # 空目录被恢复
    assert (target_root / "history" / "task_empty").is_dir()
    for name in ("idea_library", "clips", "custom_prompts"):
        assert name in summary["restored"]


def test_import_v2_does_not_resurrect_deleted_assets(data_root, tmp_path_factory):
    """源端已删除（备份里没有）的核心资产，导入后目标端旧数据不复活"""
    source_root = tmp_path_factory.mktemp("source_root")
    (source_root / "history").mkdir()
    (source_root / "history" / "index.json").write_text(
        json.dumps({"records": []}), encoding="utf-8"
    )
    # 源端没有 clips/idea_library/custom_prompts/publish_accounts.json

    exported = build_export_zip(data_root=source_root)
    exported.seek(0)
    summary = import_backup_zip(io.BytesIO(exported.read()), data_root=data_root)

    assert summary["success"] is True
    # 目标端旧数据不得复活
    assert not (data_root / "clips" / "clips.json").exists()
    assert not (data_root / "idea_library" / "ideas.json").exists()
    assert not (data_root / "custom_prompts" / "image_prompt.txt").exists()
    assert not (data_root / "publish_accounts.json").exists()
    assert "clips" in summary["removed"]
    # 备份里有的正常恢复
    assert (data_root / "history" / "index.json").exists()
    # config_with_secrets 不属于全量替换范围：包内没有则保持原样
    assert (data_root / "text_providers.yaml").exists()


def test_import_v2_overwrites_config_only_when_present(data_root, tmp_path_factory):
    """include_keys 备份包内含 providers 配置时才覆盖目标端配置"""
    source_root = tmp_path_factory.mktemp("cfg_source")
    (source_root / "history").mkdir()
    (source_root / "history" / "index.json").write_text("{}", encoding="utf-8")
    (source_root / "text_providers.yaml").write_text(
        "active_provider: from_backup\n", encoding="utf-8"
    )
    (source_root / "image_providers.yaml").write_text(
        "active_provider: from_backup_img\n", encoding="utf-8"
    )

    exported = build_export_zip(include_keys=True, data_root=source_root)
    exported.seek(0)
    import_backup_zip(io.BytesIO(exported.read()), data_root=data_root)

    assert (data_root / "text_providers.yaml").read_text(encoding="utf-8") \
        == "active_provider: from_backup\n"
    assert (data_root / "image_providers.yaml").read_text(encoding="utf-8") \
        == "active_provider: from_backup_img\n"


def test_import_rejects_tampered_checksum_without_touching_data(data_root, tmp_path_factory):
    """篡改校验和被拒，且目标端现有数据一个字节都不被修改"""
    source_root = tmp_path_factory.mktemp("tamper_source")
    (source_root / "history").mkdir()
    (source_root / "history" / "index.json").write_text(
        json.dumps({"records": ["genuine"]}), encoding="utf-8"
    )
    exported = build_export_zip(data_root=source_root)
    tampered = _tamper_zip_entry(
        exported, "history/index.json", b'{"records": ["EVIL"]}'
    )

    before = _snapshot_files(data_root)
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(tampered, data_root=data_root)

    assert exc_info.value.app_error.status == 400
    # 现有数据未被修改，也没有留下预备份/暂存目录
    assert _snapshot_files(data_root) == before
    assert not list(data_root.glob(".pre_import_backup_*"))
    assert not list(data_root.glob(".import_staging_*"))


def test_import_v2_rejects_zip_slip(data_root):
    evil = b"pwned"
    manifest = {
        "app": "RedInk", "format": 2, "version": "0.1.0",
        "files": [{
            "path": "history/../../evil.txt",
            "size": len(evil),
            "sha256": hashlib.sha256(evil).hexdigest(),
        }],
        "empty_dirs": [],
    }
    backup = _make_backup_zip({"history/../../evil.txt": evil}, manifest=manifest)
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(backup, data_root=data_root)
    assert exc_info.value.app_error.status == 400
    assert not (data_root.parent / "evil.txt").exists()
    assert not list(data_root.glob(".pre_import_backup_*"))
    assert not list(data_root.glob(".import_staging_*"))


def test_import_v2_rejects_escaping_empty_dir(data_root):
    manifest = {
        "app": "RedInk", "format": 2, "version": "0.1.0",
        "files": [],
        "empty_dirs": ["history/../../evil_dir"],
    }
    backup = _make_backup_zip({}, manifest=manifest)
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(backup, data_root=data_root)
    assert exc_info.value.app_error.status == 400
    assert not (data_root.parent / "evil_dir").exists()


def test_import_v2_rejects_empty_dir_through_file_as_400(data_root):
    """empty_dirs 指向包内文件内部时必须转 400（而非 mkdir 抛 500），数据零改动"""
    content = json.dumps({"records": []}).encode("utf-8")
    manifest = {
        "app": "RedInk", "format": 2, "version": "0.1.0",
        "files": [{
            "path": "history/index.json",
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }],
        "empty_dirs": ["history/index.json/oops"],
    }
    backup = _make_backup_zip({"history/index.json": content}, manifest=manifest)

    before = _snapshot_files(data_root)
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(backup, data_root=data_root)

    assert exc_info.value.app_error.status == 400
    assert _snapshot_files(data_root) == before
    assert not list(data_root.glob(".pre_import_backup_*"))
    assert not list(data_root.glob(".import_staging_*"))


def test_import_rejects_too_many_entries(data_root, monkeypatch):
    monkeypatch.setattr(data_admin, "MAX_IMPORT_ENTRIES", 3)
    exported = build_export_zip(data_root=data_root)
    exported.seek(0)
    before = _snapshot_files(data_root)
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(io.BytesIO(exported.read()), data_root=data_root)
    assert exc_info.value.app_error.status == 400
    assert _snapshot_files(data_root) == before


def test_import_rejects_uncompressed_size_overflow(data_root, monkeypatch):
    monkeypatch.setattr(data_admin, "MAX_IMPORT_UNCOMPRESSED_SIZE", 4)
    exported = build_export_zip(data_root=data_root)
    exported.seek(0)
    before = _snapshot_files(data_root)
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(io.BytesIO(exported.read()), data_root=data_root)
    assert exc_info.value.app_error.status == 400
    assert _snapshot_files(data_root) == before


def test_import_rejects_oversized_manifest_before_parsing(data_root, monkeypatch):
    """manifest.json 声明大小超过单项上限：在解压/解析它之前就被 400 拒绝"""
    monkeypatch.setattr(data_admin, "MAX_META_ENTRY_SIZE", 64)
    manifest = {"app": "RedInk", "format": 1, "version": "0.1.0", "pad": "x" * 200}
    backup = _make_backup_zip({"history/index.json": "{}"}, manifest=manifest)

    before = _snapshot_files(data_root)
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(backup, data_root=data_root)

    assert exc_info.value.app_error.status == 400
    # 必须是"大小超限"错误而不是解析类错误——证明没有先解压再检查
    assert "manifest.json" in exc_info.value.app_error.detail
    assert "上限" in exc_info.value.app_error.detail
    assert _snapshot_files(data_root) == before
    assert not list(data_root.glob(".pre_import_backup_*"))
    assert not list(data_root.glob(".import_staging_*"))


def test_import_rejects_oversized_local_storage_declaration(data_root, monkeypatch):
    """frontend/local_storage.json 声明大小超过单项上限：读取前即 400 拒绝"""
    # 上限设为放得下 manifest、放不下 local_storage 的值
    monkeypatch.setattr(data_admin, "MAX_META_ENTRY_SIZE", 128)
    backup = _make_backup_zip({
        "history/index.json": "{}",
        "frontend/local_storage.json": json.dumps({"pad": "x" * 500}),
    })

    before = _snapshot_files(data_root)
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(backup, data_root=data_root)

    assert exc_info.value.app_error.status == 400
    assert "local_storage.json" in exc_info.value.app_error.detail
    assert "上限" in exc_info.value.app_error.detail
    assert _snapshot_files(data_root) == before
    assert not list(data_root.glob(".pre_import_backup_*"))


def test_import_entry_limits_checked_before_manifest(data_root, monkeypatch):
    """条目数/声明总大小检查必须先于 manifest 读取（防炸弹绕过）"""
    monkeypatch.setattr(data_admin, "MAX_IMPORT_ENTRIES", 3)
    # 连 manifest 都没有的 5 条目包：应报"条目数超限"而不是"缺少 manifest"
    backup = _make_backup_zip(
        {f"history/f{i}.json": "{}" for i in range(5)},
        manifest=False,
    )
    with pytest.raises(AppErrorException) as exc_info:
        import_backup_zip(backup, data_root=data_root)
    assert exc_info.value.app_error.status == 400
    assert "条目数" in exc_info.value.app_error.detail


def test_import_v1_legacy_zip_keeps_lenient_semantics(data_root):
    """v1 旧包仍可导入：只替换包内出现的顶层目录，其余资产保持不动"""
    backup = _make_backup_zip(
        {"history/index.json": json.dumps({"records": ["from_v1"]})},
        manifest={"app": "RedInk", "format": 1, "version": "0.0.9"},
    )
    summary = import_backup_zip(backup, data_root=data_root)

    assert summary["success"] is True
    assert summary["restored"] == ["history"]
    new_index = json.loads(
        (data_root / "history" / "index.json").read_text(encoding="utf-8")
    )
    assert new_index["records"] == ["from_v1"]
    # v1 宽松语义：包里没有的资产不被清除
    assert (data_root / "clips" / "clips.json").exists()
    assert (data_root / "idea_library" / "ideas.json").exists()
    assert (data_root / "publish_accounts.json").exists()


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
