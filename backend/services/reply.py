"""
评论区互动助手服务

创作者粘贴粉丝评论（可多条），选择回复语气，
AI 为每条评论生成 2-3 个高互动的神回复建议（引导二次互动、涨粉、带节奏但不低俗），
并可选生成一条置顶引导评论（引导点赞/关注/看主页）。
"""

import logging
from typing import Any, Dict, List, Optional

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

# 单次最多处理的评论条数（防止 prompt 过长）
MAX_COMMENTS = 20

# 每条评论的回复建议数量范围
MIN_SUGGESTIONS = 2
MAX_SUGGESTIONS = 3

# 支持的回复语气及其说明（注入 prompt 用）
TONE_HINTS = {
    "热情": "高能量、有感染力，多用感叹和亲昵称呼，让粉丝感觉被热烈欢迎",
    "专业": "干货感、可信赖，用简洁专业的表达展示功底，让人觉得博主很懂行",
    "幽默": "有梗、会接梗、敢自嘲，轻松诙谐带动评论区氛围，但不低俗不冒犯",
    "温暖": "共情、治愈、真诚，先接住对方情绪再温柔回应，让粉丝感觉被看见",
}

DEFAULT_TONE = "热情"


class ReplyService:
    """评论区互动助手服务：生成神回复建议与置顶引导评论"""

    def __init__(self):
        logger.debug("初始化 ReplyService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"ReplyService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

    def _load_text_config(self) -> dict:
        """加载文本生成配置"""
        return load_text_config()

    def _get_client(self):
        """根据配置获取客户端"""
        return get_text_client(self.text_config)

    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        return load_prompt_template('backend/prompts/reply_prompt.txt')

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应"""
        return parse_llm_json(response_text)

    def _normalize_replies(self, raw_replies: Any, comments: List[str]) -> List[Dict[str, Any]]:
        """
        清洗 AI 返回的回复列表：
        - 过滤非法项，收敛 suggestions 类型为字符串列表（每条最多 MAX_SUGGESTIONS 个）
        - comment 字段兜底回填为输入的原评论，保证与输入一一对应
        """
        replies: List[Dict[str, Any]] = []
        if not isinstance(raw_replies, list):
            raw_replies = []

        for i, comment in enumerate(comments):
            item = raw_replies[i] if i < len(raw_replies) else None
            if not isinstance(item, dict):
                item = {}

            suggestions = item.get('suggestions', [])
            if isinstance(suggestions, str):
                suggestions = [suggestions]
            if not isinstance(suggestions, list):
                suggestions = []
            suggestions = [str(s).strip() for s in suggestions if str(s).strip()]
            suggestions = suggestions[:MAX_SUGGESTIONS]

            # AI 返回的 comment 可能被改写或带序号，统一以输入原文为准
            replies.append({
                "comment": comment,
                "suggestions": suggestions
            })

        return replies

    @staticmethod
    def _build_brand_reply_context(brand: Optional[Dict]) -> str:
        """
        构建评论回复专用的品牌人设注入文本：

        在通用品牌人设约束之外，明确要求把口头禅 / 签名自然用进回复建议
        （口头禅/签名恰恰最该出现在评论区回复里）。brand 为空或无有效字段
        时返回空字符串。
        """
        constraint = build_brand_constraint(brand)
        if not constraint:
            return ""

        extra_lines: List[str] = []
        catchphrases = [
            str(c).strip() for c in (brand.get("catchphrases") or [])
            if c and str(c).strip()
        ] if isinstance(brand.get("catchphrases"), list) else []
        if catchphrases:
            extra_lines.append(
                f"- 请在部分回复建议中自然融入博主口头禅（{'、'.join(catchphrases)}），"
                "让粉丝一眼认出是博主本人在回复，但不要每条都用、不要生硬堆砌"
            )
        signature = str(brand.get("signature") or "").strip()
        if signature:
            extra_lines.append(
                f"- 签名/结尾话术「{signature}」可在少量回复或置顶引导评论的结尾自然带上"
            )

        section = constraint + (
            "\n\n### 回复身份要求：\n"
            "- 所有回复建议都要以该博主本人的身份和口吻发出，语气必须贴合上述人设\n"
        )
        if extra_lines:
            section += "\n".join(extra_lines) + "\n"
        section += "- 任何回复中都绝对不得出现上述禁用词" if brand.get("banned_words") else ""
        return section

    def generate_replies(
        self,
        comments: List[str],
        tone: str = DEFAULT_TONE,
        include_pinned: bool = False,
        brand: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        为粉丝评论生成神回复建议

        参数：
            comments: 粉丝评论列表（已去空行）
            tone: 回复语气（热情/专业/幽默/温暖）
            include_pinned: 是否同时生成一条置顶引导评论
            brand: 品牌档案字典（可选），提供时以博主人设口吻生成回复，
                并把口头禅/签名自然融入回复建议

        返回：
            {
                "success": True,
                "replies": [{"comment": "原评论", "suggestions": ["回复1", "回复2"]}, ...],
                "pinned_comment": "置顶引导评论（未要求时为空字符串）"
            }
        """
        try:
            comments = [str(c).strip() for c in comments if str(c).strip()][:MAX_COMMENTS]
            if not comments:
                raise ValueError("评论列表为空，请至少输入一条粉丝评论")

            if tone not in TONE_HINTS:
                logger.warning(f"未知回复语气 [{tone}]，回退为默认语气 [{DEFAULT_TONE}]")
                tone = DEFAULT_TONE

            logger.info(
                f"开始生成评论回复: {len(comments)} 条评论, tone={tone}, include_pinned={include_pinned}"
            )

            comments_text = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(comments))
            pinned_requirement = (
                "需要生成。请在 pinned_comment 字段输出一条符合要求的置顶引导评论。"
                if include_pinned
                else "本次不需要生成置顶引导评论，pinned_comment 字段输出空字符串 \"\"。"
            )

            # 构建提示词
            prompt = self.prompt_template.format(
                tone=tone,
                tone_hint=TONE_HINTS[tone],
                comments=comments_text,
                pinned_requirement=pinned_requirement
            )

            # 品牌人设约束以字符串追加方式融入，避免破坏模板占位符
            brand_context = self._build_brand_reply_context(brand)
            if brand_context:
                logger.info(f"注入品牌人设约束: brand={brand.get('name', '')}")
                prompt += brand_context

            # 从配置中获取模型参数
            model, temperature, max_output_tokens = resolve_generation_params(
                self.text_config, default_max_output_tokens=4000
            )

            logger.info(f"调用文本生成 API: model={model}, temperature={temperature}")
            # 生成 + 解析 JSON（json_mode 约束输出格式；解析失败自动带纠正提示重试一次）
            reply_data = generate_and_parse_json(
                lambda prompt_suffix: self.client.generate_text(
                    prompt=prompt + prompt_suffix,
                    model=model,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    json_mode=True
                )
            )
            replies = self._normalize_replies(reply_data.get('replies', []), comments)

            if not any(r["suggestions"] for r in replies):
                raise ValueError("AI 未返回任何有效的回复建议，请重试")

            pinned_comment = ""
            if include_pinned:
                pinned_comment = str(reply_data.get('pinned_comment', '') or '').strip()

            logger.info(
                f"评论回复生成完成: {len(replies)} 条评论, "
                f"置顶引导评论: {'有' if pinned_comment else '无'}"
            )

            return {
                "success": True,
                "replies": replies,
                "pinned_comment": pinned_comment
            }

        except Exception as e:
            logger.error(f"评论回复生成失败: {e}")
            return {
                "success": False,
                "error": classify_llm_error(e, task_label="评论回复生成失败")
            }


def get_reply_service() -> ReplyService:
    """
    获取评论区互动助手服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return ReplyService()
