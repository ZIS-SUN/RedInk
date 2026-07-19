"""
爆款标题工坊相关 API 路由

包含功能：
- 根据主题/文案草稿、平台与风格倾向，生成爆款候选标题
"""

import time
import logging
from flask import Blueprint, request, jsonify
from backend.services.title import get_title_service
from .rewrite_routes import resolve_brand
from .utils import (
    api_error_response,
    log_request,
    log_error,
    normalize_error_result,
    validation_error,
)

logger = logging.getLogger(__name__)


def create_title_blueprint():
    """创建爆款标题路由蓝图（工厂函数，支持多次调用）"""
    title_bp = Blueprint('title', __name__)

    @title_bp.route('/title', methods=['POST'])
    def generate_titles():
        """
        生成爆款候选标题

        请求格式（application/json）：
        - topic: 主题/文案草稿
        - platform: 目标平台（如：小红书、抖音），默认 小红书
        - style: 风格倾向（如：悬念型、数字型），默认 综合
        - brand_id: 品牌档案 ID（可选），提供时按人设约束生成；档案不存在则忽略

        返回：
        - success: 是否成功
        - titles: 候选标题列表，每项含 text / score / elements
        """
        start_time = time.time()

        try:
            data = request.get_json()
            topic = (data.get('topic') or '').strip()
            platform = (data.get('platform') or '').strip() or '小红书'
            style = (data.get('style') or '').strip() or '综合'
            brand_id = (data.get('brand_id') or '').strip()

            log_request('/title', {
                'topic': topic[:50] if topic else '',
                'platform': platform,
                'style': style,
                'brand_id': brand_id,
            })

            # 验证必填参数
            if not topic:
                logger.warning("标题生成请求缺少 topic 参数")
                return api_error_response(
                    validation_error("topic 不能为空", "请输入主题或文案草稿。"),
                    context={"endpoint": "/api/title"},
                )

            # 解析品牌档案（可选，取不到时静默忽略）
            brand = resolve_brand(brand_id)

            # 调用标题生成服务
            logger.info(f"🔄 开始生成爆款标题，主题: {topic[:50]}...")
            title_service = get_title_service()
            result = title_service.generate_titles(topic, platform, style, brand=brand)

            # 记录结果
            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 爆款标题生成成功，耗时 {elapsed:.2f}s")
                return jsonify(result), 200
            else:
                logger.error(f"❌ 爆款标题生成失败: {result.get('error', '未知错误')}")
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/title"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/title', e)
            return api_error_response(e, context={"endpoint": "/api/title"})

    return title_bp
