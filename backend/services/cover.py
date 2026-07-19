"""
封面 A/B 方向生成服务

根据主题/内容一次生成 3-4 个差异化封面方向（文案 + 视觉概念），用于 A/B 测试对比
"""

import json
import logging
import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any
from backend.utils.text_client import get_text_chat_client

logger = logging.getLogger(__name__)


class CoverService:
    """封面方向生成服务：生成差异化封面方向（标题文案、视觉概念、评分、理由）"""

    def __init__(self):
        logger.debug("初始化 CoverService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"CoverService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

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
            "cover_prompt.txt"
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

    def _normalize_directions(self, directions: Any) -> List[Dict[str, Any]]:
        """校验并规范化方向列表，剔除无效项、收敛评分范围"""
        if not isinstance(directions, list):
            return []

        normalized = []
        for item in directions:
            if not isinstance(item, dict):
                continue
            title = str(item.get('title', '')).strip()
            if not title:
                continue

            try:
                score = int(item.get('score', 0))
            except (TypeError, ValueError):
                score = 0
            score = max(0, min(100, score))

            normalized.append({
                "title": title,
                "subtitle": str(item.get('subtitle', '')).strip(),
                "visual_concept": str(item.get('visual_concept', '')).strip(),
                "style": str(item.get('style', '')).strip(),
                "score": score,
                "reason": str(item.get('reason', '')).strip(),
            })
        return normalized

    def generate_cover_directions(self, topic: str, content: str = "") -> Dict[str, Any]:
        """
        生成 3-4 个差异化封面方向

        参数：
            topic: 用户输入的主题
            content: 补充内容/背景（可选）

        返回：
            包含 directions 列表的字典
        """
        try:
            logger.info(f"开始生成封面方向: topic={topic[:50]}...")

            # 构建提示词
            prompt = self.prompt_template.format(
                topic=topic,
                content=content or "（无）"
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
            cover_data = self._parse_json_response(response_text)

            directions = self._normalize_directions(cover_data.get('directions', []))
            if not directions:
                raise ValueError("AI 未返回有效的封面方向，请重试")

            logger.info(f"封面方向生成完成: {len(directions)} 个方向")

            return {
                "success": True,
                "directions": directions
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"封面方向生成失败: {error_msg}")

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
                    f"封面方向生成失败。\n"
                    f"错误详情: {error_msg}\n"
                    "建议：检查配置文件 text_providers.yaml"
                )

            return {
                "success": False,
                "error": detailed_error
            }


def get_cover_service() -> CoverService:
    """
    获取封面方向生成服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return CoverService()
