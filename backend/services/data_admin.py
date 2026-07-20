"""
数据管理中心服务：一键备份导出 / 导入恢复 / 诊断包导出。

所有用户资产 100% 本地化（资产清单唯一真源见 backend/data_catalog.py，
路径统一走 backend.paths.get_data_root()），本模块提供：

- build_export_zip(): 把注册表内全部 core_data 资产打成 zip（附 manifest.json，
  格式 v2：逐文件记录相对路径/字节数/sha256，并显式记录空目录列表）。
  providers 配置（含 API Key）默认不包含，include_keys=True 才带上。
  前端 localStorage 数据（风格模板/拆解历史/水印设置等）由前端收集后
  POST 进来，合入 zip 的 frontend/local_storage.json。
- import_backup_zip(): 校验 manifest 与路径安全（防 zip slip）后恢复数据。
  v2 包先在数据根旁的临时暂存目录完整解压并校验（校验和不符 / 路径逃逸 /
  条目数超限 / 展开后总大小超限均拒绝且不动现有数据），通过后按
  "注册表全量替换"语义提交：core_data 资产在包里没有的也会被清除，
  消除"源端已删除的数据在目标端复活"问题；config_with_secrets 仅当包内
  含有时才覆盖。v1 旧包仍按宽松语义兼容导入（只替换包内出现的顶层目录，
  不做校验和检查）。覆盖前先把现有数据整体备份到
  data_root/.pre_import_backup_时间戳/。
- build_diagnostics_zip(): 诊断包（logs/ + 版本/平台信息 + 脱敏 provider
  配置——只有"有无 Key"布尔与 base_url 域名，绝不含 Key 本身）。

安全要点：
- zip slip 防护：每个 entry 的目标路径 resolve() 后必须落在目标目录内；
- 只恢复白名单（注册表派生）内的顶层条目，zip 里的未知路径一律忽略；
- v2 导入前逐文件校验 sha256 与字节数，任何不符即整体拒绝；
- zip 炸弹防护：条目数与声明总大小上限先于一切解压（含 manifest 读取）
  执行；manifest.json 与 frontend/local_storage.json 这类需全量读入内存的
  元数据条目另设单项声明大小上限；v2 暂存解压时再按实际写出字节数兜底；
- 诊断包对 providers.yaml 全字段白名单脱敏，api_key 永不出包。
"""

import hashlib
import io
import json
import logging
import os
import platform
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import yaml

from backend import data_catalog
from backend.errors import AppError, AppErrorException
from backend.paths import get_data_root, is_frozen

logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"

# manifest 格式版本（导入时校验；v2 起逐文件带 sha256 与空目录列表）
MANIFEST_FORMAT = 2

# 导入 zip 大小上限：500MB
MAX_IMPORT_SIZE = 500 * 1024 * 1024

# 导入 zip 条目数上限（防 zip 炸弹）
MAX_IMPORT_ENTRIES = 50_000

# 导入 zip 解压后总大小上限（防 zip 炸弹）
MAX_IMPORT_UNCOMPRESSED_SIZE = 4 * MAX_IMPORT_SIZE

# 需全量读入内存的元数据条目（manifest.json / frontend/local_storage.json）
# 单项声明大小上限：32MB（防在 zip 内声明超大条目填 DEFLATE 炸弹导致 OOM）
MAX_META_ENTRY_SIZE = 32 * 1024 * 1024

# 流式读写块大小
_CHUNK_SIZE = 1024 * 1024

# 备份包含的顶层数据目录 / 文件（相对 data_root，从注册表派生，禁止硬编码）
DATA_DIRS = data_catalog.core_data_dir_names()
DATA_FILES = data_catalog.core_data_file_names()

# providers 配置文件（含 API Key），仅 include_keys=True 时才进备份包
CONFIG_FILES = data_catalog.config_with_secrets_file_names()

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

