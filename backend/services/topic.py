"""
选题灵感服务

根据用户的领域/赛道和目标平台，由 AI 生成一批有爆款潜力的选题灵感。
注意：这是基于常识/常青角度的 AI 灵感生成，不是实时热榜数据。

另含系列拆解能力（expand_series）：把一个大主题拆成递进连更的系列选题，
吃垂直连更的算法加权与粉丝追更红利。
"""

import logging
import re
from typing import Dict, Any, Optional
from backend.utils.llm_utils import (
    classify_llm_error,
    generate_and_parse_json,
    get_text_client,
    load_prompt_template,
    load_text_config,
    parse_llm_json,
    resolve_generation_params,
)
from backend.services.rewrite import build_brand_constraint

logger = logging.getLogger(__name__)

# 默认生成的选题条数
DEFAULT_TOPIC_COUNT = 10

# format 字段的合法取值，AI 返回超出范围时回退为「图文」
VALID_FORMATS = ('图文', '口播', '清单', '教程', '测评', 'Vlog', '对比', '合集', '问答', '剧情')

# 蹭热点模式：单次最多接受的热点条数（约束 prompt 体积）
MAX_HOT_TOPICS = 20

# 蹭热点模式：单条热点词的最大长度（防超长文本挤爆 prompt）
MAX_HOT_TOPIC_LEN = 100

# 系列拆解：集数取值范围与默认值
SERIES_MIN_COUNT = 5
SERIES_MAX_COUNT = 10
DEFAULT_SERIES_COUNT = 6

# 系列拆解：主题/系列名输入的最大长度（防超长文本挤爆 prompt）
MAX_SERIES_THEME_LEN = 100


