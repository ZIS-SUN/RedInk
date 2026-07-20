"""
爆款标题生成服务

根据主题/文案草稿、平台与风格倾向，一次生成 10-15 个爆款候选标题，
每个标题标注命中的爆款要素并给出 0-100 的吸引力评分。
"""

import logging
import re
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
from backend.utils.banned_words import scan_banned_words

logger = logging.getLogger(__name__)

# 生成的候选标题数量范围
TITLE_COUNT = 12
MIN_TITLES = 10
MAX_TITLES = 15


class TitleService:
    """爆款标题生成服务"""

    def __init__(self):
        logger.debug("初始化 TitleService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"TitleService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

    def _load_text_config(self) -> dict:
        """加载文本生成配置"""
        return load_text_config()

    def _get_client(self):
        """根据配置获取客户端"""
        return get_text_client(self.text_config)

    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        return load_prompt_template('backend/prompts/title_prompt.txt')

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应"""
        return parse_llm_json(response_text)

    def _normalize_titles(self, raw_titles: Any) -> list:
        """清洗 AI 返回的标题列表：过滤非法项、收敛 score/elements 类型"""
        titles = []
        if not isinstance(raw_titles, list):
            return titles

        for item in raw_titles[:MAX_TITLES]:
            if isinstance(item, str):
                item = {"text": item}
            if not isinstance(item, dict):
                continue

            text = str(item.get('text', '')).strip()
            if not text:
                continue

            try:
                score = int(round(float(item.get('score', 0))))
            except (TypeError, ValueError):
                score = 0
            score = max(0, min(100, score))

            elements = item.get('elements', [])
            if isinstance(elements, str):
                elements = [e.strip() for e in re.split(r'[,，、]', elements) if e.strip()]
            if not isinstance(elements, list):
                elements = []
            elements = [str(e).strip() for e in elements if str(e).strip()]

            titles.append({
                "text": text,
                "score": score,
                "elements": elements
            })

        return titles

    def generate_titles(
        self,
        topic: str,
        platform: str,
        style: str,
        brand: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        生成爆款候选标题

        参数：
            topic: 用户输入的主题/文案草稿
            platform: 目标平台（如：小红书、抖音）
            style: 风格倾向（如：悬念型、数字型）
            brand: 品牌档案字典（可选），提供时会把品牌人设约束注入 prompt

        返回：
            {"success": True, "titles": [{"text", "score", "elements"}, ...]}
        """
        try:
            logger.info(f"开始生成爆款标题: topic={topic[:50]}..., platform={platform}, style={style}")

            # 构建提示词
            prompt = self.prompt_template.format(
                topic=topic,
                platform=platform,
                style=style,
                count=TITLE_COUNT
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

            # 解析并清洗 JSON 响应
            title_data = self._parse_json_response(response_text)
            titles = self._normalize_titles(title_data.get('titles', []))

            if not titles:
                raise ValueError("AI 未返回任何有效标题，请重试")

            if len(titles) < MIN_TITLES:
                logger.warning(f"AI 返回标题数量偏少: {len(titles)} 个（期望 {MIN_TITLES}-{MAX_TITLES} 个）")

            # 禁用词硬校验：使用了品牌人设且设置了禁用词时，
            # 为每个候选标题附加命中列表（无品牌或未设禁用词时不加该字段）
            banned_words = brand.get('banned_words') if isinstance(brand, dict) else None
            if banned_words:
                for item in titles:
                    item["banned_word_hits"] = scan_banned_words(item["text"], banned_words)
                hit_count = sum(1 for item in titles if item["banned_word_hits"])
                if hit_count:
                    logger.warning(f"有 {hit_count} 个候选标题命中禁用词")

            logger.info(f"爆款标题生成完成: {len(titles)} 个候选")

            return {
                "success": True,
                "titles": titles
            }

        except Exception as e:
            logger.error(f"爆款标题生成失败: {e}")
            return {
                "success": False,
                "error": classify_llm_error(e, task_label="爆款标题生成失败")
            }


def get_title_service() -> TitleService:
    """
    获取爆款标题生成服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return TitleService()
