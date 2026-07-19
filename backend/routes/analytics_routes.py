"""
数据复盘（表现分析）API 路由

包含功能：
- 已发布内容表现记录的增删改查 (CRUD)
- 统计概览（总数、各平台/各类型汇总、平均互动率、按月趋势）
- AI 复盘洞察（把数据摘要发给 LLM，输出表现分析与下一步建议）

所有响应遵循 { success: true, ... } / 统一错误对象 的对外契约。
"""

import logging
from flask import Blueprint, request, jsonify

from backend.services.analytics import get_analytics_service
from .utils import api_error_response, validation_error

logger = logging.getLogger(__name__)


def create_analytics_blueprint():
    """创建数据复盘路由蓝图（工厂函数，支持多次调用）"""
    analytics_bp = Blueprint('analytics', __name__)

    @analytics_bp.route('/analytics/records', methods=['GET'])
    def list_records():
        """
        获取表现记录列表

        返回：
        - success: 是否成功
        - records: 记录列表（按发布日期倒序）
        """
        try:
            analytics_service = get_analytics_service()
            result = analytics_service.list_records()

            return jsonify({
                "success": True,
                **result
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/analytics/records"})

    @analytics_bp.route('/analytics/records', methods=['POST'])
    def create_record():
        """
        新建表现记录

        请求体：
        - title: 内容标题（必填）
        - platform: 发布平台（必填）
        - publish_date: 发布日期，YYYY-MM-DD（可选）
        - content_type: 内容类型/标签（可选）
        - views / likes / collects / comments / shares / followers_gained: 数值（可选，默认 0）
        - notes: 备注（可选）

        返回：
        - success: 是否成功
        - record: 新创建的完整记录
        """
        try:
            data = request.get_json(silent=True) or {}

            if not str(data.get('title') or '').strip():
                return api_error_response(
                    validation_error("title 不能为空", "请填写内容标题。"),
                    context={"endpoint": "/api/analytics/records"},
                )
            if not str(data.get('platform') or '').strip():
                return api_error_response(
                    validation_error("platform 不能为空", "请选择发布平台。"),
                    context={"endpoint": "/api/analytics/records"},
                )

            analytics_service = get_analytics_service()
            record = analytics_service.create_record(data)

            return jsonify({
                "success": True,
                "record": record
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/analytics/records"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/analytics/records"})

    @analytics_bp.route('/analytics/records/<record_id>', methods=['PUT'])
    def update_record(record_id):
        """
        更新表现记录（部分更新，只更新提供的字段）

        路径参数：
        - record_id: 记录 ID

        请求体：字段同新建接口，均为可选（提供了 title / platform 则不能为空）

        返回：
        - success: 是否成功
        - record: 更新后的完整记录
        """
        try:
            data = request.get_json(silent=True) or {}

            analytics_service = get_analytics_service()
            record = analytics_service.update_record(record_id, data)

            if record is None:
                return api_error_response(
                    f"表现记录不存在：{record_id}",
                    status=404,
                    context={"endpoint": "/api/analytics/records/<id>", "record_id": record_id},
                )

            return jsonify({
                "success": True,
                "record": record
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/analytics/records/<id>", "record_id": record_id},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/analytics/records/<id>", "record_id": record_id})

    @analytics_bp.route('/analytics/records/<record_id>', methods=['DELETE'])
    def delete_record(record_id):
        """
        删除表现记录

        路径参数：
        - record_id: 记录 ID

        返回：
        - success: 是否成功
        """
        try:
            analytics_service = get_analytics_service()
            success = analytics_service.delete_record(record_id)

            if not success:
                return api_error_response(
                    f"表现记录不存在：{record_id}",
                    status=404,
                    context={"endpoint": "/api/analytics/records/<id>", "record_id": record_id},
                )

            return jsonify({
                "success": True
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/analytics/records/<id>", "record_id": record_id})

    @analytics_bp.route('/analytics/stats', methods=['GET'])
    def get_stats():
        """
        获取统计概览

        返回：
        - success: 是否成功
        - stats: {
            total_records / total_views / total_likes / total_collects /
            total_comments / total_shares / total_followers_gained,
            avg_engagement_rate, platforms, content_types, trend
          }
        """
        try:
            analytics_service = get_analytics_service()
            stats = analytics_service.get_stats()

            return jsonify({
                "success": True,
                "stats": stats
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/analytics/stats"})

    @analytics_bp.route('/analytics/insight', methods=['POST'])
    def generate_insight():
        """
        AI 复盘洞察

        把当前全部表现数据的摘要发给 LLM，输出：
        哪类内容/标题/平台表现更好 + 下一步建议。

        返回：
        - success: 是否成功
        - insight: { summary, highlights: string[], suggestions: string[] }
        - data_summary: 发送给 LLM 的数据摘要文本
        """
        try:
            analytics_service = get_analytics_service()
            result = analytics_service.generate_insight()

            if not result.get("success"):
                return api_error_response(
                    result.get("error") or "AI 复盘洞察失败",
                    context={"endpoint": "/api/analytics/insight"},
                )

            return jsonify(result), 200

        except ValueError as e:
            # 无数据等校验类错误 -> 400
            return api_error_response(
                validation_error(str(e), "请先录入表现数据后再生成 AI 复盘。"),
                context={"endpoint": "/api/analytics/insight"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/analytics/insight"})

    return analytics_bp
