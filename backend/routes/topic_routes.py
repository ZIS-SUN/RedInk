"""
选题灵感相关 API 路由

包含功能：
- 根据领域/赛道 + 目标平台生成 AI 选题灵感
"""

import time
import logging
from flask import Blueprint, request, jsonify
from backend.services.topic import get_topic_service
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

        返回：
        - success: 是否成功
        - topics: 选题列表，每条含 title/angle/format/heat/tags
        - account_context_used: 本次是否实际结合了账号数据
        """
        start_time = time.time()

        try:
            data = request.get_json(silent=True) or {}
            niche = (data.get('niche') or '').strip()
            platform = (data.get('platform') or '小红书').strip() or '小红书'
            use_account_data = bool(data.get('use_account_data', False))
            brand_id = data.get('brand_id')

            log_request('/topic', {
                'niche': niche[:50],
                'platform': platform,
                'use_account_data': use_account_data,
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
                niche, platform, use_account_data=use_account_data, brand=brand
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

    return topic_bp
