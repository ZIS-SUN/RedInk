"""
创作偏好画像服务：让产品越用越懂用户。

「质量反馈闭环」数据积累层（作品评分 rating + 编辑留痕 edit_history）
的第一个消费者。本模块是纯计算服务（不调 LLM），从 HistoryService 的
全部历史记录聚合出结构化的「创作偏好画像」：

- 高分偏好：rating >= 4 的作品的主题（记录 title 即用户输入的 topic）
  与页数分布，提炼「用户满意的内容长什么样」；
- 编辑习惯：从 edit_history 统计平均改动幅度（新文与原文的长度差比例），
  按简单阈值归类高频改动信号——明显变短 = 用户嫌啰嗦（shorten）、
  明显变长 = 嫌太单薄（expand）、其余为 neutral。刻意只做长度级别的
  轻量统计，不做 NLP 过度设计；
- 样本量与置信提示：已评分样本 < MIN_RATED_SAMPLES 条时画像标记
  insufficient，不输出任何结论（避免小样本误导生成）。

对外接口：
- build_profile(): 返回结构化画像 dict（sample_count / liked_topics /
  preferred_page_count / editing_signal 等）；
- build_prompt_snippet(): 把画像浓缩成一段 <= PROMPT_SNIPPET_MAX_LEN 字
  的中文提示词片段，供大纲生成 prompt 以可选段落追加（与品牌人设
  build_brand_constraint 同模式）；画像 insufficient 时返回空字符串，
  保证注入方完全不受影响。

安全要点：
- 只读 HistoryService，不写任何数据；
- 单条记录读取失败 / 结构异常时跳过该条，聚合过程绝不抛错中断。
"""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from backend.services.history import HistoryService, get_history_service

logger = logging.getLogger(__name__)

# 画像置信下限：已评分样本少于该值时标记 insufficient，不输出结论
MIN_RATED_SAMPLES = 3

# 高分作品的评分门槛（rating >= 该值视为「用户满意」）
LIKED_RATING_THRESHOLD = 4

# 编辑信号阈值：平均长度变化比例低于/高于该值时判定「嫌啰嗦」/「嫌单薄」
SHORTEN_RATIO_THRESHOLD = -0.15
EXPAND_RATIO_THRESHOLD = 0.15

# 画像中最多保留的高分主题数（防止 prompt 片段被主题列表撑爆）
MAX_LIKED_TOPICS = 5

# prompt 片段的字数上限（中文字符计）
PROMPT_SNIPPET_MAX_LEN = 200

# prompt 片段中单个主题的截断长度
_SNIPPET_TOPIC_MAX_LEN = 12

# prompt 片段中最多列举的主题数
_SNIPPET_TOPIC_COUNT = 3

# 编辑信号 -> prompt 片段里的中文结论
_TENDENCY_SNIPPET_TEXT = {
    "shorten": "编辑习惯显示用户常把文案改短，讨厌冗长表达，请用精炼的口语化短句",
    "expand": "编辑习惯显示用户常把文案改长，嫌内容单薄，请把要点写得充实具体",
}


def _valid_rating(value: Any) -> Optional[int]:
    """从记录里取合法评分：仅 1-5 的整数（排除 bool），其余返回 None。"""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if not (1 <= value <= 5):
        return None
    return value


