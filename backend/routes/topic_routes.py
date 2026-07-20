"""
选题灵感相关 API 路由

包含功能：
- 根据领域/赛道 + 目标平台生成 AI 选题灵感
- 把大主题拆解成递进系列选题（系列/合集能力）
"""

import time
import logging
from flask import Blueprint, request, jsonify
from backend.services.topic import (
    DEFAULT_SERIES_COUNT,
    SERIES_MAX_COUNT,
    SERIES_MIN_COUNT,
    get_topic_service,
)
from backend.services.brand import resolve_brand_for_prompt
from .utils import (
    api_error_response,
    log_request,
    log_error,
    normalize_error_result,
    validation_error,
)

logger = logging.getLogger(__name__)


def create_topic_blueprint():
    """创建选题灵感路由蓝图（工厂函数，支持多次调用）"""
    topic_bp = Blueprint('topic', __name__)

    @topic_bp.route('/topic', methods=['POST'])
    def generate_topics():
        """
        生成选题灵感

        请求格式（application/json）：
        - niche: 领域/赛道（必填，如"健身减脂""职场干货"）
        - platform: 目标平台（可选，默认"小红书"）
        - use_account_data: 是否结合数据复盘工具录入的账号数据（可选，默认 False）
        - brand_id: 品牌档案 ID（可选）；未提供时自动使用「当前启用」档案，
          取不到品牌数据时静默跳过品牌注入
        - hot_topics: 手动粘贴的热榜词/热点标题，字符串数组（可选）。
          提供时进入「蹭热点」模式，非法类型静默忽略（等同常规模式）

        返回：
        - success: 是否成功
        - topics: 选题列表，每条含 title/angle/format/heat/tags
          （蹭热点模式下可能另含 hot_topic/publish_window/relevance）
        - account_context_used: 本次是否实际结合了账号数据
        """
        start_time = time.time()

        try:
            data = request.get_json(silent=True) or {}
            niche = (data.get('niche') or '').strip()
            platform = (data.get('platform') or '小红书').strip() or '小红书'
            use_account_data = bool(data.get('use_account_data', False))
            brand_id = data.get('brand_id')
            hot_topics = data.get('hot_topics')

            log_request('/topic', {
                'niche': niche[:50],
                'platform': platform,
                'use_account_data': use_account_data,
                'hot_topics_count': len(hot_topics) if isinstance(hot_topics, list) else 0,
            })

            # 验证必填参数
            if not niche:
                logger.warning("选题灵感请求缺少 niche 参数")
                return api_error_response(
                    validation_error("niche 不能为空", "请输入你的领域或赛道，例如：健身减脂。"),
                    context={"endpoint": "/api/topic"},
                )

            # 解析品牌档案（未传 brand_id 时回退当前启用档案，取不到时静默忽略）
            brand = resolve_brand_for_prompt(brand_id)

            # 调用选题灵感服务
            logger.info(f"🔄 开始生成选题灵感，领域: {niche[:50]}，平台: {platform}")
            topic_service = get_topic_service()
            result = topic_service.generate_topics(
                niche, platform, use_account_data=use_account_data, brand=brand,
                hot_topics=hot_topics
            )

            # 记录结果
            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 选题灵感生成成功，耗时 {elapsed:.2f}s")
                return jsonify(result), 200
            else:
                logger.error(f"❌ 选题灵感生成失败: {result.get('error', '未知错误')}")
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/topic"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/topic', e)
            return api_error_response(e, context={"endpoint": "/api/topic"})

    @topic_bp.route('/topic/series', methods=['POST'])
    def expand_series():
        """
        把大主题拆解成递进系列选题

        请求格式（application/json）：
        - theme: 大主题（必填，如"新手化妆"）
        - count: 集数（可选，5-10，默认 6；非数字报错，越界自动钳制）
        - niche: 领域/赛道（可选）
        - platform: 目标平台（可选）
        - series_name: 系列名（可选，不填由 AI 起名）

        返回：
        - success: 是否成功
        - series_name: 系列名
        - episodes: 系列集数列表，每集含 order/title/angle/progression，
          title 统一为「系列名｜0X 具体标题」格式
        """
        start_time = time.time()

        try:
            data = request.get_json(silent=True) or {}
            theme = (data.get('theme') or '').strip()
            # 未传或显式传 null 都走默认集数
            raw_count = data.get('count')
            if raw_count is None:
                raw_count = DEFAULT_SERIES_COUNT
            niche = (data.get('niche') or '').strip()
            platform = (data.get('platform') or '').strip()
            series_name = (data.get('series_name') or '').strip()

            log_request('/topic/series', {
                'theme': theme[:50],
                'count': raw_count,
                'niche': niche[:50],
                'platform': platform,
                'series_name': series_name[:50],
            })

            # 验证必填参数
            if not theme:
                logger.warning("系列拆解请求缺少 theme 参数")
                return api_error_response(
                    validation_error("theme 不能为空", "请输入要拆解的大主题，例如：新手化妆。"),
                    context={"endpoint": "/api/topic/series"},
                )

            # 集数必须是数字（越界由服务层钳制到 5-10，非数字直接报错）
            try:
                count = int(raw_count)
            except (TypeError, ValueError):
                logger.warning(f"系列拆解 count 参数非法: {raw_count!r}")
                return api_error_response(
                    validation_error(
                        "count 必须是数字",
                        f"请把集数设为 {SERIES_MIN_COUNT}-{SERIES_MAX_COUNT} 之间的整数。",
                    ),
                    context={"endpoint": "/api/topic/series"},
                )

            logger.info(f"🔄 开始系列拆解，主题: {theme[:50]}，集数: {count}")
            topic_service = get_topic_service()
            result = topic_service.expand_series(
                theme, count=count, niche=niche,
                platform=platform, series_name=series_name
            )

            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 系列拆解成功，耗时 {elapsed:.2f}s")
                return jsonify(result), 200
            else:
                logger.error(f"❌ 系列拆解失败: {result.get('error', '未知错误')}")
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/topic/series"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/topic/series', e)
            return api_error_response(e, context={"endpoint": "/api/topic/series"})

    return topic_bp
