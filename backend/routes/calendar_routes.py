"""
内容日历（发布计划）API 路由

包含功能：
- 计划条目的增删改查 (CRUD)
- 按月 / 平台 / 状态过滤列表
- 按月统计（本月计划数、各状态数量、各平台数量）
- AI 一周排期预览（只生成，不落盘；落盘由前端逐条调创建接口）

所有响应遵循 { success: true, ... } / 统一错误对象 的对外契约。
"""

import logging
from flask import Blueprint, request, jsonify

from backend.services.calendar_plan import generate_week_plan, get_calendar_service
from .utils import api_error_response, normalize_error_result, validation_error

logger = logging.getLogger(__name__)


def create_calendar_blueprint():
    """创建内容日历路由蓝图（工厂函数，支持多次调用）"""
    calendar_bp = Blueprint('calendar', __name__)

    @calendar_bp.route('/plans', methods=['GET'])
    def list_plans():
        """
        获取计划条目列表

        查询参数（均可选，可组合）：
        - month: 按月过滤，格式 YYYY-MM
        - platform: 按平台过滤（xiaohongshu/douyin/gongzhonghao/bilibili/shipinhao）
        - status: 按状态过滤（idea/in_progress/ready/published）

        返回：
        - success: 是否成功
        - plans: 计划条目列表（按计划发布日期升序）
        """
        try:
            month = (request.args.get('month') or '').strip() or None
            platform = (request.args.get('platform') or '').strip() or None
            status = (request.args.get('status') or '').strip() or None

            calendar_service = get_calendar_service()
            plans = calendar_service.list_plans(
                month=month, platform=platform, status=status
            )

            return jsonify({
                "success": True,
                "plans": plans
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/plans"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/plans"})

    @calendar_bp.route('/plans/stats', methods=['GET'])
    def get_stats():
        """
        获取按月统计

        查询参数：
        - month: 统计月份，格式 YYYY-MM（可选，缺省为当前月份）

        返回：
        - success: 是否成功
        - stats: { month, total, all_total, by_status, by_platform }
        """
        try:
            month = (request.args.get('month') or '').strip() or None

            calendar_service = get_calendar_service()
            stats = calendar_service.get_stats(month=month)

            return jsonify({
                "success": True,
                "stats": stats
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/plans/stats"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/plans/stats"})

    @calendar_bp.route('/plans', methods=['POST'])
    def create_plan():
        """
        新建计划条目

        请求体：
        - title: 计划标题（必填）
        - publish_date: 计划发布日期，格式 YYYY-MM-DD（必填）
        - publish_time: 计划发布时间，格式 HH:MM（可选，默认空）
        - platform: 发布平台（可选，默认 xiaohongshu）
        - status: 状态（可选，默认 idea）
        - notes: 备注（可选）
        - record_id: 关联的历史记录 ID（可选，默认空）

        返回：
        - success: 是否成功
        - plan: 新创建的完整条目
        """
        try:
            data = request.get_json(silent=True) or {}

            if not str(data.get('title') or '').strip():
                return api_error_response(
                    validation_error("title 不能为空", "请填写计划标题。"),
                    context={"endpoint": "/api/plans"},
                )
            if not str(data.get('publish_date') or '').strip():
                return api_error_response(
                    validation_error("publish_date 不能为空", "请选择计划发布日期。"),
                    context={"endpoint": "/api/plans"},
                )

            calendar_service = get_calendar_service()
            plan = calendar_service.create_plan(data)

            return jsonify({
                "success": True,
                "plan": plan
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/plans"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/plans"})

    @calendar_bp.route('/plans/generate-week', methods=['POST'])
    def generate_week():
        """
        AI 生成一周排期预览（不落盘）

        请求体：
        - niche: 领域/赛道（必填，如"健身减脂"）
        - platform: 发布平台（可选，默认 xiaohongshu）
        - start_date: 周一日期，格式 YYYY-MM-DD（可选，默认下周一）
        - frequency: 每周条数 1-7（可选，默认 3，越界自动钳制）
        - use_account_data: 是否结合账号数据（可选，默认 false）

        返回：
        - success: 是否成功
        - plans: 排期预览列表，每条含 title/platform/publish_date/publish_time/notes/status
        - account_context_used: 本次是否实际结合了账号数据
        """
        try:
            data = request.get_json(silent=True) or {}
            niche = str(data.get('niche') or '').strip()

            if not niche:
                return api_error_response(
                    validation_error("niche 不能为空", "请输入你的领域或赛道，例如：健身减脂。"),
                    context={"endpoint": "/api/plans/generate-week"},
                )

            result = generate_week_plan(
                niche=niche,
                platform=str(data.get('platform') or '').strip() or 'xiaohongshu',
                start_date=str(data.get('start_date') or '').strip() or None,
                frequency=data.get('frequency', 3),
                use_account_data=bool(data.get('use_account_data', False)),
            )

            if result.get("success"):
                return jsonify(result), 200

            result = normalize_error_result(
                result,
                context={"endpoint": "/api/plans/generate-week"},
                fallback_status=500,
            )
            return jsonify(result), result["error"].get("status", 500)

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/plans/generate-week"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/plans/generate-week"})

    @calendar_bp.route('/plans/<plan_id>', methods=['PUT'])
    def update_plan(plan_id):
        """
        更新计划条目（部分更新，只更新提供的字段）

        路径参数：
        - plan_id: 条目 ID

        请求体：字段同新建接口，均为可选（提供了 title 则不能为空）

        返回：
        - success: 是否成功
        - plan: 更新后的完整条目
        """
        try:
            data = request.get_json(silent=True) or {}

            calendar_service = get_calendar_service()
            plan = calendar_service.update_plan(plan_id, data)

            if plan is None:
                return api_error_response(
                    f"计划条目不存在：{plan_id}",
                    status=404,
                    context={"endpoint": "/api/plans/<id>", "plan_id": plan_id},
                )

            return jsonify({
                "success": True,
                "plan": plan
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/plans/<id>", "plan_id": plan_id},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/plans/<id>", "plan_id": plan_id})

    @calendar_bp.route('/plans/<plan_id>/log-performance', methods=['POST'])
    def log_performance(plan_id):
        """
        把日历条目一键转录到数据复盘（表现记录）

        路径参数：
        - plan_id: 条目 ID

        请求体（均可选，未提供的 title/platform/publish_date/publish_time/record_id
        由日历条目预填；platform 会转成中文名写入复盘）：
        - title / platform / publish_date / publish_time / content_type / notes
        - views / likes / collects / comments / shares / followers_gained: 数值指标

        防重复：同一条目重复转录时更新已有关联记录而非新建。

        返回：
        - success: 是否成功
        - record: 写入数据复盘的完整记录（带 calendar_plan_id / record_id 关联）
        - created: 是否为新建记录（false 表示更新了已有关联记录）
        """
        try:
            data = request.get_json(silent=True) or {}

            calendar_service = get_calendar_service()
            result = calendar_service.log_performance(plan_id, data)

            if result is None:
                return api_error_response(
                    f"计划条目不存在：{plan_id}",
                    status=404,
                    context={"endpoint": "/api/plans/<id>/log-performance", "plan_id": plan_id},
                )

            return jsonify({
                "success": True,
                "record": result["record"],
                "created": result["created"],
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/plans/<id>/log-performance", "plan_id": plan_id},
            )
        except Exception as e:
            return api_error_response(
                e,
                context={"endpoint": "/api/plans/<id>/log-performance", "plan_id": plan_id},
            )

    @calendar_bp.route('/plans/<plan_id>', methods=['DELETE'])
    def delete_plan(plan_id):
        """
        删除计划条目

        路径参数：
        - plan_id: 条目 ID

        返回：
        - success: 是否成功
        """
        try:
            calendar_service = get_calendar_service()
            success = calendar_service.delete_plan(plan_id)

            if not success:
                return api_error_response(
                    f"计划条目不存在：{plan_id}",
                    status=404,
                    context={"endpoint": "/api/plans/<id>", "plan_id": plan_id},
                )

            return jsonify({
                "success": True
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/plans/<id>", "plan_id": plan_id})

    return calendar_bp