class PreferenceService:
    """创作偏好画像聚合服务（纯计算，只读 HistoryService）"""

    def __init__(self, history_service: Optional[HistoryService] = None):
        """
        Args:
            history_service: 历史记录服务实例（默认取全局单例，测试可注入）
        """
        self.history_service = history_service or get_history_service()

    def _iter_records(self) -> List[Dict]:
        """
        读取全部历史记录的完整内容（评分在索引里有冗余，但编辑留痕
        只存在于记录文件中，因此按索引逐条读文件）。

        单条读取失败/结构异常时跳过该条，绝不中断聚合。
        """
        try:
            index = self.history_service._load_index()
        except Exception as e:
            logger.warning(f"读取历史索引失败，画像按无数据处理: {e}")
            return []

        records = []
        for entry in index.get("records", []):
            record_id = entry.get("id")
            if not record_id:
                continue
            try:
                record = self.history_service.get_record(record_id)
            except Exception as e:
                logger.warning(f"读取历史记录失败，跳过: id={record_id}, {e}")
                continue
            if isinstance(record, dict):
                records.append(record)
        return records

    @staticmethod
    def _page_count(record: Dict) -> Optional[int]:
        """取记录的大纲页数；结构异常时返回 None（该条不计入页数分布）。"""
        outline = record.get("outline")
        if not isinstance(outline, dict):
            return None
        pages = outline.get("pages")
        if not isinstance(pages, list) or not pages:
            return None
        return len(pages)

    @staticmethod
    def _collect_edit_ratios(records: List[Dict]) -> List[float]:
        """
        汇总全部记录的编辑留痕，计算每条改动的长度变化比例：
        (新文长度 - 原文长度) / 原文长度。原文为空或结构异常的条目跳过。
        """
        ratios: List[float] = []
        for record in records:
            traces = record.get("edit_history")
            if not isinstance(traces, list):
                continue
            for trace in traces:
                if not isinstance(trace, dict):
                    continue
                original = trace.get("original_text")
                edited = trace.get("edited_text")
                if not isinstance(original, str) or not isinstance(edited, str):
                    continue
                if not original:
                    continue
                ratios.append((len(edited) - len(original)) / len(original))
        return ratios

    @staticmethod
    def _editing_signal(ratios: List[float]) -> Dict[str, Any]:
        """
        由长度变化比例列表归纳编辑信号：

        - shorten: 平均明显变短（用户嫌啰嗦）
        - expand: 平均明显变长（用户嫌太单薄）
        - neutral: 有编辑但幅度不明显
        - tendency 为 None: 没有任何编辑留痕
        """
        if not ratios:
            return {"edit_count": 0, "avg_change_ratio": 0.0, "tendency": None}

        avg_ratio = sum(ratios) / len(ratios)
        if avg_ratio <= SHORTEN_RATIO_THRESHOLD:
            tendency = "shorten"
        elif avg_ratio >= EXPAND_RATIO_THRESHOLD:
            tendency = "expand"
        else:
            tendency = "neutral"

        return {
            "edit_count": len(ratios),
            "avg_change_ratio": round(avg_ratio, 3),
            "tendency": tendency,
        }

    def build_profile(self) -> Dict[str, Any]:
        """
        扫描全部历史记录，聚合创作偏好画像。

        Returns:
            Dict: 结构化画像
                - insufficient: 已评分样本不足时为 True（此时不输出结论字段）
                - sample_count: 已评分作品数（1-5 的合法评分）
                - min_samples: 置信下限（前端展示「当前样本 X/3」用）
                - liked_count: 高分（rating >= 4）作品数
                - liked_topics: 高分作品主题列表（去重，最多 MAX_LIKED_TOPICS 条）
                - preferred_page_count: 高分作品最常见的页数（无数据为 None）
                - page_count_distribution: 高分作品页数分布 {页数: 次数}
                - editing_signal: 编辑习惯信号
                  {edit_count, avg_change_ratio, tendency}
        """
        records = self._iter_records()

        rated = [
            (record, rating)
            for record in records
            if (rating := _valid_rating(record.get("rating"))) is not None
        ]
        sample_count = len(rated)

        # 样本不足：只报数量，不输出任何结论（避免小样本误导）
        if sample_count < MIN_RATED_SAMPLES:
            return {
                "insufficient": True,
                "sample_count": sample_count,
                "min_samples": MIN_RATED_SAMPLES,
                "liked_count": 0,
                "liked_topics": [],
                "preferred_page_count": None,
                "page_count_distribution": {},
                "editing_signal": self._editing_signal([]),
            }

        liked = [record for record, rating in rated if rating >= LIKED_RATING_THRESHOLD]

        # 高分主题：去重保序，最多 MAX_LIKED_TOPICS 条
        liked_topics: List[str] = []
        for record in liked:
            title = record.get("title")
            topic = str(title).strip() if title else ""
            if topic and topic not in liked_topics:
                liked_topics.append(topic)
        liked_topics = liked_topics[:MAX_LIKED_TOPICS]

        # 高分页数分布与众数（用户满意的篇幅长什么样）
        page_counts = [
            count for record in liked
            if (count := self._page_count(record)) is not None
        ]
        distribution = Counter(page_counts)
        preferred_page_count = (
            distribution.most_common(1)[0][0] if distribution else None
        )

        return {
            "insufficient": False,
            "sample_count": sample_count,
            "min_samples": MIN_RATED_SAMPLES,
            "liked_count": len(liked),
            "liked_topics": liked_topics,
            "preferred_page_count": preferred_page_count,
            "page_count_distribution": {
                str(count): times for count, times in sorted(distribution.items())
            },
            "editing_signal": self._editing_signal(self._collect_edit_ratios(records)),
        }

    def build_prompt_snippet(self) -> str:
        """
        把画像浓缩成一段 <= PROMPT_SNIPPET_MAX_LEN 字的中文提示词片段，
        供大纲生成 prompt 以可选段落追加。

        画像 insufficient 或没有任何可输出的结论时返回空字符串，
        注入方据此完全跳过（不影响现有 prompt）。
        """
        profile = self.build_profile()
        if profile["insufficient"]:
            return ""

        parts: List[str] = []
        if profile["preferred_page_count"]:
            parts.append(f"偏好 {profile['preferred_page_count']} 页左右的篇幅")
        if profile["liked_topics"]:
            topics = "」「".join(
                topic[:_SNIPPET_TOPIC_MAX_LEN]
                for topic in profile["liked_topics"][:_SNIPPET_TOPIC_COUNT]
            )
            parts.append(f"满意的主题如「{topics}」")
        tendency_text = _TENDENCY_SNIPPET_TEXT.get(
            profile["editing_signal"]["tendency"]
        )
        if tendency_text:
            parts.append(tendency_text)

        if not parts:
            return ""

        snippet = (
            f"【用户创作偏好】根据该用户 {profile['sample_count']} 个已评分作品："
            + "；".join(parts)
            + "。请在不违背主题的前提下贴合这些偏好。"
        )
        # 双保险：拼装内容已受主题数/主题长度约束，仍硬性截断到字数上限
        return snippet[:PROMPT_SNIPPET_MAX_LEN]


def get_preference_service() -> PreferenceService:
    """
    获取创作偏好画像服务实例。

    每次调用都创建新实例（服务本身无状态，历史数据实时读取），
    底层共享 HistoryService 全局单例。
    """
    return PreferenceService()
