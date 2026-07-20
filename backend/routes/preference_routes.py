"""
创作偏好画像 API 路由

包含功能：
- 获取从历史评分与编辑留痕聚合出的创作偏好画像
"""

import logging
from flask import Blueprint, jsonify
from backend.services.preference import get_preference_service
from .utils import (
    api_error_response,
    log_request,
    log_error,
)

logger = logging.getLogger(__name__)


def create_preference_blueprint():
    """创建创作偏好画像路由蓝图（工厂函数，支持多次调用）"""
    preference_bp = Blueprint('preference', __name__)

    @preference_bp.route('/preference/profile', methods=['GET'])
    def get_preference_profile():
        """
        获取创作偏好画像

        从全部历史记录聚合：高分作品的主题与页数偏好、编辑习惯信号。
        已评分样本不足时 profile.insufficient 为 True（只带样本数，不带结论）。

        返回：
        - success: 是否成功
        - profile: 画像对象，含 insufficient/sample_count/min_samples/
          liked_topics/preferred_page_count/editing_signal 等
        """
        try:
            log_request('/preference/profile')

            profile = get_preference_service().build_profile()
            return jsonify({
                "success": True,
                "profile": profile,
            }), 200

        except Exception as e:
            log_error('/preference/profile', e)
            return api_error_response(e, context={"endpoint": "/api/preference/profile"})

    return preference_bp
