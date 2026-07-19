"""
对标拆解相关 API 路由

包含功能：
- 拆解对标/爆款内容（钩子、开头、结构、情绪价值、受众、爆点、套路模板）
- 可选：按同样套路为用户主题生成原创仿写草稿
"""

import time
import logging
from flask import Blueprint, request, jsonify
from backend.services.benchmark import get_benchmark_service
from .utils import (
    api_error_response,
    log_request,
    log_error,
    normalize_error_result,
    validation_error,
)

logger = logging.getLogger(__name__)


def create_benchmark_blueprint():
    """创建对标拆解路由蓝图（工厂函数，支持多次调用）"""
    benchmark_bp = Blueprint('benchmark', __name__)

    @benchmark_bp.route('/benchmark', methods=['POST'])
    def analyze_benchmark():
        """
        拆解对标内容，可选生成仿写草稿

        请求格式（application/json）：
        - content: 对标/爆款内容（标题+正文），必填
        - my_topic: 用户自己的主题（可选），提供时按拆解出的套路生成原创仿写草稿

        返回：
        - success: 是否成功
        - analysis: 拆解结果（hook/opening/structure/emotion/audience/viral_elements/reusable_template）
        - draft: 仿写草稿（未提供 my_topic 时为空字符串）
        """
        start_time = time.time()

        try:
            data = request.get_json()
            content = data.get('content', '')
            my_topic = data.get('my_topic', '')

            if not isinstance(content, str):
                content = str(content) if content is not None else ''
            if not isinstance(my_topic, str):
                my_topic = str(my_topic) if my_topic is not None else ''
            content = content.strip()
            my_topic = my_topic.strip()

            log_request('/benchmark', {
                'content_length': len(content),
                'my_topic': my_topic[:50] if my_topic else ''
            })

            # 验证必填参数
            if not content:
                logger.warning("对标拆解请求缺少 content 参数")
                return api_error_response(
                    validation_error("content 不能为空", "请粘贴要拆解的对标内容。"),
                    context={"endpoint": "/api/benchmark"},
                )

            # 调用对标拆解服务
            logger.info(f"🔄 开始对标拆解，内容长度: {len(content)}")
            benchmark_service = get_benchmark_service()
            result = benchmark_service.analyze_benchmark(content, my_topic or None)

            # 记录结果
            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 对标拆解成功，耗时 {elapsed:.2f}s")
                return jsonify(result), 200
            else:
                logger.error(f"❌ 对标拆解失败: {result.get('error', '未知错误')}")
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/benchmark"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/benchmark', e)
            return api_error_response(e, context={"endpoint": "/api/benchmark"})

    return benchmark_bp
