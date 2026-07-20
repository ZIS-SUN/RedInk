"""
我的选题库 API 路由

包含功能：
- 选题条目的增删改查 (CRUD)
- 状态流转（通过 PUT 更新 status 字段实现）
- 按状态 / 来源过滤列表

所有响应遵循 { success: true, ... } / 统一错误对象 的对外契约。
"""

import logging
from flask import Blueprint, request, jsonify

from backend.services.idea_library import get_idea_library_service
from .utils import api_error_response, validation_error

logger = logging.getLogger(__name__)


def create_idea_blueprint():
    """创建选题库路由蓝图（工厂函数，支持多次调用）"""
    idea_bp = Blueprint('idea', __name__)

    @idea_bp.route('/ideas', methods=['GET'])
    def list_ideas():
        """
        获取选题列表

        查询参数：
        - status: 按状态过滤（可选：idea/todo/done/viral）
        - source: 按来源过滤（可选：manual/topic/insight/hotspot）

        返回：
        - success: 是否成功
        - ideas: 选题列表（按创建时间倒序）
        """
        try:
            idea_service = get_idea_library_service()
            ideas = idea_service.list_ideas(
                status=request.args.get('status'),
                source=request.args.get('source'),
            )

            return jsonify({
                "success": True,
                "ideas": ideas
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/ideas"})

    @idea_bp.route('/ideas', methods=['POST'])
    def create_idea():
        """
        新建选题条目

        请求体：
        - title: 选题标题（必填）
        - angle: 切入角度（可选）
        - tags: 建议标签，字符串数组（可选）
        - source: 来源（可选：manual/topic/insight/hotspot，默认 manual）
        - status: 状态（可选：idea/todo/done/viral，默认 idea）
        - niche: 赛道/领域（可选）

        返回：
        - success: 是否成功
        - idea: 新创建的完整条目
        """
        try:
            data = request.get_json(silent=True) or {}

            if not str(data.get('title') or '').strip():
                return api_error_response(
                    validation_error("title 不能为空", "请填写选题标题。"),
                    context={"endpoint": "/api/ideas"},
                )

            idea_service = get_idea_library_service()
            idea = idea_service.create_idea(data)

            return jsonify({
                "success": True,
                "idea": idea
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/ideas"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/ideas"})

    @idea_bp.route('/ideas/<idea_id>', methods=['PUT'])
    def update_idea(idea_id):
        """
        更新选题条目（部分更新，只更新提供的字段；状态流转传 status 即可）

        路径参数：
        - idea_id: 条目 ID

        请求体：字段同新建接口，均为可选（提供了 title 则不能为空，
        提供了 status/source 则必须是合法枚举值）

        返回：
        - success: 是否成功
        - idea: 更新后的完整条目
        """
        try:
            data = request.get_json(silent=True) or {}

            idea_service = get_idea_library_service()
            idea = idea_service.update_idea(idea_id, data)

            if idea is None:
                return api_error_response(
                    f"选题条目不存在：{idea_id}",
                    status=404,
                    context={"endpoint": "/api/ideas/<id>", "idea_id": idea_id},
                )

            return jsonify({
                "success": True,
                "idea": idea
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/ideas/<id>", "idea_id": idea_id},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/ideas/<id>", "idea_id": idea_id})

    @idea_bp.route('/ideas/<idea_id>', methods=['DELETE'])
    def delete_idea(idea_id):
        """
        删除选题条目

        路径参数：
        - idea_id: 条目 ID

        返回：
        - success: 是否成功
        """
        try:
            idea_service = get_idea_library_service()
            success = idea_service.delete_idea(idea_id)

            if not success:
                return api_error_response(
                    f"选题条目不存在：{idea_id}",
                    status=404,
                    context={"endpoint": "/api/ideas/<id>", "idea_id": idea_id},
                )

            return jsonify({
                "success": True
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/ideas/<id>", "idea_id": idea_id})

    return idea_bp
