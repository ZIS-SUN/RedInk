"""
剪藏收件箱服务（浏览器插件进料）

负责浏览器插件剪藏内容（Clip）的存储与增删查：
- 数据落盘到数据目录 clips/clips.json（独立目录，与 brand_kits / idea_library 互不影响）
- 与 brand 服务相同的稳健写入方式：threading 锁 + 临时文件 + os.replace 原子替换
- 收件箱定位是「临时进料区」：上限 50 条滚动，超出自动删除最旧的条目

单条剪藏字段：
- id: UUID
- source: 来源平台（xiaohongshu 小红书 / douyin 抖音 / other 其他）
- url: 原始页面链接
- title: 标题
- author: 作者
- content: 正文文本（title 与 content 至少一项非空）
- tags: 话题标签（字符串列表）
- stats: 互动数据（可选对象：likes 点赞 / collects 收藏 / comments 评论；取不到为 null）
- created_at: ISO 时间戳
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

# 来源平台的合法取值（非法值回退 other，剪藏入口宽松容错）
VALID_SOURCES = ("xiaohongshu", "douyin", "other")
DEFAULT_SOURCE = "other"

# 收件箱容量：超出后滚动删除最旧条目（收件箱是临时进料区，不是长期存储）
MAX_CLIPS = 50

# 字段长度上限（防滥用）：正文超限直接报错拒收；
# 其余短字段来自网页 DOM 提取、内容不可控，静默截断保证剪藏不失败
MAX_CONTENT_CHARS = 20000
MAX_TITLE_CHARS = 300
MAX_AUTHOR_CHARS = 120
MAX_URL_CHARS = 2048
MAX_TAGS = 20
MAX_TAG_CHARS = 60

# stats 对象中允许的互动数据字段
_STATS_FIELDS = ("likes", "collects", "comments")


class ClipStoreCorruptedError(RuntimeError):
    """数据文件损坏（存在但无法解析）时抛出，避免用空数据覆盖真实数据。"""


class ClipsService:
    def __init__(self):
        """
        初始化剪藏收件箱服务

        创建 clips 存储目录和数据文件（数据目录/clips/clips.json）
        """
        self.clips_dir = str(get_data_root() / "clips")
        os.makedirs(self.clips_dir, exist_ok=True)

        self.store_file = os.path.join(self.clips_dir, "clips.json")
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
                self._atomic_write_json(self.store_file, {"clips": []})

    def _load_store(self) -> Dict:
        """
        加载数据文件

        Raises:
            ClipStoreCorruptedError: 文件存在但无法解析/结构异常时抛出，
                绝不静默返回空库（避免调用方把空库写回覆盖真实数据）。
        """
        with self._lock:
            if not os.path.exists(self.store_file):
                return {"clips": []}
            try:
                with open(self.store_file, "r", encoding="utf-8") as f:
                    store = json.load(f)
            except Exception as e:
                logger.error("剪藏数据文件解析失败，保留原文件不覆盖: %s (%s)", self.store_file, e)
                raise ClipStoreCorruptedError(
                    f"剪藏数据文件损坏，已保留原文件: {self.store_file}"
                ) from e

            if not isinstance(store, dict) or not isinstance(store.get("clips"), list):
                logger.error("剪藏数据文件结构异常，保留原文件不覆盖: %s", self.store_file)
                raise ClipStoreCorruptedError(
                    f"剪藏数据文件结构异常，已保留原文件: {self.store_file}"
                )
            return store

    def _save_store(self, store: Dict) -> None:
        """保存数据文件（原子写）。"""
        with self._lock:
            self._atomic_write_json(self.store_file, store)

    # ==================== 字段归一化 ====================

    @staticmethod
    def _normalize_str(value, max_chars: int) -> str:
        """字符串字段归一化：None -> 空串，强转字符串、去首尾空白、截断到上限。"""
        if value is None:
            return ""
        return str(value).strip()[:max_chars]

    @staticmethod
    def _normalize_tags(value) -> List[str]:
        """标签列表归一化：只保留非空字符串项，去掉 # 前缀，数量与长度截断。"""
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip().lstrip("#").strip()
            if text:
                result.append(text[:MAX_TAG_CHARS])
            if len(result) >= MAX_TAGS:
                break
        return result

    @classmethod
    def _normalize_source(cls, value) -> str:
        """来源归一化：非法值回退 other（剪藏入口宽松容错，不因来源字段拒收）。"""
        text = cls._normalize_str(value, 32)
        return text if text in VALID_SOURCES else DEFAULT_SOURCE

    @staticmethod
    def _normalize_stats(value) -> Optional[Dict[str, int]]:
        """
        互动数据归一化：只保留 likes/collects/comments 三个非负整数字段，
        字符串数字（如 "1234"）尽量解析，解析不出的字段直接丢弃；
        全部无效时返回 None（前端按「未采集到」处理）。
        """
        if not isinstance(value, dict):
            return None
        stats: Dict[str, int] = {}
        for field in _STATS_FIELDS:
            raw = value.get(field)
            # bool 是 int 的子类，明确排除，避免 True 被算成 1 个赞
            if isinstance(raw, bool):
                continue
            if isinstance(raw, (int, float)):
                number = int(raw)
            elif isinstance(raw, str):
                try:
                    number = int(float(raw.strip()))
                except ValueError:
                    continue
            else:
                continue
            if number >= 0:
                stats[field] = number
        return stats or None

    # ==================== CRUD ====================

    def list_clips(self) -> List[Dict]:
        """
        获取全部剪藏（按时间倒序，新条目在前——创建时插入队首，落盘顺序即时间倒序）

        Returns:
            List[Dict]: 剪藏条目列表
        """
        store = self._load_store()
        return store.get("clips", [])

    def get_clip(self, clip_id: str) -> Optional[Dict]:
        """按 ID 获取剪藏条目，不存在返回 None。"""
        store = self._load_store()
        for clip in store.get("clips", []):
            if clip.get("id") == clip_id:
                return clip
        return None

    def create_clip(self, data: Dict) -> Dict:
        """
        创建剪藏条目（超过 MAX_CLIPS 条时滚动删除最旧的）

        Args:
            data: 条目字段字典，title 或 content 至少一项非空

        Returns:
            Dict: 新创建的完整条目

        Raises:
            ValueError: title 与 content 均为空，或 content 超过长度上限时抛出
        """
        title = self._normalize_str(data.get("title"), MAX_TITLE_CHARS)
        raw_content = "" if data.get("content") is None else str(data.get("content")).strip()

        if not title and not raw_content:
            raise ValueError("标题或正文至少需要一项非空")
        # 正文是主要的滥用向量（收件箱端点对插件放开了 CORS），超限拒收而非截断
        if len(raw_content) > MAX_CONTENT_CHARS:
            raise ValueError(
                f"正文过长（{len(raw_content)} 字），上限 {MAX_CONTENT_CHARS} 字"
            )

        clip = {
            "id": str(uuid.uuid4()),
            "source": self._normalize_source(data.get("source")),
            "url": self._normalize_str(data.get("url"), MAX_URL_CHARS),
            "title": title,
            "author": self._normalize_str(data.get("author"), MAX_AUTHOR_CHARS),
            "content": raw_content,
            "tags": self._normalize_tags(data.get("tags")),
            "stats": self._normalize_stats(data.get("stats")),
            "created_at": datetime.now().isoformat(),
        }

        with self._lock:
            store = self._load_store()
            store["clips"].insert(0, clip)
            # 滚动上限：新条目在队首，裁掉队尾（最旧）的超额条目
            if len(store["clips"]) > MAX_CLIPS:
                store["clips"] = store["clips"][:MAX_CLIPS]
            self._save_store(store)

        return clip

    def delete_clip(self, clip_id: str) -> bool:
        """
        删除单条剪藏

        Returns:
            bool: 删除是否成功，条目不存在返回 False
        """
        with self._lock:
            store = self._load_store()
            clips = store.get("clips", [])
            remaining = [c for c in clips if c.get("id") != clip_id]
            if len(remaining) == len(clips):
                return False

            store["clips"] = remaining
            self._save_store(store)
            return True

    def clear_clips(self) -> int:
        """
        清空收件箱

        Returns:
            int: 被清除的条目数
        """
        with self._lock:
            store = self._load_store()
            removed = len(store.get("clips", []))
            store["clips"] = []
            self._save_store(store)
            return removed


_service_instance = None


def get_clips_service() -> ClipsService:
    """
    获取剪藏收件箱服务实例（单例模式）

    Returns:
        ClipsService: 剪藏收件箱服务实例
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = ClipsService()
    return _service_instance
