"""
数据管理中心服务：一键备份导出 / 导入恢复 / 诊断包导出。

所有用户资产 100% 本地化（history/ brand_kits/ content_calendar/
analytics_data/ publish_accounts.json，路径统一走 backend.paths.get_data_root()），
本模块提供：

- build_export_zip(): 把全部数据目录打成 zip（附 manifest.json）。
  providers 配置（含 API Key）默认不包含，include_keys=True 才带上。
  前端 localStorage 数据（风格模板/拆解历史/水印设置等）由前端收集后
  POST 进来，合入 zip 的 frontend/local_storage.json。
- import_backup_zip(): 校验 manifest 与路径安全（防 zip slip）后恢复数据；
  覆盖前先把现有数据整体备份到 data_root/.pre_import_backup_时间戳/。
- build_diagnostics_zip(): 诊断包（logs/ + 版本/平台信息 + 脱敏 provider
  配置——只有"有无 Key"布尔与 base_url 域名，绝不含 Key 本身）。

安全要点：
- zip slip 防护：每个 entry 的目标路径 resolve() 后必须落在 data_root 内；
- 只恢复白名单内的顶层条目，zip 里的未知路径一律忽略；
- 诊断包对 providers.yaml 全字段白名单脱敏，api_key 永不出包。
"""

import io
import json
import logging
import platform
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional
from urllib.parse import urlsplit

import yaml

from backend.errors import AppError, AppErrorException
from backend.paths import get_data_root, is_frozen

logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"

# manifest 格式版本（导入时校验，未来结构变更时递增并做兼容）
MANIFEST_FORMAT = 1

# 导入 zip 大小上限：500MB
MAX_IMPORT_SIZE = 500 * 1024 * 1024

# 备份包含的顶层数据目录 / 文件（相对 data_root）
DATA_DIRS = ("history", "brand_kits", "content_calendar", "analytics_data")
DATA_FILES = ("publish_accounts.json",)

# providers 配置文件（含 API Key），仅 include_keys=True 时才进备份包
CONFIG_FILES = ("text_providers.yaml", "image_providers.yaml")

# 前端 localStorage 数据在 zip 内的路径
LOCAL_STORAGE_ENTRY = "frontend/local_storage.json"

MANIFEST_ENTRY = "manifest.json"

# 导入时允许恢复的顶层条目（目录名或文件名）
_IMPORT_ALLOWED_TOPLEVEL = set(DATA_DIRS) | set(DATA_FILES) | set(CONFIG_FILES)


def _bad_request(detail: str, suggestion: str = "请检查备份文件后重试。") -> AppErrorException:
    return AppErrorException(AppError(
        code="INVALID_REQUEST",
        title="备份文件不合法",
        detail=detail,
        suggestion=suggestion,
        status=400,
        retryable=False,
    ))


def _platform_info() -> Dict[str, Any]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "frozen": is_frozen(),
    }


# ==================== 备份导出 ====================

def build_export_zip(
    include_keys: bool = False,
    local_storage: Optional[Dict[str, str]] = None,
    data_root: Optional[Path] = None,
) -> BinaryIO:
    """
    把全部用户数据打成 zip。

    Args:
        include_keys: 是否包含 providers 配置（text/image_providers.yaml，
            含 API Key 明文）。默认不包含。
        local_storage: 前端收集的 localStorage 键值（可选），
            写入 zip 的 frontend/local_storage.json。
        data_root: 数据根目录（默认 get_data_root()，测试可注入）。

    Returns:
        可读的二进制文件对象（SpooledTemporaryFile，大备份自动落盘避免
        全量驻留内存），指针已移到开头，可直接交给 send_file 流式下发。
    """
    root = (data_root or get_data_root()).resolve()
    included: List[str] = []

    spool = tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024)
    with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as zf:
        for dir_name in DATA_DIRS:
            dir_path = root / dir_name
            if not dir_path.is_dir():
                continue
            has_content = False
            for file_path in sorted(dir_path.rglob("*")):
                if not file_path.is_file():
                    continue
                # 跳过写入过程中的临时文件
                if file_path.name.startswith(".tmp_"):
                    continue
                zf.write(file_path, file_path.relative_to(root).as_posix())
                has_content = True
            if has_content:
                included.append(dir_name)

        for file_name in DATA_FILES:
            file_path = root / file_name
            if file_path.is_file():
                zf.write(file_path, file_name)
                included.append(file_name)

        if include_keys:
            for file_name in CONFIG_FILES:
                file_path = root / file_name
                if file_path.is_file():
                    zf.write(file_path, file_name)
                    included.append(file_name)

        if local_storage:
            zf.writestr(
                LOCAL_STORAGE_ENTRY,
                json.dumps(local_storage, ensure_ascii=False, indent=2),
            )
            included.append(LOCAL_STORAGE_ENTRY)

        manifest = {
            "app": "RedInk",
            "format": MANIFEST_FORMAT,
            "version": APP_VERSION,
            "exported_at": datetime.now().isoformat(),
            "platform": _platform_info(),
            "include_keys": include_keys,
            "items": included,
        }
        zf.writestr(MANIFEST_ENTRY, json.dumps(manifest, ensure_ascii=False, indent=2))

    spool.seek(0)
    logger.info(f"📦 备份导出完成: 包含 {included}, include_keys={include_keys}")
    return spool


