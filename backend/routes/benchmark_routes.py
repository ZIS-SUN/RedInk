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
from backend.services.link_extract import MAX_ARTICLE_CHARS, get_link_extract_service
from .rewrite_routes import resolve_brand
from .utils import (
    api_error_response,
    log_request,
    log_error,
    normalize_error_result,
    validation_error,
)

logger = logging.getLogger(__name__)

# 链接长度上限（与 link 路由保持一致）
MAX_URL_LENGTH = 2048


def create_benchmark_blueprint():
    """创建对标拆解路由蓝图（工厂函数，支持多次调用）"""
    benchmark_bp = Blueprint('benchmark', __name__)

    @benchmark_bp.route('/benchmark', methods=['POST'])
    def analyze_benchmark():
        """
        拆解对标内容，可选生成仿写草稿

        请求格式（application/json，content 与 url 至少提供一个，优先 content）：
        - content: 对标/爆款内容（标题+正文）
        - url: 对标内容的网页链接（无 content 时，服务端先抓取正文再分析）
        - my_topic: 用户自己的主题（可选），提供时按拆解出的套路生成原创仿写草稿
        - brand_id: 品牌档案 ID（可选），提供时仿写草稿按人设约束生成；档案不存在则忽略

        返回：
        - success: 是否成功
        - analysis: 拆解结果（hook/opening/structure/emotion/audience/viral_elements/reusable_template）
        - draft: 仿写草稿（未提供 my_topic 时为空字符串）
        """
        start_time = time.time()

        try:
            data = request.get_json(silent=True) or {}
            content = data.get('content', '')
            url = data.get('url', '')
            my_topic = data.get('my_topic', '')
            brand_id = str(data.get('brand_id') or '').strip()

            if not isinstance(content, str):
                content = str(content) if content is not None else ''
            if not isinstance(url, str):
                url = str(url) if url is not None else ''
            if not isinstance(my_topic, str):
                my_topic = str(my_topic) if my_topic is not None else ''
            content = content.strip()
            url = url.strip()
            my_topic = my_topic.strip()

            log_request('/benchmark', {
                'content_length': len(content),
                'url': url[:100] if url else '',
                'my_topic': my_topic[:50] if my_topic else '',
                'brand_id': brand_id,
            })

            # 验证必填参数：content 与 url 至少提供一个
            if not content and not url:
                logger.warning("对标拆解请求 content 和 url 均为空")
                return api_error_response(
                    validation_error(
                        "content 和 url 不能同时为空",
                        "请粘贴要拆解的对标内容，或提供内容的网页链接。"
                    ),
                    context={"endpoint": "/api/benchmark"},
                )

            # 无 content 时，先抓取链接正文（复用 link_extract 的 SSRF 校验与错误信息）
            if not content:
                if len(url) > MAX_URL_LENGTH:
                    return api_error_response(
                        validation_error("链接过长", "请检查链接是否正确。"),
                        context={"endpoint": "/api/benchmark"},
                    )

                logger.info(f"🔄 对标拆解 url 模式，开始抓取正文: {url[:80]}")
                try:
                    content = get_link_extract_service().fetch_article_text(url).strip()
                except ValueError as e:
                    # 透传 link_extract 的原始错误提示（如小红书/抖音抓不到正文时引导改为粘贴）
                    logger.warning(f"对标拆解抓取链接失败: {e}")
                    result = normalize_error_result(
                        {"success": False, "error": str(e)},
                        context={"endpoint": "/api/benchmark"},
                        fallback_status=400,
                    )
                    return jsonify(result), result["error"].get("status", 400)

                if not content:
                    result = normalize_error_result(
                        {"success": False, "error": "未能从该链接提取到正文内容，请直接粘贴要拆解的对标内容"},
                        context={"endpoint": "/api/benchmark"},
                        fallback_status=400,
                    )
                    return jsonify(result), result["error"].get("status", 400)

                # 与 link 路由一致：截断超长正文，避免撑爆 LLM 上下文
                if len(content) > MAX_ARTICLE_CHARS:
                    logger.info(f"对标正文过长（{len(content)} 字符），截断至 {MAX_ARTICLE_CHARS}")
                    content = content[:MAX_ARTICLE_CHARS]

            # 解析品牌档案（可选，取不到时静默忽略）
            brand = resolve_brand(brand_id)

            # 调用对标拆解服务
            logger.info(f"🔄 开始对标拆解，内容长度: {len(content)}")
            benchmark_service = get_benchmark_service()
            result = benchmark_service.analyze_benchmark(content, my_topic or None, brand=brand)

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
