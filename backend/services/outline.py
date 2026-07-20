import logging
import re
from typing import Dict, List, Any, Optional
from backend.utils.llm_utils import (
    get_text_client,
    load_prompt_template,
    load_text_config,
    resolve_generation_params,
)
from backend.services.rewrite import build_brand_constraint

logger = logging.getLogger(__name__)


def clean_llm_text(text: str) -> str:
    """清洗 LLM 返回的文本：去掉首尾空白，剥掉可能的 ``` 代码块包裹"""
    if not text:
        return ""

    cleaned = text.strip()

    # 剥掉 ```lang\n...\n``` 或 ```\n...\n``` 形式的整体包裹
    fence_match = re.match(r'^```[^\n]*\n([\s\S]*?)\n?```$', cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    return cleaned


class OutlineService:
    def __init__(self):
        logger.debug("初始化 OutlineService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"OutlineService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

    def _load_text_config(self) -> dict:
        """加载文本生成配置"""
        return load_text_config()

    def _get_client(self):
        """根据配置获取客户端"""
        return get_text_client(self.text_config)

    def _load_prompt_template(self) -> str:
        return load_prompt_template('backend/prompts/outline_prompt.txt')

    def _load_polish_prompt_template(self) -> str:
        return load_prompt_template('backend/prompts/polish_page_prompt.txt')

    def polish_page(
        self,
        content: str,
        page_type: str = "content",
        topic: str = "",
        instruction: str = "",
        brand: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        单页 AI 润色：对大纲中某一页的文案按指令重写

        参数：
            content: 该页原文
            page_type: 页面类型（cover/content/summary）
            topic: 整篇主题（可为空）
            instruction: 润色指令（已经过路由层白名单映射的中文描述）
            brand: 品牌档案字典（可选），提供时约束润色结果保持人设语气、不引入禁用词

        返回：
            {"success": True, "content": "润色后的文案"} 或 {"success": False, "error": "..."}
        """
        try:
            logger.info(f"开始单页润色: type={page_type}, 原文长度={len(content)}")

            template = self._load_polish_prompt_template()
            prompt = template.format(
                page_content=content,
                page_type=page_type or "content",
                user_topic=topic.strip() if topic and topic.strip() else "未提供",
                instruction=instruction,
            )

            # 品牌人设约束以字符串追加方式融入，避免破坏模板占位符
            brand_constraint = build_brand_constraint(brand)
            if brand_constraint:
                logger.info(f"注入品牌人设约束: brand={brand.get('name', '')}")
                prompt += brand_constraint + (
                    "\n\n润色后的文案必须保持以上人设的语气风格（不要把人设语气洗掉），"
                    "并且绝对不得引入任何禁用词。"
                )

            # 与大纲生成使用同一 provider/model 配置
            model, temperature, max_output_tokens = resolve_generation_params(
                self.text_config, default_max_output_tokens=8000
            )

            logger.info(f"调用文本生成 API: model={model}, temperature={temperature}")
            raw_text = self.client.generate_text(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

            polished = clean_llm_text(raw_text)
            if not polished:
                raise ValueError("AI 返回的润色结果为空")

            logger.info(f"单页润色完成，结果长度={len(polished)}")
            return {
                "success": True,
                "content": polished,
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"单页润色失败: {error_msg}")

            if "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower() or "401" in error_msg:
                detailed_error = (
                    f"API 认证失败。\n"
                    f"错误详情: {error_msg}\n"
                    "解决方案：在系统设置页面检查并更新 API Key"
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
                    f"单页润色失败。\n"
                    f"错误详情: {error_msg}\n"
                    "建议：检查文本生成服务商配置后重试"
                )

            return {
                "success": False,
                "error": detailed_error
            }

    def build_outline_prompt(
        self,
        topic: str,
        images: Optional[List[bytes]] = None,
        brand: Optional[Dict] = None
    ) -> str:
        """
        组装大纲生成 prompt（流式与非流式共用，保证两条链路产出完全一致）

        参数：
            topic: 用户主题
            images: 参考图片列表（可选，仅影响 prompt 中的提示文案）
            brand: 品牌档案字典（可选），提供时追加品牌人设约束
        """
        prompt = self.prompt_template.format(topic=topic)

        if images and len(images) > 0:
            prompt += f"\n\n注意：用户提供了 {len(images)} 张参考图片，请在生成大纲时考虑这些图片的内容和风格。这些图片可能是产品图、个人照片或场景图，请根据图片内容来优化大纲，使生成的内容与图片相关联。"
            logger.debug(f"添加了 {len(images)} 张参考图片到提示词")

        # 品牌人设约束以字符串追加方式融入，避免破坏模板占位符
        brand_constraint = build_brand_constraint(brand)
        if brand_constraint:
            logger.info(f"注入品牌人设约束: brand={brand.get('name', '')}")
            prompt += brand_constraint

        return prompt

    def get_generation_params(self) -> tuple:
        """解析大纲生成的模型调用参数：(model, temperature, max_output_tokens)"""
        return resolve_generation_params(
            self.text_config, default_max_output_tokens=8000
        )

    def parse_outline(self, outline_text: str) -> List[Dict[str, Any]]:
        """把大纲原始文本解析为页面列表（_parse_outline 的公开入口，供流式端点复用）"""
        return self._parse_outline(outline_text)

    def _parse_outline(self, outline_text: str) -> List[Dict[str, Any]]:
        # 按 <page> 分割页面（兼容旧的 --- 分隔符）
        if '<page>' in outline_text:
            pages_raw = re.split(r'<page>', outline_text, flags=re.IGNORECASE)
        else:
            # 向后兼容：如果没有 <page> 则使用 ---
            pages_raw = outline_text.split("---")

        pages = []

        for index, page_text in enumerate(pages_raw):
            page_text = page_text.strip()
            if not page_text:
                continue

            page_type = "content"
            type_match = re.match(r"\[(\S+)\]", page_text)
            if type_match:
                type_cn = type_match.group(1)
                type_mapping = {
                    "封面": "cover",
                    "内容": "content",
                    "总结": "summary",
                }
                page_type = type_mapping.get(type_cn, "content")

            pages.append({
                "index": index,
                "type": page_type,
                "content": page_text
            })

        return pages

    def generate_outline(
        self,
        topic: str,
        images: Optional[List[bytes]] = None,
        brand: Optional[Dict] = None
    ) -> Dict[str, Any]:
        try:
            logger.info(f"开始生成大纲: topic={topic[:50]}..., images={len(images) if images else 0}")
            # prompt 组装收敛到 build_outline_prompt，与流式端点共用同一逻辑
            prompt = self.build_outline_prompt(topic, images=images, brand=brand)

            # 从配置中获取模型参数
            model, temperature, max_output_tokens = self.get_generation_params()

            logger.info(f"调用文本生成 API: model={model}, temperature={temperature}")
            outline_text = self.client.generate_text(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                images=images
            )

            logger.debug(f"API 返回文本长度: {len(outline_text)} 字符")
            pages = self._parse_outline(outline_text)
            logger.info(f"大纲解析完成，共 {len(pages)} 页")

            return {
                "success": True,
                "outline": outline_text,
                "pages": pages,
                "has_images": images is not None and len(images) > 0
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"大纲生成失败: {error_msg}")

            # 根据错误类型提供更详细的错误信息
            if "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower() or "401" in error_msg:
                detailed_error = (
                    f"API 认证失败。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：\n"
                    "1. API Key 无效或已过期\n"
                    "2. API Key 没有访问该模型的权限\n"
                    "解决方案：在系统设置页面检查并更新 API Key"
                )
            elif "model" in error_msg.lower() or "404" in error_msg:
                detailed_error = (
                    f"模型访问失败。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：\n"
                    "1. 模型名称不正确\n"
                    "2. 没有访问该模型的权限\n"
                    "解决方案：在系统设置页面检查模型名称配置"
                )
            elif "timeout" in error_msg.lower() or "连接" in error_msg:
                detailed_error = (
                    f"网络连接失败。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：\n"
                    "1. 网络连接不稳定\n"
                    "2. API 服务暂时不可用\n"
                    "3. Base URL 配置错误\n"
                    "解决方案：检查网络连接，稍后重试"
                )
            elif "rate" in error_msg.lower() or "429" in error_msg or "quota" in error_msg.lower():
                detailed_error = (
                    f"API 配额限制。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：\n"
                    "1. API 调用次数超限\n"
                    "2. 账户配额用尽\n"
                    "解决方案：等待配额重置，或升级 API 套餐"
                )
            else:
                detailed_error = (
                    f"大纲生成失败。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：\n"
                    "1. Text API 配置错误或密钥无效\n"
                    "2. 网络连接问题\n"
                    "3. 模型无法访问或不存在\n"
                    "建议：检查配置文件 text_providers.yaml"
                )

            return {
                "success": False,
                "error": detailed_error
            }


def get_outline_service() -> OutlineService:
    """
    获取大纲生成服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return OutlineService()
