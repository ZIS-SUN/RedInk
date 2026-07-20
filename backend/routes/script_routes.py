"""
口播视频脚本生成 API 路由

包含功能：
- 把图文内容（正文/大纲/主题）转成短视频口播/分镜脚本
"""

import time
import logging
from flask import Blueprint, request, jsonify
from backend.services.script import (
    get_script_service,
    SUPPORTED_DURATIONS,
    SUPPORTED_SCENES,
    DEFAULT_DURATION,
    DEFAULT_SCENE,
)
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


def create_script_blueprint():
    """创建口播脚本生成路由蓝图（工厂函数，支持多次调用）"""
    script_bp = Blueprint('script', __name__)

    @script_bp.route('/script', methods=['POST'])
    def generate_script():
        """
        口播视频脚本生成

        请求格式（application/json）：
        - content: 图文内容（正文/大纲）或主题文本
        - duration: 时长档位代号（可选，30s/60s/3min，默认 60s）
        - scene: 场景类型代号（可选，talking_head/voiceover/drama，默认 talking_head）
        - brand_id: 品牌档案 ID（可选），提供时按人设约束生成；档案不存在则忽略

        返回：
        - success: 是否成功
        - script: 脚本对象，含 title/hook/bgm_mood/duration/scene/segments/cta
        """
        start_time = time.time()

        try:
            data = request.get_json() or {}
            content = (data.get('content') or '').strip()
            duration = (data.get('duration') or DEFAULT_DURATION).strip()
            scene = (data.get('scene') or DEFAULT_SCENE).strip()
            brand_id = (data.get('brand_id') or '').strip()

            log_request('/script', {
                'content_length': len(content),
                'duration': duration,
                'scene': scene,
                'brand_id': brand_id,
            })

            # 验证必填参数
            if not content:
                logger.warning("口播脚本请求缺少 content 参数")
                return api_error_response(
                    validation_error("content 不能为空", "请输入图文内容或主题。"),
                    context={"endpoint": "/api/script"},
                )

            if duration not in SUPPORTED_DURATIONS:
                supported = ', '.join(SUPPORTED_DURATIONS.keys())
                logger.warning(f"口播脚本请求包含不支持的时长档位: {duration}")
                return api_error_response(
                    validation_error(
                        f"不支持的时长档位: {duration}",
                        f"支持的时长档位: {supported}",
                    ),
                    context={"endpoint": "/api/script"},
                )

            if scene not in SUPPORTED_SCENES:
                supported = ', '.join(SUPPORTED_SCENES.keys())
                logger.warning(f"口播脚本请求包含不支持的场景类型: {scene}")
                return api_error_response(
                    validation_error(
                        f"不支持的场景类型: {scene}",
                        f"支持的场景类型: {supported}",
                    ),
                    context={"endpoint": "/api/script"},
                )

            # 解析品牌档案（可选，取不到时静默忽略）
            brand = resolve_brand(brand_id)

            # 调用口播脚本生成服务
            logger.info(f"🔄 开始生成口播脚本，时长: {duration}，场景: {scene}")
            script_service = get_script_service()
            result = script_service.generate_script(
                content, duration, scene, brand=brand
            )

            # 记录结果
            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 口播脚本生成成功，耗时 {elapsed:.2f}s")
                return jsonify(result), 200
            else:
                logger.error(f"❌ 口播脚本生成失败: {result.get('error', '未知错误')}")
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/script"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/script', e)
            return api_error_response(e, context={"endpoint": "/api/script"})

    return script_bp