# ==================== 备份导入 ====================

def _validate_entry_path(root: Path, entry_name: str) -> Optional[Path]:
    """
    校验 zip entry 目标路径必须落在 data_root 内（防 zip slip）。

    Returns:
        合法时返回目标绝对路径；entry 为目录项时返回 None。

    Raises:
        AppErrorException: 路径逃逸（绝对路径 / .. / 盘符）时抛 400。
    """
    if entry_name.endswith("/"):
        return None

    raw = Path(entry_name)
    if raw.is_absolute() or ".." in raw.parts:
        raise _bad_request(f"备份包内存在非法路径: {entry_name}")

    target = (root / raw).resolve()
    # resolve() 后逐级校验必须仍在 data_root 内（覆盖符号链接等边界情况）
    if root != target and root not in target.parents:
        raise _bad_request(f"备份包内存在越界路径: {entry_name}")
    return target


def _read_manifest(zf: zipfile.ZipFile) -> Dict[str, Any]:
    if MANIFEST_ENTRY not in zf.namelist():
        raise _bad_request(
            "备份包缺少 manifest.json",
            "请使用 RedInk 设置页「导出备份」生成的 zip 文件。",
        )
    try:
        manifest = json.loads(zf.read(MANIFEST_ENTRY).decode("utf-8"))
    except Exception:
        raise _bad_request("manifest.json 无法解析")
    if not isinstance(manifest, dict) or manifest.get("app") != "RedInk":
        raise _bad_request("manifest.json 不是 RedInk 备份格式")
    fmt = manifest.get("format")
    if not isinstance(fmt, int) or fmt > MANIFEST_FORMAT:
        raise _bad_request(
            f"备份格式版本不支持: {fmt}",
            "该备份由更新版本的 RedInk 导出，请升级应用后再导入。",
        )
    return manifest