class TopicService:
    """选题灵感服务：生成选题标题、切入角度、内容形式、热度预估和话题标签"""

    def __init__(self):
        logger.debug("初始化 TopicService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"TopicService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

    def _load_text_config(self) -> dict:
        """加载文本生成配置"""
        return load_text_config()

    def _get_client(self):
        """根据配置获取客户端"""
        return get_text_client(self.text_config)

    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        return load_prompt_template('backend/prompts/topic_prompt.txt')

    def _build_account_context(self) -> str:
        """
        从数据复盘服务构建账号画像文本（用于注入选题 prompt）。

        无记录、数据不可用或读取异常时一律返回空串（调用方静默忽略），
        绝不因账号数据问题中断选题生成主流程。
        """
        try:
            # 惰性导入：避免选题服务在 analytics 环境异常时初始化失败
            from backend.services.analytics import get_analytics_service
            stats = get_analytics_service().get_stats()
        except Exception as e:
            logger.warning(f"读取账号数据失败，忽略账号画像: {e}")
            return ""

        if not isinstance(stats, dict):
            return ""

        try:
            total_records = int(stats.get('total_records') or 0)
        except (TypeError, ValueError):
            return ""
        if total_records <= 0:
            return ""

        lines = [
            f"- 已发布内容共 {total_records} 篇，平均互动率 {stats.get('avg_engagement_rate', 0)}%"
        ]

        platforms = [p for p in (stats.get('platforms') or []) if isinstance(p, dict) and p.get('name')]
        best_platforms = sorted(
            platforms, key=lambda p: float(p.get('engagement_rate') or 0), reverse=True
        )[:2]
        if best_platforms:
            lines.append(
                "- 表现最好的平台：" + "、".join(
                    f"{p['name']}（{p.get('count', 0)} 篇，互动率 {p.get('engagement_rate', 0)}%）"
                    for p in best_platforms
                )
            )

        content_types = [c for c in (stats.get('content_types') or []) if isinstance(c, dict) and c.get('name')]
        best_types = sorted(
            content_types, key=lambda c: float(c.get('engagement_rate') or 0), reverse=True
        )[:3]
        if best_types:
            lines.append(
                "- 表现最好的内容类型：" + "、".join(
                    f"{c['name']}（{c.get('count', 0)} 篇，互动率 {c.get('engagement_rate', 0)}%）"
                    for c in best_types
                )
            )

        trend = [t for t in (stats.get('trend') or []) if isinstance(t, dict) and t.get('month')]
        if len(trend) >= 2:
            prev, last = trend[-2], trend[-1]
            prev_eng = int(prev.get('engagements') or 0)
            last_eng = int(last.get('engagements') or 0)
            if last_eng > prev_eng:
                direction = '上升'
            elif last_eng < prev_eng:
                direction = '下降'
            else:
                direction = '持平'
            lines.append(
                f"- 近期月趋势：{prev['month']} 互动 {prev_eng} → {last['month']} 互动 {last_eng}，整体{direction}"
            )
        elif len(trend) == 1:
            only = trend[0]
            lines.append(
                f"- 近期月趋势：目前仅 {only['month']} 一个月数据"
                f"（{only.get('count', 0)} 条，互动 {only.get('engagements', 0)}）"
            )

        return "\n".join(lines)

    @staticmethod
    def _apply_account_context(prompt: str, account_context: str) -> str:
        """
        在已构建好的 prompt 末尾追加账号画像段落。

        与 image 服务的 _apply_style_prompt 相同：用运行时字符串拼接而非
        模板占位符，避免给模板新增占位符导致其他 .format 调用点 KeyError。
        account_context 为空时原样返回。
        """
        context = (account_context or "").strip()
        if not context:
            return prompt
        return (
            f"{prompt}\n\n"
            "### 账号画像（基于该用户已录入的真实发布数据）：\n"
            f"{context}\n\n"
            "请在生成选题时优先贴合该账号表现最好的平台调性与内容类型，"
            "并结合近期趋势给出更有把握的选题方向。"
        )

    @staticmethod
    def normalize_hot_topics(hot_topics) -> list:
        """
        归一化用户粘贴的热榜词/热点标题列表：
        - 非列表输入一律返回空列表（等同于常规选题模式）
        - 逐条转字符串、去首尾空白、丢弃空行
        - 单条截断到 MAX_HOT_TOPIC_LEN，总条数截断到 MAX_HOT_TOPICS
        """
        if not isinstance(hot_topics, list):
            return []
        result = []
        for item in hot_topics:
            if item is None:
                continue
            text = str(item).strip()
            if not text:
                continue
            result.append(text[:MAX_HOT_TOPIC_LEN])
            if len(result) >= MAX_HOT_TOPICS:
                break
        return result

    @staticmethod
    def _apply_hot_topics(prompt: str, hot_topics: list) -> str:
        """
        在已构建好的 prompt 末尾追加蹭热点指令段落。

        与 _apply_account_context 相同：用运行时字符串拼接而非模板占位符，
        避免给模板新增占位符导致其他 .format 调用点 KeyError。
        hot_topics 为空时原样返回（保持常规选题行为完全不变）。
        """
        if not hot_topics:
            return prompt

        hot_lines = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(hot_topics))
        return (
            f"{prompt}\n\n"
            "### 蹭热点模式（用户手动粘贴的热榜词/热点标题，每行一条）：\n"
            f"{hot_lines}\n\n"
            "本次进入「蹭热点」模式，请调整生成策略：\n"
            "1. 不再基于常青角度自由发挥，改为围绕上面列出的每个热点逐一产出选题，"
            "每个热点至少产出 1 条，把热点与用户的领域/赛道自然结合\n"
            "2. angle 字段写清「蹭点角度」：这个热点怎么和用户赛道挂钩、借哪股情绪或流量\n"
            "3. 每条选题在原有字段基础上额外输出以下字段（都是字符串）：\n"
            '   - "hot_topic": 对应的热点原词（与上面列表中的某一条一致）\n'
            '   - "publish_window": 建议发布窗口（如"48 小时内""3 天内"，热点时效性越强窗口越短）\n'
            '   - "relevance": 与用户赛道的关联度评估（高/中/低 + 一句话理由，'
            "关联度低的热点也要如实标注，帮用户判断值不值得蹭）\n"
            "4. 其余输出格式要求（JSON 结构、title/format/heat/tags 的标准）保持不变"
        )

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应"""
        return parse_llm_json(response_text)

    def _normalize_topic(self, item: Any) -> Dict[str, Any]:
        """把 AI 返回的单条选题收敛为标准结构，非法字段做兜底"""
        if not isinstance(item, dict):
            return {}

        title = str(item.get('title', '')).strip()
        if not title:
            return {}

        angle = str(item.get('angle', '')).strip()

        content_format = str(item.get('format', '')).strip()
        if content_format not in VALID_FORMATS:
            content_format = '图文'

        try:
            heat = int(item.get('heat', 0))
        except (TypeError, ValueError):
            heat = 0
        heat = max(0, min(100, heat))

        tags = item.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]
        if not isinstance(tags, list):
            tags = []
        tags = [str(t).strip().lstrip('#') for t in tags if str(t).strip()]

        topic = {
            'title': title,
            'angle': angle,
            'format': content_format,
            'heat': heat,
            'tags': tags
        }

        # 蹭热点模式的增量字段（可选）：仅在 AI 返回了非空值时透传
        for optional_field in ('hot_topic', 'publish_window', 'relevance'):
            value = str(item.get(optional_field, '') or '').strip()
            if value:
                topic[optional_field] = value

        return topic

    def generate_topics(
        self,
        niche: str,
        platform: str = '小红书',
        count: int = DEFAULT_TOPIC_COUNT,
        use_account_data: bool = False,
        brand: Optional[Dict] = None,
        hot_topics: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        生成选题灵感列表

        参数：
            niche: 用户的领域/赛道（如"健身减脂""职场干货"）
            platform: 目标平台（如"小红书""抖音"）
            count: 期望生成的选题条数
            use_account_data: 是否结合数据复盘工具录入的账号数据（无记录时静默忽略）
            brand: 品牌档案字典（可选），提供时会把品牌人设约束注入 prompt
            hot_topics: 用户手动粘贴的热榜词/热点标题列表（可选）。
                提供时进入「蹭热点」模式：围绕每个热点产出蹭点角度、
                建议发布窗口与赛道关联度评估（增量字段可选）

        返回：
            包含 topics 列表的字典，每条含 title/angle/format/heat/tags
            （蹭热点模式下可能另含 hot_topic/publish_window/relevance）；
            另含 account_context_used 表示本次是否实际注入了账号画像
        """
        account_context_used = False
        try:
            normalized_hot_topics = self.normalize_hot_topics(hot_topics)
            logger.info(
                f"开始生成选题灵感: niche={niche[:50]}, platform={platform}, "
                f"use_account_data={use_account_data}, "
                f"hot_topics={len(normalized_hot_topics)} 条"
            )

            # 构建提示词
            prompt = self.prompt_template.format(
                niche=niche,
                platform=platform,
                count=count
            )

            # 蹭热点模式：把热点列表与蹭点要求追加到 prompt 末尾（空列表时不改变行为）
            if normalized_hot_topics:
                prompt = self._apply_hot_topics(prompt, normalized_hot_topics)
                logger.info("已注入蹭热点指令到选题 prompt")

            # 结合账号数据：有记录时把账号画像追加到 prompt 末尾，无记录时静默忽略
            if use_account_data:
                account_context = self._build_account_context()
                if account_context:
                    prompt = self._apply_account_context(prompt, account_context)
                    account_context_used = True
                    logger.info("已注入账号画像到选题 prompt")
                else:
                    logger.info("use_account_data=True 但暂无账号数据，忽略账号画像")

            # 品牌人设约束以字符串追加方式融入，避免破坏模板占位符
            brand_constraint = build_brand_constraint(brand)
            if brand_constraint:
                logger.info(f"注入品牌人设约束: brand={brand.get('name', '')}")
                prompt += brand_constraint + (
                    "\n\n请确保生成的选题方向贴合以上品牌人设的定位与目标人群，"
                    "选题标题的措辞风格也要符合该人设的语气，并且不出现任何禁用词。"
                )

            # 从配置中获取模型参数
            model, temperature, max_output_tokens = resolve_generation_params(
                self.text_config, default_max_output_tokens=4000
            )

            logger.info(f"调用文本生成 API: model={model}, temperature={temperature}")
            # 生成 + 解析 JSON（json_mode 约束输出格式；解析失败自动带纠正提示重试一次）
            topic_data = generate_and_parse_json(
                lambda prompt_suffix: self.client.generate_text(
                    prompt=prompt + prompt_suffix,
                    model=model,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    json_mode=True
                )
            )

            raw_topics = topic_data.get('topics', [])
            if not isinstance(raw_topics, list):
                raw_topics = []

            topics = [t for t in (self._normalize_topic(item) for item in raw_topics) if t]

            if not topics:
                logger.error("AI 返回结果中没有有效的选题条目")
                raise ValueError("AI 未返回有效的选题内容，请重试")

            logger.info(f"选题灵感生成完成: {len(topics)} 条")

            return {
                "success": True,
                "topics": topics,
                "account_context_used": account_context_used
            }

        except Exception as e:
            logger.error(f"选题灵感生成失败: {e}")
            return {
                "success": False,
                "error": classify_llm_error(e, task_label="选题灵感生成失败")
            }

    # ==================== 系列拆解（把大主题拆成递进连更系列） ====================

    @staticmethod
    def clamp_series_count(count) -> int:
        """
        集数归一化：非法类型回退默认值，越界钳制到 [SERIES_MIN_COUNT, SERIES_MAX_COUNT]。
        """
        try:
            value = int(count)
        except (TypeError, ValueError):
            return DEFAULT_SERIES_COUNT
        return max(SERIES_MIN_COUNT, min(SERIES_MAX_COUNT, value))

    @staticmethod
    def _build_series_prompt(
        theme: str,
        count: int,
        niche: str = '',
        platform: str = '',
        series_name: str = ''
    ) -> str:
        """
        运行时拼接系列拆解 prompt（不走模板文件，保持简单、避免占位符冲突）。

        编排要求写死在 prompt 里：第 1 集立题引流、中段逐层深入各打一个
        具体痛点、末集进阶/总结收口，标题差异化不同质。
        """
        # 选填上下文逐段拼接，空值不出现在 prompt 中
        context_lines = []
        if niche:
            context_lines.append(f"创作者领域/赛道：{niche}")
        if platform:
            context_lines.append(f"目标平台：{platform}")
        context_block = ("\n".join(context_lines) + "\n\n") if context_lines else ""

        if series_name:
            series_name_rule = (
                f"系列名固定使用用户指定的「{series_name}」，"
                '输出的 "series_name" 字段必须与其完全一致。'
            )
        else:
            series_name_rule = (
                "用户未指定系列名，请你起一个 4-10 字、有辨识度、方便读者追更的系列名"
                "（如「新手化妆避坑」「租房改造日记」），不要带书名号或引号。"
            )

        return (
            "你是一个深耕内容创作行业的系列策划专家，深谙垂直连更的算法逻辑：\n"
            "系列内容会获得平台算法加权，粉丝会追更，系列中一篇爆则全系列被翻牌。\n\n"
            "## 任务\n"
            f"把下面的大主题拆解成一个 {count} 集的递进系列选题，每一集都能独立成篇，"
            "串起来又是一个完整的进阶路径。\n\n"
            f"大主题：{theme}\n\n"
            f"{context_block}"
            "## 系列编排要求（必须遵守）\n"
            f"1. 第 1 集负责立题引流：点明系列价值、制造追更钩子，让读者知道追完整个系列能得到什么\n"
            f"2. 中段各集逐层深入，每一集只打一个具体痛点，一集讲透一件事，不贪多\n"
            f"3. 最后一集负责进阶/总结收口：给出进阶方向或全系列要点回顾，形成完整闭环\n"
            "4. 各集标题措辞差异化，不要同质化（不要每集都是「XX 的 N 个技巧」这种同一句式）\n"
            f"5. {series_name_rule}\n\n"
            "## 输出格式\n"
            "请严格按以下 JSON 格式输出（必须是有效的 JSON，不要包含其他说明文字）：\n\n"
            "{\n"
            '  "series_name": "系列名",\n'
            '  "episodes": [\n'
            "    {\n"
            '      "order": 1,\n'
            '      "title": "系列名｜01 本集具体标题",\n'
            '      "angle": "本集切入角度：这一集讲什么、戳中什么痛点",\n'
            '      "progression": "在系列中的递进作用一句话（如：立题引流，建立追更预期）"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "## 字段要求\n"
            f"- episodes 恰好 {count} 集，order 从 1 开始连续递增\n"
            '- title 统一格式「系列名｜0X 本集具体标题」：竖线用全角「｜」，'
            "集数编号两位数字（01、02……），编号后接一个空格再写本集具体标题；"
            "具体标题 8-20 字、有画面感，能独立当一篇笔记/视频的标题用\n"
            "- angle 一句话说清本集的切入角度与痛点，20-50 字，讲人话\n"
            "- progression 一句话说清这一集在整个系列递进结构中的位置和作用，15-40 字\n\n"
            "## 重要提醒\n"
            "- 直接输出 JSON，不要有任何其他说明或对话\n"
            "- 确保 JSON 格式正确，可以被解析"
        )

    @staticmethod
    def _format_series_title(series_name: str, order: int, bare_title: str) -> str:
        """按统一格式「{series_name}｜0X 具体标题」组装单集标题。"""
        return f"{series_name}｜{order:02d} {bare_title}"

    def _normalize_episode(
        self, item: Any, fallback_order: int, series_name: str
    ) -> Dict[str, Any]:
        """
        把 AI 返回的单集收敛为标准结构 {order, title, angle, progression}。

        - title 为空的条目直接丢弃（返回空 dict）
        - order 非法时回退为该集在数组中的位置
        - AI 没按「系列名｜0X 标题」格式输出时，剥掉它自带的编号前缀后重新组装，
          保证入库/铺日历拿到的标题格式统一
        """
        if not isinstance(item, dict):
            return {}

        title = str(item.get('title', '')).strip()
        if not title:
            return {}

        try:
            order = int(item.get('order', 0))
        except (TypeError, ValueError):
            order = 0
        if order <= 0:
            order = fallback_order

        # 已符合「系列名｜」前缀的标题只取竖线后的部分重排编号；
        # 兼容 AI 用半角 | 或漏写系列名的情况
        bare = title
        for sep in ('｜', '|'):
            if sep in bare:
                prefix, rest = bare.split(sep, 1)
                if prefix.strip() == series_name or not prefix.strip():
                    bare = rest
                break
        # 剥掉「第1集：」「01.」等编号前缀，避免双重编号
        bare = re.sub(
            r'^\s*(?:第\s*\d+\s*[集期篇]\s*[.、:：\-\s]?|\d{1,2}\s*[.、:：\-])\s*',
            '', bare
        ).strip()
        # 「数字+空格」前缀仅在编号与集数吻合时才剥（如 01 对应第 1 集），
        # 避免误伤「10 分钟搞定底妆」这类以数字开头的正常标题
        numbered = re.match(r'^\s*(\d{1,2})\s+(\S.*)$', bare)
        if numbered and int(numbered.group(1)) == order:
            bare = numbered.group(2).strip()
        if not bare:
            bare = title

        angle = str(item.get('angle', '')).strip()
        progression = str(item.get('progression', '')).strip()

        return {
            'order': order,
            'title': self._format_series_title(series_name, order, bare),
            'angle': angle,
            'progression': progression,
        }

    def expand_series(
        self,
        theme: str,
        count: int = DEFAULT_SERIES_COUNT,
        niche: str = '',
        platform: str = '',
        series_name: str = ''
    ) -> Dict[str, Any]:
        """
        把一个大主题拆解成递进系列选题（一次 LLM 调用）

        参数：
            theme: 大主题（必填，如"新手化妆"）
            count: 集数（5-10，越界自动钳制，默认 6）
            niche: 领域/赛道（选填，注入 prompt 供 AI 贴合赛道语境）
            platform: 目标平台（选填）
            series_name: 系列名（选填，不填由 AI 起名）

        返回：
            成功：{success: True, series_name, episodes}，每集含
                order/title/angle/progression，title 统一为「系列名｜0X 标题」格式
            失败：{success: False, error}
        """
        try:
            theme = (theme or '').strip()[:MAX_SERIES_THEME_LEN]
            if not theme:
                raise ValueError("系列主题不能为空")

            count = self.clamp_series_count(count)
            niche = (niche or '').strip()[:MAX_SERIES_THEME_LEN]
            platform = (platform or '').strip()[:MAX_SERIES_THEME_LEN]
            series_name = (series_name or '').strip()[:MAX_SERIES_THEME_LEN]

            logger.info(
                f"开始系列拆解: theme={theme[:50]}, count={count}, "
                f"niche={niche[:30]}, platform={platform}, "
                f"series_name={series_name[:30] or '(AI 起名)'}"
            )

            prompt = self._build_series_prompt(
                theme, count, niche=niche, platform=platform, series_name=series_name
            )

            model, temperature, max_output_tokens = resolve_generation_params(
                self.text_config, default_max_output_tokens=4000
            )

            logger.info(f"调用文本生成 API: model={model}, temperature={temperature}")
            # 生成 + 解析 JSON（与 generate_topics 相同：解析失败自动带纠正提示重试一次）
            series_data = generate_and_parse_json(
                lambda prompt_suffix: self.client.generate_text(
                    prompt=prompt + prompt_suffix,
                    model=model,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    json_mode=True
                )
            )

            # 系列名：优先用户指定，其次 AI 返回，最后回退大主题
            final_series_name = series_name or str(
                series_data.get('series_name', '') or ''
            ).strip() or theme

            raw_episodes = series_data.get('episodes', [])
            if not isinstance(raw_episodes, list):
                raw_episodes = []

            episodes = []
            for index, item in enumerate(raw_episodes):
                episode = self._normalize_episode(item, index + 1, final_series_name)
                if episode:
                    episodes.append(episode)

            if not episodes:
                logger.error("AI 返回结果中没有有效的系列集数")
                raise ValueError("AI 未返回有效的系列内容，请重试")

            # 按 order 排序后重排为连续编号，标题中的编号同步刷新
            episodes.sort(key=lambda e: e['order'])
            title_prefix = f"{final_series_name}｜"
            for index, episode in enumerate(episodes):
                new_order = index + 1
                if episode['order'] != new_order:
                    # 标题里的编号是按旧 order 组装的，剥掉已知前缀与旧编号后重新组装
                    bare = episode['title']
                    if bare.startswith(title_prefix):
                        bare = bare[len(title_prefix):]
                    bare = re.sub(r'^\d{2}\s', '', bare)
                    episode['order'] = new_order
                    episode['title'] = self._format_series_title(
                        final_series_name, new_order, bare
                    )

            logger.info(f"系列拆解完成: 「{final_series_name}」共 {len(episodes)} 集")

            return {
                "success": True,
                "series_name": final_series_name,
                "episodes": episodes,
            }

        except Exception as e:
            logger.error(f"系列拆解失败: {e}")
            return {
                "success": False,
                "error": classify_llm_error(e, task_label="系列拆解失败")
            }


def get_topic_service() -> TopicService:
    """
    获取选题灵感服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return TopicService()
