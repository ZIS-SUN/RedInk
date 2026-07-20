"""
品牌风格记忆（品牌资料库）API 路由

包含功能：
- 品牌档案的增删改查 (CRUD)
- 设置/获取「当前启用」的档案
- 新手账号定位向导：根据三个回答由 AI 生成档案草稿

所有响应遵循 { success: true, ... } / 统一错误对象 的对外契约。
"""

import logging
import time
from flask import Blueprint, request, jsonify

from backend.services.brand import generate_brand_draft, get_brand_service
from .utils import (
    api_error_response,
    log_error,
    normalize_error_result,
    validation_error,
)

logger = logging.getLogger(__name__)


def create_brand_blueprint():
    """创建品牌资料库路由蓝图（工厂函数，支持多次调用）"""
    brand_bp = Blueprint('brand', __name__)

    @brand_bp.route('/brands', methods=['GET'])
    def list_brands():
        """
        获取品牌档案列表

        返回：
        - success: 是否成功
        - brands: 档案列表（按创建时间倒序）
        - active_id: 当前启用的档案 ID（可能为 null）
        """
        try:
            brand_service = get_brand_service()
            result = brand_service.list_brands()

            return jsonify({
                "success": True,
                **result
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/brands"})

    @brand_bp.route('/brands', methods=['POST'])
    def create_brand():
        """
        新建品牌档案

        请求体：
        - name: 品牌/IP 名称（必填）
        - tagline: 一句话定位（可选）
        - audience: 目标人群（可选）
        - tone: 语气风格（可选）
        - catchphrases: 常用口头禅/开场白，字符串数组（可选）
        - signature: 签名/结尾话术（可选）
        - primary_color: 主色调（可选，如 #FF2442）
        - banned_words: 禁用词，字符串数组（可选）
        - notes: 备注（可选）

        返回：
        - success: 是否成功
        - brand: 新创建的完整档案
        """
        try:
            data = request.get_json(silent=True) or {}

            if not str(data.get('name') or '').strip():
                return api_error_response(
                    validation_error("name 不能为空", "请填写品牌/IP 名称。"),
                    context={"endpoint": "/api/brands"},
                )

            brand_service = get_brand_service()
            brand = brand_service.create_brand(data)

            return jsonify({
                "success": True,
                "brand": brand
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/brands"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/brands"})

    @brand_bp.route('/brands/active', methods=['GET'])
    def get_active_brand():
        """
        获取当前启用的品牌档案

        返回：
        - success: 是否成功
        - brand: 当前启用的档案；未设置时为 null
        """
        try:
            brand_service = get_brand_service()
            brand = brand_service.get_active_brand()

            return jsonify({
                "success": True,
                "brand": brand
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/brands/active"})

    @brand_bp.route('/brands/<brand_id>', methods=['PUT'])
    def update_brand(brand_id):
        """
        更新品牌档案（部分更新，只更新提供的字段）

        路径参数：
        - brand_id: 档案 ID

        请求体：字段同新建接口，均为可选（提供了 name 则不能为空）

        返回：
        - success: 是否成功
        - brand: 更新后的完整档案
        """
        try:
            data = request.get_json(silent=True) or {}

            brand_service = get_brand_service()
            brand = brand_service.update_brand(brand_id, data)

            if brand is None:
                return api_error_response(
                    f"品牌档案不存在：{brand_id}",
                    status=404,
                    context={"endpoint": "/api/brands/<id>", "brand_id": brand_id},
                )

            return jsonify({
                "success": True,
                "brand": brand
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/brands/<id>", "brand_id": brand_id},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/brands/<id>", "brand_id": brand_id})

    @brand_bp.route('/brands/<brand_id>', methods=['DELETE'])
    def delete_brand(brand_id):
        """
        删除品牌档案

        如果删除的是当前启用档案，启用状态会被清空。

        路径参数：
        - brand_id: 档案 ID

        返回：
        - success: 是否成功
        """
        try:
            brand_service = get_brand_service()
            success = brand_service.delete_brand(brand_id)

            if not success:
                return api_error_response(
                    f"品牌档案不存在：{brand_id}",
                    status=404,
                    context={"endpoint": "/api/brands/<id>", "brand_id": brand_id},
                )

            return jsonify({
                "success": True
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/brands/<id>", "brand_id": brand_id})

    @brand_bp.route('/brand/draft', methods=['POST'])
    def generate_draft():
        """
        新手账号定位向导：根据三个回答由 AI 生成品牌档案草稿

        请求体（application/json，三项均必填）：
        - who: 「你是谁」——身份/经历
        - audience: 「做给谁看」——目标人群
        - advantage: 「凭什么是你」——独特优势

        返回：
        - success: 是否成功
        - draft: 档案草稿，含 name（账号名建议列表）/positioning（一句话定位）/
          tone/catchphrases/signature/banned_words/niche_tags/
          starter_topics（前 10 篇起号选题，每条含 title/angle）
        """
        start_time = time.time()

        try:
            data = request.get_json(silent=True) or {}
            who = str(data.get('who') or '').strip()
            audience = str(data.get('audience') or '').strip()
            advantage = str(data.get('advantage') or '').strip()

            # 三个回答都是生成定位的必要输入，缺一不可
            missing_hints = []
            if not who:
                missing_hints.append("「你是谁」")
            if not audience:
                missing_hints.append("「做给谁看」")
            if not advantage:
                missing_hints.append("「凭什么是你」")
            if missing_hints:
                return api_error_response(
                    validation_error(
                        f"缺少必填回答: {'、'.join(missing_hints)}",
                        "请先完成三个定位问题的回答。",
                    ),
                    context={"endpoint": "/api/brand/draft"},
                )

            logger.info(f"🔄 开始生成账号定位草稿: who={who[:30]}")
            result = generate_brand_draft(who, audience, advantage)

            elapsed = time.time() - start_time
            if result.get("success"):
                logger.info(f"✅ 账号定位草稿生成成功，耗时 {elapsed:.2f}s")
                return jsonify(result), 200

            logger.error(f"❌ 账号定位草稿生成失败: {result.get('error', '未知错误')}")
            result = normalize_error_result(
                result,
                context={"endpoint": "/api/brand/draft"},
                fallback_status=500,
            )
            return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/brand/draft', e)
            return api_error_response(e, context={"endpoint": "/api/brand/draft"})

    @brand_bp.route('/brands/<brand_id>/activate', methods=['POST'])
    def activate_brand(brand_id):
        """
        设置某个档案为「当前启用」

        路径参数：
        - brand_id: 档案 ID

        返回：
        - success: 是否成功
        - active_id: 启用后的档案 ID
        """
        try:
            brand_service = get_brand_service()
            success = brand_service.activate_brand(brand_id)

            if not success:
                return api_error_response(
                    f"品牌档案不存在：{brand_id}",
                    status=404,
                    context={"endpoint": "/api/brands/<id>/activate", "brand_id": brand_id},
                )

            return jsonify({
                "success": True,
                "active_id": brand_id
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/brands/<id>/activate", "brand_id": brand_id})

    return brand_bp
