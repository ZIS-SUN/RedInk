"""
多平台文案改写服务

将一段文案改写成各内容平台（小红书/抖音口播/公众号/B站/微博）的原生风格
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


def build_brand_visual_constraint(brand: Optional[Dict]) -> str:
    """
    把品牌档案中的视觉字段（主色调等）拼成一段「品牌视觉约束」文本，
    用于图片生成 / 封面方向等视觉类 prompt 的字符串追加注入。

    brand 为空或未设置任何视觉字段时返回空字符串（即不注入任何内容）。
    """
    if not isinstance(brand, dict):
        return ""

    lines: List[str] = []
    primary_color = str(brand.get("primary_color") or "").strip()
    if primary_color:
        lines.append(
            f"- 品牌主色调：{primary_color}"
            "（画面配色必须以该颜色作为主色或关键点缀色，保持全套内容的品牌视觉统一）"
        )

    if not lines:
        return ""

    name = str(brand.get("name") or "").strip()
    header = "\n\n### 品牌视觉约束（必须遵守）：\n"
    if name:
        header += f"以下是「{name}」的品牌视觉设定，输出的视觉方案必须与之保持一致：\n"
    return header + "\n".join(lines)


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
        return load_text_config()

    def _get_client(self):
        """根据配置获取客户端"""
        return get_text_client(self.text_config)

    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        return load_prompt_template('backend/prompts/rewrite_prompt.txt')

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应"""
        return parse_llm_json(response_text)

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
            model, temperature, max_output_tokens = resolve_generation_params(
                self.text_config, default_max_output_tokens=8000
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
            logger.error(f"文案改写失败: {e}")
            return {
                "success": False,
                "error": classify_llm_error(e, task_label="文案改写失败")
            }


def get_rewrite_service() -> RewriteService:
    """
    获取文案改写服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return RewriteService()
