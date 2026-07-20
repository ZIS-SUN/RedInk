"""
发布助手服务（半自动）

只做三件事，绝不触碰任何平台凭证：
1. 多平台账号清单管理（仅存平台 + 昵称 + 备注等标签信息，
   不存密码/cookie/会话，不做自动登录、自动发布）；
2. 一键备料：把某条历史记录的原图导出到本地
   get_data_root()/publish_exports/<record_id>_<时间戳>/，
   并整理一份「发布文案.txt」；
3. 平台创作者发布页 URL 常量下发（由前端打开，用户手动发布）。

账号数据落盘到 get_data_root()/publish_accounts.json，
与 brand/calendar 服务相同的稳健写入方式：threading 锁 + 临时文件 + os.replace 原子替换。

单个账号字段：
- id: uuid4 hex 前 8 位
- platform: 平台 code（见 PLATFORM_CREATOR_URLS 白名单）
- nickname: 账号昵称（必填非空）
- notes: 备注
- created_at / updated_at: ISO 时间戳
"""

import os
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional

from backend.paths import get_data_root
from backend.services.history import get_history_service

logger = logging.getLogger(__name__)

# 守护实例锁的惰性创建（实例可能通过 __new__ 构造，绕过 __init__）
_LOCK_INIT_GUARD = threading.Lock()

# 平台 code -> 创作者发布页 URL（前端打开，由用户手动登录、手动发布）
PLATFORM_CREATOR_URLS = {
    "xiaohongshu": "https://creator.xiaohongshu.com/publish/publish",
    "douyin": "https://creator.douyin.com/creator-micro/content/upload",
    "shipinhao": "https://channels.weixin.qq.com/platform/post/create",
    "bilibili": "https://member.bilibili.com/platform/upload/video/frame",
    "gongzhonghao": "https://mp.weixin.qq.com/",
    "kuaishou": "https://cp.kuaishou.com/article/publish/video",
}

# 平台 code -> 中文名（前端展示）
PLATFORM_LABELS = {
    "xiaohongshu": "小红书",
    "douyin": "抖音",
    "shipinhao": "视频号",
    "bilibili": "B站",
    "gongzhonghao": "公众号",
    "kuaishou": "快手",
}

PLATFORMS = tuple(PLATFORM_CREATOR_URLS)

# 导出目录名（get_data_root() 下）
_EXPORTS_DIR_NAME = "publish_exports"

# 账号清单文件名（get_data_root() 下）
_STORE_FILE_NAME = "publish_accounts.json"

_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")


class PublishStoreCorruptedError(RuntimeError):
    """账号数据文件损坏（存在但无法解析）时抛出，避免用空数据覆盖真实数据。"""


class RecordNotFoundError(LookupError):
    """一键备料时历史记录不存在。"""


def list_platforms() -> List[Dict]:
    """平台清单（key/中文名/创作者发布页 URL），供前端渲染与打开发布页。"""
    return [
        {
            "key": key,
            "label": PLATFORM_LABELS.get(key, key),
            "creator_url": url,
        }
        for key, url in PLATFORM_CREATOR_URLS.items()
    ]


