"""
选题灵感服务

根据用户的领域/赛道和目标平台，由 AI 生成一批有爆款潜力的选题灵感。
注意：这是基于常识/常青角度的 AI 灵感生成，不是实时热榜数据。
"""

import logging
from typing import Dict, Any, Optional
from backend.utils.llm_utils import (
    classify_llm_error,
    generate_and_parse_json,
    get_text_client,
    load_prompt_template,
    load_text_config,
    parse_llm_json,
    resolve_generation_params,
)
from backend.services.rewrite import build_brand_constraint

logger = logging.getLogger(__name__)

# 默认生成的选题条数
DEFAULT_TOPIC_COUNT = 10

# format 字段的合法取值，AI 返回超出范围时回退为「图文」
VALID_FORMATS = ('图文', '口播', '清单', '教程', '测评', 'Vlog', '对比', '合集', '问答', '剧情')

# 蹭热点模式：单次最多接受的热点条数（约束 prompt 体积）
MAX_HOT_TOPICS = 20

# 蹭热点模式：单条热点词的最大长度（防超长文本挤爆 prompt）
MAX_HOT_TOPIC_LEN = 100


class TopicService:
    """选题灵感服务：生成选题标题、切入角度、内容形式、热度预估和话题标签"""

    def __init__(self):
        logger.debug("初始化 TopicService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"TopicService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

    def _load_text_config(self) -> dict:
        """加载文本生成配置"""
        return load_text_config()

    def _get_client(self):
        """根据配置获取客户端"""
        return get_text_client(self.text_config)

    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        return load_prompt_template('backend/prompts/topic_prompt.txt')

    def _build_account_context(self) -> str:
        """
        从数据复盘服务构建账号画像文本（用于注入选题 prompt）。

        无记录、数据不可用或读取异常时一律返回空串（调用方静默忽略），
        绝不因账号数据问题中断选题生成主流程。
        """
        try:
            # 惰性导入：避免选题服务在 analytics 环境异常时初始化失败
            from backend.services.analytics import get_analytics_service
            stats = get_analytics_service().get_stats()
        except Exception as e:
            logger.warning(f"读取账号数据失败，忽略账号画像: {e}")
            return ""

        if not isinstance(stats, dict):
            return ""

        try:
            total_records = int(stats.get('total_records') or 0)
        except (TypeError, ValueError):
            return ""
        if total_records <= 0:
            return ""

        lines = [
            f"- 已发布内容共 {total_records} 篇，平均互动率 {stats.get('avg_engagement_rate', 0)}%"
        ]

        platforms = [p for p in (stats.get('platforms') or []) if isinstance(p, dict) and p.get('name')]
        best_platforms = sorted(
            platforms, key=lambda p: float(p.get('engagement_rate') or 0), reverse=True
        )[:2]
        if best_platforms:
            lines.append(
                "- 表现最好的平台：" + "、".join(
                    f"{p['name']}（{p.get('count', 0)} 篇，互动率 {p.get('engagement_rate', 0)}%）"
                    for p in best_platforms
                )
            )

        content_types = [c for c in (stats.get('content_types') or []) if isinstance(c, dict) and c.get('name')]
        best_types = sorted(
            content_types, key=lambda c: float(c.get('engagement_rate') or 0), reverse=True
        )[:3]
        if best_types:
            lines.append(
                "- 表现最好的内容类型：" + "、".join(
                    f"{c['name']}（{c.get('count', 0)} 篇，互动率 {c.get('engagement_rate', 0)}%）"
                    for c in best_types
                )
            )

        trend = [t for t in (stats.get('trend') or []) if isinstance(t, dict) and t.get('month')]
        if len(trend) >= 2:
            prev, last = trend[-2], trend[-1]
            prev_eng = int(prev.get('engagements') or 0)
            last_eng = int(last.get('engagements') or 0)
            if last_eng > prev_eng:
                direction = '上升'
            elif last_eng < prev_eng:
                direction = '下降'
            else:
                direction = '持平'
            lines.append(
                f"- 近期月趋势：{prev['month']} 互动 {prev_eng} → {last['month']} 互动 {last_eng}，整体{direction}"
            )
        elif len(trend) == 1:
            only = trend[0]
            lines.append(
                f"- 近期月趋势：目前仅 {only['month']} 一个月数据"
                f"（{only.get('count', 0)} 条，互动 {only.get('engagements', 0)}）"
            )

        return "\n".join(lines)

    @staticmethod
    def _apply_account_context(prompt: str, account_context: str) -> str:
        """
        在已构建好的 prompt 末尾追加账号画像段落。

        与 image 服务的 _apply_style_prompt 相同：用运行时字符串拼接而非
        模板占位符，避免给模板新增占位符导致其他 .format 调用点 KeyError。
        account_context 为空时原样返回。
        """
        context = (account_context or "").strip()
        if not context:
            return prompt
        return (
            f"{prompt}\n\n"
            "### 账号画像（基于该用户已录入的真实发布数据）：\n"
            f"{context}\n\n"
            "请在生成选题时优先贴合该账号表现最好的平台调性与内容类型，"
            "并结合近期趋势给出更有把握的选题方向。"
        )

    @staticmethod
    def normalize_hot_topics(hot_topics) -> list:
        """
        归一化用户粘贴的热榜词/热点标题列表：
        - 非列表输入一律返回空列表（等同于常规选题模式）
        - 逐条转字符串、去首尾空白、丢弃空行
        - 单条截断到 MAX_HOT_TOPIC_LEN，总条数截断到 MAX_HOT_TOPICS
        """
        if not isinstance(hot_topics, list):
            return []
        result = []
        for item in hot_topics:
            if item is None:
                continue
            text = str(item).strip()
            if not text:
                continue
            result.append(text[:MAX_HOT_TOPIC_LEN])
            if len(result) >= MAX_HOT_TOPICS:
                break
        return result

    @staticmethod
    def _apply_hot_topics(prompt: str, hot_topics: list) -> str:
        """
        在已构建好的 prompt 末尾追加蹭热点指令段落。

        与 _apply_account_context 相同：用运行时字符串拼接而非模板占位符，
        避免给模板新增占位符导致其他 .format 调用点 KeyError。
        hot_topics 为空时原样返回（保持常规选题行为完全不变）。
        """
        if not hot_topics:
            return prompt

        hot_lines = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(hot_topics))
        return (
            f"{prompt}\n\n"
            "### 蹭热点模式（用户手动粘贴的热榜词/热点标题，每行一条）：\n"
            f"{hot_lines}\n\n"
            "本次进入「蹭热点」模式，请调整生成策略：\n"
            "1. 不再基于常青角度自由发挥，改为围绕上面列出的每个热点逐一产出选题，"
            "每个热点至少产出 1 条，把热点与用户的领域/赛道自然结合\n"
            "2. angle 字段写清「蹭点角度」：这个热点怎么和用户赛道挂钩、借哪股情绪或流量\n"
            "3. 每条选题在原有字段基础上额外输出以下字段（都是字符串）：\n"
            '   - "hot_topic": 对应的热点原词（与上面列表中的某一条一致）\n'
            '   - "publish_window": 建议发布窗口（如"48 小时内""3 天内"，热点时效性越强窗口越短）\n'
            '   - "relevance": 与用户赛道的关联度评估（高/中/低 + 一句话理由，'
            "关联度低的热点也要如实标注，帮用户判断值不值得蹭）\n"
            "4. 其余输出格式要求（JSON 结构、title/format/heat/tags 的标准）保持不变"
        )

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应"""
        return parse_llm_json(response_text)

    def _normalize_topic(self, item: Any) -> Dict[str, Any]:
        """把 AI 返回的单条选题收敛为标准结构，非法字段做兜底"""
        if not isinstance(item, dict):
            return {}

        title = str(item.get('title', '')).strip()
        if not title:
            return {}

        angle = str(item.get('angle', '')).strip()

        content_format = str(item.get('format', '')).strip()
        if content_format not in VALID_FORMATS:
            content_format = '图文'

        try:
            heat = int(item.get('heat', 0))
        except (TypeError, ValueError):
            heat = 0
        heat = max(0, min(100, heat))

        tags = item.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]
        if not isinstance(tags, list):
            tags = []
        tags = [str(t).strip().lstrip('#') for t in tags if str(t).strip()]

        topic = {
            'title': title,
            'angle': angle,
            'format': content_format,
            'heat': heat,
            'tags': tags
        }

        # 蹭热点模式的增量字段（可选）：仅在 AI 返回了非空值时透传
        for optional_field in ('hot_topic', 'publish_window', 'relevance'):
            value = str(item.get(optional_field, '') or '').strip()
            if value:
                topic[optional_field] = value

        return topic

    def generate_topics(
        self,
        niche: str,
        platform: str = '小红书',
        count: int = DEFAULT_TOPIC_COUNT,
        use_account_data: bool = False,
        brand: Optional[Dict] = None,
        hot_topics: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        生成选题灵感列表

        参数：
            niche: 用户的领域/赛道（如"健身减脂""职场干货"）
            platform: 目标平台（如"小红书""抖音"）
            count: 期望生成的选题条数
            use_account_data: 是否结合数据复盘工具录入的账号数据（无记录时静默忽略）
            brand: 品牌档案字典（可选），提供时会把品牌人设约束注入 prompt
            hot_topics: 用户手动粘贴的热榜词/热点标题列表（可选）。
                提供时进入「蹭热点」模式：围绕每个热点产出蹭点角度、
                建议发布窗口与赛道关联度评估（增量字段可选）

        返回：
            包含 topics 列表的字典，每条含 title/angle/format/heat/tags
            （蹭热点模式下可能另含 hot_topic/publish_window/relevance）；
            另含 account_context_used 表示本次是否实际注入了账号画像
        """
        account_context_used = False
        try:
            normalized_hot_topics = self.normalize_hot_topics(hot_topics)
            logger.info(
                f"开始生成选题灵感: niche={niche[:50]}, platform={platform}, "
                f"use_account_data={use_account_data}, "
                f"hot_topics={len(normalized_hot_topics)} 条"
            )

            # 构建提示词
            prompt = self.prompt_template.format(
                niche=niche,
                platform=platform,
                count=count
            )

            # 蹭热点模式：把热点列表与蹭点要求追加到 prompt 末尾（空列表时不改变行为）
            if normalized_hot_topics:
                prompt = self._apply_hot_topics(prompt, normalized_hot_topics)
                logger.info("已注入蹭热点指令到选题 prompt")

            # 结合账号数据：有记录时把账号画像追加到 prompt 末尾，无记录时静默忽略
            if use_account_data:
                account_context = self._build_account_context()
                if account_context:
                    prompt = self._apply_account_context(prompt, account_context)
                    account_context_used = True
                    logger.info("已注入账号画像到选题 prompt")
                else:
                    logger.info("use_account_data=True 但暂无账号数据，忽略账号画像")

            # 品牌人设约束以字符串追加方式融入，避免破坏模板占位符
            brand_constraint = build_brand_constraint(brand)
            if brand_constraint:
                logger.info(f"注入品牌人设约束: brand={brand.get('name', '')}")
                prompt += brand_constraint + (
                    "\n\n请确保生成的选题方向贴合以上品牌人设的定位与目标人群，"
                    "选题标题的措辞风格也要符合该人设的语气，并且不出现任何禁用词。"
                )

            # 从配置中获取模型参数
            model, temperature, max_output_tokens = resolve_generation_params(
                self.text_config, default_max_output_tokens=4000
            )

            logger.info(f"调用文本生成 API: model={model}, temperature={temperature}")
            # 生成 + 解析 JSON（json_mode 约束输出格式；解析失败自动带纠正提示重试一次）
            topic_data = generate_and_parse_json(
                lambda prompt_suffix: self.client.generate_text(
                    prompt=prompt + prompt_suffix,
                    model=model,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    json_mode=True
                )
            )

            raw_topics = topic_data.get('topics', [])
            if not isinstance(raw_topics, list):
                raw_topics = []

            topics = [t for t in (self._normalize_topic(item) for item in raw_topics) if t]

            if not topics:
                logger.error("AI 返回结果中没有有效的选题条目")
                raise ValueError("AI 未返回有效的选题内容，请重试")

            logger.info(f"选题灵感生成完成: {len(topics)} 条")

            return {
                "success": True,
                "topics": topics,
                "account_context_used": account_context_used
            }

        except Exception as e:
            logger.error(f"选题灵感生成失败: {e}")
            return {
                "success": False,
                "error": classify_llm_error(e, task_label="选题灵感生成失败")
            }


def get_topic_service() -> TopicService:
    """
    获取选题灵感服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return TopicService()
