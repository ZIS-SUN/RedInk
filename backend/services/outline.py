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


def load_preference_snippet() -> str:
    """
    获取创作偏好画像的提示词片段（样本不足时为空字符串）。

    画像读取失败一律降级为空字符串——偏好注入是可选增强，
    绝不允许它影响大纲生成主链路。
    """
    # 惰性导入，避免服务模块间的循环依赖
    from backend.services.preference import get_preference_service

    try:
        return get_preference_service().build_prompt_snippet()
    except Exception as e:
        logger.warning(f"获取创作偏好画像失败，忽略偏好注入: {e}")
        return ""


def normalize_seo_keywords(seo_keywords) -> List[str]:
    """
    归一化目标搜索词（小红书搜索埋词）：
    只保留非空字符串，去首尾空白、去重，最多取前 3 个。
    非列表输入（None/脏数据）一律返回空列表，保证埋词是可选增强、
    绝不影响生成主链路。
    """
    if not isinstance(seo_keywords, list):
        return []
    result: List[str] = []
    for item in seo_keywords:
        if not isinstance(item, str):
            continue
        word = item.strip()
        if word and word not in result:
            result.append(word)
    return result[:3]


def build_seo_keywords_constraint(seo_keywords) -> str:
    """
    组装「目标搜索词埋入要求」prompt 片段（大纲生成用）。

    与品牌人设约束同模式：以字符串追加方式融入 prompt，
    避免改动模板占位符；未提供有效搜索词时返回空字符串。
    """
    keywords = normalize_seo_keywords(seo_keywords)
    if not keywords:
        return ""
    core = keywords[0]
    all_words = "、".join(f"「{w}」" for w in keywords)
    return (
        "\n\n## 目标搜索词埋入要求（搜索流量优化）\n"
        f"用户提供了目标搜索词：{all_words}，其中核心词是「{core}」。\n"
        f"1. 封面页的标题文案必须自然包含核心词「{core}」，且核心词要出现在标题的前 15 个字以内\n"
        f"2. 第一个内容页（第 2 页）的开头要自然出现一次核心词「{core}」\n"
        "3. 其余搜索词在后续内容页中自然带到即可，不强求逐页出现\n"
        "4. 严禁堆砌关键词、严禁生硬插入：读起来必须像正常表达，宁可少埋一次也不要影响可读性\n"
    )


# ==================== 批量变体（抖音图文量产） ====================

# 变体数量约束：抖音图文日更 3-5 条的量产节奏，单批最多 5 套
MIN_VARIANT_COUNT = 2
MAX_VARIANT_COUNT = 5
DEFAULT_VARIANT_COUNT = 3

# 差异化维度的中文名（变体标签与前端展示共用同一套文案）
VARIANT_DIMENSION_LABELS = {
    "hook": "换钩子",
    "angle": "换角度",
    "format": "换形式",
}

# 维度默认顺序（未指定 dimensions 时全选，轮转错位也按此顺序）
DEFAULT_VARIANT_DIMENSIONS = ["hook", "angle", "format"]

# 变体差异化指令池：三个维度各备 3-4 条具体指令文案（中文、贴合小红书/
# 抖音语感）。生成第 i 套变体时按「变体序号 + 维度位次」错位轮转取指令，
# 池长取 4/4/3 错开步长，保证全选三维度时 2-5 套的指令组合两两不同。
# 指令全部在运行时以字符串拼接注入 prompt，不改 outline_prompt.txt 模板。
VARIANT_INSTRUCTION_POOLS = {
    "hook": [
        "本套封面标题采用悬念反问式钩子：用一个直戳痛点的反问开头（如“为什么你的××一直没效果？”），把答案留到内页，让人不点进来心痒",
        "本套封面标题采用数字清单式钩子：标题里带明确数字（如“3 个细节”“5 步搞定”），让人一眼觉得干货密度高、照做就行",
        "本套封面标题采用反常识颠覆式钩子：直接推翻一个大家习以为常的做法（如“××根本不用买贵的”），制造“原来我一直做错了”的认知冲击",
        "本套封面标题采用结果前置式钩子：把最诱人的结果或改变放到标题最前面（如“靠这招××直接翻倍”），先给甜头再讲方法",
    ],
    "angle": [
        "本套从新手踩坑视角切入：以过来人口吻复盘最容易犯的错，先讲坑再给解法，通篇带“我踩过所以你别踩”的语气",
        "本套从效率党视角切入：只讲最省时省力的做法，强调“懒人也能照做”，删掉一切可有可无的步骤",
        "本套从对比测评视角切入：把两种以上做法或方案放在一起横向对比，给出明确的优劣结论，让读者直接抄作业",
        "本套从亲身经历视角切入：用第一人称讲一段具体经历（时间、场景、转折都要有），让读者有强代入感",
    ],
    "format": [
        "本套整体采用清单体结构：每页用序号或要点符号罗列干货短句，一页 3-5 条，读起来像可以直接截图保存的清单",
        "本套整体采用问答体结构：每个内容页先抛出一个读者最关心的问题，再给出干脆利落的回答，一问一答推进",
        "本套整体采用步骤教程结构：按“第一步/第二步”的操作顺序推进，每页聚焦一个动作，看完就能上手照做",
    ],
}


