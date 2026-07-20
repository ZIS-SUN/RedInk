"""
数据复盘（表现分析）服务

负责已发布内容表现记录的增删改查、统计概览与 AI 复盘洞察：
- 数据落盘到项目根目录 analytics_data/records.json（独立目录，与 history/brand 互不影响）
- 与 brand 服务相同的稳健写入方式：threading 锁 + 临时文件 + os.replace 原子替换
- 手动录入，不做任何平台自动抓取

单条表现记录字段：
- id: UUID
- title: 内容标题（必填）
- platform: 发布平台（必填，如"小红书"/"抖音"）
- publish_date: 发布日期（YYYY-MM-DD 字符串）
- publish_time: 发布时间（"HH:MM" 字符串或空串，可选）
- content_type: 内容类型/标签（如"干货教程"/"好物种草"）
- views: 曝光/播放数
- likes: 点赞数
- collects: 收藏数
- comments: 评论数
- shares: 转发数
- followers_gained: 涨粉数
- notes: 备注
- record_id: 关联的历史作品 ID（可选，空串表示未关联；旧记录可能缺失该字段）
- calendar_plan_id: 关联的内容日历条目 ID（可选，空串表示未关联；旧记录可能缺失该字段）
- created_at / updated_at: ISO 时间戳
"""

import base64
import os
import json
import logging
import re
import tempfile
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.errors import AppError, AppErrorException
from backend.paths import get_data_root, resource_path
from backend.utils.llm_utils import (
    classify_llm_error,
    generate_and_parse_json,
    get_text_client,
    load_prompt_template,
    load_text_config,
    parse_llm_json,
    resolve_generation_params,
)

logger = logging.getLogger(__name__)

# 守护实例锁的惰性创建（实例可能通过 __new__ 构造，绕过 __init__）
_LOCK_INIT_GUARD = threading.Lock()

# 记录中允许由调用方写入的字段
_EDITABLE_STR_FIELDS = (
    "title", "platform", "publish_date", "publish_time", "content_type", "notes",
    "record_id", "calendar_plan_id",
)
_EDITABLE_INT_FIELDS = ("views", "likes", "collects", "comments", "shares", "followers_gained")

# 批量导入单次上限
_BATCH_MAX_RECORDS = 200

# 发布时段划分：(名称, 起始小时含, 结束小时不含)；深夜跨零点单独处理
_TIME_SLOTS = (
    ("早晨 6-9", 6, 9),
    ("上午 9-12", 9, 12),
    ("午间 12-14", 12, 14),
    ("下午 14-18", 14, 18),
    ("晚间 18-22", 18, 22),
    ("深夜 22-6", 22, 6),
)

# 宽松的时间格式：H:MM / HH:MM，允许全角冒号和秒数
_TIME_PATTERN = re.compile(r"^(\d{1,2})[:：](\d{1,2})(?:[:：]\d{1,2})?$")

# ==================== 行业基准（红黄绿评级） ====================

# 评级常量：低于下限 red、达到达标线 green、两者之间 yellow
RATING_RED = "red"
RATING_YELLOW = "yellow"
RATING_GREEN = "green"

# 行业基准 JSON 数据文件（随包分发；基准调整时只需更新该文件）
_BENCHMARKS_FILE_REL_PATH = "backend/data/analytics_benchmarks.json"

# 内置默认基准（JSON 缺失/损坏时的回退值，须与 analytics_benchmarks.json 同步）。
# 数值为公开行业经验值，仅供参考；red_below=红线下限，green_at=达标线
_DEFAULT_BENCHMARK_METRICS: Dict[str, Dict] = {
    "engagement_rate": {
        "label": "互动率", "formula": "（点赞+收藏+评论+转发）/ 曝光", "unit": "%",
        "red_below": 3.0, "green_at": 5.0,
        "note": "图文内容互动率 ≥5% 达标；3%-5% 待提升；低于 3% 偏低，选题或封面标题需要优化",
    },
    "like_rate": {
        "label": "点赞率", "formula": "点赞 / 曝光", "unit": "%",
        "red_below": 1.5, "green_at": 3.0,
        "note": "点赞率 ≥3% 达标；低于 1.5% 通常说明内容共鸣不足或封面进来的流量不精准",
    },
    "collect_rate": {
        "label": "收藏率", "formula": "收藏 / 曝光", "unit": "%",
        "red_below": 1.0, "green_at": 3.0,
        "note": "收藏率 ≥3% 达标；收藏是干货留存价值的信号，低于 1% 建议增加可保存的清单/步骤类信息",
    },
    "comment_rate": {
        "label": "评论率", "formula": "评论 / 曝光", "unit": "%",
        "red_below": 0.2, "green_at": 0.5,
        "note": "评论率 ≥0.5% 达标；低于 0.2% 建议在文末增加互动提问或争议性话题引导讨论",
    },
}

# 回退时的基准元信息（version 固定为 builtin，便于排查是否读到了 JSON）
_DEFAULT_BENCHMARKS_META = {
    "version": "builtin",
    "updated_at": "2026-07-20",
    "source": "公开行业经验值，仅供参考",
}


def _validate_benchmarks_data(metrics) -> bool:
    """校验基准 JSON 的结构完整性（缺字段/类型不对视为损坏，整体回退）。"""
    if not isinstance(metrics, dict) or not metrics:
        return False
    for rule in metrics.values():
        if not isinstance(rule, dict) or not str(rule.get("label") or "").strip():
            return False
        red_below, green_at = rule.get("red_below"), rule.get("green_at")
        for value in (red_below, green_at):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False
        if red_below > green_at:
            return False
    return True


