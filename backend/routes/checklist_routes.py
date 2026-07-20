"""
发布前体检清单相关 API 路由

包含功能：
- 发布前检查：按目标平台的发布规范（标题字数/标签数量/禁用词/图片数等）
  对成品做纯规则合规校验，不调用 LLM，秒回结果
"""

import logging
from flask import Blueprint, request, jsonify
from backend.services.checklist import run_checklist
from .utils import (
    api_error_response,
    log_request,
    log_error,
    validation_error,
)

logger = logging.getLogger(__name__)


def _load_brand_banned_words() -> list:
    """读取当前启用品牌档案的禁用词，任何异常都静默降级为空列表。"""
    try:
        from backend.services.brand import get_brand_service
        brand = get_brand_service().get_active_brand()
        if brand and isinstance(brand.get("banned_words"), list):
            return brand["banned_words"]
    except Exception as e:
        # 品牌数据损坏/读取失败不应阻断体检，仅记录日志
        logger.warning(f"读取品牌禁用词失败，降级为空列表: {e}")
    return []


def create_checklist_blueprint():
    """创建发布前体检清单路由蓝图（工厂函数，支持多次调用）"""
    checklist_bp = Blueprint('checklist', __name__)

    @checklist_bp.route('/checklist', methods=['POST'])
    def run_publish_checklist():
        """
        发布前检查：按平台规范做纯规则合规校验

        请求格式（application/json）：
        - platform: 平台标识（xiaohongshu/douyin/weixin/bilibili/weibo，必填）
        - title: 标题（可选）
        - body: 正文文案（可选）
        - tags: 标签列表（可选）
        - image_count: 已生成图片数（可选，默认 0）
        - banned_words: 禁用词列表（可选；未传时自动读取当前启用品牌档案的禁用词）
        - seo_keywords: 目标搜索词列表（可选；提供时追加搜索埋词三项检查）

        返回：
        - success: 是否成功
        - platform: 平台标识
        - items: 检查项列表 [{id, label, status, detail}]
        - summary: 各状态计数 {pass, warn, fail}
        """
        try:
            data = request.get_json(silent=True) or {}
            platform = data.get('platform')

            log_request('/checklist', {
                'platform': platform,
                'title_len': len(str(data.get('title') or '')),
                'body_len': len(str(data.get('body') or '')),
                'tags_count': len(data.get('tags')) if isinstance(data.get('tags'), list) else 0,
                'image_count': data.get('image_count'),
            })

            # 验证必填参数：platform 不能为空
            if not platform or not isinstance(platform, str) or not platform.strip():
                logger.warning("发布前检查请求 platform 为空")
                return api_error_response(
                    validation_error(
                        "platform 不能为空",
                        "请指定目标平台（xiaohongshu/douyin/weixin/bilibili/weibo）。"
                    ),
                    context={"endpoint": "/api/checklist"},
                )

            # 禁用词来源：请求显式传入优先，否则读取当前启用品牌档案（失败静默降级）
            banned_words = data.get('banned_words')
            if not isinstance(banned_words, list):
                banned_words = _load_brand_banned_words()

            try:
                result = run_checklist({
                    'platform': platform,
                    'title': data.get('title'),
                    'body': data.get('body'),
                    'tags': data.get('tags'),
                    'image_count': data.get('image_count'),
                    'banned_words': banned_words,
                    # 目标搜索词（可选）：携带时服务层追加搜索埋词三项检查
                    'seo_keywords': data.get('seo_keywords'),
                })
            except ValueError as e:
                # 未知平台等参数错误返回 400
                logger.warning(f"发布前检查参数错误: {e}")
                return api_error_response(
                    validation_error(str(e), "请使用支持的平台标识后重试。"),
                    context={"endpoint": "/api/checklist"},
                )

            summary = result.get('summary', {})
            logger.info(
                f"✅ 发布前检查完成 [{platform}]: "
                f"通过 {summary.get('pass', 0)} / 提醒 {summary.get('warn', 0)} / 不合规 {summary.get('fail', 0)}"
            )
            return jsonify(result), 200

        except Exception as e:
            log_error('/checklist', e)
            return api_error_response(e, context={"endpoint": "/api/checklist"})

    return checklist_bp