def normalize_variant_dimensions(dimensions) -> List[str]:
    """
    归一化差异化维度：仅保留合法维度键并按默认顺序去重；
    非列表/空列表/全非法时回落为默认全选，保证维度是可选增强、
    脏数据绝不影响批量生成主链路。
    """
    if not isinstance(dimensions, list):
        return list(DEFAULT_VARIANT_DIMENSIONS)
    valid = [d for d in DEFAULT_VARIANT_DIMENSIONS if d in dimensions]
    return valid or list(DEFAULT_VARIANT_DIMENSIONS)


def build_variant_label(variant_index: int, dimensions: List[str]) -> str:
    """
    组装变体标签，如「变体2·换角度」「变体1·换钩子+换角度+换形式」。
    用于历史记录标题标注与前端结果展示。
    """
    dims = normalize_variant_dimensions(dimensions)
    dim_text = "+".join(VARIANT_DIMENSION_LABELS[d] for d in dims)
    return f"变体{variant_index + 1}·{dim_text}"


def build_variant_instruction(variant_index: int, dimensions: List[str]) -> str:
    """
    组装第 variant_index 套（0 起）变体的差异化指令 prompt 片段。

    每个所选维度按「变体序号 + 维度位次」错位轮转从指令池取一条，
    多维度组合两两错开；片段以字符串追加方式融入 prompt
    （与品牌人设/搜索埋词同模式），不改动模板占位符。
    """
    dims = normalize_variant_dimensions(dimensions)
    lines = []
    for dim_pos, dim in enumerate(dims):
        pool = VARIANT_INSTRUCTION_POOLS[dim]
        lines.append(f"- {pool[(variant_index + dim_pos) % len(pool)]}")
    return (
        f"\n\n## 本套大纲的差异化要求（第 {variant_index + 1} 套变体）\n"
        "这是同一主题批量生成的多套大纲之一，本套必须严格执行以下差异化指令，"
        "并确保与其他套在开头钩子、切入角度、行文结构上明显不同、不复用同样的表达：\n"
        + "\n".join(lines)
    )