def _backup_existing_data(root: Path) -> str:
    """把现有数据目录/文件整体备份到 data_root/.pre_import_backup_时间戳/。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = root / f".pre_import_backup_{timestamp}"
    # 同一秒内重复导入时避免撞名
    suffix = 0
    while backup_dir.exists():
        suffix += 1
        backup_dir = root / f".pre_import_backup_{timestamp}_{suffix}"
    backup_dir.mkdir(parents=True)

    for name in (*DATA_DIRS, *DATA_FILES, *CONFIG_FILES):
        source = root / name
        if source.is_dir():
            shutil.copytree(source, backup_dir / name)
        elif source.is_file():
            shutil.copyfile(source, backup_dir / name)
    return backup_dir.name


def import_backup_zip(
    file_stream: BinaryIO,
    data_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    导入备份 zip 并恢复数据。

    流程：格式/manifest/路径安全校验（全部通过才动数据）→
    现有数据整体备份到 .pre_import_backup_时间戳/ → 覆盖恢复 → 返回摘要。

    Returns:
        摘要 dict：restored（恢复的顶层条目）、skipped（忽略的未知条目）、
        pre_import_backup（自动备份目录名）、local_storage（zip 内的前端
        localStorage 数据，由前端负责写回，没有则为 None）。

    Raises:
        AppErrorException: 非 zip / manifest 非法 / 路径逃逸 / 超限时抛 400。
    """
    root = (data_root or get_data_root()).resolve()

    data = file_stream.read(MAX_IMPORT_SIZE + 1)
    if len(data) > MAX_IMPORT_SIZE:
        raise _bad_request(
            f"备份文件超过大小上限（{MAX_IMPORT_SIZE // (1024 * 1024)}MB）",
            "请确认上传的是 RedInk 备份 zip 文件。",
        )

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise _bad_request("文件不是合法的 zip 格式")

    with zf:
        manifest = _read_manifest(zf)

        # 第一遍：先完成所有 entry 的路径安全校验，任何一条非法都不动现有数据
        plan: List[tuple] = []  # (entry_name, target_path)
        skipped: List[str] = []
        local_storage: Optional[Dict[str, str]] = None

        for info in zf.infolist():
            name = info.filename
            target = _validate_entry_path(root, name)
            if target is None:
                continue  # 目录项
            if name == MANIFEST_ENTRY:
                continue
            if name == LOCAL_STORAGE_ENTRY:
                try:
                    parsed = json.loads(zf.read(info).decode("utf-8"))
                except Exception:
                    raise _bad_request("frontend/local_storage.json 无法解析")
                if isinstance(parsed, dict):
                    local_storage = parsed
                continue
            top_level = Path(name).parts[0]
            if top_level not in _IMPORT_ALLOWED_TOPLEVEL:
                skipped.append(name)
                continue
            plan.append((info, target))

        if not plan and local_storage is None:
            raise _bad_request(
                "备份包内没有可恢复的数据",
                "请使用 RedInk 设置页「导出备份」生成的 zip 文件。",
            )

        # 覆盖前：现有数据整体备份
        pre_import_backup = _backup_existing_data(root)

        # 恢复：zip 中出现的顶层目录先清空再写入，保证与备份内容一致
        restored_toplevel: List[str] = []
        for info, target in plan:
            top_level = Path(info.filename).parts[0]
            if top_level not in restored_toplevel:
                existing = root / top_level
                if top_level in DATA_DIRS and existing.is_dir():
                    shutil.rmtree(existing)
                restored_toplevel.append(top_level)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as source, open(target, "wb") as dest:
                shutil.copyfileobj(source, dest)

    logger.info(
        f"📥 备份导入完成: 恢复 {restored_toplevel}, "
        f"忽略 {len(skipped)} 项, 导入前备份 {pre_import_backup}"
    )
    return {
        "success": True,
        "manifest": {
            "version": manifest.get("version"),
            "exported_at": manifest.get("exported_at"),
            "include_keys": bool(manifest.get("include_keys")),
        },
        "restored": restored_toplevel,
        "skipped": skipped,
        "pre_import_backup": pre_import_backup,
        "local_storage": local_storage,
    }


# ==================== 诊断包 ====================

def _sanitize_provider_config(config_path: Path) -> Dict[str, Any]:
    """
    脱敏 provider 配置：只保留结构信息，绝不输出 api_key。

    每个服务商只导出：type / model / has_api_key（布尔）/
    base_url_host（仅域名，去掉路径与查询参数）。
    """
    if not config_path.is_file():
        return {"exists": False}
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return {"exists": True, "parse_error": type(e).__name__}

    providers = raw.get("providers")
    sanitized: Dict[str, Any] = {}
    if isinstance(providers, dict):
        for name, cfg in providers.items():
            if not isinstance(cfg, dict):
                sanitized[str(name)] = {"invalid": True}
                continue
            base_url = cfg.get("base_url")
            host = ""
            if isinstance(base_url, str) and base_url.strip():
                try:
                    host = urlsplit(base_url.strip()).hostname or ""
                except ValueError:
                    host = ""
            sanitized[str(name)] = {
                "type": str(cfg.get("type", "")),
                "model": str(cfg.get("model", "")),
                "has_api_key": bool(cfg.get("api_key")),
                "base_url_host": host,
            }
    return {
        "exists": True,
        "active_provider": str(raw.get("active_provider", "")),
        "providers": sanitized,
    }


def build_diagnostics_zip(data_root: Optional[Path] = None) -> io.BytesIO:
    """
    构建诊断包 zip：logs/ 下全部日志 + diagnostics.json
    （版本号 / 平台信息 / 脱敏后的 provider 配置）。
    """
    root = (data_root or get_data_root()).resolve()
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        logs_dir = root / "logs"
        if logs_dir.is_dir():
            for log_file in sorted(logs_dir.iterdir()):
                if log_file.is_file():
                    zf.write(log_file, f"logs/{log_file.name}")

        diagnostics = {
            "app": "RedInk",
            "version": APP_VERSION,
            "generated_at": datetime.now().isoformat(),
            "platform": _platform_info(),
            "providers": {
                "text": _sanitize_provider_config(root / "text_providers.yaml"),
                "image": _sanitize_provider_config(root / "image_providers.yaml"),
            },
        }
        zf.writestr(
            "diagnostics.json",
            json.dumps(diagnostics, ensure_ascii=False, indent=2),
        )

    buffer.seek(0)
    logger.info("🩺 诊断包导出完成")
    return buffer
