"""
对标拆解服务

拆解对标/爆款内容为什么火（钩子、开头、结构、情绪价值、受众、爆点、套路模板），
并可选按同样套路为用户自己的主题生成一篇原创仿写草稿
"""

import json
import logging
import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from backend.utils.text_client import get_text_chat_client

logger = logging.getLogger(__name__)

# analysis 各字段的默认值（str 字段为空串，list 字段为空列表）
_ANALYSIS_STR_FIELDS = ('hook', 'opening', 'emotion', 'audience', 'reusable_template')
_ANALYSIS_LIST_FIELDS = ('structure', 'viral_elements')


class BenchmarkService:
    """对标拆解服务：分析爆款内容 + 可选生成仿写草稿"""

    def __init__(self):
        logger.debug("初始化 BenchmarkService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"BenchmarkService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

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
            "benchmark_prompt.txt"
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

    def _build_draft_section(self, my_topic: Optional[str]) -> str:
        """构建仿写草稿指令段：有 my_topic 时要求仿写，否则要求 draft 留空"""
        if my_topic:
            return (
                "\n用户自己的主题：\n"
                f"{my_topic}\n\n"
                "除了拆解之外，请围绕「用户自己的主题」，按照你从对标内容中拆解出的同一套路，"
                "写一篇完整的仿写草稿，填入 JSON 的 \"draft\" 字段：\n"
                "- 钩子类型、开头手法、内容结构、情绪调动方式与对标内容严格对齐\n"
                "- 内容必须完全原创，只借鉴套路和结构，严禁抄袭或改写对标内容的具体表述\n"
                "- 使用自然、真诚、接地气的表达，可适当使用 emoji 点缀\n"
                "- 不要使用 markdown 格式，直接输出纯文本，段落间用换行分隔\n"
            )
        return (
            "\n本次用户没有提供自己的主题，不需要仿写。"
            "JSON 中的 \"draft\" 字段请保持为空字符串 \"\"。\n"
        )

    @staticmethod
    def _normalize_analysis(analysis: Any) -> Dict[str, Any]:
        """规整 analysis 字段：保证 str/list 字段类型正确、缺失字段补默认值"""
        if not isinstance(analysis, dict):
            analysis = {}

        normalized: Dict[str, Any] = {}
        for field in _ANALYSIS_STR_FIELDS:
            value = analysis.get(field, '')
            if isinstance(value, list):
                value = '\n'.join(str(v) for v in value)
            normalized[field] = str(value) if value is not None else ''

        for field in _ANALYSIS_LIST_FIELDS:
            value = analysis.get(field, [])
            if isinstance(value, str):
                value = [line.strip() for line in value.split('\n') if line.strip()]
            if not isinstance(value, list):
                value = [str(value)]
            normalized[field] = [str(v) for v in value]

        return normalized

    def analyze_benchmark(
        self,
        content: str,
        my_topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        拆解对标内容，可选生成仿写草稿

        参数：
            content: 对标/爆款内容（标题+正文）
            my_topic: 用户自己的主题（可选），提供时按拆解出的套路生成原创仿写草稿

        返回：
            包含 analysis（拆解结果）和 draft（仿写草稿，无 my_topic 时为空串）的字典
        """
        try:
            logger.info(f"开始对标拆解: content_length={len(content)}, my_topic={my_topic[:50] if my_topic else '无'}")

            # 构建提示词
            prompt = self.prompt_template.format(
                content=content,
                draft_section=self._build_draft_section(my_topic)
            )

            # 从配置中获取模型参数
            active_provider = self.text_config.get('active_provider', 'google_gemini')
            providers = self.text_config.get('providers', {})
            provider_config = providers.get(active_provider, {})

            model = provider_config.get('model', 'gemini-2.0-flash-exp')
            temperature = provider_config.get('temperature', 1.0)
            max_output_tokens = provider_config.get('max_output_tokens', 8000)

            logger.info(f"调用文本生成 API: model={model}, temperature={temperature}")
            response_text = self.client.generate_text(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens
            )

            logger.debug(f"API 返回文本长度: {len(response_text)} 字符")

            # 解析 JSON 响应
            data = self._parse_json_response(response_text)

            analysis = self._normalize_analysis(data.get('analysis'))

            draft = data.get('draft', '')
            if not isinstance(draft, str):
                draft = str(draft) if draft is not None else ''
            # 未提供 my_topic 时强制清空草稿，避免模型自作主张输出内容
            if not my_topic:
                draft = ''

            logger.info(
                f"对标拆解完成: {len(analysis['structure'])} 个结构段, "
                f"{len(analysis['viral_elements'])} 个爆点要素, 草稿长度={len(draft)}"
            )

            return {
                "success": True,
                "analysis": analysis,
                "draft": draft
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"对标拆解失败: {error_msg}")

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
                    f"对标拆解失败。\n"
                    f"错误详情: {error_msg}\n"
                    "建议：检查配置文件 text_providers.yaml"
                )

            return {
                "success": False,
                "error": detailed_error
            }


def get_benchmark_service() -> BenchmarkService:
    """
    获取对标拆解服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return BenchmarkService()
