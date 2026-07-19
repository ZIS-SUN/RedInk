"""
多平台文案改写 API 路由

包含功能：
- 将一段文案改写为多个目标平台的原生风格
"""

import time
import logging
from flask import Blueprint, request, jsonify
from backend.services.rewrite import get_rewrite_service, SUPPORTED_PLATFORMS
from backend.services.brand import get_brand_service
from .utils import (
    api_error_response,
    log_request,
    log_error,
    normalize_error_result,
    validation_error,
)

logger = logging.getLogger(__name__)


def resolve_brand(brand_id) -> dict | None:
    """
    按 brand_id 获取品牌档案；id 为空、档案不存在或读取失败时返回 None（静默忽略）。
    """
    brand_id = str(brand_id or '').strip()
    if not brand_id:
        return None
    try:
        brand = get_brand_service().get_brand(brand_id)
    except Exception as e:
        logger.warning(f"读取品牌档案失败，忽略品牌人设: brand_id={brand_id}, error={e}")
        return None
    if brand is None:
        logger.warning(f"品牌档案不存在，忽略品牌人设: brand_id={brand_id}")
    return brand


def create_rewrite_blueprint():
    """创建文案改写路由蓝图（工厂函数，支持多次调用）"""
    rewrite_bp = Blueprint('rewrite', __name__)

    @rewrite_bp.route('/rewrite', methods=['POST'])
    def rewrite_copy():
        """
        多平台文案改写

        请求格式（application/json）：
        - content: 原始文案或主题文本
        - source_platform: 源平台代号（可选，xiaohongshu/douyin/wechat/bilibili/weibo，留空表示通用）
        - target_platforms: 目标平台代号列表（至少一个）
        - brand_id: 品牌档案 ID（可选），提供时按人设约束生成；档案不存在则忽略

        返回：
        - success: 是否成功
        - results: 各平台改写结果列表，每项含 platform/title/content/tags
        """
        start_time = time.time()

        try:
            data = request.get_json() or {}
            content = (data.get('content') or '').strip()
            source_platform = (data.get('source_platform') or '').strip()
            target_platforms = data.get('target_platforms') or []
            brand_id = (data.get('brand_id') or '').strip()

            log_request('/rewrite', {
                'content_length': len(content),
                'source_platform': source_platform,
                'target_platforms': target_platforms,
                'brand_id': brand_id,
            })

            # 验证必填参数
            if not content:
                logger.warning("文案改写请求缺少 content 参数")
                return api_error_response(
                    validation_error("content 不能为空", "请输入需要改写的文案或主题。"),
                    context={"endpoint": "/api/rewrite"},
                )

            if not isinstance(target_platforms, list) or not target_platforms:
                logger.warning("文案改写请求缺少 target_platforms 参数")
                return api_error_response(
                    validation_error("target_platforms 不能为空", "请至少选择一个目标平台。"),
                    context={"endpoint": "/api/rewrite"},
                )

            invalid = [p for p in target_platforms if p not in SUPPORTED_PLATFORMS]
            if invalid:
                supported = ', '.join(SUPPORTED_PLATFORMS.keys())
                logger.warning(f"文案改写请求包含不支持的平台: {invalid}")
                return api_error_response(
                    validation_error(
                        f"不支持的目标平台: {', '.join(invalid)}",
                        f"支持的平台: {supported}",
                    ),
                    context={"endpoint": "/api/rewrite"},
                )

            if source_platform and source_platform not in SUPPORTED_PLATFORMS:
                logger.warning(f"文案改写请求包含不支持的源平台: {source_platform}")
                return api_error_response(
                    validation_error(
                        f"不支持的源平台: {source_platform}",
                        f"支持的平台: {', '.join(SUPPORTED_PLATFORMS.keys())}，或留空表示通用",
                    ),
                    context={"endpoint": "/api/rewrite"},
                )

            # 解析品牌档案（可选，取不到时静默忽略）
            brand = resolve_brand(brand_id)

            # 调用文案改写服务
            logger.info(f"🔄 开始改写文案，目标平台: {target_platforms}")
            rewrite_service = get_rewrite_service()
            result = rewrite_service.rewrite_copy(
                content, source_platform, target_platforms, brand=brand
            )

            # 记录结果
            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 文案改写成功，耗时 {elapsed:.2f}s")
                return jsonify(result), 200
            else:
                logger.error(f"❌ 文案改写失败: {result.get('error', '未知错误')}")
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/rewrite"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/rewrite', e)
            return api_error_response(e, context={"endpoint": "/api/rewrite"})

    return rewrite_bp
