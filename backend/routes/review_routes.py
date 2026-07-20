"""
爆款体检相关 API 路由

包含功能：
- AI 审稿：对已完成的图文作品（页面文案 + 可选标题/文案/标签）
  从五个维度打分，并给出最多 5 条可执行的修改建议
"""

import time
import logging
from flask import Blueprint, request, jsonify
from backend.services.review import get_review_service
from backend.services.brand import resolve_brand_for_prompt
from .utils import (
    api_error_response,
    log_request,
    log_error,
    normalize_error_result,
    validation_error,
)

logger = logging.getLogger(__name__)


def create_review_blueprint():
    """创建爆款体检路由蓝图（工厂函数，支持多次调用）"""
    review_bp = Blueprint('review', __name__)

    @review_bp.route('/review', methods=['POST'])
    def review_work():
        """
        爆款体检：给成品打分并给出修改建议

        请求格式（application/json）：
        - topic: 创作主题
        - pages: 页面列表 [{index, type, content}]（必填，不能为空）
        - titles: 候选标题列表（可选）
        - copywriting: 发布文案（可选）
        - tags: 标签列表（可选）
        - brand_id: 品牌档案 ID（可选）；未提供时自动使用「当前启用」档案，
          有品牌时体检追加「人设一致性」检查维度，取不到时静默跳过

        返回：
        - success: 是否成功
        - review: 体检报告（overall_score/verdict/dimensions/suggestions）
        """
        start_time = time.time()

        try:
            data = request.get_json(silent=True) or {}
            topic = data.get('topic', '')
            pages = data.get('pages', [])
            titles = data.get('titles')
            copywriting = data.get('copywriting')
            tags = data.get('tags')
            brand_id = data.get('brand_id')

            if not isinstance(topic, str):
                topic = str(topic) if topic is not None else ''
            topic = topic.strip()

            if not isinstance(pages, list):
                pages = []
            # 只保留合法的页面对象，避免脏数据进入 prompt
            pages = [p for p in pages if isinstance(p, dict)]

            if not isinstance(titles, list):
                titles = None
            else:
                titles = [str(t) for t in titles if t is not None and str(t).strip()]

            if not isinstance(copywriting, str):
                copywriting = None

            if not isinstance(tags, list):
                tags = None
            else:
                tags = [str(t) for t in tags if t is not None and str(t).strip()]

            log_request('/review', {
                'topic': topic[:50] if topic else '',
                'pages_count': len(pages),
                'titles_count': len(titles) if titles else 0,
                'has_copywriting': bool(copywriting),
                'tags_count': len(tags) if tags else 0
            })

            # 验证必填参数：pages 不能为空
            if not pages:
                logger.warning("爆款体检请求 pages 为空")
                return api_error_response(
                    validation_error(
                        "pages 不能为空",
                        "请先生成图文页面，再进行爆款体检。"
                    ),
                    context={"endpoint": "/api/review"},
                )

            # 解析品牌档案（未传 brand_id 时回退当前启用档案，取不到时静默忽略）
            brand = resolve_brand_for_prompt(brand_id)

            # 调用爆款体检服务
            logger.info(f"🔄 开始爆款体检，页面数: {len(pages)}")
            review_service = get_review_service()
            result = review_service.review_work(
                topic, pages, titles, copywriting, tags, brand=brand
            )

            # 记录结果
            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 爆款体检成功，耗时 {elapsed:.2f}s")
                return jsonify(result), 200
            else:
                logger.error(f"❌ 爆款体检失败: {result.get('error', '未知错误')}")
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/review"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/review', e)
            return api_error_response(e, context={"endpoint": "/api/review"})

    return review_bp
