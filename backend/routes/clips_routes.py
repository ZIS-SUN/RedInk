"""
剪藏收件箱 API 路由（浏览器插件进料）

包含功能：
- 浏览器插件 POST 剪藏内容（小红书/抖音笔记的标题、正文、标签、互动数据）
- 前端「对标拆解」页拉取/删除/清空收件箱

所有响应遵循 { success: true, ... } / 统一错误对象 的对外契约。

CORS 说明：本组端点在 backend/app.py 中额外放行了
chrome-extension:// 与 moz-extension:// 来源（仅 /api/clips* 路径），
其余 /api/* 路径仍维持原白名单。
"""

import logging
from flask import Blueprint, request, jsonify

from backend.services.clips import MAX_CONTENT_CHARS, get_clips_service
from .utils import api_error_response, validation_error

logger = logging.getLogger(__name__)


def create_clips_blueprint():
    """创建剪藏收件箱路由蓝图（工厂函数，支持多次调用）"""
    clips_bp = Blueprint('clips', __name__)

    @clips_bp.route('/clips', methods=['GET'])
    def list_clips():
        """
        获取剪藏列表（按时间倒序，新条目在前）

        返回：
        - success: 是否成功
        - clips: 剪藏条目列表
        """
        try:
            clips_service = get_clips_service()
            clips = clips_service.list_clips()

            return jsonify({
                "success": True,
                "clips": clips
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/clips"})

    @clips_bp.route('/clips', methods=['POST'])
    def create_clip():
        """
        新建剪藏（浏览器插件调用）

        请求体：
        - source: 来源平台 xiaohongshu / douyin / other（可选，非法值回退 other）
        - url: 原始页面链接（可选）
        - title: 标题（title 与 content 至少一项非空）
        - author: 作者（可选）
        - content: 正文文本（可选，上限 20000 字）
        - tags: 话题标签，字符串数组（可选）
        - stats: 互动数据对象 { likes, collects, comments }（可选）

        返回：
        - success: 是否成功
        - clip: 新创建的完整条目
        """
        try:
            data = request.get_json(silent=True) or {}

            title = str(data.get('title') or '').strip()
            content = str(data.get('content') or '').strip()
            if not title and not content:
                return api_error_response(
                    validation_error(
                        "title 与 content 至少需要一项非空",
                        "请确认页面内容已成功提取后再发送。",
                    ),
                    context={"endpoint": "/api/clips"},
                )
            if len(content) > MAX_CONTENT_CHARS:
                return api_error_response(
                    validation_error(
                        f"正文过长（{len(content)} 字），上限 {MAX_CONTENT_CHARS} 字",
                        "剪藏收件箱只接收单篇笔记正文，请勿提交超长内容。",
                    ),
                    context={"endpoint": "/api/clips"},
                )

            clips_service = get_clips_service()
            clip = clips_service.create_clip(data)

            return jsonify({
                "success": True,
                "clip": clip
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/clips"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/clips"})

    @clips_bp.route('/clips/<clip_id>', methods=['DELETE'])
    def delete_clip(clip_id):
        """
        删除单条剪藏

        路径参数：
        - clip_id: 条目 ID

        返回：
        - success: 是否成功
        """
        try:
            clips_service = get_clips_service()
            success = clips_service.delete_clip(clip_id)

            if not success:
                return api_error_response(
                    f"剪藏条目不存在：{clip_id}",
                    status=404,
                    context={"endpoint": "/api/clips/<id>", "clip_id": clip_id},
                )

            return jsonify({
                "success": True
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/clips/<id>", "clip_id": clip_id})

    @clips_bp.route('/clips', methods=['DELETE'])
    def clear_clips():
        """
        清空收件箱

        返回：
        - success: 是否成功
        - removed: 被清除的条目数
        """
        try:
            clips_service = get_clips_service()
            removed = clips_service.clear_clips()

            return jsonify({
                "success": True,
                "removed": removed
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/clips"})

    return clips_bp