def _write_file_to_zip(zf: zipfile.ZipFile, file_path: Path, arcname: str) -> Dict[str, Any]:
    """流式写入单个文件到 zip，同时计算字节数与 sha256（manifest v2 用）。"""
    zinfo = zipfile.ZipInfo.from_file(file_path, arcname)
    zinfo.compress_type = zipfile.ZIP_DEFLATED
    hasher = hashlib.sha256()
    size = 0
    with open(file_path, "rb") as src, zf.open(zinfo, "w") as dest:
        while True:
            chunk = src.read(_CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
            size += len(chunk)
            dest.write(chunk)
    return {"path": arcname, "size": size, "sha256": hasher.hexdigest()}


def build_export_zip(
    include_keys: bool = False,
    local_storage: Optional[Dict[str, str]] = None,
    data_root: Optional[Path] = None,
) -> BinaryIO:
    """
    把全部用户数据打成 zip（manifest 格式 v2）。

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
    file_records: List[Dict[str, Any]] = []
    empty_dirs: List[str] = []

    spool = tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024)
    with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as zf:
        for dir_name in DATA_DIRS:
            dir_path = root / dir_name
            if not dir_path.is_dir():
                continue
            included.append(dir_name)

            exported_rel: List[str] = []
            sub_dirs: List[Path] = [dir_path]
            for path in sorted(dir_path.rglob("*")):
                if path.is_dir():
                    sub_dirs.append(path)
                    continue
                if not path.is_file():
                    continue
                # 跳过写入过程中的临时文件
                if path.name.startswith(".tmp_"):
                    continue
                rel = path.relative_to(root).as_posix()
                file_records.append(_write_file_to_zip(zf, path, rel))
                exported_rel.append(rel)

            # 空目录：子树内没有任何导出文件的目录（含顶层目录自身），
            # 显式记录进 manifest，恢复时重建
            for sub in sorted(sub_dirs):
                sub_rel = sub.relative_to(root).as_posix()
                prefix = sub_rel + "/"
                if not any(rel.startswith(prefix) for rel in exported_rel):
                    empty_dirs.append(sub_rel)

        for file_name in DATA_FILES:
            file_path = root / file_name
            if file_path.is_file():
                file_records.append(_write_file_to_zip(zf, file_path, file_name))
                included.append(file_name)

        if include_keys:
            for file_name in CONFIG_FILES:
                file_path = root / file_name
                if file_path.is_file():
                    file_records.append(_write_file_to_zip(zf, file_path, file_name))
                    included.append(file_name)

        if local_storage:
            payload = json.dumps(local_storage, ensure_ascii=False, indent=2)
            raw = payload.encode("utf-8")
            zf.writestr(LOCAL_STORAGE_ENTRY, raw)
            file_records.append({
                "path": LOCAL_STORAGE_ENTRY,
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
            included.append(LOCAL_STORAGE_ENTRY)

        manifest = {
            "app": "RedInk",
            "format": MANIFEST_FORMAT,
            "version": APP_VERSION,
            "exported_at": datetime.now().isoformat(),
            "platform": _platform_info(),
            "include_keys": include_keys,
            "items": included,
            "files": file_records,
            "empty_dirs": empty_dirs,
        }
        zf.writestr(MANIFEST_ENTRY, json.dumps(manifest, ensure_ascii=False, indent=2))

    spool.seek(0)
    logger.info(f"📦 备份导出完成: 包含 {included}, include_keys={include_keys}")
    return spool


# ==================== 备份导入 ====================

def _validate_entry_path(root: Path, entry_name: str) -> Optional[Path]:
    """
    校验 zip entry 目标路径必须落在 root 内（防 zip slip）。

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
    # resolve() 后逐级校验必须仍在 root 内（覆盖符号链接等边界情况）
    if root != target and root not in target.parents:
        raise _bad_request(f"备份包内存在越界路径: {entry_name}")
    return target


def _read_manifest(zf: zipfile.ZipFile) -> Dict[str, Any]:
    if MANIFEST_ENTRY not in zf.namelist():
        raise _bad_request(
            "备份包缺少 manifest.json",
            "请使用 RedInk 设置页「导出备份」生成的 zip 文件。",
        )
    # 解压前先查声明大小（zipfile 读取时以声明值为准截断，
    # 该检查即内存占用的有效上限），防超大元数据条目 OOM
    if zf.getinfo(MANIFEST_ENTRY).file_size > MAX_META_ENTRY_SIZE:
        raise _bad_request(
            f"manifest.json 声明大小超过单项上限"
            f"（{MAX_META_ENTRY_SIZE // (1024 * 1024)}MB）"
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


def _build_restore_plan(
    zf: zipfile.ZipFile, root: Path
) -> Tuple[List[Tuple[zipfile.ZipInfo, str]], List[str], Optional[Dict[str, str]], Optional[bytes]]:
    """
    第一遍扫描：完成所有 entry 的路径安全校验（任何一条非法都不动现有数据），
    并划分出待恢复清单 / 忽略清单 / 前端 localStorage 数据。

    Returns:
        (plan, skipped, local_storage, local_storage_raw)：
        plan 元素为 (entry_info, 规范化相对路径)。
    """
    plan: List[Tuple[zipfile.ZipInfo, str]] = []
    skipped: List[str] = []
    local_storage: Optional[Dict[str, str]] = None
    local_storage_raw: Optional[bytes] = None

    for info in zf.infolist():
        name = info.filename
        target = _validate_entry_path(root, name)
        if target is None:
            continue  # 目录项
        if name == MANIFEST_ENTRY:
            continue
        if name == LOCAL_STORAGE_ENTRY:
            # 与 manifest 相同：解压前先查声明大小，防超大条目 OOM
            if info.file_size > MAX_META_ENTRY_SIZE:
                raise _bad_request(
                    f"frontend/local_storage.json 声明大小超过单项上限"
                    f"（{MAX_META_ENTRY_SIZE // (1024 * 1024)}MB）"
                )
            local_storage_raw = zf.read(info)
            try:
                parsed = json.loads(local_storage_raw.decode("utf-8"))
            except Exception:
                raise _bad_request("frontend/local_storage.json 无法解析")
            if isinstance(parsed, dict):
                local_storage = parsed
            continue
        rel = Path(name)
        if rel.parts[0] not in _IMPORT_ALLOWED_TOPLEVEL:
            skipped.append(name)
            continue
        plan.append((info, rel.as_posix()))

    return plan, skipped, local_storage, local_storage_raw


def _manifest_summary(manifest: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "version": manifest.get("version"),
        "exported_at": manifest.get("exported_at"),
        "include_keys": bool(manifest.get("include_keys")),
    }


def _import_v1_lenient(
    zf: zipfile.ZipFile,
    root: Path,
    manifest: Dict[str, Any],
    plan: List[Tuple[zipfile.ZipInfo, str]],
    skipped: List[str],
    local_storage: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    """
    v1 旧包导入：维持历史宽松语义——只清空并替换 zip 中出现的顶层目录，
    包里没有的资产保持不动；不做校验和检查。
    """
    if not plan and local_storage is None:
        raise _bad_request(
            "备份包内没有可恢复的数据",
            "请使用 RedInk 设置页「导出备份」生成的 zip 文件。",
        )

    # 覆盖前：现有数据整体备份
    pre_import_backup = _backup_existing_data(root)

    # 恢复：zip 中出现的顶层目录先清空再写入，保证与备份内容一致
    restored_toplevel: List[str] = []
    for info, rel in plan:
        top_level = Path(rel).parts[0]
        if top_level not in restored_toplevel:
            existing = root / top_level
            if top_level in DATA_DIRS and existing.is_dir():
                shutil.rmtree(existing)
            restored_toplevel.append(top_level)
        target = root / Path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as source, open(target, "wb") as dest:
            shutil.copyfileobj(source, dest)

    logger.info(
        f"📥 v1 备份导入完成: 恢复 {restored_toplevel}, "
        f"忽略 {len(skipped)} 项, 导入前备份 {pre_import_backup}"
    )
    return {
        "success": True,
        "manifest": _manifest_summary(manifest),
        "restored": restored_toplevel,
        "removed": [],
        "skipped": skipped,
        "pre_import_backup": pre_import_backup,
        "local_storage": local_storage,
    }


def _parse_v2_file_records(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """解析并校验 v2 manifest 的逐文件清单结构。"""
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise _bad_request("v2 备份缺少逐文件清单（manifest.files）")
    records: Dict[str, Dict[str, Any]] = {}
    for item in raw_files:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or not isinstance(item.get("size"), int)
            or item["size"] < 0
            or not isinstance(item.get("sha256"), str)
        ):
            raise _bad_request("manifest.files 清单结构非法")
        records[item["path"]] = item
    return records


def _parse_v2_empty_dirs(manifest: Dict[str, Any], root: Path) -> Tuple[List[str], List[str]]:
    """
    解析并校验 v2 manifest 的空目录清单。

    Returns:
        (合法且属于注册表内数据目录的相对路径列表, 被忽略的未知顶层条目)。

    Raises:
        AppErrorException: 存在路径逃逸的空目录条目时抛 400。
    """
    raw_dirs = manifest.get("empty_dirs", [])
    if not isinstance(raw_dirs, list):
        raise _bad_request("manifest.empty_dirs 清单结构非法")
    safe_dirs: List[str] = []
    ignored: List[str] = []
    for entry in raw_dirs:
        if not isinstance(entry, str) or not entry.strip():
            raise _bad_request("manifest.empty_dirs 清单结构非法")
        # 与文件 entry 相同的路径逃逸校验
        _validate_entry_path(root, entry.rstrip("/") or entry)
        rel = Path(entry.rstrip("/"))
        if rel.parts and rel.parts[0] in DATA_DIRS:
            safe_dirs.append(rel.as_posix())
        else:
            ignored.append(entry)
    return safe_dirs, ignored


def _verify_v2_completeness(
    records: Dict[str, Dict[str, Any]],
    plan: List[Tuple[zipfile.ZipInfo, str]],
    local_storage_raw: Optional[bytes],
) -> None:
    """
    v2 严格一致性校验：zip 内可恢复的数据文件与 manifest.files 必须一一对应，
    localStorage 条目（若登记）必须存在且校验和一致。
    """
    plan_paths = {rel for _, rel in plan}

    missing_in_manifest = sorted(plan_paths - set(records))
    if missing_in_manifest:
        raise _bad_request(
            f"备份包内存在未在 manifest 登记的文件: {missing_in_manifest[:5]}",
            "备份包可能已被篡改或损坏，请重新导出备份。",
        )

    for path, record in records.items():
        if path == LOCAL_STORAGE_ENTRY:
            if local_storage_raw is None:
                raise _bad_request("manifest 登记的 frontend/local_storage.json 在包内缺失")
            digest = hashlib.sha256(local_storage_raw).hexdigest()
            if len(local_storage_raw) != record["size"] or digest != record["sha256"]:
                raise _bad_request(
                    "frontend/local_storage.json 校验和不符",
                    "备份包可能已被篡改或损坏，请重新导出备份。",
                )
            continue
        if path not in plan_paths:
            raise _bad_request(
                f"manifest 登记的文件在包内缺失或不可恢复: {path}",
                "备份包可能已被篡改，或由包含新数据资产的更新版本导出，"
                "请重新导出备份或升级应用。",
            )

    if local_storage_raw is not None and LOCAL_STORAGE_ENTRY not in records:
        raise _bad_request(
            "备份包内存在未在 manifest 登记的文件: frontend/local_storage.json",
            "备份包可能已被篡改或损坏，请重新导出备份。",
        )


def _extract_and_verify_to_staging(
    zf: zipfile.ZipFile,
    staging: Path,
    plan: List[Tuple[zipfile.ZipInfo, str]],
    records: Dict[str, Dict[str, Any]],
    empty_dirs: List[str],
) -> None:
    """
    把待恢复文件完整解压到暂存目录并逐文件校验 sha256 / 字节数；
    同时以实际写出的字节数兜底解压总大小上限（防声明值造假的 zip 炸弹）。
    任何不符立即抛 400（调用方负责清理暂存目录，现有数据不受影响）。
    """
    extracted_total = 0
    for info, rel in plan:
        record = records[rel]
        target = _validate_entry_path(staging, info.filename)
        if target is None:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        written = 0
        with zf.open(info) as source, open(target, "wb") as dest:
            while True:
                chunk = source.read(_CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                extracted_total += len(chunk)
                if extracted_total > MAX_IMPORT_UNCOMPRESSED_SIZE:
                    raise _bad_request(
                        "备份包解压后总大小超过上限"
                        f"（{MAX_IMPORT_UNCOMPRESSED_SIZE // (1024 * 1024)}MB）"
                    )
                hasher.update(chunk)
                dest.write(chunk)

        if written != record["size"] or hasher.hexdigest() != record["sha256"]:
            raise _bad_request(
                f"文件校验和不符: {rel}",
                "备份包可能已被篡改或损坏，请重新导出备份。",
            )

    for rel in empty_dirs:
        try:
            (staging / Path(rel)).mkdir(parents=True, exist_ok=True)
        except OSError:
            # 例如空目录路径落在包内某个文件内部（history/index.json/oops）
            raise _bad_request(
                f"备份包内的空目录条目无法创建: {rel}",
                "备份包可能已被篡改或损坏，请重新导出备份。",
            )


def _commit_registry_replacement(root: Path, staging: Path) -> Tuple[List[str], List[str]]:
    """
    按注册表全量替换语义提交暂存数据：

    - core_data 资产：先清除现有数据，再把暂存版本移入；暂存里没有的
      资产保持清除状态（消除"源端已删除的数据复活"）；
    - config_with_secrets：仅当暂存中含有时才覆盖，缺席不删除。

    Returns:
        (restored, removed)：恢复的顶层资产名 / 因包内缺席而被清除的资产名。
    """
    restored: List[str] = []
    removed: List[str] = []

    for name in (*DATA_DIRS, *DATA_FILES):
        target = root / name
        staged = staging / name
        existed = target.exists()
        if existed:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        if staged.exists():
            shutil.move(str(staged), str(target))
            restored.append(name)
        elif existed:
            removed.append(name)

    for name in CONFIG_FILES:
        staged = staging / name
        if staged.is_file():
            os.replace(staged, root / name)
            restored.append(name)

    return restored, removed


def _import_v2_verified(
    zf: zipfile.ZipFile,
    root: Path,
    manifest: Dict[str, Any],
    plan: List[Tuple[zipfile.ZipInfo, str]],
    skipped: List[str],
    local_storage: Optional[Dict[str, str]],
    local_storage_raw: Optional[bytes],
) -> Dict[str, Any]:
    """
    v2 包导入：暂存目录完整解压 + 逐文件校验，全部通过后按注册表
    全量替换语义提交。校验失败时现有数据保持原样。
    """
    records = _parse_v2_file_records(manifest)
    empty_dirs, ignored_dirs = _parse_v2_empty_dirs(manifest, root)
    skipped = [*skipped, *ignored_dirs]
    _verify_v2_completeness(records, plan, local_storage_raw)

    if not plan and not empty_dirs and local_storage is None:
        raise _bad_request(
            "备份包内没有可恢复的数据",
            "请使用 RedInk 设置页「导出备份」生成的 zip 文件。",
        )

    # 暂存目录建在数据根旁（同一文件系统，提交阶段可用 rename 移入）
    staging = Path(tempfile.mkdtemp(prefix=".import_staging_", dir=root))
    try:
        _extract_and_verify_to_staging(zf, staging, plan, records, empty_dirs)

        # 校验全部通过，才允许触碰现有数据：先整体预备份，再提交替换
        pre_import_backup = _backup_existing_data(root)
        restored, removed = _commit_registry_replacement(root, staging)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    logger.info(
        f"📥 v2 备份导入完成: 恢复 {restored}, 清除 {removed}, "
        f"忽略 {len(skipped)} 项, 导入前备份 {pre_import_backup}"
    )
    return {
        "success": True,
        "manifest": _manifest_summary(manifest),
        "restored": restored,
        "removed": removed,
        "skipped": skipped,
        "pre_import_backup": pre_import_backup,
        "local_storage": local_storage,
    }


def import_backup_zip(
    file_stream: BinaryIO,
    data_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    导入备份 zip 并恢复数据。

    通用流程：zip 格式/条目数/声明总大小校验 → manifest 校验（读取前
    先查单项声明大小上限）→ 路径安全校验（local_storage 同样先查单项
    上限）→ 全部通过后按 manifest 格式分派：
    - v2：暂存目录完整解压 + 逐文件 sha256 校验 → 现有数据整体备份到
      .pre_import_backup_时间戳/ → 按注册表全量替换提交；
    - v1：现有数据整体备份 → 宽松覆盖恢复（仅替换包内出现的顶层目录）。

    Returns:
        摘要 dict：restored（恢复的顶层条目）、removed（v2 下因包内缺席
        而清除的条目）、skipped（忽略的未知条目）、pre_import_backup
        （自动备份目录名）、local_storage（zip 内的前端 localStorage 数据，
        由前端负责写回，没有则为 None）。

    Raises:
        AppErrorException: 非 zip / manifest 非法 / 路径逃逸 / 校验和不符 /
            超限时抛 400，且不修改现有数据。
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
        # 条目数/声明总大小上限先于一切解压（含 manifest 读取）执行，
        # 防止在检查前就把炸弹条目解压进内存
        infos = zf.infolist()
        if len(infos) > MAX_IMPORT_ENTRIES:
            raise _bad_request(f"备份包条目数超过上限（{MAX_IMPORT_ENTRIES}）")
        declared_total = sum(info.file_size for info in infos)
        if declared_total > MAX_IMPORT_UNCOMPRESSED_SIZE:
            raise _bad_request(
                "备份包解压后总大小超过上限"
                f"（{MAX_IMPORT_UNCOMPRESSED_SIZE // (1024 * 1024)}MB）"
            )

        manifest = _read_manifest(zf)

        plan, skipped, local_storage, local_storage_raw = _build_restore_plan(zf, root)

        if manifest.get("format", 1) >= 2:
            return _import_v2_verified(
                zf, root, manifest, plan, skipped, local_storage, local_storage_raw
            )
        return _import_v1_lenient(zf, root, manifest, plan, skipped, local_storage)


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
