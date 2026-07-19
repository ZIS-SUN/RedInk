"""
品牌风格记忆（品牌资料库）服务

负责品牌档案（BrandKit）的增删改查与持久化：
- 数据落盘到项目根目录 brand_kits/brands.json（独立目录，与 history 互不影响）
- 与 history 服务相同的稳健写入方式：threading 锁 + 临时文件 + os.replace 原子替换
- 支持设置一个「当前启用」的档案（active_id）

单个品牌档案字段：
- id: UUID
- name: 品牌/IP 名称（必填）
- tagline: 一句话定位
- audience: 目标人群
- tone: 语气风格（如"专业克制"/"活泼种草"）
- catchphrases: 常用口头禅/开场白（字符串列表）
- signature: 签名/结尾话术
- primary_color: 主色调（如 #FF2442）
- banned_words: 禁用词（字符串列表）
- notes: 备注
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

logger = logging.getLogger(__name__)

# 守护实例锁的惰性创建（实例可能通过 __new__ 构造，绕过 __init__）
_LOCK_INIT_GUARD = threading.Lock()

# 品牌档案中允许由调用方写入的字段（除 name 外均可选）
_EDITABLE_STR_FIELDS = (
    "name", "tagline", "audience", "tone",
    "signature", "primary_color", "notes",
)
_EDITABLE_LIST_FIELDS = ("catchphrases", "banned_words")


class BrandStoreCorruptedError(RuntimeError):
    """数据文件损坏（存在但无法解析）时抛出，避免用空数据覆盖真实数据。"""


class BrandService:
    def __init__(self):
        """
        初始化品牌资料库服务

        创建 brand_kits 存储目录和数据文件（项目根目录/brand_kits/brands.json）
        """
        self.brand_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "brand_kits"
        )
        os.makedirs(self.brand_dir, exist_ok=True)

        self.store_file = os.path.join(self.brand_dir, "brands.json")
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
                self._atomic_write_json(
                    self.store_file, {"brands": [], "active_id": None}
                )

    def _load_store(self) -> Dict:
        """
        加载数据文件

        Raises:
            BrandStoreCorruptedError: 文件存在但无法解析/结构异常时抛出，
                绝不静默返回空库（避免调用方把空库写回覆盖真实数据）。
        """
        with self._lock:
            if not os.path.exists(self.store_file):
                return {"brands": [], "active_id": None}
            try:
                with open(self.store_file, "r", encoding="utf-8") as f:
                    store = json.load(f)
            except Exception as e:
                logger.error("品牌数据文件解析失败，保留原文件不覆盖: %s (%s)", self.store_file, e)
                raise BrandStoreCorruptedError(
                    f"品牌数据文件损坏，已保留原文件: {self.store_file}"
                ) from e

            if not isinstance(store, dict) or not isinstance(store.get("brands"), list):
                logger.error("品牌数据文件结构异常，保留原文件不覆盖: %s", self.store_file)
                raise BrandStoreCorruptedError(
                    f"品牌数据文件结构异常，已保留原文件: {self.store_file}"
                )
            if "active_id" not in store:
                store["active_id"] = None
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
    def _normalize_list(value) -> List[str]:
        """列表字段归一化：只保留非空字符串项。"""
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                result.append(text)
        return result

    # ==================== CRUD ====================

    def list_brands(self) -> Dict:
        """
        获取全部品牌档案

        Returns:
            Dict: { brands: [...], active_id: str | None }
        """
        store = self._load_store()
        return {
            "brands": store.get("brands", []),
            "active_id": store.get("active_id"),
        }

    def get_brand(self, brand_id: str) -> Optional[Dict]:
        """按 ID 获取品牌档案，不存在返回 None。"""
        store = self._load_store()
        for brand in store.get("brands", []):
            if brand.get("id") == brand_id:
                return brand
        return None

    def create_brand(self, data: Dict) -> Dict:
        """
        创建品牌档案

        Args:
            data: 档案字段字典，name 必填，其余可选

        Returns:
            Dict: 新创建的完整档案

        Raises:
            ValueError: name 为空时抛出
        """
        name = self._normalize_str(data.get("name"))
        if not name:
            raise ValueError("品牌/IP 名称不能为空")

        now = datetime.now().isoformat()
        brand = {
            "id": str(uuid.uuid4()),
            "name": name,
            "tagline": self._normalize_str(data.get("tagline")),
            "audience": self._normalize_str(data.get("audience")),
            "tone": self._normalize_str(data.get("tone")),
            "catchphrases": self._normalize_list(data.get("catchphrases")),
            "signature": self._normalize_str(data.get("signature")),
            "primary_color": self._normalize_str(data.get("primary_color")),
            "banned_words": self._normalize_list(data.get("banned_words")),
            "notes": self._normalize_str(data.get("notes")),
            "created_at": now,
            "updated_at": now,
        }

        with self._lock:
            store = self._load_store()
            store["brands"].insert(0, brand)
            # 首个档案自动设为启用，省去用户一步操作
            if store.get("active_id") is None and len(store["brands"]) == 1:
                store["active_id"] = brand["id"]
            self._save_store(store)

        return brand

    def update_brand(self, brand_id: str, data: Dict) -> Optional[Dict]:
        """
        更新品牌档案（部分更新，只更新提供的字段）

        Args:
            brand_id: 档案 ID
            data: 待更新字段字典

        Returns:
            Optional[Dict]: 更新后的完整档案；档案不存在返回 None

        Raises:
            ValueError: 显式传入空 name 时抛出
        """
        if "name" in data and not self._normalize_str(data.get("name")):
            raise ValueError("品牌/IP 名称不能为空")

        with self._lock:
            store = self._load_store()
            target = None
            for brand in store.get("brands", []):
                if brand.get("id") == brand_id:
                    target = brand
                    break
            if target is None:
                return None

            for field in _EDITABLE_STR_FIELDS:
                if field in data:
                    target[field] = self._normalize_str(data.get(field))
            for field in _EDITABLE_LIST_FIELDS:
                if field in data:
                    target[field] = self._normalize_list(data.get(field))

            target["updated_at"] = datetime.now().isoformat()
            self._save_store(store)
            return target

    def delete_brand(self, brand_id: str) -> bool:
        """
        删除品牌档案

        如果删除的是当前启用档案，active_id 置空。

        Returns:
            bool: 删除是否成功，档案不存在返回 False
        """
        with self._lock:
            store = self._load_store()
            brands = store.get("brands", [])
            remaining = [b for b in brands if b.get("id") != brand_id]
            if len(remaining) == len(brands):
                return False

            store["brands"] = remaining
            if store.get("active_id") == brand_id:
                store["active_id"] = None
            self._save_store(store)
            return True

    # ==================== 启用管理 ====================

    def activate_brand(self, brand_id: str) -> bool:
        """
        设置某个档案为「当前启用」

        Returns:
            bool: 是否成功，档案不存在返回 False
        """
        with self._lock:
            store = self._load_store()
            if not any(b.get("id") == brand_id for b in store.get("brands", [])):
                return False
            store["active_id"] = brand_id
            self._save_store(store)
            return True

    def get_active_brand(self) -> Optional[Dict]:
        """
        获取当前启用的档案，未设置或已被删除时返回 None。
        """
        store = self._load_store()
        active_id = store.get("active_id")
        if not active_id:
            return None
        for brand in store.get("brands", []):
            if brand.get("id") == active_id:
                return brand
        return None


_service_instance = None


def get_brand_service() -> BrandService:
    """
    获取品牌资料库服务实例（单例模式）

    Returns:
        BrandService: 品牌资料库服务实例
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = BrandService()
    return _service_instance
