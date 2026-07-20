"""
封面 A/B 方向相关 API 路由

包含功能：
- 一次生成 3-4 个差异化封面方向，用于 A/B 测试
"""

import time
import logging
from flask import Blueprint, request, jsonify
from backend.services.cover import get_cover_service
from backend.services.brand import resolve_brand_for_prompt
from .utils import (
    api_error_response,
    log_request,
    log_error,
    normalize_error_result,
    validation_error,
)

logger = logging.getLogger(__name__)


def create_cover_blueprint():
    """创建封面方向路由蓝图（工厂函数，支持多次调用）"""
    cover_bp = Blueprint('cover', __name__)

    @cover_bp.route('/cover', methods=['POST'])
    def generate_cover_directions():
        """
        生成封面 A/B 方向

        请求格式（application/json）：
        - topic: 主题文本（必填）
        - content: 补充内容/背景（可选）
        - brand_id: 品牌档案 ID（可选）；未提供时自动使用「当前启用」档案，
          有品牌时注入人设约束与品牌视觉约束（主色调），取不到时静默跳过

        返回：
        - success: 是否成功
        - directions: 封面方向列表（3-4 个），每项含
          title / subtitle / visual_concept / style / score / reason
        """
        start_time = time.time()

        try:
            data = request.get_json()
            topic = data.get('topic', '')
            content = data.get('content', '')
            brand_id = data.get('brand_id')

            log_request('/cover', {
                'topic': topic[:50] if topic else '',
                'content_length': len(content) if content else 0,
            })

            # 验证必填参数
            if not topic:
                logger.warning("封面方向生成请求缺少 topic 参数")
                return api_error_response(
                    validation_error("topic 不能为空", "请输入主题内容。"),
                    context={"endpoint": "/api/cover"},
                )

            # 解析品牌档案（未传 brand_id 时回退当前启用档案，取不到时静默忽略）
            brand = resolve_brand_for_prompt(brand_id)

            # 调用封面方向生成服务
            logger.info(f"🔄 开始生成封面方向，主题: {topic[:50]}...")
            cover_service = get_cover_service()
            result = cover_service.generate_cover_directions(topic, content, brand=brand)

            # 记录结果
            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 封面方向生成成功，耗时 {elapsed:.2f}s")
                return jsonify(result), 200
            else:
                logger.error(f"❌ 封面方向生成失败: {result.get('error', '未知错误')}")
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/cover"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/cover', e)
            return api_error_response(e, context={"endpoint": "/api/cover"})

    return cover_bp
