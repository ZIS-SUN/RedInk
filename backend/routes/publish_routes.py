"""
发布助手 API 路由（半自动）

包含功能：
- 多平台账号清单 CRUD（仅存平台/昵称/备注标签，绝不存任何凭证）
- 平台创作者发布页 URL 下发（前端打开，用户手动发布）
- 一键备料：导出作品原图与发布文案到本地文件夹
- 在 Finder 中打开导出文件夹（仅限导出目录内，防目录穿越）

所有响应遵循 { success: true, ... } / 统一错误对象 的对外契约。
"""

import logging
from flask import Blueprint, request, jsonify

from backend.services.publish import (
    RecordNotFoundError,
    get_publish_service,
    list_platforms,
    open_export_folder,
    prepare_publish_materials,
)
from .utils import api_error_response, validation_error

logger = logging.getLogger(__name__)


def create_publish_blueprint():
    """创建发布助手路由蓝图（工厂函数，支持多次调用）"""
    publish_bp = Blueprint('publish', __name__)

    # ==================== 账号清单 CRUD ====================

    @publish_bp.route('/publish/accounts', methods=['GET'])
    def list_accounts():
        """
        获取账号清单

        返回：
        - success: 是否成功
        - accounts: 账号列表（新账号在前）
        """
        try:
            accounts = get_publish_service().list_accounts()
            return jsonify({
                "success": True,
                "accounts": accounts
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/publish/accounts"})

    @publish_bp.route('/publish/accounts', methods=['POST'])
    def create_account():
        """
        新建账号

        请求体：
        - platform: 平台 code（必填，白名单：xiaohongshu/douyin/shipinhao/
          bilibili/gongzhonghao/kuaishou）
        - nickname: 账号昵称（必填非空）
        - notes: 备注（可选）

        返回：
        - success: 是否成功
        - account: 新创建的完整账号
        """
        try:
            data = request.get_json(silent=True) or {}
            account = get_publish_service().create_account(data)

            return jsonify({
                "success": True,
                "account": account
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/publish/accounts"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/publish/accounts"})

    @publish_bp.route('/publish/accounts/<account_id>', methods=['PUT'])
    def update_account(account_id):
        """
        更新账号（部分更新，字段同新建接口，均为可选）

        返回：
        - success: 是否成功
        - account: 更新后的完整账号（404 若账号不存在）
        """
        try:
            data = request.get_json(silent=True) or {}
            account = get_publish_service().update_account(account_id, data)

            if account is None:
                return api_error_response(
                    f"账号不存在：{account_id}",
                    status=404,
                    context={"endpoint": "/api/publish/accounts/<id>", "account_id": account_id},
                )

            return jsonify({
                "success": True,
                "account": account
            }), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e)),
                context={"endpoint": "/api/publish/accounts/<id>", "account_id": account_id},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/publish/accounts/<id>", "account_id": account_id})

    @publish_bp.route('/publish/accounts/<account_id>', methods=['DELETE'])
    def delete_account(account_id):
        """
        删除账号

        返回：
        - success: 是否成功（404 若账号不存在）
        """
        try:
            success = get_publish_service().delete_account(account_id)

            if not success:
                return api_error_response(
                    f"账号不存在：{account_id}",
                    status=404,
                    context={"endpoint": "/api/publish/accounts/<id>", "account_id": account_id},
                )

            return jsonify({
                "success": True
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/publish/accounts/<id>", "account_id": account_id})

    # ==================== 平台发布页 ====================

    @publish_bp.route('/publish/platforms', methods=['GET'])
    def get_platforms():
        """
        获取平台清单（含创作者发布页 URL，由前端打开、用户手动发布）

        返回：
        - success: 是否成功
        - platforms: [{ key, label, creator_url }]
        """
        try:
            return jsonify({
                "success": True,
                "platforms": list_platforms()
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/publish/platforms"})

    # ==================== 一键备料 ====================

    @publish_bp.route('/publish/prepare', methods=['POST'])
    def prepare():
        """
        一键备料：导出作品原图与发布文案到本地文件夹

        请求体：
        - record_id: 历史记录 ID（必填）

        返回：
        - success: 是否成功
        - folder: 导出文件夹绝对路径
        - files: 相对文件名列表（page_N.png... 与 发布文案.txt）
        - text: { titles: [], copywriting: "", tags: [] }

        错误：
        - 404 历史记录不存在
        - 400 该作品还没有生成图片
        """
        try:
            data = request.get_json(silent=True) or {}
            record_id = str(data.get('record_id') or '').strip()

            if not record_id:
                return api_error_response(
                    validation_error("record_id 不能为空", "请先选择一个作品。"),
                    context={"endpoint": "/api/publish/prepare"},
                )

            result = prepare_publish_materials(record_id)

            return jsonify({
                "success": True,
                **result
            }), 200

        except RecordNotFoundError as e:
            return api_error_response(
                str(e),
                status=404,
                context={"endpoint": "/api/publish/prepare"},
            )
        except ValueError as e:
            return api_error_response(
                validation_error(str(e), "请先在生成页完成图片生成。"),
                context={"endpoint": "/api/publish/prepare"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/publish/prepare"})

    # ==================== 打开本地文件夹 ====================

    @publish_bp.route('/publish/open-folder', methods=['POST'])
    def open_folder():
        """
        在 Finder 中打开导出文件夹

        请求体：
        - path: 文件夹绝对路径（必须位于 publish_exports 导出目录内，
          否则 400，防目录穿越）

        返回：
        - success: 是否成功打开
        - message: 失败提示（非 macOS / open 失败 / 文件夹不存在时给出，
          此时 success 为 false 但 HTTP 仍为 200，不抛异常）
        """
        try:
            data = request.get_json(silent=True) or {}
            path = str(data.get('path') or '').strip()

            result = open_export_folder(path)
            return jsonify(result), 200

        except ValueError as e:
            return api_error_response(
                validation_error(str(e), "只允许打开发布导出目录内的文件夹。"),
                context={"endpoint": "/api/publish/open-folder"},
            )
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/publish/open-folder"})

    return publish_bp