def _load_benchmarks() -> Tuple[Dict[str, Dict], Dict[str, str]]:
    """
    读取外置行业基准 JSON，返回 (指标规则表, 元信息 {version, updated_at, source})。

    任何读取/解析/结构错误都整体回退到内置默认值（与 checklist 的
    platform_rules.json 相同的策略）——基准展示不能因数据文件问题而不可用。
    """
    try:
        benchmarks_path = resource_path(_BENCHMARKS_FILE_REL_PATH)
        with open(benchmarks_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        metrics = data.get("metrics") if isinstance(data, dict) else None
        if not _validate_benchmarks_data(metrics):
            raise ValueError("analytics_benchmarks.json 结构不完整或字段类型非法")
        meta = {
            "version": str(data.get("version") or "unknown"),
            "updated_at": str(data.get("updated_at") or "unknown"),
            "source": str(data.get("source") or _DEFAULT_BENCHMARKS_META["source"]),
        }
        logger.info(
            "行业基准已从 JSON 加载: version=%s, updated_at=%s",
            meta["version"], meta["updated_at"],
        )
        return metrics, meta
    except Exception as e:
        logger.warning("行业基准 JSON 读取失败，回退内置默认基准: %s", e)
        return dict(_DEFAULT_BENCHMARK_METRICS), dict(_DEFAULT_BENCHMARKS_META)


# 模块加载（启动）时读取一次；失败自动回退内置默认，保证功能可用
ANALYTICS_BENCHMARKS, ANALYTICS_BENCHMARKS_META = _load_benchmarks()


def rate_by_benchmark(metric_key: str, value: Optional[float]) -> Optional[str]:
    """
    按行业基准给指标值打红黄绿评级。

    Args:
        metric_key: 指标键（engagement_rate / like_rate / collect_rate / comment_rate）
        value: 指标值（百分比数值，如 5.2 表示 5.2%）；None 表示无曝光数据无法评级

    Returns:
        'red' | 'yellow' | 'green'；无对应基准或值为 None 时返回 None
    """
    rule = ANALYTICS_BENCHMARKS.get(metric_key)
    if rule is None or value is None:
        return None
    if value >= rule["green_at"]:
        return RATING_GREEN
    if value < rule["red_below"]:
        return RATING_RED
    return RATING_YELLOW


# ==================== 截图 OCR 导入（B3）常量 ====================

# 单次最多识别的截图张数
_OCR_MAX_IMAGES = 3
# 单张截图 base64 解码后的大小上限（10MB），防止滥用
_OCR_MAX_IMAGE_BYTES = 10 * 1024 * 1024
# OCR 返回行的全部字段（缺失为 None，前端预览时由用户补全）
_OCR_STR_FIELDS = ("title", "publish_date")
_OCR_INT_FIELDS = ("views", "likes", "collects", "comments", "shares", "followers_gained")
# 中文数量单位 -> 倍数（模型偶尔不换算时后端二次清洗）
_CN_NUMBER_UNITS = (("亿", 100000000), ("万", 10000), ("w", 10000), ("W", 10000))
# OCR 识别的日期归一化：2026-7-1 / 2026/07/01 / 2026.7.1 / 2026年7月1日
_OCR_DATE_PATTERN = re.compile(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})")


class AnalyticsStoreCorruptedError(RuntimeError):
    """数据文件损坏（存在但无法解析）时抛出，避免用空数据覆盖真实数据。"""


