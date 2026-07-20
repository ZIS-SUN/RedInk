"""
我的选题库服务

负责选题条目（Idea）的增删改查与持久化，解决「先攒题、后定题」：
- 数据落盘到数据目录 idea_library/ideas.json（独立目录，与 brand_kits 互不影响）
- 与 brand 服务相同的稳健写入方式：threading 锁 + 临时文件 + os.replace 原子替换
- 支持按状态（status）与来源（source）过滤列表

单条选题字段：
- id: UUID
- title: 选题标题（必填）
- angle: 切入角度
- tags: 建议标签（字符串列表）
- source: 来源（manual 手动 / topic 选题灵感 / insight 评论洞察 / hotspot 蹭热点）
- status: 状态（idea 想法 / todo 待做 / done 已做 / viral 已爆）
- niche: 赛道/领域
- created_at / updated_at: ISO 时间戳
"""

import os
import json
import tempfile
import threading
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional

from backend.paths import get_data_root

logger = logging.getLogger(__name__)

# 守护实例锁的惰性创建（实例可能通过 __new__ 构造，绕过 __init__）
_LOCK_INIT_GUARD = threading.Lock()

# 来源与状态的合法取值（超出范围时创建走默认值，更新则报错）
VALID_SOURCES = ("manual", "topic", "insight", "hotspot")
VALID_STATUSES = ("idea", "todo", "done", "viral")

DEFAULT_SOURCE = "manual"
DEFAULT_STATUS = "idea"

# 除 title 外允许由调用方写入/更新的字符串字段
_EDITABLE_STR_FIELDS = ("title", "angle", "niche")


class IdeaStoreCorruptedError(RuntimeError):
    """数据文件损坏（存在但无法解析）时抛出，避免用空数据覆盖真实数据。"""


