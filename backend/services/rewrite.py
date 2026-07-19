"""
多平台文案改写服务

将一段文案改写成各内容平台（小红书/抖音口播/公众号/B站/微博）的原生风格
"""

import json
import logging
import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from backend.utils.text_client import get_text_chat_client

logger = logging.getLogger(__name__)

# 支持的平台代号 -> 中文名
SUPPORTED_PLATFORMS = {
    'xiaohongshu': '小红书',
    'douyin': '抖音口播脚本',
    'wechat': '公众号',
    'bilibili': 'B站',
    'weibo': '微博',
}


def build_brand_constraint(brand: Optional[Dict]) -> str:
    """
    把品牌档案（BrandKit 字典）拼成一段「品牌人设约束」文本，
    用于以字符串追加的方式融入生成 prompt（避免破坏模板 .format 占位符）。

    brand 为空或无有效字段时返回空字符串。
    """
    if not isinstance(brand, dict):
        return ""

    def _text(key: str) -> str:
        value = brand.get(key)
        return str(value).strip() if value else ""

    def _items(key: str) -> List[str]:
        value = brand.get(key)
        if not isinstance(value, list):
            return []
        return [str(v).strip() for v in value if v and str(v).strip()]

    lines: List[str] = []
    if _text("name"):
        lines.append(f"- 品牌/IP 名称：{_text('name')}")
    if _text("tagline"):
        lines.append(f"- 一句话定位：{_text('tagline')}")
    if _text("audience"):
        lines.append(f"- 目标人群：{_text('audience')}")
    if _text("tone"):
        lines.append(f"- 语气风格：{_text('tone')}（所有输出的语气必须贴合这一风格）")
    catchphrases = _items("catchphrases")
    if catchphrases:
        lines.append(
            f"- 常用口头禅/开场白：{'、'.join(catchphrases)}（可自然融入内容，不要生硬堆砌）"
        )
    if _text("signature"):
        lines.append(f"- 签名/结尾话术：{_text('signature')}（在内容结尾自然带上）")
    banned_words = _items("banned_words")
    if banned_words:
        lines.append(
            f"- 【禁用词】：{'、'.join(banned_words)} —— 生成的任何内容中都绝对不得出现这些词及其明显变体"
        )
    if _text("notes"):
        lines.append(f"- 补充说明：{_text('notes')}")

    if not lines:
        return ""

    return (
        "\n\n### 品牌人设约束（必须严格遵守）：\n"
        "以下是该账号的品牌人设设定，所有生成内容都必须符合这一人设：\n"
        + "\n".join(lines)
    )


class RewriteService:
    """多平台文案改写服务"""

    def __init__(self):
        logger.debug("初始化 RewriteService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"RewriteService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

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
            "rewrite_prompt.txt"
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

    def rewrite_copy(
        self,
        content: str,
        source_platform: str,
        target_platforms: List[str],
        brand: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        将文案改写为目标平台风格

        参数：
            content: 原始文案（或主题）
            source_platform: 源平台代号（可为空，表示通用文案）
            target_platforms: 目标平台代号列表
            brand: 品牌档案字典（可选），提供时会把品牌人设约束注入 prompt

        返回：
            包含 results 的字典，每项含 platform/title/content/tags
        """
        try:
            logger.info(f"开始改写文案: targets={target_platforms}, 长度={len(content)}")

            source_label = SUPPORTED_PLATFORMS.get(source_platform, '通用（未指定平台）')
            targets_desc = '、'.join(
                f"{code}（{SUPPORTED_PLATFORMS[code]}）" for code in target_platforms
            )

            # 构建提示词
            prompt = self.prompt_template.format(
                content=content,
                source_platform=source_label,
                target_platforms=targets_desc
            )

            # 品牌人设约束以字符串追加方式融入，避免破坏模板占位符
            brand_constraint = build_brand_constraint(brand)
            if brand_constraint:
                logger.info(f"注入品牌人设约束: brand={brand.get('name', '')}")
                prompt += brand_constraint

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
            rewrite_data = self._parse_json_response(response_text)

            raw_results = rewrite_data.get('results', [])
            if not isinstance(raw_results, list) or not raw_results:
                raise ValueError("AI 返回结果中缺少 results 列表")

            results = []
            for item in raw_results:
                if not isinstance(item, dict):
                    continue
                tags = item.get('tags', [])
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(',') if t.strip()]
                results.append({
                    "platform": item.get('platform', ''),
                    "title": item.get('title', ''),
                    "content": item.get('content', ''),
                    "tags": tags,
                })

            if not results:
                raise ValueError("AI 返回的 results 列表为空或格式不正确")

            logger.info(f"文案改写完成: 输出 {len(results)} 个平台版本")

            return {
                "success": True,
                "results": results
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"文案改写失败: {error_msg}")

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
                    f"文案改写失败。\n"
                    f"错误详情: {error_msg}\n"
                    "建议：检查配置文件 text_providers.yaml"
                )

            return {
                "success": False,
                "error": detailed_error
            }


def get_rewrite_service() -> RewriteService:
    """
    获取文案改写服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return RewriteService()
