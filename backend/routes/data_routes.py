"""
数据管理中心 API 路由

包含功能：
- GET/POST /data/export: 一键备份导出（zip 下载；POST 可附带前端
  localStorage 数据合入包内；include_keys=true 时包含 providers 配置）
- POST /data/import: 备份导入恢复（先自动备份现有数据再覆盖）
- GET /data/diagnostics: 诊断包导出（日志 + 版本/平台 + 脱敏配置）
"""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

from backend.services.data_admin import (
    MAX_IMPORT_SIZE,
    build_diagnostics_zip,
    build_export_zip,
    import_backup_zip,
)
from .utils import api_error_response, log_error, validation_error

logger = logging.getLogger(__name__)


def create_data_blueprint():
    """创建数据管理路由蓝图（工厂函数，支持多次调用）"""
    data_bp = Blueprint('data', __name__)

    @data_bp.route('/data/export', methods=['GET', 'POST'])
    def export_data():
        """
        导出全量数据备份 zip。

        query 参数：
        - include_keys: 为 "true" 时包含 text/image_providers.yaml
          （含 API Key 明文），默认不包含。

        POST 请求体（application/json，可选）：
        - local_storage: 前端收集的 localStorage 键值对象，
          合入 zip 的 frontend/local_storage.json
        """
        try:
            include_keys = request.args.get('include_keys', '').lower() == 'true'

            local_storage = None
            if request.method == 'POST':
                body = request.get_json(silent=True) or {}
                candidate = body.get('local_storage')
                if isinstance(candidate, dict):
                    # 只接受字符串键值（localStorage 语义），其余丢弃
                    local_storage = {
                        str(k): v for k, v in candidate.items()
                        if isinstance(v, str)
                    }

            logger.info(
                f"📥 收到备份导出请求: include_keys={include_keys}, "
                f"local_storage_keys={len(local_storage) if local_storage else 0}"
            )

            zip_stream = build_export_zip(
                include_keys=include_keys,
                local_storage=local_storage,
            )
            filename = f"redink_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            return send_file(
                zip_stream,
                mimetype='application/zip',
                as_attachment=True,
                download_name=filename,
            )
        except Exception as e:
            log_error('/data/export', e)
            return api_error_response(e, context={"endpoint": "/api/data/export"})

    @data_bp.route('/data/import', methods=['POST'])
    def import_data():
        """
        导入备份 zip 恢复数据。

        请求格式（multipart/form-data）：
        - file: RedInk 备份 zip 文件

        覆盖前会先把现有数据整体备份到 data_root/.pre_import_backup_时间戳/。
        非法 zip / manifest 缺失 / 路径逃逸 / 超过 500MB 返回 400。
        """
        try:
            uploaded = request.files.get('file')
            if uploaded is None:
                return api_error_response(
                    validation_error(
                        "缺少备份文件",
                        "请通过 multipart/form-data 的 file 字段上传备份 zip。",
                    ),
                    context={"endpoint": "/api/data/import"},
                )

            # 声明的 Content-Length 超限直接拒绝（流式读取上限在服务层兜底）
            if request.content_length and request.content_length > MAX_IMPORT_SIZE:
                return api_error_response(
                    validation_error(
                        f"备份文件超过大小上限（{MAX_IMPORT_SIZE // (1024 * 1024)}MB）",
                        "请确认上传的是 RedInk 备份 zip 文件。",
                    ),
                    context={"endpoint": "/api/data/import"},
                )

            summary = import_backup_zip(uploaded.stream)
            return jsonify(summary), 200
        except Exception as e:
            log_error('/data/import', e)
            return api_error_response(e, context={"endpoint": "/api/data/import"})

    @data_bp.route('/data/diagnostics', methods=['GET'])
    def export_diagnostics():
        """
        导出诊断包 zip：logs/ 全部日志 + diagnostics.json
        （版本号 / 平台信息 / 脱敏 provider 配置，绝不含 API Key）。
        """
        try:
            zip_stream = build_diagnostics_zip()
            filename = f"redink_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            return send_file(
                zip_stream,
                mimetype='application/zip',
                as_attachment=True,
                download_name=filename,
            )
        except Exception as e:
            log_error('/data/diagnostics', e)
            return api_error_response(e, context={"endpoint": "/api/data/diagnostics"})

    return data_bp
