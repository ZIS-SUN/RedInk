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
- publish_time: 计划发布时间（"HH:MM" 或空串，可选）
- status: 状态（idea 想法 / in_progress 制作中 / ready 待发布 / published 已发布）
- notes: 备注
- record_id: 关联的历史记录 ID（可选，空串表示未关联）
- created_at / updated_at: ISO 时间戳

另提供 generate_week_plan()：调用 LLM 生成一周排期预览（不落盘）。
"""

import os
import re
import json
import tempfile
import threading
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from backend.paths import get_data_root
from backend.utils.llm_utils import (
    classify_llm_error,
    get_text_client,
    load_prompt_template,
    load_text_config,
    parse_llm_json,
    resolve_generation_params,
)

logger = logging.getLogger(__name__)

# 守护实例锁的惰性创建（实例可能通过 __new__ 构造，绕过 __init__）
_LOCK_INIT_GUARD = threading.Lock()

# 允许的平台与状态枚举（对外统一使用英文 code，中文文案由前端负责）
PLATFORMS = ("xiaohongshu", "douyin", "gongzhonghao", "bilibili", "shipinhao")
STATUSES = ("idea", "in_progress", "ready", "published")

_DEFAULT_PLATFORM = "xiaohongshu"
_DEFAULT_STATUS = "idea"

# 宽松的时间格式：H:MM / HH:MM，允许全角冒号和秒数（与 analytics 的 publish_time 风格一致）
_TIME_PATTERN = re.compile(r"^(\d{1,2})[:：](\d{1,2})(?:[:：]\d{1,2})?$")

# AI 一周排期的条数上下限
_WEEK_FREQUENCY_MIN = 1
_WEEK_FREQUENCY_MAX = 7


class CalendarStoreCorruptedError(RuntimeError):
    """数据文件损坏（存在但无法解析）时抛出，避免用空数据覆盖真实数据。"""


class CalendarService:
    def __init__(self):
        """
        初始化内容日历服务

        创建 content_calendar 存储目录和数据文件（项目根目录/content_calendar/plans.json）
        """
        self.calendar_dir = str(get_data_root() / "content_calendar")
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

    @classmethod
    def _normalize_time(cls, value) -> str:
        """
        计划发布时间归一化（宽松校验，与 analytics 的 publish_time 风格一致）：
        - None / 空串 -> ""（表示未填写）
        - "H:MM" / "HH:MM" / "HH:MM:SS"（含全角冒号）-> "HH:MM"

        Raises:
            ValueError: 无法解析或时/分越界时抛出
        """
        text = cls._normalize_str(value)
        if not text:
            return ""
        match = _TIME_PATTERN.match(text)
        if not match:
            raise ValueError(f"发布时间格式应为 HH:MM（如 21:30），收到：{text}")
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            raise ValueError(f"发布时间超出范围（时 0-23、分 0-59），收到：{text}")
        return f"{hour:02d}:{minute:02d}"

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
            "publish_time": self._normalize_time(data.get("publish_time")),
            "status": status,
            "notes": self._normalize_str(data.get("notes")),
            "record_id": self._normalize_str(data.get("record_id")),
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
            if "publish_time" in data:
                target["publish_time"] = self._normalize_time(data.get("publish_time"))
            if "notes" in data:
                target["notes"] = self._normalize_str(data.get("notes"))
            if "record_id" in data:
                target["record_id"] = self._normalize_str(data.get("record_id"))

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

    # ==================== 一键转录到数据复盘 ====================

    def log_performance(self, plan_id: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """
        把日历条目一键转录到数据复盘（analytics 表现记录）

        从条目预填 title / platform（转中文名）/ publish_date（条目日期，
        缺失时用当天）/ publish_time / record_id，调用方（用户）显式提供的
        同名字段优先；写入的记录始终带 calendar_plan_id 关联回本条目。

        防重复：同一条目重复转录时更新已有关联记录而非新建
        （幂等行为由 AnalyticsService.upsert_record_for_plan 保证）。

        Args:
            plan_id: 日历条目 ID
            data: 用户补充的字段字典（views / likes 等指标，可覆盖预填字段）

        Returns:
            Optional[Dict]: { record: 表现记录, created: 是否新建 }；
                条目不存在返回 None

        Raises:
            ValueError: 字段校验失败（如 publish_time 格式非法）时抛出
        """
        plan = self.get_plan(plan_id)
        if plan is None:
            return None

        # 惰性导入：避免日历服务在 analytics 环境异常时初始化失败
        from backend.services.analytics import get_analytics_service

        payload = dict(data or {})

        def _prefill(field: str, value) -> None:
            """仅在用户未显式提供非空值时，用日历条目的值预填。"""
            if not str(payload.get(field) or "").strip():
                payload[field] = value

        _prefill("title", plan.get("title") or "")
        # analytics 的 platform 是自由文本中文名，这里把平台 code 转成中文
        platform_code = str(plan.get("platform") or "").strip()
        _prefill("platform", _PLATFORM_LABELS.get(platform_code, platform_code))
        _prefill("publish_date", str(plan.get("publish_date") or "").strip()
                 or datetime.now().strftime("%Y-%m-%d"))
        _prefill("publish_time", plan.get("publish_time") or "")
        # 日历条目已关联历史作品时，把作品 ID 一并带到复盘记录
        _prefill("record_id", plan.get("record_id") or "")

        return get_analytics_service().upsert_record_for_plan(plan_id, payload)

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


# ==================== AI 一周排期（只生成预览，不落盘） ====================

# 平台 code -> 中文名（注入 prompt，让 AI 输出更贴合平台调性）
_PLATFORM_LABELS = {
    "xiaohongshu": "小红书",
    "douyin": "抖音",
    "gongzhonghao": "公众号",
    "bilibili": "B站",
    "shipinhao": "视频号",
}


def next_monday(today: Optional[datetime] = None) -> str:
    """返回下周一的日期字符串（YYYY-MM-DD）。今天是周一也返回下周一。"""
    base = today or datetime.now()
    days_ahead = 7 - base.weekday()
    return (base + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


def _clamp_frequency(value) -> int:
    """每周条数钳制到 1-7，无法解析时回退默认 3。"""
    try:
        freq = int(value)
    except (TypeError, ValueError):
        return 3
    return max(_WEEK_FREQUENCY_MIN, min(_WEEK_FREQUENCY_MAX, freq))


def _build_week_account_context() -> str:
    """
    从数据复盘服务构建账号画像文本（用于注入排期 prompt）。

    无记录、数据不可用或读取异常时一律返回空串（调用方静默忽略），
    绝不因账号数据问题中断排期生成主流程。
    """
    try:
        # 惰性导入：避免排期服务在 analytics 环境异常时初始化失败
        from backend.services.analytics import get_analytics_service
        stats = get_analytics_service().get_stats()
    except Exception as e:
        logger.warning(f"读取账号数据失败，忽略账号画像: {e}")
        return ""

    if not isinstance(stats, dict):
        return ""

    try:
        total_records = int(stats.get("total_records") or 0)
    except (TypeError, ValueError):
        return ""
    if total_records <= 0:
        return ""

    lines = [
        f"- 已发布内容共 {total_records} 篇，平均互动率 {stats.get('avg_engagement_rate', 0)}%"
    ]

    content_types = [
        c for c in (stats.get("content_types") or [])
        if isinstance(c, dict) and c.get("name")
    ]
    best_types = sorted(
        content_types, key=lambda c: float(c.get("engagement_rate") or 0), reverse=True
    )[:3]
    if best_types:
        lines.append(
            "- 表现最好的内容类型：" + "、".join(
                f"{c['name']}（{c.get('count', 0)} 篇，互动率 {c.get('engagement_rate', 0)}%）"
                for c in best_types
            )
        )

    time_slots = [
        s for s in (stats.get("time_slots") or [])
        if isinstance(s, dict) and s.get("name")
    ]
    if time_slots:
        slot_desc = "、".join(
            f"{s['name']}（{s.get('count', 0)} 条，平均互动率 {s.get('avg_engagement', 0)}%）"
            for s in time_slots
        )
        best_slot = max(time_slots, key=lambda s: float(s.get("avg_engagement") or 0))
        lines.append(f"- 发布时段表现：{slot_desc}")
        lines.append(
            f"- 请务必把每条计划的 publish_time 安排在互动率最高的时段（如「{best_slot['name']}」）内"
        )

    return "\n".join(lines)


def _build_week_brand_constraint() -> str:
    """
    读取当前启用的品牌档案并构建品牌人设约束文本（用于注入排期 prompt）。

    无启用品牌、品牌数据不可用或读取异常时一律返回空串（调用方静默忽略），
    绝不因品牌数据问题中断排期生成主流程。
    """
    try:
        # 惰性导入：避免排期服务在 brand 环境异常时初始化失败
        from backend.services.brand import resolve_brand_for_prompt
        from backend.services.rewrite import build_brand_constraint
        return build_brand_constraint(resolve_brand_for_prompt())
    except Exception as e:
        logger.warning(f"读取品牌档案失败，忽略品牌人设: {e}")
        return ""


def _clamp_date_to_week(date_str: str, start: datetime) -> Optional[str]:
    """
    把日期钳制到 [start, start+6] 的一周范围内。

    无法解析的日期返回 None（调用方丢弃该条目）。
    """
    try:
        d = datetime.strptime(str(date_str or "").strip(), "%Y-%m-%d")
    except ValueError:
        return None
    end = start + timedelta(days=6)
    if d < start:
        d = start
    elif d > end:
        d = end
    return d.strftime("%Y-%m-%d")


def _normalize_week_item(item, platform: str, start: datetime) -> Dict:
    """把 AI 返回的单条排期收敛为标准预览结构，坏条目返回空字典（丢弃）。"""
    if not isinstance(item, dict):
        return {}

    title = str(item.get("title") or "").strip()
    if not title:
        return {}

    publish_date = _clamp_date_to_week(item.get("publish_date"), start)
    if publish_date is None:
        return {}

    try:
        publish_time = CalendarService._normalize_time(item.get("publish_time"))
    except ValueError:
        # 时间格式坏掉不至于丢弃整条计划，置空让用户手动补
        publish_time = ""

    return {
        "title": title,
        "platform": platform,
        "publish_date": publish_date,
        "publish_time": publish_time,
        "notes": str(item.get("notes") or "").strip(),
        "status": _DEFAULT_STATUS,
    }


def generate_week_plan(
    niche: str,
    platform: str = _DEFAULT_PLATFORM,
    start_date: Optional[str] = None,
    frequency: int = 3,
    use_account_data: bool = False,
) -> Dict:
    """
    AI 生成一周排期预览（不落盘，由前端确认后逐条调创建接口）。

    Args:
        niche: 领域/赛道（必填）
        platform: 发布平台 code（默认 xiaohongshu，非法值抛 ValueError）
        start_date: 周一日期 YYYY-MM-DD（缺省为下周一，格式非法抛 ValueError）
        frequency: 每周条数（钳制到 1-7）
        use_account_data: 是否结合账号数据画像（无数据时静默忽略）

    Returns:
        成功：{ success: True, plans: [...], account_context_used: bool }
        失败：{ success: False, error: 详细错误文案 }

    Raises:
        ValueError: niche 为空 / platform 非法 / start_date 格式非法时抛出
    """
    niche = str(niche or "").strip()
    if not niche:
        raise ValueError("领域/赛道不能为空")

    # 参数校验复用 CalendarService 的枚举/日期校验
    platform = CalendarService._validate_platform(platform or _DEFAULT_PLATFORM)
    start_date = str(start_date or "").strip() or next_monday()
    start_date = CalendarService._validate_publish_date(start_date)
    frequency = _clamp_frequency(frequency)

    account_context_used = False
    try:
        logger.info(
            f"开始生成一周排期: niche={niche[:50]}, platform={platform}, "
            f"start_date={start_date}, frequency={frequency}, "
            f"use_account_data={use_account_data}"
        )

        account_context = ""
        if use_account_data:
            account_context = _build_week_account_context()
            if account_context:
                account_context_used = True
                logger.info("已注入账号画像到排期 prompt")
            else:
                logger.info("use_account_data=True 但暂无账号数据，忽略账号画像")

        prompt_template = load_prompt_template("backend/prompts/calendar_plan_prompt.txt")
        prompt = prompt_template.format(
            niche=niche,
            platform=_PLATFORM_LABELS.get(platform, platform),
            start_date=start_date,
            frequency=frequency,
            account_context=account_context or "未提供",
        )

        # 品牌人设约束：有启用品牌时以字符串追加方式注入（软失败，绝不中断排期）
        brand_constraint = _build_week_brand_constraint()
        if brand_constraint:
            logger.info("已注入品牌人设约束到排期 prompt")
            prompt += brand_constraint + (
                "\n\n排期中的每条选题标题与备注都应贴合以上品牌人设的定位、"
                "目标人群与语气风格，并且不出现任何禁用词。"
            )

        text_config = load_text_config()
        client = get_text_client(text_config)
        model, temperature, max_output_tokens = resolve_generation_params(
            text_config, default_max_output_tokens=4000
        )

        logger.info(f"调用文本生成 API: model={model}, temperature={temperature}")
        response_text = client.generate_text(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        plan_data = parse_llm_json(response_text)

        raw_plans = plan_data.get("plans", [])
        if not isinstance(raw_plans, list):
            raw_plans = []

        start = datetime.strptime(start_date, "%Y-%m-%d")
        plans = [
            p for p in (_normalize_week_item(item, platform, start) for item in raw_plans)
            if p
        ]

        if not plans:
            logger.error("AI 返回结果中没有有效的排期条目")
            raise ValueError("AI 未返回有效的排期内容，请重试")

        # 条数多于 frequency 时截断（少于时保留实际条数）
        plans = plans[:frequency]

        logger.info(f"一周排期生成完成: {len(plans)} 条")
        return {
            "success": True,
            "plans": plans,
            "account_context_used": account_context_used,
        }

    except Exception as e:
        logger.error(f"一周排期生成失败: {e}")
        return {
            "success": False,
            "error": classify_llm_error(e, task_label="一周排期生成失败"),
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
