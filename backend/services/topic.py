"""
选题灵感服务

根据用户的领域/赛道和目标平台，由 AI 生成一批有爆款潜力的选题灵感。
注意：这是基于常识/常青角度的 AI 灵感生成，不是实时热榜数据。
"""

import json
import logging
import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any
from backend.utils.text_client import get_text_chat_client

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
            "topic_prompt.txt"
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
        count: int = DEFAULT_TOPIC_COUNT
    ) -> Dict[str, Any]:
        """
        生成选题灵感列表

        参数：
            niche: 用户的领域/赛道（如"健身减脂""职场干货"）
            platform: 目标平台（如"小红书""抖音"）
            count: 期望生成的选题条数

        返回：
            包含 topics 列表的字典，每条含 title/angle/format/heat/tags
        """
        try:
            logger.info(f"开始生成选题灵感: niche={niche[:50]}, platform={platform}")

            # 构建提示词
            prompt = self.prompt_template.format(
                niche=niche,
                platform=platform,
                count=count
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
                "topics": topics
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"选题灵感生成失败: {error_msg}")

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
                    f"选题灵感生成失败。\n"
                    f"错误详情: {error_msg}\n"
                    "建议：检查配置文件 text_providers.yaml"
                )

            return {
                "success": False,
                "error": detailed_error
            }


def get_topic_service() -> TopicService:
    """
    获取选题灵感服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return TopicService()
