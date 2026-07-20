"""
封面 A/B 方向生成服务

根据主题/内容一次生成 3-4 个差异化封面方向（文案 + 视觉概念），用于 A/B 测试对比
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
from backend.services.rewrite import build_brand_constraint, build_brand_visual_constraint

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
        return load_text_config()

    def _get_client(self):
        """根据配置获取客户端"""
        return get_text_client(self.text_config)

    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        return load_prompt_template('backend/prompts/cover_prompt.txt')

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应"""
        return parse_llm_json(response_text)

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

    def generate_cover_directions(
        self,
        topic: str,
        content: str = "",
        brand: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        生成 3-4 个差异化封面方向

        参数：
            topic: 用户输入的主题
            content: 补充内容/背景（可选）
            brand: 品牌档案字典（可选），提供时注入品牌人设约束；
                档案设置了主色调等视觉字段时，额外注入品牌视觉约束

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

            # 品牌人设/视觉约束以字符串追加方式融入，避免破坏模板占位符
            brand_constraint = build_brand_constraint(brand)
            if brand_constraint:
                logger.info(f"注入品牌人设约束: brand={brand.get('name', '')}")
                prompt += brand_constraint
            # 品牌未设置视觉字段（如主色调）时不注入任何视觉内容
            visual_constraint = build_brand_visual_constraint(brand)
            if visual_constraint:
                prompt += visual_constraint + (
                    "\n各封面方向的 visual_concept 配色方案应以品牌主色调为基础展开，"
                    "同时保持方向之间的差异化。"
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
            logger.error(f"封面方向生成失败: {e}")
            return {
                "success": False,
                "error": classify_llm_error(e, task_label="封面方向生成失败")
            }


def get_cover_service() -> CoverService:
    """
    获取封面方向生成服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return CoverService()
