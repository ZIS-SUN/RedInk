"""
链接/长文转图文大纲 API 路由

包含功能：
- POST /link/outline：传入网页链接或长文本，返回提炼后的图文大纲
"""

import time
import logging
from flask import Blueprint, request, jsonify
from backend.services.link_extract import get_link_extract_service
from .utils import (
    api_error_response,
    log_request,
    log_error,
    normalize_error_result,
    validation_error,
)

logger = logging.getLogger(__name__)

# 输入长度上限（防止超大 payload）
MAX_URL_LENGTH = 2048
MAX_TEXT_LENGTH = 100_000


def create_link_blueprint():
    """创建链接转图文路由蓝图（工厂函数，支持多次调用）"""
    link_bp = Blueprint('link', __name__)

    @link_bp.route('/link/outline', methods=['POST'])
    def link_to_outline():
        """
        链接/长文 → 图文大纲

        请求格式（application/json，url 与 text 二选一，优先 url）：
        - url: 网页链接（http/https，禁止私网/环回/保留地址）
        - text: 用户直接粘贴的长文本

        返回：
        - success: 是否成功
        - topic: 提炼出的主题
        - outline: 大纲原始文本
        - pages: 页面列表 [{index, type, content}]（与现有大纲结构一致）
        """
        start_time = time.time()

        try:
            data = request.get_json(silent=True) or {}
            url = (data.get('url') or '').strip()
            text = (data.get('text') or '').strip()

            log_request('/link/outline', {
                'url': url[:100] if url else '',
                'text_length': len(text),
            })

            if not url and not text:
                return api_error_response(
                    validation_error("url 和 text 不能同时为空", "请输入网页链接或粘贴文章内容。"),
                    context={"endpoint": "/api/link/outline"},
                )

            if url and len(url) > MAX_URL_LENGTH:
                return api_error_response(
                    validation_error("链接过长", "请检查链接是否正确。"),
                    context={"endpoint": "/api/link/outline"},
                )

            if text and len(text) > MAX_TEXT_LENGTH:
                return api_error_response(
                    validation_error(
                        f"文本过长（最多 {MAX_TEXT_LENGTH} 字符）",
                        "请精简内容后重试。"
                    ),
                    context={"endpoint": "/api/link/outline"},
                )

            logger.info(f"🔄 开始链接/长文转大纲: url={url[:80] if url else '(无)'}, text_len={len(text)}")
            service = get_link_extract_service()
            result = service.extract_outline(
                url=url or None,
                raw_text=text or None,
            )

            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 链接/长文转大纲成功，共 {len(result.get('pages', []))} 页，耗时 {elapsed:.2f}s")
                return jsonify(result), 200

            logger.error(f"❌ 链接/长文转大纲失败: {result.get('error', '未知错误')}")
            result = normalize_error_result(
                result,
                context={"endpoint": "/api/link/outline"},
                fallback_status=400,
            )
            return jsonify(result), result["error"].get("status", 400)

        except Exception as e:
            log_error('/link/outline', e)
            return api_error_response(e, context={"endpoint": "/api/link/outline"})

    return link_bp
