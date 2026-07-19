"""
评论区互动助手 API 路由

包含功能：
- 为粉丝评论批量生成神回复建议，可选生成置顶引导评论
"""

import time
import logging
from flask import Blueprint, request, jsonify
from backend.services.reply import get_reply_service
from .utils import (
    api_error_response,
    log_request,
    log_error,
    normalize_error_result,
    validation_error,
)

logger = logging.getLogger(__name__)


def create_reply_blueprint():
    """创建评论区互动助手路由蓝图（工厂函数，支持多次调用）"""
    reply_bp = Blueprint('reply', __name__)

    @reply_bp.route('/reply', methods=['POST'])
    def generate_replies():
        """
        为粉丝评论生成神回复建议

        请求格式（application/json）：
        - comments: 粉丝评论，字符串列表；也兼容传入多行字符串（按行拆分）
        - tone: 回复语气（热情/专业/幽默/温暖），默认"热情"
        - include_pinned: 是否同时生成一条置顶引导评论，默认 false

        返回：
        - success: 是否成功
        - replies: [{"comment": "原评论", "suggestions": ["回复1", "回复2"]}, ...]
        - pinned_comment: 置顶引导评论（未要求生成时为空字符串）
        """
        start_time = time.time()

        try:
            data = request.get_json(silent=True) or {}
            raw_comments = data.get('comments', [])
            tone = data.get('tone', '热情')
            include_pinned = bool(data.get('include_pinned', False))

            # 兼容多行字符串输入：按行拆分为多条评论
            if isinstance(raw_comments, str):
                raw_comments = raw_comments.splitlines()
            if not isinstance(raw_comments, list):
                raw_comments = []

            comments = [str(c).strip() for c in raw_comments if str(c).strip()]

            log_request('/reply', {
                'comment_count': len(comments),
                'tone': tone,
                'include_pinned': include_pinned,
            })

            # 验证必填参数
            if not comments:
                logger.warning("评论回复请求缺少 comments 参数")
                return api_error_response(
                    validation_error("comments 不能为空", "请至少粘贴一条粉丝评论。"),
                    context={"endpoint": "/api/reply"},
                )

            # 调用评论回复生成服务
            logger.info(f"🔄 开始生成评论回复，共 {len(comments)} 条评论，语气: {tone}")
            reply_service = get_reply_service()
            result = reply_service.generate_replies(
                comments,
                tone=tone,
                include_pinned=include_pinned,
            )

            # 记录结果
            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 评论回复生成成功，耗时 {elapsed:.2f}s")
                return jsonify(result), 200
            else:
                logger.error(f"❌ 评论回复生成失败: {result.get('error', '未知错误')}")
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/reply"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/reply', e)
            return api_error_response(e, context={"endpoint": "/api/reply"})

    return reply_bp
