"""
对标拆解服务

拆解对标/爆款内容为什么火（钩子、开头、结构、情绪价值、受众、爆点、套路模板），
并可选按同样套路为用户自己的主题生成一篇原创仿写草稿
"""

import logging
from typing import Dict, Any, Optional
from backend.utils.llm_utils import (
    classify_llm_error,
    get_text_client,
    load_prompt_template,
    load_text_config,
    parse_llm_json,
    resolve_generation_params,
)

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
        return load_text_config()

    def _get_client(self):
        """根据配置获取客户端"""
        return get_text_client(self.text_config)

    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        return load_prompt_template('backend/prompts/benchmark_prompt.txt')

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应"""
        return parse_llm_json(response_text)

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
            logger.error(f"对标拆解失败: {e}")
            return {
                "success": False,
                "error": classify_llm_error(e, task_label="对标拆解失败")
            }


def get_benchmark_service() -> BenchmarkService:
    """
    获取对标拆解服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return BenchmarkService()