class PublishAccountService:
    """多平台账号清单（纯标签管理，不含任何凭证）。"""

    def __init__(self):
        self.store_file = str(get_data_root() / _STORE_FILE_NAME)
        self._init_store()

    @property
    def _lock(self) -> "threading.RLock":
        """实例级可重入锁（惰性创建，兼容通过 __new__ 构造的实例）。"""
        lock = self.__dict__.get("_lock_obj")
        if lock is None:
            with _LOCK_INIT_GUARD:
                lock = self.__dict__.get("_lock_obj")
                if lock is None:
                    lock = threading.RLock()
                    self.__dict__["_lock_obj"] = lock
        return lock

    @staticmethod
    def _atomic_write_json(path: str, data: Dict) -> None:
        """原子写 JSON：先写同目录临时文件，再 os.replace() 覆盖。"""
        dir_name = os.path.dirname(path) or "."
        os.makedirs(dir_name, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            prefix=".tmp_", suffix=".json", dir=dir_name
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

    def _init_store(self) -> None:
        """数据文件不存在时创建一个空库。"""
        with self._lock:
            if not os.path.exists(self.store_file):
                self._atomic_write_json(self.store_file, {"accounts": []})

    def _load_store(self) -> Dict:
        """
        加载数据文件。

        Raises:
            PublishStoreCorruptedError: 文件存在但无法解析/结构异常时抛出，
                绝不静默返回空库（避免调用方把空库写回覆盖真实数据）。
        """
        with self._lock:
            if not os.path.exists(self.store_file):
                return {"accounts": []}
            try:
                with open(self.store_file, "r", encoding="utf-8") as f:
                    store = json.load(f)
            except Exception as e:
                logger.error("发布账号数据文件解析失败，保留原文件不覆盖: %s (%s)", self.store_file, e)
                raise PublishStoreCorruptedError(
                    f"发布账号数据文件损坏，已保留原文件: {self.store_file}"
                ) from e

            if not isinstance(store, dict) or not isinstance(store.get("accounts"), list):
                logger.error("发布账号数据文件结构异常，保留原文件不覆盖: %s", self.store_file)
                raise PublishStoreCorruptedError(
                    f"发布账号数据文件结构异常，已保留原文件: {self.store_file}"
                )
            return store

    def _save_store(self, store: Dict) -> None:
        with self._lock:
            self._atomic_write_json(self.store_file, store)

    # ==================== 字段校验 ====================

    @staticmethod
    def _normalize_str(value) -> str:
        """None -> 空串，其余强转字符串并去首尾空白。"""
        if value is None:
            return ""
        return str(value).strip()

    @classmethod
    def _validate_platform(cls, value) -> str:
        platform = cls._normalize_str(value)
        if platform not in PLATFORMS:
            raise ValueError(
                f"平台取值非法：{platform or '(空)'}，可选值：{', '.join(PLATFORMS)}"
            )
        return platform

    @classmethod
    def _validate_nickname(cls, value) -> str:
        nickname = cls._normalize_str(value)
        if not nickname:
            raise ValueError("账号昵称不能为空")
        return nickname

    # ==================== CRUD ====================

    def list_accounts(self) -> List[Dict]:
        """获取全部账号（按创建时间倒序，新账号在前）。"""
        store = self._load_store()
        return store.get("accounts", [])

    def create_account(self, data: Dict) -> Dict:
        """
        新建账号

        Raises:
            ValueError: platform 不在白名单或 nickname 为空时抛出
        """
        platform = self._validate_platform(data.get("platform"))
        nickname = self._validate_nickname(data.get("nickname"))

        now = datetime.now().isoformat()
        account = {
            "id": uuid.uuid4().hex[:8],
            "platform": platform,
            "nickname": nickname,
            "notes": self._normalize_str(data.get("notes")),
            "created_at": now,
            "updated_at": now,
        }

        with self._lock:
            store = self._load_store()
            store["accounts"].insert(0, account)
            self._save_store(store)

        return account

    def update_account(self, account_id: str, data: Dict) -> Optional[Dict]:
        """
        更新账号（部分更新，只更新提供的字段）

        Returns:
            更新后的完整账号；账号不存在返回 None

        Raises:
            ValueError: 显式传入的字段非法时抛出
        """
        with self._lock:
            store = self._load_store()
            target = None
            for account in store.get("accounts", []):
                if account.get("id") == account_id:
                    target = account
                    break
            if target is None:
                return None

            if "platform" in data:
                target["platform"] = self._validate_platform(data.get("platform"))
            if "nickname" in data:
                target["nickname"] = self._validate_nickname(data.get("nickname"))
            if "notes" in data:
                target["notes"] = self._normalize_str(data.get("notes"))

            target["updated_at"] = datetime.now().isoformat()
            self._save_store(store)
            return target

    def delete_account(self, account_id: str) -> bool:
        """删除账号；账号不存在返回 False。"""
        with self._lock:
            store = self._load_store()
            accounts = store.get("accounts", [])
            remaining = [a for a in accounts if a.get("id") != account_id]
            if len(remaining) == len(accounts):
                return False

            store["accounts"] = remaining
            self._save_store(store)
            return True


# ==================== 一键备料 ====================

def _list_source_images(task_dir: str) -> List[str]:
    """
    列出任务目录下的原图文件名（跳过 thumb_ 缩略图），
    数字命名（0.png/1.png...）按序号升序排在前，其余按文件名排序垫后。
    与 history_routes._create_images_zip 的筛选规则保持一致。
    """
    numbered = []
    others = []
    for filename in os.listdir(task_dir):
        if filename.startswith("thumb_"):
            continue
        if not filename.endswith(_IMAGE_EXTENSIONS):
            continue
        try:
            index = int(filename.split(".")[0])
            numbered.append((index, filename))
        except ValueError:
            others.append(filename)

    return [f for _, f in sorted(numbered)] + sorted(others)


def _extract_publish_content(record: Dict) -> Dict:
    """从 record.content 提取结构化文案（缺失/坏结构一律回落空值）。"""
    content = record.get("content")
    if not isinstance(content, dict):
        content = {}

    titles = content.get("titles")
    titles = [t.strip() for t in titles if isinstance(t, str) and t.strip()] \
        if isinstance(titles, list) else []

    copywriting = content.get("copywriting")
    copywriting = copywriting.strip() if isinstance(copywriting, str) else ""

    tags = content.get("tags")
    tags = [t.strip() for t in tags if isinstance(t, str) and t.strip()] \
        if isinstance(tags, list) else []

    return {"titles": titles, "copywriting": copywriting, "tags": tags}


def prepare_publish_materials(record_id: str) -> Dict:
    """
    一键备料：把历史记录的原图与文案导出到本地文件夹。

    在 get_data_root()/publish_exports/<record_id>_<YYYYMMDD_HHMMSS>/ 下：
    - 原图按 page_1.png 递增复制（跳过 thumb_ 缩略图）；
    - 有可用文案时写入「发布文案.txt」（UTF-8）。

    Returns:
        {
            "folder": 导出文件夹绝对路径,
            "files": [相对文件名...],
            "text": { "titles": [], "copywriting": "", "tags": [] },
        }

    Raises:
        RecordNotFoundError: 历史记录不存在（路由映射 404）
        ValueError: 该记录还没有已生成图片（路由映射 400）
    """
    history_service = get_history_service()
    record = history_service.get_record(record_id, sync_images=True)
    if not record:
        raise RecordNotFoundError(f"历史记录不存在：{record_id}")

    no_images_error = ValueError("该作品还没有生成图片")

    task_id = (record.get("images") or {}).get("task_id")
    if not task_id:
        raise no_images_error

    task_dir = os.path.join(history_service.history_dir, task_id)
    if not os.path.isdir(task_dir):
        raise no_images_error

    source_images = _list_source_images(task_dir)
    if not source_images:
        raise no_images_error

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = get_data_root() / _EXPORTS_DIR_NAME / f"{record_id}_{timestamp}"
    export_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for i, filename in enumerate(source_images, start=1):
        ext = os.path.splitext(filename)[1] or ".png"
        target_name = f"page_{i}{ext}"
        shutil.copyfile(
            os.path.join(task_dir, filename), str(export_dir / target_name)
        )
        files.append(target_name)

    # 发布文案文本与 zip 发布包完全同源（history_routes 的拼装逻辑）
    from backend.routes.history_routes import _build_publish_text
    publish_text = _build_publish_text(record)
    if publish_text:
        text_name = "发布文案.txt"
        (export_dir / text_name).write_text(publish_text, encoding="utf-8")
        files.append(text_name)

    return {
        "folder": str(export_dir.resolve()),
        "files": files,
        "text": _extract_publish_content(record),
    }


# ==================== 打开本地文件夹 ====================

def open_export_folder(path: str) -> Dict:
    """
    在 Finder 中打开导出文件夹（仅限 publish_exports 目录内，防目录穿越）。

    Returns:
        { "success": bool, "message": 失败提示（成功时省略） }

    Raises:
        ValueError: 路径不在 get_data_root()/publish_exports/ 之内（路由映射 400）
    """
    exports_root = os.path.realpath(str(get_data_root() / _EXPORTS_DIR_NAME))
    target = os.path.realpath(str(path or ""))

    if target != exports_root and not target.startswith(exports_root + os.sep):
        raise ValueError("路径不在发布导出目录内，已拒绝打开")

    if not os.path.isdir(target):
        return {"success": False, "message": "文件夹不存在，可能已被移动或删除"}

    if sys.platform != "darwin":
        return {"success": False, "message": "当前系统不支持自动打开文件夹，请手动前往该目录"}

    try:
        result = subprocess.run(
            ["open", target], capture_output=True, timeout=10
        )
    except Exception as e:
        logger.warning("打开文件夹失败: %s (%s)", target, e)
        return {"success": False, "message": "打开文件夹失败，请手动前往该目录"}

    if result.returncode != 0:
        logger.warning(
            "open 命令返回非零: %s (%s)", target, result.stderr.decode(errors="ignore")
        )
        return {"success": False, "message": "打开文件夹失败，请手动前往该目录"}

    return {"success": True}


_service_instance = None


def get_publish_service() -> PublishAccountService:
    """获取发布账号服务实例（单例模式）。"""
    global _service_instance
    if _service_instance is None:
        _service_instance = PublishAccountService()
    return _service_instance
