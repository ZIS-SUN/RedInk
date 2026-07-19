"""
评论区互动助手服务

创作者粘贴粉丝评论（可多条），选择回复语气，
AI 为每条评论生成 2-3 个高互动的神回复建议（引导二次互动、涨粉、带节奏但不低俗），
并可选生成一条置顶引导评论（引导点赞/关注/看主页）。
"""

import json
import logging
import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict, List

from backend.utils.text_client import get_text_chat_client

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
        config_path = Path(__file__).parent.parent.parent / 'text_providers.yaml'
        logger.debug(f"加载文本配置: {config_path}")

        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                logger.debug(f"文本配置加载成功: active={config.get('active_provider')}")
                return config
            except yaml.YAMLError as e:
                logger.error(f"文本配置 YAML 解析失败: {e}")
                raise ValueError(
                    f"文本配置文件格式错误: text_providers.yaml\n"
                    f"YAML 解析错误: {e}\n"
                    "解决方案：检查 YAML 缩进和语法"
                )

        logger.warning("text_providers.yaml 不存在，使用默认配置")
        return {
            'active_provider': 'google_gemini',
            'providers': {
                'google_gemini': {
                    'type': 'google_gemini',
                    'model': 'gemini-2.0-flash-exp',
                    'temperature': 1.0,
                    'max_output_tokens': 8000
                }
            }
        }

    def _get_client(self):
        """根据配置获取客户端"""
        active_provider = self.text_config.get('active_provider', 'google_gemini')
        providers = self.text_config.get('providers', {})

        if not providers:
            logger.error("未找到任何文本生成服务商配置")
            raise ValueError(
                "未找到任何文本生成服务商配置。\n"
                "解决方案：\n"
                "1. 在系统设置页面添加文本生成服务商\n"
                "2. 或手动编辑 text_providers.yaml 文件"
            )

        if active_provider not in providers:
            available = ', '.join(providers.keys())
            logger.error(f"文本服务商 [{active_provider}] 不存在，可用: {available}")
            raise ValueError(
                f"未找到文本生成服务商配置: {active_provider}\n"
                f"可用的服务商: {available}\n"
                "解决方案：在系统设置中选择一个可用的服务商"
            )

        provider_config = providers.get(active_provider, {})

        if not provider_config.get('api_key'):
            logger.error(f"文本服务商 [{active_provider}] 未配置 API Key")
            raise ValueError(
                f"文本服务商 {active_provider} 未配置 API Key\n"
                "解决方案：在系统设置页面编辑该服务商，填写 API Key"
            )

        logger.info(f"使用文本服务商: {active_provider} (type={provider_config.get('type')})")
        return get_text_chat_client(provider_config)

    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts",
            "reply_prompt.txt"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应"""
        # 尝试直接解析
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块中提取
        json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 尝试找到 JSON 对象的开始和结束
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            try:
                return json.loads(response_text[start_idx:end_idx + 1])
            except json.JSONDecodeError:
                pass

        logger.error(f"无法解析 JSON 响应: {response_text[:200]}...")
        raise ValueError("AI 返回的内容格式不正确，无法解析")

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

    def generate_replies(
        self,
        comments: List[str],
        tone: str = DEFAULT_TONE,
        include_pinned: bool = False
    ) -> Dict[str, Any]:
        """
        为粉丝评论生成神回复建议

        参数：
            comments: 粉丝评论列表（已去空行）
            tone: 回复语气（热情/专业/幽默/温暖）
            include_pinned: 是否同时生成一条置顶引导评论

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

            # 从配置中获取模型参数
            active_provider = self.text_config.get('active_provider', 'google_gemini')
            providers = self.text_config.get('providers', {})
            provider_config = providers.get(active_provider, {})

            model = provider_config.get('model', 'gemini-2.0-flash-exp')
            temperature = provider_config.get('temperature', 1.0)
            max_output_tokens = provider_config.get('max_output_tokens', 4000)

            logger.info(f"调用文本生成 API: model={model}, temperature={temperature}")
            response_text = self.client.generate_text(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens
            )

            logger.debug(f"API 返回文本长度: {len(response_text)} 字符")

            # 解析并清洗 JSON 响应
            reply_data = self._parse_json_response(response_text)
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
            error_msg = str(e)
            logger.error(f"评论回复生成失败: {error_msg}")

            # 根据错误类型提供更详细的错误信息
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
                    f"评论回复生成失败。\n"
                    f"错误详情: {error_msg}\n"
                    "建议：检查配置文件 text_providers.yaml"
                )

            return {
                "success": False,
                "error": detailed_error
            }


def get_reply_service() -> ReplyService:
    """
    获取评论区互动助手服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return ReplyService()
