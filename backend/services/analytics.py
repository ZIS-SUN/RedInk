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
- content_type: 内容类型/标签（如"干货教程"/"好物种草"）
- views: 曝光/播放数
- likes: 点赞数
- collects: 收藏数
- comments: 评论数
- shares: 转发数
- followers_gained: 涨粉数
- notes: 备注
- created_at / updated_at: ISO 时间戳
"""

import os
import json
import logging
import re
import tempfile
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

# 守护实例锁的惰性创建（实例可能通过 __new__ 构造，绕过 __init__）
_LOCK_INIT_GUARD = threading.Lock()

# 记录中允许由调用方写入的字段
_EDITABLE_STR_FIELDS = ("title", "platform", "publish_date", "content_type", "notes")
_EDITABLE_INT_FIELDS = ("views", "likes", "collects", "comments", "shares", "followers_gained")


class AnalyticsStoreCorruptedError(RuntimeError):
    """数据文件损坏（存在但无法解析）时抛出，避免用空数据覆盖真实数据。"""


class AnalyticsService:
    def __init__(self):
        """
        初始化数据复盘服务

        创建 analytics_data 存储目录和数据文件（项目根目录/analytics_data/records.json）
        """
        self.analytics_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "analytics_data"
        )
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

    # ==================== CRUD ====================

    def list_records(self) -> Dict:
        """
        获取全部表现记录

        Returns:
            Dict: { records: [...] }（按发布日期倒序，其次按创建时间倒序）
        """
        store = self._load_store()
        records = list(store.get("records", []))
        records.sort(
            key=lambda r: (str(r.get("publish_date") or ""), str(r.get("created_at") or "")),
            reverse=True,
        )
        return {"records": records}

    def get_record(self, record_id: str) -> Optional[Dict]:
        """按 ID 获取记录，不存在返回 None。"""
        store = self._load_store()
        for record in store.get("records", []):
            if record.get("id") == record_id:
                return record
        return None

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
        title = self._normalize_str(data.get("title"))
        platform = self._normalize_str(data.get("platform"))
        if not title:
            raise ValueError("内容标题不能为空")
        if not platform:
            raise ValueError("发布平台不能为空")

        now = datetime.now().isoformat()
        record = {
            "id": str(uuid.uuid4()),
            "title": title,
            "platform": platform,
            "publish_date": self._normalize_str(data.get("publish_date")),
            "content_type": self._normalize_str(data.get("content_type")),
            "views": self._normalize_int(data.get("views")),
            "likes": self._normalize_int(data.get("likes")),
            "collects": self._normalize_int(data.get("collects")),
            "comments": self._normalize_int(data.get("comments")),
            "shares": self._normalize_int(data.get("shares")),
            "followers_gained": self._normalize_int(data.get("followers_gained")),
            "notes": self._normalize_str(data.get("notes")),
            "created_at": now,
            "updated_at": now,
        }

        with self._lock:
            store = self._load_store()
            store["records"].insert(0, record)
            self._save_store(store)

        return record

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
                    target[field] = self._normalize_str(data.get(field))
            for field in _EDITABLE_INT_FIELDS:
                if field in data:
                    target[field] = self._normalize_int(data.get(field))

            target["updated_at"] = datetime.now().isoformat()
            self._save_store(store)
            return target

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
            }
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
            summary.append({
                "name": name,
                "count": len(group),
                "views": sum(int(r.get("views") or 0) for r in group),
                "likes": sum(int(r.get("likes") or 0) for r in group),
                "collects": sum(int(r.get("collects") or 0) for r in group),
                "comments": sum(int(r.get("comments") or 0) for r in group),
                "shares": sum(int(r.get("shares") or 0) for r in group),
                "followers_gained": sum(int(r.get("followers_gained") or 0) for r in group),
                "engagement_rate": cls._engagement_rate(group),
            })
        summary.sort(key=lambda item: item["views"], reverse=True)
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

    @staticmethod
    def _load_text_config() -> dict:
        """加载文本生成配置（text_providers.yaml，与 content 服务保持一致）。"""
        config_path = Path(__file__).parent.parent.parent / "text_providers.yaml"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                logger.error("文本配置 YAML 解析失败: %s", e)
                raise ValueError(
                    f"文本配置文件格式错误: text_providers.yaml\n"
                    f"YAML 解析错误: {e}\n"
                    "解决方案：检查 YAML 缩进和语法"
                )
        logger.warning("text_providers.yaml 不存在，使用默认配置")
        return {
            "active_provider": "google_gemini",
            "providers": {},
        }

    @staticmethod
    def _get_client(text_config: dict):
        """根据配置获取文本生成客户端（惰性导入，避免 CRUD 路径依赖 LLM 环境）。"""
        from backend.utils.text_client import get_text_chat_client

        active_provider = text_config.get("active_provider", "google_gemini")
        providers = text_config.get("providers", {})

        if not providers:
            raise ValueError(
                "未找到任何文本生成服务商配置。\n"
                "解决方案：\n"
                "1. 在系统设置页面添加文本生成服务商\n"
                "2. 或手动编辑 text_providers.yaml 文件"
            )

        if active_provider not in providers:
            available = ", ".join(providers.keys())
            raise ValueError(
                f"未找到文本生成服务商配置: {active_provider}\n"
                f"可用的服务商: {available}\n"
                "解决方案：在系统设置中选择一个可用的服务商"
            )

        provider_config = providers.get(active_provider, {})
        if not provider_config.get("api_key"):
            raise ValueError(
                f"文本服务商 {active_provider} 未配置 API Key\n"
                "解决方案：在系统设置页面编辑该服务商，填写 API Key"
            )

        logger.info(
            "AI 复盘使用文本服务商: %s (type=%s)",
            active_provider, provider_config.get("type"),
        )
        return get_text_chat_client(provider_config)

    @staticmethod
    def _load_prompt_template() -> str:
        """加载 AI 复盘洞察提示词模板。"""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts",
            "analytics_prompt.txt"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def _parse_json_response(response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应（与 content 服务相同的多级降级策略）。"""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            try:
                return json.loads(response_text[start_idx:end_idx + 1])
            except json.JSONDecodeError:
                pass

        logger.error("无法解析 JSON 响应: %s...", response_text[:200])
        raise ValueError("AI 返回的内容格式不正确，无法解析")

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
            prompt = self._load_prompt_template().format(data_summary=data_summary)

            active_provider = text_config.get("active_provider", "google_gemini")
            provider_config = text_config.get("providers", {}).get(active_provider, {})
            model = provider_config.get("model", "gemini-2.0-flash-exp")
            temperature = provider_config.get("temperature", 1.0)
            max_output_tokens = provider_config.get("max_output_tokens", 4000)

            logger.info("调用 AI 复盘洞察: model=%s, records=%d", model, len(records))
            response_text = client.generate_text(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

            insight_data = self._parse_json_response(response_text)

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
            error_msg = str(e)
            logger.error("AI 复盘洞察失败: %s", error_msg)

            if "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower() or "401" in error_msg:
                detailed_error = (
                    f"API 认证失败。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：API Key 无效或已过期\n"
                    "解决方案：在系统设置页面检查并更新 API Key"
                )
            elif "model" in error_msg.lower() or "404" in error_msg:
                detailed_error = (
                    f"模型访问失败。\n"
                    f"错误详情: {error_msg}\n"
                    "解决方案：在系统设置页面检查模型名称配置"
                )
            elif "timeout" in error_msg.lower() or "连接" in error_msg:
                detailed_error = (
                    f"网络连接失败。\n"
                    f"错误详情: {error_msg}\n"
                    "解决方案：检查网络连接，稍后重试"
                )
            elif "rate" in error_msg.lower() or "429" in error_msg or "quota" in error_msg.lower():
                detailed_error = (
                    f"API 配额限制。\n"
                    f"错误详情: {error_msg}\n"
                    "解决方案：等待配额重置，或升级 API 套餐"
                )
            else:
                detailed_error = (
                    f"AI 复盘洞察失败。\n"
                    f"错误详情: {error_msg}\n"
                    "建议：检查配置文件 text_providers.yaml"
                )

            return {
                "success": False,
                "error": detailed_error,
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
