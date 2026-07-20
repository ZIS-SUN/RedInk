"""
评论洞察选题挖掘 API 路由

包含功能：
- 从一批粉丝评论中聚类痛点主题，并为每个痛点生成可直接开写的选题
"""

import time
import logging
from flask import Blueprint, request, jsonify
from backend.services.insight import get_insight_service
from backend.services.brand import resolve_brand_for_prompt
from .utils import (
    api_error_response,
    log_request,
    log_error,
    normalize_error_result,
    validation_error,
)

logger = logging.getLogger(__name__)


def create_insight_blueprint():
    """创建评论洞察选题挖掘路由蓝图（工厂函数，支持多次调用）"""
    insight_bp = Blueprint('insight', __name__)

    @insight_bp.route('/insight', methods=['POST'])
    def mine_insights():
        """
        从粉丝评论中挖掘痛点主题与选题

        请求格式（application/json）：
        - comments: 粉丝评论，字符串列表；也兼容传入多行字符串（按行拆分）
        - niche: 创作者的领域/赛道（可选），提供时帮助 AI 聚焦
        - brand_id: 品牌档案 ID（可选）；未提供时自动使用「当前启用」档案，
          取不到品牌数据时静默跳过品牌注入

        返回：
        - success: 是否成功
        - pain_points: 痛点列表，每个含 theme/summary/frequency/evidence/topics，
          topics 中每条选题含 title/angle/format/heat/tags
        - comment_count: 实际参与分析的评论条数
        """
        start_time = time.time()

        try:
            data = request.get_json(silent=True) or {}
            raw_comments = data.get('comments', [])
            niche = (data.get('niche') or '').strip()
            brand_id = data.get('brand_id')

            # 兼容多行字符串输入：按行拆分为多条评论
            if isinstance(raw_comments, str):
                raw_comments = raw_comments.splitlines()
            if not isinstance(raw_comments, list):
                raw_comments = []

            comments = [str(c).strip() for c in raw_comments if str(c).strip()]

            log_request('/insight', {
                'comment_count': len(comments),
                'niche': niche[:50],
            })

            # 验证必填参数
            if not comments:
                logger.warning("评论洞察请求缺少 comments 参数")
                return api_error_response(
                    validation_error("comments 不能为空", "请至少粘贴一条粉丝评论。"),
                    context={"endpoint": "/api/insight"},
                )

            # 解析品牌档案（未传 brand_id 时回退当前启用档案，取不到时静默忽略）
            brand = resolve_brand_for_prompt(brand_id)

            # 调用评论洞察挖掘服务
            logger.info(f"🔄 开始评论洞察挖掘，共 {len(comments)} 条评论")
            insight_service = get_insight_service()
            result = insight_service.mine_insights(comments, niche=niche, brand=brand)

            # 记录结果
            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 评论洞察挖掘成功，耗时 {elapsed:.2f}s")
                return jsonify(result), 200
            else:
                logger.error(f"❌ 评论洞察挖掘失败: {result.get('error', '未知错误')}")
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/insight"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/insight', e)
            return api_error_response(e, context={"endpoint": "/api/insight"})

    return insight_bp
