"""
选题灵感服务

根据用户的领域/赛道和目标平台，由 AI 生成一批有爆款潜力的选题灵感。
注意：这是基于常识/常青角度的 AI 灵感生成，不是实时热榜数据。
"""

import logging
from typing import Dict, Any, Optional
from backend.utils.llm_utils import (
    classify_llm_error,
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

        return {
            'title': title,
            'angle': angle,
            'format': content_format,
            'heat': heat,
            'tags': tags
        }

    def generate_topics(
        self,
        niche: str,
        platform: str = '小红书',
        count: int = DEFAULT_TOPIC_COUNT,
        use_account_data: bool = False,
        brand: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        生成选题灵感列表

        参数：
            niche: 用户的领域/赛道（如"健身减脂""职场干货"）
            platform: 目标平台（如"小红书""抖音"）
            count: 期望生成的选题条数
            use_account_data: 是否结合数据复盘工具录入的账号数据（无记录时静默忽略）
            brand: 品牌档案字典（可选），提供时会把品牌人设约束注入 prompt

        返回：
            包含 topics 列表的字典，每条含 title/angle/format/heat/tags；
            另含 account_context_used 表示本次是否实际注入了账号画像
        """
        account_context_used = False
        try:
            logger.info(
                f"开始生成选题灵感: niche={niche[:50]}, platform={platform}, "
                f"use_account_data={use_account_data}"
            )

            # 构建提示词
            prompt = self.prompt_template.format(
                niche=niche,
                platform=platform,
                count=count
            )

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
            response_text = self.client.generate_text(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens
            )

            logger.debug(f"API 返回文本长度: {len(response_text)} 字符")

            # 解析 JSON 响应
            topic_data = self._parse_json_response(response_text)

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
