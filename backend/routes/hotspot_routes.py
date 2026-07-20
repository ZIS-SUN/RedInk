"""
热点节点（营销日历图层）API 路由

包含功能：
- GET /hotspots?start=YYYY-MM-DD&end=YYYY-MM-DD 返回区间内的营销节点列表
  （纯本地静态数据，不依赖 AI 模型配置，未配置模型时也可用）

参数缺省行为：
- start 缺省为今天，end 缺省为 start + 60 天（默认查未来 60 天）
- 日期格式非法或 start 晚于 end 返回 400

所有响应遵循 { success: true, ... } / 统一错误对象 的对外契约。
"""

import logging

from flask import Blueprint, jsonify, request

from backend.services.hotspot import get_hotspots, resolve_range
from .utils import api_error_response, validation_error

logger = logging.getLogger(__name__)


def create_hotspot_blueprint():
    """创建热点节点路由蓝图（工厂函数，支持多次调用）"""
    hotspot_bp = Blueprint('hotspot', __name__)

    @hotspot_bp.route('/hotspots', methods=['GET'])
    def list_hotspots():
        """
        获取区间内的营销节点列表

        查询参数（均可选）：
        - start: 区间起点，格式 YYYY-MM-DD（缺省为今天）
        - end: 区间终点，格式 YYYY-MM-DD（缺省为 start + 60 天）

        返回：
        - success: 是否成功
        - hotspots: 节点列表（按日期升序），每个节点含
          id/name/date/type/prep_days/platform_hint/niche_hint
        - start / end: 实际生效的查询区间
        """
        try:
            start = (request.args.get('start') or '').strip() or None
            end = (request.args.get('end') or '').strip() or None

            start, end = resolve_range(start, end)
            hotspots = get_hotspots(start, end)

            return jsonify({
                "success": True,
                "hotspots": hotspots,
                "start": start,
                "end": end,
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/hotspots"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/hotspots"})

    return hotspot_bp
