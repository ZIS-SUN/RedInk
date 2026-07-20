"""
爆款体检服务

AI 审稿：对已完成的图文作品（页面文案 + 可选标题/文案/标签）从
封面钩子、标题吸引力、内容结构、情绪价值、行动引导五个维度打分，
并给出最多 5 条可执行的修改建议（含可直接应用的改写文本）

注意：_load_text_config/_get_client 与其他文本服务（如 benchmark.py）
保持一致的自包含实现，等待后续统一重构收编，不要在这里 import
其他服务的私有函数；JSON 解析已收归共享的 parse_llm_json。
"""

import logging
import yaml
from typing import Any, Dict, List, Optional, Tuple
from backend.paths import get_data_root, resource_path
from backend.utils.llm_utils import generate_and_parse_json, parse_llm_json
from backend.utils.text_client import get_text_chat_client
from backend.services.rewrite import build_brand_constraint

logger = logging.getLogger(__name__)

# 五个固定评分维度（顺序即展示顺序）
_DIMENSION_NAMES = ('封面钩子', '标题吸引力', '内容结构', '情绪价值', '行动引导')

# 有激活品牌时追加的第 6 个评分维度
_BRAND_DIMENSION_NAME = '人设一致性'

# 建议的合法 target 与数量上限
_VALID_TARGETS = ('page', 'title', 'copywriting', 'tags')
_MAX_SUGGESTIONS = 5