class IdeaLibraryService:
    def __init__(self):
        """
        初始化选题库服务

        创建 idea_library 存储目录和数据文件（数据目录/idea_library/ideas.json）
        """
        self.idea_dir = str(get_data_root() / "idea_library")
        os.makedirs(self.idea_dir, exist_ok=True)

        self.store_file = os.path.join(self.idea_dir, "ideas.json")
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
        """
        原子写 JSON 文件：先写同目录临时文件，再 os.replace() 覆盖，
        避免其他读者读到半截文件。
        """
        dir_name = os.path.dirname(path) or "."
        # 目录可能在运行期被删除（如用户清理本地数据），写入前确保其存在，避免 500
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
                self._atomic_write_json(self.store_file, {"ideas": []})

    def _load_store(self) -> Dict:
        """
        加载数据文件

        Raises:
            IdeaStoreCorruptedError: 文件存在但无法解析/结构异常时抛出，
                绝不静默返回空库（避免调用方把空库写回覆盖真实数据）。
        """
        with self._lock:
            if not os.path.exists(self.store_file):
                return {"ideas": []}
            try:
                with open(self.store_file, "r", encoding="utf-8") as f:
                    store = json.load(f)
            except Exception as e:
                logger.error("选题库数据文件解析失败，保留原文件不覆盖: %s (%s)", self.store_file, e)
                raise IdeaStoreCorruptedError(
                    f"选题库数据文件损坏，已保留原文件: {self.store_file}"
                ) from e

            if not isinstance(store, dict) or not isinstance(store.get("ideas"), list):
                logger.error("选题库数据文件结构异常，保留原文件不覆盖: %s", self.store_file)
                raise IdeaStoreCorruptedError(
                    f"选题库数据文件结构异常，已保留原文件: {self.store_file}"
                )
            return store

    def _save_store(self, store: Dict) -> None:
        """保存数据文件（原子写）。"""
        with self._lock:
            self._atomic_write_json(self.store_file, store)

    # ==================== 字段归一化 ====================

    @staticmethod
    def _normalize_str(value) -> str:
        """字符串字段归一化：None -> 空串，其余强转字符串并去首尾空白。"""
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_tags(value) -> List[str]:
        """标签列表归一化：只保留非空字符串项，去掉 # 前缀。"""
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip().lstrip("#")
            if text:
                result.append(text)
        return result

    @classmethod
    def _normalize_source(cls, value) -> str:
        """来源归一化：非法值回退 manual（创建入口宽松容错）。"""
        text = cls._normalize_str(value)
        return text if text in VALID_SOURCES else DEFAULT_SOURCE

    @classmethod
    def _normalize_status(cls, value) -> str:
        """状态归一化：非法值回退 idea（创建入口宽松容错）。"""
        text = cls._normalize_str(value)
        return text if text in VALID_STATUSES else DEFAULT_STATUS

    # ==================== CRUD ====================

    def list_ideas(
        self,
        status: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Dict]:
        """
        获取选题列表（按创建时间倒序，新条目在前）

        Args:
            status: 按状态过滤（可选；值按原样比较，非法值自然匹配不到任何条目）
            source: 按来源过滤（可选）

        Returns:
            List[Dict]: 命中的选题条目列表
        """
        store = self._load_store()
        ideas = store.get("ideas", [])

        status = self._normalize_str(status)
        source = self._normalize_str(source)
        if status:
            ideas = [i for i in ideas if i.get("status") == status]
        if source:
            ideas = [i for i in ideas if i.get("source") == source]
        return ideas

    def get_idea(self, idea_id: str) -> Optional[Dict]:
        """按 ID 获取选题条目，不存在返回 None。"""
        store = self._load_store()
        for idea in store.get("ideas", []):
            if idea.get("id") == idea_id:
                return idea
        return None

    def create_idea(self, data: Dict) -> Dict:
        """
        创建选题条目

        Args:
            data: 条目字段字典，title 必填；source/status 非法时回退默认值

        Returns:
            Dict: 新创建的完整条目

        Raises:
            ValueError: title 为空时抛出
        """
        title = self._normalize_str(data.get("title"))
        if not title:
            raise ValueError("选题标题不能为空")

        now = datetime.now().isoformat()
        idea = {
            "id": str(uuid.uuid4()),
            "title": title,
            "angle": self._normalize_str(data.get("angle")),
            "tags": self._normalize_tags(data.get("tags")),
            "source": self._normalize_source(data.get("source")),
            "status": self._normalize_status(data.get("status")),
            "niche": self._normalize_str(data.get("niche")),
            "created_at": now,
            "updated_at": now,
        }

        with self._lock:
            store = self._load_store()
            store["ideas"].insert(0, idea)
            self._save_store(store)

        return idea

    def update_idea(self, idea_id: str, data: Dict) -> Optional[Dict]:
        """
        更新选题条目（部分更新，只更新提供的字段；状态流转也走这里）

        Args:
            idea_id: 条目 ID
            data: 待更新字段字典

        Returns:
            Optional[Dict]: 更新后的完整条目；条目不存在返回 None

        Raises:
            ValueError: 显式传入空 title、非法 status 或非法 source 时抛出
                （更新是明确的用户操作，非法值直接报错而不静默回退）
        """
        if "title" in data and not self._normalize_str(data.get("title")):
            raise ValueError("选题标题不能为空")
        if "status" in data:
            status = self._normalize_str(data.get("status"))
            if status not in VALID_STATUSES:
                raise ValueError(f"非法的选题状态: {status or '(空)'}")
        if "source" in data:
            source = self._normalize_str(data.get("source"))
            if source not in VALID_SOURCES:
                raise ValueError(f"非法的选题来源: {source or '(空)'}")

        with self._lock:
            store = self._load_store()
            target = None
            for idea in store.get("ideas", []):
                if idea.get("id") == idea_id:
                    target = idea
                    break
            if target is None:
                return None

            for field in _EDITABLE_STR_FIELDS:
                if field in data:
                    target[field] = self._normalize_str(data.get(field))
            if "tags" in data:
                target["tags"] = self._normalize_tags(data.get("tags"))
            if "status" in data:
                target["status"] = self._normalize_str(data.get("status"))
            if "source" in data:
                target["source"] = self._normalize_str(data.get("source"))

            target["updated_at"] = datetime.now().isoformat()
            self._save_store(store)
            return target

    def delete_idea(self, idea_id: str) -> bool:
        """
        删除选题条目

        Returns:
            bool: 删除是否成功，条目不存在返回 False
        """
        with self._lock:
            store = self._load_store()
            ideas = store.get("ideas", [])
            remaining = [i for i in ideas if i.get("id") != idea_id]
            if len(remaining) == len(ideas):
                return False

            store["ideas"] = remaining
            self._save_store(store)
            return True


_service_instance = None


def get_idea_library_service() -> IdeaLibraryService:
    """
    获取选题库服务实例（单例模式）

    Returns:
        IdeaLibraryService: 选题库服务实例
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = IdeaLibraryService()
    return _service_instance
