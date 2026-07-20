"""
内容生成服务

生成小红书风格的标题、文案和标签
"""

import logging
from typing import Dict, List, Any, Optional
from backend.utils.llm_utils import (
    classify_llm_error,
    get_text_client,
    load_prompt_template,
    load_text_config,
    parse_llm_json,
    resolve_generation_params,
)
from backend.services.rewrite import build_brand_constraint
from backend.utils.banned_words import scan_banned_words

logger = logging.getLogger(__name__)


class ContentService:
    """内容生成服务：生成标题、文案、标签"""

    def __init__(self):
        logger.debug("初始化 ContentService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"ContentService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

    def _load_text_config(self) -> dict:
        """加载文本生成配置"""
        return load_text_config()

    def _get_client(self):
        """根据配置获取客户端"""
        return get_text_client(self.text_config)

    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        return load_prompt_template('backend/prompts/content_prompt.txt')

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应"""
        return parse_llm_json(response_text)

    def generate_content(
        self,
        topic: str,
        outline: str,
        brand: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        生成标题、文案和标签

        参数：
            topic: 用户输入的主题
            outline: 大纲内容
            brand: 品牌档案字典（可选），提供时会把品牌人设约束注入 prompt

        返回：
            包含 titles, copywriting, tags 的字典
        """
        try:
            logger.info(f"开始生成内容: topic={topic[:50]}...")

            # 构建提示词
            prompt = self.prompt_template.format(
                topic=topic,
                outline=outline
            )

            # 品牌人设约束以字符串追加方式融入，避免破坏模板占位符
            brand_constraint = build_brand_constraint(brand)
            if brand_constraint:
                logger.info(f"注入品牌人设约束: brand={brand.get('name', '')}")
                prompt += brand_constraint

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
            content_data = self._parse_json_response(response_text)

            # 验证必要字段
            titles = content_data.get('titles', [])
            copywriting = content_data.get('copywriting', '')
            tags = content_data.get('tags', [])

            # 确保 titles 是列表
            if isinstance(titles, str):
                titles = [titles]

            # 确保 tags 是列表
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(',')]

            logger.info(f"内容生成完成: {len(titles)} 个标题, {len(tags)} 个标签")

            result = {
                "success": True,
                "titles": titles,
                "copywriting": copywriting,
                "tags": tags
            }

            # 禁用词硬校验：使用了品牌人设且设置了禁用词时，
            # 扫描标题/正文/标签并附加命中列表（无品牌或未设禁用词时不加该字段）
            banned_words = brand.get('banned_words') if isinstance(brand, dict) else None
            if banned_words:
                combined_text = "\n".join(
                    [str(t) for t in titles] + [str(copywriting)] + [str(t) for t in tags]
                )
                hits = scan_banned_words(combined_text, banned_words)
                result["banned_word_hits"] = hits
                if hits:
                    logger.warning(f"生成内容命中禁用词: {hits}")

            return result

        except Exception as e:
            logger.error(f"内容生成失败: {e}")
            return {
                "success": False,
                "error": classify_llm_error(e, task_label="内容生成失败")
            }


def get_content_service() -> ContentService:
    """
    获取内容生成服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return ContentService()