class ReviewService:
    """爆款体检服务：LLM 给成品打分并输出可执行修改建议"""

    def __init__(self):
        logger.debug("初始化 ReviewService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"ReviewService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

    def _load_text_config(self) -> dict:
        """加载文本生成配置"""
        config_path = get_data_root() / 'text_providers.yaml'
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
        prompt_path = resource_path('backend/prompts/review_prompt.txt')
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应（收归共享的 parse_llm_json）"""
        return parse_llm_json(response_text)

    # ==================== 输入构建 ====================

    @staticmethod
    def _format_pages(pages: List[Dict[str, Any]]) -> str:
        """把页面列表拼成带页码标记的大纲文本"""
        lines = []
        for page in pages:
            index = page.get('index', 0)
            page_type = page.get('type', 'content')
            content = str(page.get('content', '') or '')
            lines.append(f"【第 {int(index) + 1} 页 / {page_type} / page_index={index}】\n{content}")
        return '\n\n'.join(lines)

    @staticmethod
    def _format_optional_list(items: Optional[List[str]]) -> str:
        """标题/标签列表：空时显示「未生成」"""
        if not items:
            return '未生成'
        return '\n'.join(f"- {str(item)}" for item in items)

    @staticmethod
    def _format_optional_text(text: Optional[str]) -> str:
        """发布文案：空时显示「未生成」"""
        text = (text or '').strip()
        return text if text else '未生成'

    # ==================== 字段归一化 ====================

    @staticmethod
    def _clamp_score(value: Any) -> int:
        """把分数收敛为 0-100 的整数，非法值回落为 0"""
        try:
            score = int(round(float(value)))
        except (TypeError, ValueError):
            score = 0
        return max(0, min(100, score))

    @classmethod
    def _normalize_dimensions(
        cls,
        dimensions: Any,
        names: Tuple[str, ...] = _DIMENSION_NAMES
    ) -> List[Dict[str, Any]]:
        """规整维度列表：按预设名称对齐（默认固定 5 项），缺失补默认"""
        if not isinstance(dimensions, list):
            dimensions = []

        # 先按 name 建索引，便于把模型输出对齐到固定维度
        by_name: Dict[str, Dict[str, Any]] = {}
        for item in dimensions:
            if isinstance(item, dict) and item.get('name'):
                by_name[str(item['name'])] = item

        normalized = []
        for position, name in enumerate(names):
            # 优先按名称匹配；匹配不到时按位置兜底
            item = by_name.get(name)
            if item is None and position < len(dimensions) and isinstance(dimensions[position], dict):
                item = dimensions[position]
            if not isinstance(item, dict):
                item = {}
            comment = item.get('comment', '')
            normalized.append({
                'name': name,
                'score': cls._clamp_score(item.get('score')),
                'comment': str(comment) if comment is not None else ''
            })
        return normalized

    @staticmethod
    def _normalize_suggestions(suggestions: Any) -> List[Dict[str, Any]]:
        """规整建议列表：过滤非法 target、page_index 收敛、裁剪到上限"""
        if not isinstance(suggestions, list):
            suggestions = []

        normalized = []
        for item in suggestions:
            if not isinstance(item, dict):
                continue
            target = str(item.get('target', '') or '').strip()
            if target not in _VALID_TARGETS:
                continue

            page_index = item.get('page_index')
            if target == 'page':
                try:
                    page_index = int(page_index)
                except (TypeError, ValueError):
                    # page 类建议没有合法页码时无法应用改写，丢弃页码但保留建议
                    page_index = None
                if page_index is not None and page_index < 0:
                    page_index = None
            else:
                page_index = None

            issue = item.get('issue', '')
            suggestion = item.get('suggestion', '')
            rewrite = item.get('rewrite', '')
            normalized.append({
                'target': target,
                'page_index': page_index,
                'issue': str(issue) if issue is not None else '',
                'suggestion': str(suggestion) if suggestion is not None else '',
                'rewrite': str(rewrite) if rewrite is not None else ''
            })
            if len(normalized) >= _MAX_SUGGESTIONS:
                break
        return normalized

    @classmethod
    def _normalize_review(
        cls,
        data: Any,
        include_brand_dimension: bool = False
    ) -> Dict[str, Any]:
        """
        规整整份体检报告：缺失补默认、score 钳制、suggestions 裁剪

        include_brand_dimension 为 True 时（本次体检注入了品牌人设），
        维度按 6 项对齐（原 5 项 + 「人设一致性」）。
        """
        if not isinstance(data, dict):
            data = {}

        names = _DIMENSION_NAMES
        if include_brand_dimension:
            names = _DIMENSION_NAMES + (_BRAND_DIMENSION_NAME,)

        verdict = data.get('verdict', '')
        return {
            'overall_score': cls._clamp_score(data.get('overall_score')),
            'verdict': str(verdict) if verdict is not None else '',
            'dimensions': cls._normalize_dimensions(data.get('dimensions'), names),
            'suggestions': cls._normalize_suggestions(data.get('suggestions'))
        }

    @staticmethod
    def _build_brand_section(brand: Optional[Dict]) -> str:
        """
        构建体检专用的品牌人设注入文本（有激活品牌时追加到 prompt 末尾）：

        在通用品牌人设约束之外，要求 AI 追加第 6 个评分维度「人设一致性」，
        检查语气贴合度、口头禅/签名的使用以及是否命中禁用词。
        brand 为空或无有效字段时返回空字符串。
        """
        constraint = build_brand_constraint(brand)
        if not constraint:
            return ""
        return constraint + (
            "\n\n### 人设一致性检查（附加维度）：\n"
            "该账号已设置品牌人设（见上）。请在上述 5 个维度之外，"
            "在 dimensions 数组末尾追加第 6 项：\n"
            '{ "name": "人设一致性", "score": 0, "comment": "简短点评" }\n'
            "该维度评估：全文语气是否贴合人设、口头禅/签名是否自然出现、"
            "是否出现禁用词。一旦发现内容中出现禁用词，该维度得分不得高于 40，"
            "并在 comment 中点名命中的禁用词。本次 dimensions 共 6 项。"
        )

    # ==================== 主流程 ====================

    def review_work(
        self,
        topic: str,
        pages: List[Dict[str, Any]],
        titles: Optional[List[str]] = None,
        copywriting: Optional[str] = None,
        tags: Optional[List[str]] = None,
        brand: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        爆款体检：给成品打分并给出修改建议

        参数：
            topic: 创作主题
            pages: 页面列表 [{index, type, content}]
            titles: 候选标题列表（可选）
            copywriting: 发布文案（可选）
            tags: 标签列表（可选）
            brand: 品牌档案字典（可选），提供时追加「人设一致性」检查维度

        返回：
            成功时 {success, review: {overall_score, verdict, dimensions, suggestions}}
            失败时 {success: False, error}
        """
        try:
            logger.info(
                f"开始爆款体检: topic={topic[:50] if topic else '无'}, "
                f"pages={len(pages)}, titles={len(titles) if titles else 0}"
            )

            prompt = self.prompt_template.format(
                topic=topic or '未提供',
                outline=self._format_pages(pages),
                titles=self._format_optional_list(titles),
                copywriting=self._format_optional_text(copywriting),
                tags=self._format_optional_list(tags)
            )

            # 品牌人设约束以字符串追加方式融入（避免破坏模板占位符），
            # 并要求追加「人设一致性」检查维度
            brand_section = self._build_brand_section(brand)
            if brand_section:
                logger.info(f"注入品牌人设约束: brand={brand.get('name', '')}")
                prompt += brand_section

            # 从配置中获取模型参数
            active_provider = self.text_config.get('active_provider', 'google_gemini')
            providers = self.text_config.get('providers', {})
            provider_config = providers.get(active_provider, {})

            model = provider_config.get('model', 'gemini-2.0-flash-exp')
            temperature = provider_config.get('temperature', 1.0)
            max_output_tokens = provider_config.get('max_output_tokens', 8000)

            logger.info(f"调用文本生成 API: model={model}, temperature={temperature}")
            # 生成 + 解析 JSON（json_mode 约束输出格式；解析失败自动带纠正提示重试一次）
            data = generate_and_parse_json(
                lambda prompt_suffix: self.client.generate_text(
                    prompt=prompt + prompt_suffix,
                    model=model,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    json_mode=True
                )
            )
            review = self._normalize_review(
                data, include_brand_dimension=bool(brand_section)
            )

            logger.info(
                f"爆款体检完成: overall_score={review['overall_score']}, "
                f"suggestions={len(review['suggestions'])} 条"
            )

            return {
                "success": True,
                "review": review
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"爆款体检失败: {error_msg}")

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
                    f"爆款体检失败。\n"
                    f"错误详情: {error_msg}\n"
                    "建议：检查配置文件 text_providers.yaml"
                )

            return {
                "success": False,
                "error": detailed_error
            }


def get_review_service() -> ReviewService:
    """
    获取爆款体检服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return ReviewService()
