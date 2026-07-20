"""
评论洞察选题挖掘服务

创作者粘贴一批粉丝评论，AI 从中聚类出 3-6 个痛点主题，
每个痛点附代表性原评论摘录与出现频次估计，
并为每个痛点生成 2-3 个可直接开写的选题
（选题结构对齐选题灵感服务的输出 schema：title/angle/format/heat/tags）。
"""

import logging
from typing import Any, Dict, List

from backend.utils.llm_utils import (
    classify_llm_error,
    get_text_client,
    load_prompt_template,
    load_text_config,
    parse_llm_json,
    resolve_generation_params,
)
# 复用选题灵感服务的内容形式合法取值，保证选题 schema 与 topic 服务一致
from backend.services.topic import VALID_FORMATS

logger = logging.getLogger(__name__)

# 单次最多处理的评论条数（防止 prompt 过长；洞察聚类需要比回复更多的样本）
MAX_COMMENTS = 50

# 痛点主题数量范围
MIN_PAIN_POINTS = 3
MAX_PAIN_POINTS = 6

# 每个痛点保留的代表性评论摘录上限
MAX_EVIDENCE = 3

# 每个痛点的选题数量上限
MAX_TOPICS_PER_PAIN_POINT = 3


class InsightService:
    """评论洞察选题挖掘服务：痛点聚类 + 按痛点生成选题"""

    def __init__(self):
        logger.debug("初始化 InsightService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"InsightService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

    def _load_text_config(self) -> dict:
        """加载文本生成配置"""
        return load_text_config()

    def _get_client(self):
        """根据配置获取客户端"""
        return get_text_client(self.text_config)

    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        return load_prompt_template('backend/prompts/insight_prompt.txt')

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应"""
        return parse_llm_json(response_text)

    @staticmethod
    def _normalize_topic(item: Any) -> Dict[str, Any]:
        """
        把 AI 返回的单条选题收敛为标准结构（与 topic 服务的选题 schema 一致），
        非法字段做兜底，无标题的条目返回空 dict 由调用方过滤
        """
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

        return {
            'title': title,
            'angle': angle,
            'format': content_format,
            'heat': heat,
            'tags': tags
        }

    def _normalize_pain_point(self, item: Any, total_comments: int) -> Dict[str, Any]:
        """
        把 AI 返回的单个痛点收敛为标准结构：
        - theme 为空则整条作废（返回空 dict）
        - frequency 钳制到 [1, 输入评论总数]
        - evidence 收敛为字符串列表并裁剪
        - topics 逐条走选题归一化，无有效选题的痛点也作废
        """
        if not isinstance(item, dict):
            return {}

        theme = str(item.get('theme', '')).strip()
        if not theme:
            return {}

        summary = str(item.get('summary', '')).strip()

        try:
            frequency = int(item.get('frequency', 1))
        except (TypeError, ValueError):
            frequency = 1
        frequency = max(1, min(total_comments, frequency))

        evidence = item.get('evidence', [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list):
            evidence = []
        evidence = [str(e).strip() for e in evidence if str(e).strip()][:MAX_EVIDENCE]

        raw_topics = item.get('topics', [])
        if not isinstance(raw_topics, list):
            raw_topics = []
        topics = [t for t in (self._normalize_topic(x) for x in raw_topics) if t]
        topics = topics[:MAX_TOPICS_PER_PAIN_POINT]
        if not topics:
            return {}

        return {
            'theme': theme,
            'summary': summary,
            'frequency': frequency,
            'evidence': evidence,
            'topics': topics
        }

    def mine_insights(self, comments: List[str], niche: str = "") -> Dict[str, Any]:
        """
        从粉丝评论中挖掘痛点主题与选题

        参数：
            comments: 粉丝评论列表（已去空行），最多处理 MAX_COMMENTS 条
            niche: 创作者的领域/赛道（可选），提供时帮助 AI 聚焦

        返回：
            {
                "success": True,
                "pain_points": [
                    {
                        "theme": "痛点主题",
                        "summary": "痛点说明",
                        "frequency": 5,
                        "evidence": ["代表性原评论摘录", ...],
                        "topics": [{"title": ..., "angle": ..., "format": ...,
                                    "heat": ..., "tags": [...]}, ...]
                    },
                    ...
                ],
                "comment_count": 实际参与分析的评论条数
            }
        """
        try:
            comments = [str(c).strip() for c in comments if str(c).strip()][:MAX_COMMENTS]
            if not comments:
                raise ValueError("评论列表为空，请至少输入一条粉丝评论")

            niche = str(niche or "").strip()

            logger.info(
                f"开始评论洞察挖掘: {len(comments)} 条评论, niche={niche[:50] or '(未提供)'}"
            )

            comments_text = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(comments))
            niche_text = niche if niche else "未提供（请根据评论内容自行判断所属领域）"

            # 构建提示词
            prompt = self.prompt_template.format(
                niche=niche_text,
                comments=comments_text
            )

            # 从配置中获取模型参数
            model, temperature, max_output_tokens = resolve_generation_params(
                self.text_config, default_max_output_tokens=4000
            )

            logger.info(f"调用文本生成 API: model={model}, temperature={temperature}")
            response_text = self.client.generate_text(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens
            )

            logger.debug(f"API 返回文本长度: {len(response_text)} 字符")

            # 解析并清洗 JSON 响应
            insight_data = self._parse_json_response(response_text)

            raw_pain_points = insight_data.get('pain_points', [])
            if not isinstance(raw_pain_points, list):
                raw_pain_points = []

            pain_points = [
                p for p in (
                    self._normalize_pain_point(item, len(comments))
                    for item in raw_pain_points
                ) if p
            ][:MAX_PAIN_POINTS]

            if not pain_points:
                logger.error("AI 返回结果中没有有效的痛点主题")
                raise ValueError("AI 未返回有效的痛点洞察，请重试")

            logger.info(
                f"评论洞察挖掘完成: {len(pain_points)} 个痛点主题, "
                f"共 {sum(len(p['topics']) for p in pain_points)} 条选题"
            )

            return {
                "success": True,
                "pain_points": pain_points,
                "comment_count": len(comments)
            }

        except Exception as e:
            logger.error(f"评论洞察挖掘失败: {e}")
            return {
                "success": False,
                "error": classify_llm_error(e, task_label="评论洞察挖掘失败")
            }


def get_insight_service() -> InsightService:
    """
    获取评论洞察选题挖掘服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return InsightService()