def extract_title_hint(pages) -> str:
    """
    从解析后的页面列表提取标题预览（封面页首行文案）。

    取第一个封面页（无封面页则取第一页）内容中去掉 [封面] 类型标记后的
    第一行非空文本，并剥掉「标题：」前缀，供变体结果列表快速预览。
    结构异常一律返回空字符串，不影响批量生成主链路。
    """
    if not isinstance(pages, list) or not pages:
        return ""
    cover = next(
        (p for p in pages if isinstance(p, dict) and p.get("type") == "cover"),
        None,
    )
    page = cover if cover is not None else pages[0]
    content = page.get("content") if isinstance(page, dict) else None
    if not isinstance(content, str):
        return ""
    for line in content.splitlines():
        text = line.strip()
        # 跳过空行与 [封面] 之类的页面类型标记行
        if not text or re.fullmatch(r"\[\S+\]", text):
            continue
        for prefix in ("标题：", "标题:"):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        return text
    return ""


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
        brand: Optional[Dict] = None,
        seo_keywords: Optional[List[str]] = None,
        variant_instruction: Optional[str] = None
    ) -> str:
        """
        组装大纲生成 prompt（流式与非流式共用，保证两条链路产出完全一致）

        参数：
            topic: 用户主题
            images: 参考图片列表（可选，仅影响 prompt 中的提示文案）
            brand: 品牌档案字典（可选），提供时追加品牌人设约束
            seo_keywords: 目标搜索词列表（可选），提供时追加搜索埋词要求
            variant_instruction: 变体差异化指令片段（可选，批量变体专用），
                提供时以字符串追加方式融入 prompt，不改模板占位符；
                未提供时 prompt 与旧行为完全一致
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

        # 创作偏好画像以可选段落追加（与品牌人设同模式）：
        # 样本不足/读取失败时片段为空字符串，完全不影响现有 prompt
        preference_snippet = load_preference_snippet()
        if preference_snippet:
            logger.info("注入创作偏好画像片段")
            prompt += "\n\n" + preference_snippet

        # 目标搜索词埋入要求（与品牌人设同模式）：
        # 未提供有效搜索词时片段为空字符串，prompt 与旧行为完全一致
        seo_constraint = build_seo_keywords_constraint(seo_keywords)
        if seo_constraint:
            logger.info(f"注入目标搜索词埋入要求: keywords={normalize_seo_keywords(seo_keywords)}")
            prompt += seo_constraint

        # 变体差异化指令（批量变体专用，与品牌人设同模式）：
        # 未提供时不追加任何内容，单篇生成链路行为完全不变
        if variant_instruction:
            logger.info("注入变体差异化指令片段")
            prompt += variant_instruction

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
        brand: Optional[Dict] = None,
        seo_keywords: Optional[List[str]] = None,
        variant_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            logger.info(f"开始生成大纲: topic={topic[:50]}..., images={len(images) if images else 0}")
            # prompt 组装收敛到 build_outline_prompt，与流式端点共用同一逻辑
            prompt = self.build_outline_prompt(
                topic, images=images, brand=brand, seo_keywords=seo_keywords,
                variant_instruction=variant_instruction
            )

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

    def generate_outline_variants(
        self,
        topic: str,
        count: int = DEFAULT_VARIANT_COUNT,
        dimensions: Optional[List[str]] = None,
        brand: Optional[Dict] = None,
        seo_keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        同一选题批量生成多套差异化大纲（抖音图文量产）

        串行循环 count 次复用 generate_outline 的核心逻辑，每次注入不同的
        变体差异化指令（运行时字符串拼接，不改 prompt 模板文件）；每次循环
        都是一次付费 LLM 调用。单套失败不中断整批：记录错误后继续下一套。

        参数：
            topic: 用户主题
            count: 变体套数（调用方需先校验 2-5 范围）
            dimensions: 差异化维度键列表（hook/angle/format），
                非法或缺省时回落为默认全选
            brand / seo_keywords: 透传现有品牌人设与搜索埋词机制

        返回：
            {
                "success": True,
                "variants": [  # 与请求顺序一致，成功失败都在列
                    {"variant_index": 0, "variant_label": "变体1·换钩子+…",
                     "success": True, "outline": 原始文本, "pages": 页面列表}
                    或
                    {"variant_index": 1, "variant_label": "…",
                     "success": False, "error": "错误详情"}
                ],
                "succeeded": 成功套数,
                "failed": 失败套数,
            }
        """
        dims = normalize_variant_dimensions(dimensions)
        logger.info(
            f"开始批量生成大纲变体: topic={topic[:50]}..., "
            f"count={count}, dimensions={dims}"
        )

        variants: List[Dict[str, Any]] = []
        for i in range(count):
            label = build_variant_label(i, dims)
            instruction = build_variant_instruction(i, dims)
            # generate_outline 内部已捕获所有异常并返回 success=False，
            # 天然满足「单套失败不中断整批」
            result = self.generate_outline(
                topic,
                brand=brand,
                seo_keywords=seo_keywords,
                variant_instruction=instruction,
            )
            if result.get("success"):
                variants.append({
                    "variant_index": i,
                    "variant_label": label,
                    "success": True,
                    "outline": result.get("outline", ""),
                    "pages": result.get("pages", []),
                })
            else:
                logger.warning(f"变体生成失败（继续下一套）: {label}")
                variants.append({
                    "variant_index": i,
                    "variant_label": label,
                    "success": False,
                    "error": result.get("error", "大纲生成失败"),
                })

        succeeded = sum(1 for v in variants if v["success"])
        logger.info(f"批量变体生成完成: 成功 {succeeded}/{count} 套")
        return {
            "success": True,
            "variants": variants,
            "succeeded": succeeded,
            "failed": count - succeeded,
        }


def get_outline_service() -> OutlineService:
    """
    获取大纲生成服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return OutlineService()
