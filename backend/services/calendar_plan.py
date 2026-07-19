"""
内容日历（发布计划）服务

负责内容计划条目（PlanItem）的增删改查与持久化：
- 数据落盘到项目根目录 content_calendar/plans.json（独立目录，与 history/brand_kits 互不影响）
- 与 brand 服务相同的稳健写入方式：threading 锁 + 临时文件 + os.replace 原子替换
- 支持按月（YYYY-MM）、平台、状态过滤，以及按月统计

单个计划条目字段：
- id: UUID
- title: 计划标题（必填）
- platform: 发布平台（xiaohongshu/douyin/gongzhonghao/bilibili/shipinhao）
- publish_date: 计划发布日期（YYYY-MM-DD，必填）
- status: 状态（idea 想法 / in_progress 制作中 / ready 待发布 / published 已发布）
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

# 允许的平台与状态枚举（对外统一使用英文 code，中文文案由前端负责）
PLATFORMS = ("xiaohongshu", "douyin", "gongzhonghao", "bilibili", "shipinhao")
STATUSES = ("idea", "in_progress", "ready", "published")

_DEFAULT_PLATFORM = "xiaohongshu"
_DEFAULT_STATUS = "idea"


class CalendarStoreCorruptedError(RuntimeError):
    """数据文件损坏（存在但无法解析）时抛出，避免用空数据覆盖真实数据。"""


class CalendarService:
    def __init__(self):
        """
        初始化内容日历服务

        创建 content_calendar 存储目录和数据文件（项目根目录/content_calendar/plans.json）
        """
        self.calendar_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "content_calendar"
        )
        os.makedirs(self.calendar_dir, exist_ok=True)

        self.store_file = os.path.join(self.calendar_dir, "plans.json")
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
                self._atomic_write_json(self.store_file, {"plans": []})

    def _load_store(self) -> Dict:
        """
        加载数据文件

        Raises:
            CalendarStoreCorruptedError: 文件存在但无法解析/结构异常时抛出，
                绝不静默返回空库（避免调用方把空库写回覆盖真实数据）。
        """
        with self._lock:
            if not os.path.exists(self.store_file):
                return {"plans": []}
            try:
                with open(self.store_file, "r", encoding="utf-8") as f:
                    store = json.load(f)
            except Exception as e:
                logger.error("内容日历数据文件解析失败，保留原文件不覆盖: %s (%s)", self.store_file, e)
                raise CalendarStoreCorruptedError(
                    f"内容日历数据文件损坏，已保留原文件: {self.store_file}"
                ) from e

            if not isinstance(store, dict) or not isinstance(store.get("plans"), list):
                logger.error("内容日历数据文件结构异常，保留原文件不覆盖: %s", self.store_file)
                raise CalendarStoreCorruptedError(
                    f"内容日历数据文件结构异常，已保留原文件: {self.store_file}"
                )
            return store

    def _save_store(self, store: Dict) -> None:
        """保存数据文件（原子写）。"""
        with self._lock:
            self._atomic_write_json(self.store_file, store)

    # ==================== 字段归一化与校验 ====================

    @staticmethod
    def _normalize_str(value) -> str:
        """字符串字段归一化：None -> 空串，其余强转字符串并去首尾空白。"""
        if value is None:
            return ""
        return str(value).strip()

    @classmethod
    def _validate_platform(cls, value) -> str:
        """校验平台取值，非法时抛 ValueError。"""
        platform = cls._normalize_str(value)
        if platform not in PLATFORMS:
            raise ValueError(
                f"平台取值非法：{platform or '(空)'}，可选值：{', '.join(PLATFORMS)}"
            )
        return platform

    @classmethod
    def _validate_status(cls, value) -> str:
        """校验状态取值，非法时抛 ValueError。"""
        status = cls._normalize_str(value)
        if status not in STATUSES:
            raise ValueError(
                f"状态取值非法：{status or '(空)'}，可选值：{', '.join(STATUSES)}"
            )
        return status

    @classmethod
    def _validate_publish_date(cls, value) -> str:
        """校验计划发布日期，格式必须为 YYYY-MM-DD。"""
        date_str = cls._normalize_str(value)
        if not date_str:
            raise ValueError("计划发布日期不能为空")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"计划发布日期格式非法：{date_str}，应为 YYYY-MM-DD")
        return date_str

    @staticmethod
    def _validate_month(value) -> str:
        """校验月份过滤参数，格式必须为 YYYY-MM。"""
        month = str(value or "").strip()
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            raise ValueError(f"月份格式非法：{month}，应为 YYYY-MM")
        return month

    # ==================== CRUD ====================

    def list_plans(
        self,
        month: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """
        获取计划条目列表（按计划发布日期升序）

        Args:
            month: 按月过滤（YYYY-MM，可选）
            platform: 按平台过滤（可选）
            status: 按状态过滤（可选）

        Returns:
            List[Dict]: 过滤后的计划条目列表

        Raises:
            ValueError: 过滤参数非法时抛出
        """
        if month is not None:
            month = self._validate_month(month)
        if platform is not None:
            platform = self._validate_platform(platform)
        if status is not None:
            status = self._validate_status(status)

        store = self._load_store()
        plans = store.get("plans", [])

        if month:
            plans = [p for p in plans if str(p.get("publish_date", "")).startswith(month)]
        if platform:
            plans = [p for p in plans if p.get("platform") == platform]
        if status:
            plans = [p for p in plans if p.get("status") == status]

        return sorted(plans, key=lambda p: (p.get("publish_date", ""), p.get("created_at", "")))

    def get_plan(self, plan_id: str) -> Optional[Dict]:
        """按 ID 获取计划条目，不存在返回 None。"""
        store = self._load_store()
        for plan in store.get("plans", []):
            if plan.get("id") == plan_id:
                return plan
        return None

    def create_plan(self, data: Dict) -> Dict:
        """
        创建计划条目

        Args:
            data: 条目字段字典，title 与 publish_date 必填，
                platform 默认小红书，status 默认「想法」

        Returns:
            Dict: 新创建的完整条目

        Raises:
            ValueError: 必填字段缺失或枚举/日期非法时抛出
        """
        title = self._normalize_str(data.get("title"))
        if not title:
            raise ValueError("计划标题不能为空")

        platform = self._validate_platform(data.get("platform") or _DEFAULT_PLATFORM)
        status = self._validate_status(data.get("status") or _DEFAULT_STATUS)
        publish_date = self._validate_publish_date(data.get("publish_date"))

        now = datetime.now().isoformat()
        plan = {
            "id": str(uuid.uuid4()),
            "title": title,
            "platform": platform,
            "publish_date": publish_date,
            "status": status,
            "notes": self._normalize_str(data.get("notes")),
            "created_at": now,
            "updated_at": now,
        }

        with self._lock:
            store = self._load_store()
            store["plans"].insert(0, plan)
            self._save_store(store)

        return plan

    def update_plan(self, plan_id: str, data: Dict) -> Optional[Dict]:
        """
        更新计划条目（部分更新，只更新提供的字段）

        Args:
            plan_id: 条目 ID
            data: 待更新字段字典

        Returns:
            Optional[Dict]: 更新后的完整条目；条目不存在返回 None

        Raises:
            ValueError: 显式传入的字段非法时抛出
        """
        if "title" in data and not self._normalize_str(data.get("title")):
            raise ValueError("计划标题不能为空")

        with self._lock:
            store = self._load_store()
            target = None
            for plan in store.get("plans", []):
                if plan.get("id") == plan_id:
                    target = plan
                    break
            if target is None:
                return None

            if "title" in data:
                target["title"] = self._normalize_str(data.get("title"))
            if "platform" in data:
                target["platform"] = self._validate_platform(data.get("platform"))
            if "status" in data:
                target["status"] = self._validate_status(data.get("status"))
            if "publish_date" in data:
                target["publish_date"] = self._validate_publish_date(data.get("publish_date"))
            if "notes" in data:
                target["notes"] = self._normalize_str(data.get("notes"))

            target["updated_at"] = datetime.now().isoformat()
            self._save_store(store)
            return target

    def delete_plan(self, plan_id: str) -> bool:
        """
        删除计划条目

        Returns:
            bool: 删除是否成功，条目不存在返回 False
        """
        with self._lock:
            store = self._load_store()
            plans = store.get("plans", [])
            remaining = [p for p in plans if p.get("id") != plan_id]
            if len(remaining) == len(plans):
                return False

            store["plans"] = remaining
            self._save_store(store)
            return True

    # ==================== 统计 ====================

    def get_stats(self, month: Optional[str] = None) -> Dict:
        """
        按月统计计划情况

        Args:
            month: 统计月份（YYYY-MM），缺省为当前月份

        Returns:
            Dict: {
                month: 统计月份,
                total: 该月计划总数,
                all_total: 全部计划总数,
                by_status: 该月各状态数量,
                by_platform: 该月各平台数量,
            }

        Raises:
            ValueError: 月份格式非法时抛出
        """
        if month is None or not str(month).strip():
            month = datetime.now().strftime("%Y-%m")
        else:
            month = self._validate_month(month)

        store = self._load_store()
        all_plans = store.get("plans", [])
        month_plans = [
            p for p in all_plans
            if str(p.get("publish_date", "")).startswith(month)
        ]

        by_status = {s: 0 for s in STATUSES}
        by_platform = {p: 0 for p in PLATFORMS}
        for plan in month_plans:
            status = plan.get("status")
            if status in by_status:
                by_status[status] += 1
            platform = plan.get("platform")
            if platform in by_platform:
                by_platform[platform] += 1

        return {
            "month": month,
            "total": len(month_plans),
            "all_total": len(all_plans),
            "by_status": by_status,
            "by_platform": by_platform,
        }


_service_instance = None


def get_calendar_service() -> CalendarService:
    """
    获取内容日历服务实例（单例模式）

    Returns:
        CalendarService: 内容日历服务实例
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = CalendarService()
    return _service_instance