class AnalyticsService:
    def __init__(self):
        """
        初始化数据复盘服务

        创建 analytics_data 存储目录和数据文件（项目根目录/analytics_data/records.json）
        """
        self.analytics_dir = str(get_data_root() / "analytics_data")
        os.makedirs(self.analytics_dir, exist_ok=True)

        self.store_file = os.path.join(self.analytics_dir, "records.json")
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
                self._atomic_write_json(self.store_file, {"records": []})

    def _load_store(self) -> Dict:
        """
        加载数据文件

        Raises:
            AnalyticsStoreCorruptedError: 文件存在但无法解析/结构异常时抛出，
                绝不静默返回空库（避免调用方把空库写回覆盖真实数据）。
        """
        with self._lock:
            if not os.path.exists(self.store_file):
                return {"records": []}
            try:
                with open(self.store_file, "r", encoding="utf-8") as f:
                    store = json.load(f)
            except Exception as e:
                logger.error("表现数据文件解析失败，保留原文件不覆盖: %s (%s)", self.store_file, e)
                raise AnalyticsStoreCorruptedError(
                    f"表现数据文件损坏，已保留原文件: {self.store_file}"
                ) from e

            if not isinstance(store, dict) or not isinstance(store.get("records"), list):
                logger.error("表现数据文件结构异常，保留原文件不覆盖: %s", self.store_file)
                raise AnalyticsStoreCorruptedError(
                    f"表现数据文件结构异常，已保留原文件: {self.store_file}"
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
    def _normalize_int(value) -> int:
        """数值字段归一化：无法解析或为负时返回 0。"""
        if value is None or value == "":
            return 0
        try:
            number = int(float(value))
        except (TypeError, ValueError):
            return 0
        return max(number, 0)

    @classmethod
    def _normalize_time(cls, value) -> str:
        """
        发布时间归一化（宽松校验）：
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

    # ==================== CRUD ====================

    def list_records(self) -> Dict:
        """
        获取全部表现记录

        Returns:
            Dict: { records: [...] }（按发布日期倒序，其次按创建时间倒序）。
            每条记录附带 metrics 计算字段（各指标值与红黄绿评级，纯计算不落盘）。
        """
        store = self._load_store()
        records = list(store.get("records", []))
        records.sort(
            key=lambda r: (str(r.get("publish_date") or ""), str(r.get("created_at") or "")),
            reverse=True,
        )
        # 返回附加了指标评级的副本，避免把计算字段写回存储
        return {"records": [self._with_record_metrics(r) for r in records]}

    def get_record(self, record_id: str) -> Optional[Dict]:
        """按 ID 获取记录，不存在返回 None。"""
        store = self._load_store()
        for record in store.get("records", []):
            if record.get("id") == record_id:
                return record
        return None

    def _build_record(self, data: Dict) -> Dict:
        """
        由入参构建一条完整记录（含校验与归一化，不落盘）。

        Raises:
            ValueError: title / platform 为空，或 publish_time 格式非法时抛出
        """
        title = self._normalize_str(data.get("title"))
        platform = self._normalize_str(data.get("platform"))
        if not title:
            raise ValueError("内容标题不能为空")
        if not platform:
            raise ValueError("发布平台不能为空")

        now = datetime.now().isoformat()
        return {
            "id": str(uuid.uuid4()),
            "title": title,
            "platform": platform,
            "publish_date": self._normalize_str(data.get("publish_date")),
            "publish_time": self._normalize_time(data.get("publish_time")),
            "content_type": self._normalize_str(data.get("content_type")),
            "views": self._normalize_int(data.get("views")),
            "likes": self._normalize_int(data.get("likes")),
            "collects": self._normalize_int(data.get("collects")),
            "comments": self._normalize_int(data.get("comments")),
            "shares": self._normalize_int(data.get("shares")),
            "followers_gained": self._normalize_int(data.get("followers_gained")),
            "notes": self._normalize_str(data.get("notes")),
            "record_id": self._normalize_str(data.get("record_id")),
            "calendar_plan_id": self._normalize_str(data.get("calendar_plan_id")),
            "created_at": now,
            "updated_at": now,
        }

    def create_record(self, data: Dict) -> Dict:
        """
        创建表现记录

        Args:
            data: 记录字段字典，title 和 platform 必填，其余可选

        Returns:
            Dict: 新创建的完整记录

        Raises:
            ValueError: title 或 platform 为空时抛出
        """
        record = self._build_record(data)

        with self._lock:
            store = self._load_store()
            store["records"].insert(0, record)
            self._save_store(store)

        return record

    def create_records_batch(self, items: List) -> Dict:
        """
        批量创建表现记录（逐条走与单条创建相同的校验，一次原子落盘）

        Args:
            items: 记录字段字典列表，每条结构同 create_record 的入参

        Returns:
            Dict: { created: 成功条数, failed: [{index, error}] }

        Raises:
            ValueError: items 不是非空列表，或超出单次上限（200 条）时抛出
        """
        if not isinstance(items, list) or not items:
            raise ValueError("records 必须是非空数组")
        if len(items) > _BATCH_MAX_RECORDS:
            raise ValueError(f"一次最多导入 {_BATCH_MAX_RECORDS} 条记录，当前 {len(items)} 条")

        created: List[Dict] = []
        failed: List[Dict] = []
        for index, item in enumerate(items):
            try:
                if not isinstance(item, dict):
                    raise ValueError("记录格式错误，应为对象")
                created.append(self._build_record(item))
            except ValueError as e:
                failed.append({"index": index, "error": str(e)})

        if created:
            with self._lock:
                store = self._load_store()
                # 整批插到最前，保持导入时的相对顺序
                store["records"][:0] = created
                self._save_store(store)

        return {"created": len(created), "failed": failed}

    def update_record(self, record_id: str, data: Dict) -> Optional[Dict]:
        """
        更新表现记录（部分更新，只更新提供的字段）

        Args:
            record_id: 记录 ID
            data: 待更新字段字典

        Returns:
            Optional[Dict]: 更新后的完整记录；记录不存在返回 None

        Raises:
            ValueError: 显式传入空 title / platform 时抛出
        """
        if "title" in data and not self._normalize_str(data.get("title")):
            raise ValueError("内容标题不能为空")
        if "platform" in data and not self._normalize_str(data.get("platform")):
            raise ValueError("发布平台不能为空")

        with self._lock:
            store = self._load_store()
            target = None
            for record in store.get("records", []):
                if record.get("id") == record_id:
                    target = record
                    break
            if target is None:
                return None

            for field in _EDITABLE_STR_FIELDS:
                if field in data:
                    if field == "publish_time":
                        target[field] = self._normalize_time(data.get(field))
                    else:
                        target[field] = self._normalize_str(data.get(field))
            for field in _EDITABLE_INT_FIELDS:
                if field in data:
                    target[field] = self._normalize_int(data.get(field))

            target["updated_at"] = datetime.now().isoformat()
            self._save_store(store)
            return target

    def upsert_record_for_plan(self, calendar_plan_id: str, data: Dict) -> Dict:
        """
        按内容日历条目 ID 幂等写入表现记录（日历「一键转录到复盘」使用）

        同一日历条目重复转录时更新已有关联记录（按 calendar_plan_id 匹配，
        取最早创建的一条），而不是重复新建。

        Args:
            calendar_plan_id: 内容日历条目 ID（必填）
            data: 记录字段字典（结构同 create_record / update_record 的入参）

        Returns:
            Dict: { record: 完整记录, created: 是否为新建（False 表示更新了已有记录） }

        Raises:
            ValueError: calendar_plan_id 为空，或字段校验失败时抛出
        """
        calendar_plan_id = self._normalize_str(calendar_plan_id)
        if not calendar_plan_id:
            raise ValueError("calendar_plan_id 不能为空")

        payload = dict(data or {})
        payload["calendar_plan_id"] = calendar_plan_id

        # RLock 可重入：持锁期间「查找已有关联 -> 创建或更新」整体原子
        with self._lock:
            store = self._load_store()
            existing = [
                r for r in store.get("records", [])
                if r.get("calendar_plan_id") == calendar_plan_id
            ]
            if existing:
                # 极端情况下（老数据）可能有多条关联，稳定取最早创建的一条更新
                target = min(existing, key=lambda r: str(r.get("created_at") or ""))
                record = self.update_record(target.get("id"), payload)
                return {"record": record, "created": False}

            record = self.create_record(payload)
            return {"record": record, "created": True}

    def delete_record(self, record_id: str) -> bool:
        """
        删除表现记录

        Returns:
            bool: 删除是否成功，记录不存在返回 False
        """
        with self._lock:
            store = self._load_store()
            records = store.get("records", [])
            remaining = [r for r in records if r.get("id") != record_id]
            if len(remaining) == len(records):
                return False

            store["records"] = remaining
            self._save_store(store)
            return True

    # ==================== 统计概览 ====================

    @staticmethod
    def _engagements(record: Dict) -> int:
        """单条记录的互动总数：点赞 + 收藏 + 评论 + 转发。"""
        return (
            int(record.get("likes") or 0)
            + int(record.get("collects") or 0)
            + int(record.get("comments") or 0)
            + int(record.get("shares") or 0)
        )

    @classmethod
    def _engagement_rate(cls, records: List[Dict]) -> float:
        """一组记录的互动率（百分比，保留两位小数）：总互动 / 总曝光。"""
        total_views = sum(int(r.get("views") or 0) for r in records)
        if total_views <= 0:
            return 0.0
        total_engagements = sum(cls._engagements(r) for r in records)
        return round(total_engagements / total_views * 100, 2)

    # ==================== 行业基准评级（B10） ====================

    @classmethod
    def _metric_values(cls, records: List[Dict]) -> Dict[str, Optional[float]]:
        """
        计算一组记录的各基准指标值（百分比，保留两位小数）。

        无曝光数据时全部为 None（表示无法评级，与 0% 语义不同）。
        指标键与 analytics_benchmarks.json 的 metrics 键一一对应。
        """
        total_views = sum(int(r.get("views") or 0) for r in records)
        if total_views <= 0:
            return {
                "engagement_rate": None, "like_rate": None,
                "collect_rate": None, "comment_rate": None,
            }

        def _pct(numerator: int) -> float:
            return round(numerator / total_views * 100, 2)

        return {
            "engagement_rate": _pct(sum(cls._engagements(r) for r in records)),
            "like_rate": _pct(sum(int(r.get("likes") or 0) for r in records)),
            "collect_rate": _pct(sum(int(r.get("collects") or 0) for r in records)),
            "comment_rate": _pct(sum(int(r.get("comments") or 0) for r in records)),
        }

    @classmethod
    def _build_metric_ratings(cls, records: List[Dict]) -> Dict[str, Dict]:
        """
        汇总层的指标评级（带基准阈值与说明，供前端指标卡展示）。

        Returns:
            { 指标键: { value, rating, label, red_below, green_at, note } }
            只输出基准表中存在规则的指标。
        """
        ratings: Dict[str, Dict] = {}
        for key, value in cls._metric_values(records).items():
            rule = ANALYTICS_BENCHMARKS.get(key)
            if not rule:
                continue
            ratings[key] = {
                "value": value,
                "rating": rate_by_benchmark(key, value),
                "label": rule.get("label") or key,
                "red_below": rule.get("red_below"),
                "green_at": rule.get("green_at"),
                "note": str(rule.get("note") or ""),
            }
        return ratings

    @classmethod
    def _with_record_metrics(cls, record: Dict) -> Dict:
        """
        返回附加了 metrics 计算字段的记录副本（不修改入参、不落盘）。

        metrics 结构：{ 指标键: { value: 百分比值或 None, rating: red/yellow/green/None } }
        """
        metrics = {
            key: {"value": value, "rating": rate_by_benchmark(key, value)}
            for key, value in cls._metric_values([record]).items()
            if key in ANALYTICS_BENCHMARKS
        }
        return {**record, "metrics": metrics}

    def get_stats(self) -> Dict:
        """
        统计概览

        Returns:
            Dict: {
                total_records / total_views / total_likes / total_collects /
                total_comments / total_shares / total_followers_gained,
                avg_engagement_rate: 平均互动率（百分比）,
                platforms: 各平台汇总列表（按曝光倒序）,
                content_types: 各内容类型汇总列表（按曝光倒序）,
                trend: 按月趋势（升序，[{month, count, views, engagements}]）,
                time_slots: 发布时段汇总（仅含有 publish_time 的记录，
                    [{name, count, avg_engagement}]，按时段固定顺序）,
                metric_ratings: 各基准指标的汇总评级（B10 新增，
                    {指标键: {value, rating, label, red_below, green_at, note}}）,
                benchmarks_meta: 基准表元信息（B10 新增，{version, updated_at, source}）,
            }

        注意：已有字段的结构/名字保持向后兼容，只允许新增字段。
        """
        records = self._load_store().get("records", [])

        stats: Dict[str, Any] = {
            "total_records": len(records),
            "total_views": sum(int(r.get("views") or 0) for r in records),
            "total_likes": sum(int(r.get("likes") or 0) for r in records),
            "total_collects": sum(int(r.get("collects") or 0) for r in records),
            "total_comments": sum(int(r.get("comments") or 0) for r in records),
            "total_shares": sum(int(r.get("shares") or 0) for r in records),
            "total_followers_gained": sum(int(r.get("followers_gained") or 0) for r in records),
            "avg_engagement_rate": self._engagement_rate(records),
        }

        stats["platforms"] = self._group_summary(records, "platform")
        stats["content_types"] = self._group_summary(records, "content_type")
        stats["trend"] = self._monthly_trend(records)
        stats["time_slots"] = self._time_slot_summary(records)
        # B10 纯增量字段：汇总指标的红黄绿评级与基准元信息
        stats["metric_ratings"] = self._build_metric_ratings(records)
        stats["benchmarks_meta"] = dict(ANALYTICS_BENCHMARKS_META)
        return stats

    @classmethod
    def _group_summary(cls, records: List[Dict], field: str) -> List[Dict]:
        """按指定字段分组汇总（空值归入「未分类」），按曝光倒序。"""
        groups: Dict[str, List[Dict]] = {}
        for record in records:
            key = str(record.get(field) or "").strip() or "未分类"
            groups.setdefault(key, []).append(record)

        summary = []
        for name, group in groups.items():
            views = sum(int(r.get("views") or 0) for r in group)
            engagement_rate = cls._engagement_rate(group)
            summary.append({
                "name": name,
                "count": len(group),
                "views": views,
                "likes": sum(int(r.get("likes") or 0) for r in group),
                "collects": sum(int(r.get("collects") or 0) for r in group),
                "comments": sum(int(r.get("comments") or 0) for r in group),
                "shares": sum(int(r.get("shares") or 0) for r in group),
                "followers_gained": sum(int(r.get("followers_gained") or 0) for r in group),
                "engagement_rate": engagement_rate,
                # B10 纯增量字段：无曝光数据时不评级（None）
                "engagement_rating": rate_by_benchmark(
                    "engagement_rate", engagement_rate if views > 0 else None
                ),
            })
        summary.sort(key=lambda item: item["views"], reverse=True)
        return summary

    @staticmethod
    def _slot_name_for_hour(hour: int) -> str:
        """把小时（0-23）映射到发布时段名称，深夜 22-6 跨零点。"""
        for name, start, end in _TIME_SLOTS:
            if start < end and start <= hour < end:
                return name
        return _TIME_SLOTS[-1][0]  # 深夜 22-6（22-24 与 0-6）

    @classmethod
    def _time_slot_summary(cls, records: List[Dict]) -> List[Dict]:
        """
        按发布时段汇总（早晨/上午/午间/下午/晚间/深夜）。

        没有 publish_time（或格式无法解析）的记录不计入；
        只输出 count > 0 的时段，按 _TIME_SLOTS 固定顺序排列。
        """
        buckets: Dict[str, List[Dict]] = {}
        for record in records:
            time_str = str(record.get("publish_time") or "").strip()
            match = _TIME_PATTERN.match(time_str)
            if not match:
                continue
            hour = int(match.group(1))
            if hour > 23:
                continue
            buckets.setdefault(cls._slot_name_for_hour(hour), []).append(record)

        summary = []
        for name, _, _ in _TIME_SLOTS:
            group = buckets.get(name)
            if not group:
                continue
            summary.append({
                "name": name,
                "count": len(group),
                "avg_engagement": cls._engagement_rate(group),
            })
        return summary

    @classmethod
    def _monthly_trend(cls, records: List[Dict]) -> List[Dict]:
        """按发布月份（YYYY-MM）的简单趋势，缺失日期的记录跳过，按月份升序。"""
        buckets: Dict[str, List[Dict]] = {}
        for record in records:
            date_str = str(record.get("publish_date") or "").strip()
            match = re.match(r"^(\d{4}-\d{2})", date_str)
            if not match:
                continue
            buckets.setdefault(match.group(1), []).append(record)

        trend = []
        for month in sorted(buckets.keys()):
            group = buckets[month]
            trend.append({
                "month": month,
                "count": len(group),
                "views": sum(int(r.get("views") or 0) for r in group),
                "engagements": sum(cls._engagements(r) for r in group),
                "followers_gained": sum(int(r.get("followers_gained") or 0) for r in group),
            })
        return trend

    # ==================== 截图 OCR 智能回填（B3） ====================

    @staticmethod
    def _decode_ocr_images(images_base64) -> List[bytes]:
        """
        校验并解码 OCR 导入的 base64 图片列表。

        接受裸 base64 或带 data URL 前缀（data:image/png;base64,...）的字符串。

        Raises:
            ValueError: 非 1-3 张、base64 非法、或单张解码后超过 10MB 时抛出
        """
        if not isinstance(images_base64, list) or not images_base64:
            raise ValueError("images 必须是非空数组（1-3 张截图的 base64 字符串）")
        if len(images_base64) > _OCR_MAX_IMAGES:
            raise ValueError(
                f"一次最多识别 {_OCR_MAX_IMAGES} 张截图，当前 {len(images_base64)} 张"
            )

        images: List[bytes] = []
        for index, item in enumerate(images_base64):
            label = f"第 {index + 1} 张图片"
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{label}数据为空或格式错误")

            payload = item.strip()
            # 允许 data URL 前缀，取逗号后的 base64 部分
            if payload.startswith("data:"):
                _, _, payload = payload.partition(",")
            # 去掉换行/空白后再严格校验 base64
            payload = re.sub(r"\s+", "", payload)
            if not payload:
                raise ValueError(f"{label}数据为空或格式错误")
            try:
                data = base64.b64decode(payload, validate=True)
            except Exception:
                raise ValueError(f"{label}不是合法的 base64 图片数据")
            if not data:
                raise ValueError(f"{label}数据为空或格式错误")
            if len(data) > _OCR_MAX_IMAGE_BYTES:
                size_mb = len(data) / (1024 * 1024)
                raise ValueError(
                    f"{label}解码后 {size_mb:.1f}MB，超过单张 10MB 上限，请压缩或裁剪后重试"
                )
            images.append(data)
        return images

    @staticmethod
    def _clean_ocr_number(value) -> Optional[int]:
        """
        OCR 数字字段的后端二次清洗（模型没按要求换算时兜底）：
        - None / 空串 / 无法解析 / 负数 -> None（表示识别失败，与 0 区分）
        - int / float -> 非负整数
        - "1.2万" / "3.5w" / "2.3亿" / "1,024" -> 换算后的整数
        """
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            number = int(value)
            return number if number >= 0 else None

        text = str(value).strip().replace(",", "").replace("，", "").replace(" ", "").replace("+", "")
        if not text:
            return None
        multiplier = 1
        for unit, factor in _CN_NUMBER_UNITS:
            if text.endswith(unit):
                multiplier = factor
                text = text[: -len(unit)]
                break
        try:
            number = round(float(text) * multiplier)
        except (TypeError, ValueError):
            return None
        return number if number >= 0 else None

    @classmethod
    def _clean_ocr_date(cls, value) -> Optional[str]:
        """OCR 日期字段清洗：归一化为 YYYY-MM-DD，无法解析返回 None。"""
        text = cls._normalize_str(value)
        if not text:
            return None
        match = _OCR_DATE_PATTERN.search(text)
        if not match:
            return None
        year, month, day = match.group(1), int(match.group(2)), int(match.group(3))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        return f"{year}-{month:02d}-{day:02d}"

    @classmethod
    def _clean_ocr_row(cls, row: Dict) -> Dict:
        """
        清洗单行 OCR 识别结果，输出固定字段结构（识别不了的字段为 None）。
        """
        cleaned: Dict[str, Any] = {}
        title = cls._normalize_str(row.get("title"))
        cleaned["title"] = title or None
        cleaned["publish_date"] = cls._clean_ocr_date(row.get("publish_date"))
        for field in _OCR_INT_FIELDS:
            cleaned[field] = cls._clean_ocr_number(row.get(field))
        return cleaned

    @staticmethod
    def _is_empty_ocr_row(row: Dict) -> bool:
        """标题与全部数字字段都是 None 的行视为无效行，过滤掉。"""
        if row.get("title"):
            return False
        return all(row.get(field) is None for field in _OCR_INT_FIELDS)

    @staticmethod
    def _parse_ocr_rows(response_text: str) -> List[Dict]:
        """
        解析模型返回的 JSON 数组（多级容错）：

        1. 直接 json.loads 原文
        2. 从 ```json ... ``` / ``` ... ``` 代码块中提取
        3. 截取首个 '[' 到最后一个 ']' 之间的内容（应对前后杂文本）
        4. 兜底走共享的 parse_llm_json（含保守 JSON 修复），
           兼容模型把数组包在 { "rows": [...] } 之类对象里的情况

        Raises:
            ValueError: 所有策略均失败时抛出
        """
        def _extract_rows(value) -> Optional[List]:
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                # 模型偶尔把数组包进对象：优先常见键名，再兜底取第一个列表值
                for key in ("rows", "records", "data", "items", "list"):
                    if isinstance(value.get(key), list):
                        return value[key]
                for candidate in value.values():
                    if isinstance(candidate, list):
                        return candidate
            return None

        candidates = [response_text]
        fence_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", response_text)
        if fence_match:
            candidates.append(fence_match.group(1).strip())
        start_idx = response_text.find("[")
        end_idx = response_text.rfind("]")
        if start_idx != -1 and end_idx > start_idx:
            candidates.append(response_text[start_idx:end_idx + 1])

        for candidate in candidates:
            try:
                rows = _extract_rows(json.loads(candidate))
            except (json.JSONDecodeError, ValueError):
                continue
            if rows is not None:
                return rows

        # 最后兜底：共享解析器带保守修复能力（尾逗号/单引号/裸换行等）
        try:
            rows = _extract_rows(parse_llm_json(response_text))
            if rows is not None:
                return rows
        except ValueError:
            pass
        raise ValueError("AI 返回的内容不是可解析的 JSON 数组")

    @staticmethod
    def _resolve_vision_provider(text_config: dict) -> dict:
        """
        取出当前激活服务商的完整配置（校验逻辑与 llm_utils.get_text_client
        一致，但只返回配置不构建客户端——视觉调用由 vision_ocr 模块自行分发）。

        Raises:
            ValueError: 无服务商配置 / 激活服务商不存在 / 未配置 API Key
        """
        active_provider = text_config.get("active_provider", "")
        providers = text_config.get("providers", {})
        if not providers:
            raise ValueError(
                "未找到任何文本生成服务商配置。\n"
                "解决方案：在系统设置页面添加文本生成服务商"
            )
        if active_provider not in providers:
            available = ", ".join(providers.keys())
            raise ValueError(
                f"未找到文本生成服务商配置: {active_provider}\n"
                f"可用的服务商: {available}\n"
                "解决方案：在系统设置中选择一个可用的服务商"
            )
        provider_config = providers.get(active_provider) or {}
        if not provider_config.get("api_key"):
            raise ValueError(
                f"文本服务商 {active_provider} 未配置 API Key\n"
                "解决方案：在系统设置页面编辑该服务商，填写 API Key"
            )
        return provider_config

    @staticmethod
    def _call_vision_model(
        provider_config: dict, *, prompt: str, images: List[bytes],
        model: str, max_output_tokens: int,
    ) -> str:
        """调用多模态视觉识别（惰性导入，便于测试 mock 与保持 CRUD 路径轻量）。"""
        from backend.utils.vision_ocr import generate_vision_text
        return generate_vision_text(
            provider_config,
            prompt=prompt,
            images=images,
            model=model,
            max_output_tokens=max_output_tokens,
        )

    @staticmethod
    def _load_ocr_prompt_template() -> str:
        """加载截图 OCR 识别提示词模板。"""
        return load_prompt_template("backend/prompts/analytics_ocr_prompt.txt")

    def ocr_import(self, images_base64: List) -> Dict[str, Any]:
        """
        截图 OCR 智能回填：识别 1-3 张创作者后台数据截图，返回结构化行数组。

        只做识别不落盘——识别结果由前端预览确认后走既有批量创建接口入库。

        Args:
            images_base64: base64 字符串列表（允许 data URL 前缀），1-3 张，
                单张解码后 ≤10MB

        Returns:
            Dict: { rows: [{title, publish_date, views, likes, collects,
                comments, shares, followers_gained}], count, model }
                识别不了的字段为 None

        Raises:
            ValueError: 图片参数校验失败 / 文本服务商配置缺失（走 400）
            AppErrorException: 模型不支持视觉或识别/解析失败
                （结构化错误，建议文案明确「请改用手动录入」）
        """
        images = self._decode_ocr_images(images_base64)

        # 配置类错误（无服务商/无 API Key）保持 ValueError 语义，走 400 校验错误
        text_config = self._load_text_config()
        provider_config = self._resolve_vision_provider(text_config)
        model, _temperature, max_output_tokens = resolve_generation_params(
            text_config, default_max_output_tokens=4000
        )
        # 日期缺少年份时按当前年份补全（prompt 中说明）
        prompt = self._load_ocr_prompt_template().format(current_year=datetime.now().year)

        try:
            logger.info("调用截图 OCR 识别: model=%s, images=%d", model, len(images))
            response_text = self._call_vision_model(
                provider_config,
                prompt=prompt,
                images=images,
                model=model,
                max_output_tokens=max_output_tokens,
            )
            raw_rows = self._parse_ocr_rows(response_text)
        except Exception as e:
            logger.error("截图 OCR 识别失败: %s", e)
            # 统一归类为结构化错误：视觉不支持与识别失败对用户的处置一致（改手动录入）
            raise AppErrorException(AppError(
                code="VISION_OCR_FAILED",
                title="截图识别失败",
                detail=f"当前模型不支持图片识别或识别失败：{str(e)[:300]}",
                suggestion="当前模型不支持图片识别或识别失败，请改用手动录入。",
                status=400,
                retryable=False,
                diagnostics={"model": model, "image_count": len(images)},
            )) from e

        rows = [
            cleaned
            for item in raw_rows
            if isinstance(item, dict)
            for cleaned in [self._clean_ocr_row(item)]
            if not self._is_empty_ocr_row(cleaned)
        ]
        logger.info("截图 OCR 识别完成: 原始 %d 行, 有效 %d 行", len(raw_rows), len(rows))
        return {"rows": rows, "count": len(rows), "model": model}

    # ==================== AI 复盘洞察 ====================

    def _build_data_summary(self, records: List[Dict]) -> str:
        """把用户数据整理成给 LLM 的文本摘要（不含任何账号敏感信息）。"""
        stats = self.get_stats()
        lines: List[str] = []

        lines.append(
            f"共 {stats['total_records']} 条已发布内容记录；"
            f"总曝光/播放 {stats['total_views']}，总点赞 {stats['total_likes']}，"
            f"总收藏 {stats['total_collects']}，总评论 {stats['total_comments']}，"
            f"总转发 {stats['total_shares']}，累计涨粉 {stats['total_followers_gained']}，"
            f"平均互动率 {stats['avg_engagement_rate']}%。"
        )

        lines.append("\n各平台表现：")
        for p in stats["platforms"]:
            lines.append(
                f"- {p['name']}：{p['count']} 条，曝光 {p['views']}，"
                f"互动率 {p['engagement_rate']}%，涨粉 {p['followers_gained']}"
            )

        lines.append("\n各内容类型表现：")
        for c in stats["content_types"]:
            lines.append(
                f"- {c['name']}：{c['count']} 条，曝光 {c['views']}，"
                f"互动率 {c['engagement_rate']}%，涨粉 {c['followers_gained']}"
            )

        if stats["trend"]:
            lines.append("\n按月趋势：")
            for t in stats["trend"]:
                lines.append(
                    f"- {t['month']}：{t['count']} 条，曝光 {t['views']}，"
                    f"互动 {t['engagements']}，涨粉 {t['followers_gained']}"
                )

        time_slots = stats.get("time_slots") or []
        if time_slots:
            lines.append("\n发布时段表现（仅统计填写了发布时间的记录）：")
            for slot in time_slots:
                lines.append(
                    f"- {slot['name']}：{slot['count']} 条，平均互动率 {slot['avg_engagement']}%"
                )

        # 按互动率排序列出明细（最多 30 条，避免 prompt 过长）
        def rate(r: Dict) -> float:
            views = int(r.get("views") or 0)
            return self._engagements(r) / views if views > 0 else 0.0

        detailed = sorted(records, key=rate, reverse=True)[:30]
        lines.append("\n内容明细（按互动率从高到低，最多 30 条）：")
        for r in detailed:
            views = int(r.get("views") or 0)
            rate_text = f"{round(rate(r) * 100, 2)}%" if views > 0 else "无曝光数据"
            lines.append(
                f"- 《{r.get('title', '')}》 | 平台: {r.get('platform', '')}"
                f" | 类型: {r.get('content_type') or '未分类'}"
                f" | 日期: {r.get('publish_date') or '未知'}"
                f" | 曝光 {views} | 点赞 {r.get('likes', 0)} | 收藏 {r.get('collects', 0)}"
                f" | 评论 {r.get('comments', 0)} | 转发 {r.get('shares', 0)}"
                f" | 涨粉 {r.get('followers_gained', 0)} | 互动率 {rate_text}"
            )

        return "\n".join(lines)

    def _build_benchmark_block(self, records: List[Dict]) -> str:
        """
        把行业基准与当前账号各指标的达标情况整理成给 LLM 的文本块（B10）。

        每行包含：阈值说明 + 当前值 + 评级 + 距达标线的差距，
        供 AI 洞察给出「距及格线差多少、优先修哪个指标」的结论。
        """
        meta = ANALYTICS_BENCHMARKS_META
        lines = [f"行业基准（{meta.get('source', '公开行业经验值，仅供参考')}，更新于 {meta.get('updated_at', '未知')}）："]

        rating_text = {RATING_RED: "红·偏低", RATING_YELLOW: "黄·待提升", RATING_GREEN: "绿·达标"}
        for item in self._build_metric_ratings(records).values():
            threshold = f"达标线 ≥{item['green_at']}%、及格下限 {item['red_below']}%"
            if item["value"] is None:
                lines.append(f"- {item['label']}：{threshold}；当前无曝光数据，无法评级")
                continue
            gap = round(item["green_at"] - item["value"], 2)
            gap_text = f"距达标线还差 {gap} 个百分点" if gap > 0 else "已达标"
            lines.append(
                f"- {item['label']}：{threshold}；"
                f"当前 {item['value']}%（{rating_text[item['rating']]}，{gap_text}）"
            )
        return "\n".join(lines)

    @staticmethod
    def _load_text_config() -> dict:
        """加载文本生成配置（text_providers.yaml，与 content 服务保持一致）。"""
        return load_text_config(default_providers=False)

    @staticmethod
    def _get_client(text_config: dict):
        """根据配置获取文本生成客户端（惰性导入，避免 CRUD 路径依赖 LLM 环境）。"""
        return get_text_client(text_config)

    @staticmethod
    def _load_prompt_template() -> str:
        """加载 AI 复盘洞察提示词模板。"""
        return load_prompt_template('backend/prompts/analytics_prompt.txt')

    @staticmethod
    def _parse_json_response(response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应（与 content 服务相同的多级降级策略）。"""
        return parse_llm_json(response_text)

    @staticmethod
    def _normalize_str_list(value) -> List[str]:
        """把 AI 返回的字段归一化成字符串列表。"""
        if isinstance(value, str):
            return [value] if value.strip() else []
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def generate_insight(self) -> Dict[str, Any]:
        """
        AI 复盘洞察：把数据摘要发给 LLM，输出表现分析与下一步建议

        Returns:
            Dict: {
                success: True,
                insight: { summary, highlights: [...], suggestions: [...] },
                data_summary: 发送给 LLM 的数据摘要（方便前端展示/核对）
            }
            失败时返回 { success: False, error: 详细错误信息 }

        Raises:
            ValueError: 没有任何记录时抛出（属于参数/状态校验，走 400）
        """
        records = self._load_store().get("records", [])
        if not records:
            raise ValueError("暂无表现数据，请先录入至少一条记录再生成 AI 复盘")

        data_summary = self._build_data_summary(records)

        try:
            text_config = self._load_text_config()
            client = self._get_client(text_config)
            # B10：把行业基准表与当前达标情况注入洞察 prompt
            prompt = self._load_prompt_template().format(
                data_summary=data_summary,
                benchmark_summary=self._build_benchmark_block(records),
            )

            model, temperature, max_output_tokens = resolve_generation_params(
                text_config, default_max_output_tokens=4000
            )

            logger.info("调用 AI 复盘洞察: model=%s, records=%d", model, len(records))
            # 生成 + 解析 JSON（json_mode 约束输出格式；解析失败自动带纠正提示重试一次）
            insight_data = generate_and_parse_json(
                lambda prompt_suffix: client.generate_text(
                    prompt=prompt + prompt_suffix,
                    model=model,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    json_mode=True,
                )
            )

            insight = {
                "summary": str(insight_data.get("summary") or "").strip(),
                "highlights": self._normalize_str_list(insight_data.get("highlights")),
                "suggestions": self._normalize_str_list(insight_data.get("suggestions")),
            }
            if not insight["summary"] and not insight["highlights"] and not insight["suggestions"]:
                raise ValueError("AI 返回的洞察内容为空，请重试")

            logger.info(
                "AI 复盘洞察完成: %d 条亮点, %d 条建议",
                len(insight["highlights"]), len(insight["suggestions"]),
            )
            return {
                "success": True,
                "insight": insight,
                "data_summary": data_summary,
            }

        except Exception as e:
            logger.error("AI 复盘洞察失败: %s", e)
            return {
                "success": False,
                "error": classify_llm_error(e, task_label="AI 复盘洞察失败"),
            }


_service_instance = None


def get_analytics_service() -> AnalyticsService:
    """
    获取数据复盘服务实例（单例模式）

    Returns:
        AnalyticsService: 数据复盘服务实例
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = AnalyticsService()
    return _service_instance
