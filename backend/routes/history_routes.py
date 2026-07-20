"""
历史记录相关 API 路由

包含功能：
- 创建/获取/更新/删除历史记录 (CRUD)
- 搜索历史记录
- 获取统计信息
- 扫描和同步任务图片
- 打包下载图片
"""

import os
import io
import zipfile
import logging
from flask import Blueprint, request, jsonify, send_file
from backend.services.history import get_history_service
from .utils import api_error_response, normalize_error_result, validation_error

logger = logging.getLogger(__name__)


def create_history_blueprint():
    """创建历史记录路由蓝图（工厂函数，支持多次调用）"""
    history_bp = Blueprint('history', __name__)

    # ==================== CRUD 操作 ====================

    @history_bp.route('/history', methods=['POST'])
    def create_history():
        """
        创建历史记录（草稿）

        在用户生成大纲后立即调用，创建一个草稿状态的历史记录。
        初始状态为 draft，表示大纲已创建但尚未开始生成图片。

        请求体：
        - topic: 主题标题（必填）
        - outline: 大纲内容（必填），包含 pages 数组等
        - task_id: 关联的任务 ID（可选）

        返回：
        - success: 是否成功
        - record_id: 新创建的记录 ID（UUID 格式）

        状态流转：
            新建 -> draft（草稿状态）

        示例请求：
        {
            "topic": "小猫的冒险",
            "outline": {
                "title": "小猫的冒险",
                "pages": [
                    {"page": 1, "content": "..."},
                    {"page": 2, "content": "..."}
                ]
            },
            "task_id": "abc123"
        }
        """
        try:
            data = request.get_json()
            topic = data.get('topic')
            outline = data.get('outline')
            task_id = data.get('task_id')

            if not topic or not outline:
                return api_error_response(
                    validation_error("topic 和 outline 不能为空", "请提供主题和大纲内容。"),
                    context={"endpoint": "/api/history"},
                )

            history_service = get_history_service()
            record_id = history_service.create_record(topic, outline, task_id)

            return jsonify({
                "success": True,
                "record_id": record_id
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/history"})

    @history_bp.route('/history', methods=['GET'])
    def list_history():
        """
        获取历史记录列表（分页）

        查询参数：
        - page: 页码（默认 1）
        - page_size: 每页数量（默认 20）
        - status: 状态过滤（可选：all/completed/draft）

        返回：
        - success: 是否成功
        - records: 记录列表
        - total: 总数
        - total_pages: 总页数
        """
        try:
            # 参数校验：非数字回落默认值，越界值收敛到合法范围（防止除零/负页码）
            page = _parse_positive_int(request.args.get('page'), default=1, minimum=1)
            page_size = _parse_positive_int(
                request.args.get('page_size'), default=20, minimum=1, maximum=100
            )
            status = request.args.get('status')

            history_service = get_history_service()
            result = history_service.list_records(page, page_size, status)

            return jsonify({
                "success": True,
                **result
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/history"})

    @history_bp.route('/history/<record_id>', methods=['GET'])
    def get_history(record_id):
        """
        获取历史记录详情

        路径参数：
        - record_id: 记录 ID

        返回：
        - success: 是否成功
        - record: 完整的记录数据
        """
        try:
            history_service = get_history_service()
            record = history_service.get_record(record_id, sync_images=True)

            if not record:
                return api_error_response(
                    f"历史记录不存在：{record_id}",
                    status=404,
                    context={"endpoint": "/api/history/<id>", "record_id": record_id},
                )

            # 旧记录没有 rating / edit_history 字段：显式补默认值，前端无需判空
            record.setdefault("rating", None)
            record.setdefault("edit_history", [])

            return jsonify({
                "success": True,
                "record": record
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/history/<id>", "record_id": record_id})

    @history_bp.route('/history/<record_id>/exists', methods=['GET'])
    def check_history_exists(record_id):
        """
        检查历史记录是否存在

        用于前端在开始生成前检查草稿记录是否已创建。

        路径参数：
        - record_id: 记录 ID

        返回：
        - exists: 记录是否存在（boolean）
        """
        try:
            history_service = get_history_service()
            exists = history_service.record_exists(record_id)

            return jsonify({
                "exists": exists
            }), 200

        except Exception as e:
            payload, status_code = api_error_response(e, context={"endpoint": "/api/history/<id>/exists", "record_id": record_id})
            payload_json = payload.get_json()
            payload_json["exists"] = False
            return jsonify(payload_json), status_code

    @history_bp.route('/history/<record_id>', methods=['PUT'])
    def update_history(record_id):
        """
        更新历史记录

        支持部分更新，只更新提供的字段。
        每次更新都会自动刷新 updated_at 时间戳。

        路径参数：
        - record_id: 记录 ID

        请求体（均为可选）：
        - outline: 大纲内容（支持修改大纲）
        - images: 图片信息 { task_id, generated: [] }
        - status: 状态（draft/generating/partial/completed/error）
        - thumbnail: 缩略图文件名
        - content: 发布内容 { titles: [], copywriting: "", tags: [] }（坏结构静默忽略）
        - edit_trace: 编辑留痕 { page_index, original_text, edited_text,
          source: 'manual'|'polish' }，追加到 edit_history（坏结构静默忽略）

        返回：
        - success: 是否成功

        状态流转说明：
            draft -> generating: 开始生成图片
            generating -> partial: 部分图片生成完成
            generating -> completed: 所有图片生成完成
            generating -> error: 生成过程出错
            partial -> generating: 继续生成剩余图片
            partial -> completed: 剩余图片生成完成

        示例请求（更新状态为生成中）：
        {
            "status": "generating"
        }

        示例请求（更新图片列表）：
        {
            "images": {
                "task_id": "abc123",
                "generated": ["0.png", "1.png"]
            },
            "status": "partial",
            "thumbnail": "0.png"
        }
        """
        try:
            data = request.get_json()
            outline = data.get('outline')
            images = data.get('images')
            status = data.get('status')
            thumbnail = data.get('thumbnail')
            content = data.get('content')
            edit_trace = data.get('edit_trace')

            history_service = get_history_service()
            success = history_service.update_record(
                record_id,
                outline=outline,
                images=images,
                status=status,
                thumbnail=thumbnail,
                content=content,
                edit_trace=edit_trace
            )

            if not success:
                return api_error_response(
                    f"更新历史记录失败：{record_id}",
                    status=404,
                    context={"endpoint": "/api/history/<id>", "record_id": record_id},
                )

            return jsonify({
                "success": True
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/history/<id>", "record_id": record_id})

    @history_bp.route('/history/<record_id>/rating', methods=['PATCH'])
    def rate_history(record_id):
        """
        设置或清除作品评分

        路径参数：
        - record_id: 记录 ID

        请求体：
        - rating: 1-5 的整数保存评分，null 清除评分（其他值返回 400）

        返回：
        - success: 是否成功
        - rating: 保存后的评分（清除后为 null）
        """
        try:
            data = request.get_json(silent=True) or {}
            if 'rating' not in data:
                return api_error_response(
                    validation_error("缺少 rating 字段", "请传 1-5 的整数或 null。"),
                    context={"endpoint": "/api/history/<id>/rating", "record_id": record_id},
                )
            rating = data.get('rating')

            history_service = get_history_service()
            # rating 非法时 set_rating 抛 AppErrorException，统一转 400
            success = history_service.set_rating(record_id, rating)

            if not success:
                return api_error_response(
                    f"历史记录不存在：{record_id}",
                    status=404,
                    context={"endpoint": "/api/history/<id>/rating", "record_id": record_id},
                )

            return jsonify({
                "success": True,
                "rating": rating
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/history/<id>/rating", "record_id": record_id})

    @history_bp.route('/history/<record_id>', methods=['DELETE'])
    def delete_history(record_id):
        """
        删除历史记录

        路径参数：
        - record_id: 记录 ID

        返回：
        - success: 是否成功
        """
        try:
            history_service = get_history_service()
            success = history_service.delete_record(record_id)

            if not success:
                return api_error_response(
                    f"删除历史记录失败：{record_id}",
                    status=404,
                    context={"endpoint": "/api/history/<id>", "record_id": record_id},
                )

            return jsonify({
                "success": True
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/history/<id>", "record_id": record_id})

    # ==================== 搜索和统计 ====================

    @history_bp.route('/history/search', methods=['GET'])
    def search_history():
        """
        搜索历史记录

        查询参数：
        - keyword: 搜索关键词（必填）

        返回：
        - success: 是否成功
        - records: 匹配的记录列表
        """
        try:
            keyword = request.args.get('keyword', '')

            if not keyword:
                return api_error_response(
                    validation_error("keyword 不能为空", "请输入搜索关键词。"),
                    context={"endpoint": "/api/history/search"},
                )

            history_service = get_history_service()
            results = history_service.search_records(keyword)

            return jsonify({
                "success": True,
                "records": results
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/history/search"})

    @history_bp.route('/history/stats', methods=['GET'])
    def get_history_stats():
        """
        获取历史记录统计信息

        返回：
        - success: 是否成功
        - total: 总记录数
        - by_status: 按状态分组的统计
        """
        try:
            history_service = get_history_service()
            stats = history_service.get_statistics()

            return jsonify({
                "success": True,
                **stats
            }), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/history/stats"})

    # ==================== 扫描和同步 ====================

    @history_bp.route('/history/scan/<task_id>', methods=['GET'])
    def scan_task(task_id):
        """
        扫描单个任务并同步图片列表

        路径参数：
        - task_id: 任务 ID

        返回：
        - success: 是否成功
        - images: 同步后的图片列表
        """
        try:
            history_service = get_history_service()
            result = history_service.scan_and_sync_task_images(task_id)

            if not result.get("success"):
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/history/scan/<task_id>", "task_id": task_id},
                    fallback_status=404,
                )
                return jsonify(result), result["error"].get("status", 404)

            return jsonify(result), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/history/scan/<task_id>", "task_id": task_id})

    @history_bp.route('/history/scan-all', methods=['POST'])
    def scan_all_tasks():
        """
        扫描所有任务并同步图片列表

        返回：
        - success: 是否成功
        - total_tasks: 扫描的任务总数
        - synced: 成功同步的任务数
        - failed: 失败的任务数
        - orphan_tasks: 孤立任务列表（有图片但无记录）
        """
        try:
            history_service = get_history_service()
            result = history_service.scan_all_tasks()

            if not result.get("success"):
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/history/scan-all"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

            return jsonify(result), 200

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/history/scan-all"})

    # ==================== 下载功能 ====================

    @history_bp.route('/history/<record_id>/download', methods=['GET'])
    def download_history_zip(record_id):
        """
        下载历史记录的所有图片为 ZIP 文件

        路径参数：
        - record_id: 记录 ID

        返回：
        - 成功：ZIP 文件下载
        - 失败：JSON 错误信息
        """
        try:
            history_service = get_history_service()
            record = history_service.get_record(record_id)

            if not record:
                return api_error_response(
                    f"历史记录不存在：{record_id}",
                    status=404,
                    context={"endpoint": "/api/history/<id>/download", "record_id": record_id},
                )

            task_id = record.get('images', {}).get('task_id')
            if not task_id:
                return api_error_response(
                    "该记录没有关联的任务图片",
                    status=404,
                    context={"endpoint": "/api/history/<id>/download", "record_id": record_id},
                )

            # 获取任务目录
            task_dir = os.path.join(history_service.history_dir, task_id)
            if not os.path.exists(task_dir):
                return api_error_response(
                    f"任务目录不存在：{task_id}",
                    status=404,
                    context={"endpoint": "/api/history/<id>/download", "record_id": record_id, "task_id": task_id},
                )

            # 创建内存中的 ZIP 文件（附带发布文案文本）
            zip_buffer = _create_images_zip(task_dir, record)

            # 生成安全的下载文件名
            title = record.get('title', 'images')
            safe_title = _sanitize_filename(title)
            filename = f"{safe_title}.zip"

            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name=filename
            )

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/history/<id>/download", "record_id": record_id})

    return history_bp


def _parse_positive_int(value, default: int, minimum: int, maximum: int = None) -> int:
    """
    解析分页参数：非法值回落默认值，越界值收敛到 [minimum, maximum] 范围

    Args:
        value: 原始查询参数（可能为 None 或非数字字符串）
        default: 解析失败时的默认值
        minimum: 允许的最小值
        maximum: 允许的最大值（None 表示不限）

    Returns:
        int: 合法的整数值
    """
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default

    if result < minimum:
        return minimum
    if maximum is not None and result > maximum:
        return maximum
    return result


def _create_images_zip(task_dir: str, record: dict = None) -> io.BytesIO:
    """
    创建包含所有图片的 ZIP 文件（发布包）

    record 中存在发布内容（content）或大纲原文时，额外打包一份
    「发布文案.txt」，方便一键发布时直接复制粘贴。

    Args:
        task_dir: 任务目录路径
        record: 历史记录（可选，用于生成发布文案文本）

    Returns:
        io.BytesIO: 内存中的 ZIP 文件
    """
    memory_file = io.BytesIO()

    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 遍历任务目录中的所有图片（排除缩略图）
        used_names: set[str] = set()
        for filename in sorted(os.listdir(task_dir)):
            # 跳过缩略图文件
            if filename.startswith('thumb_'):
                continue

            if filename.endswith(('.png', '.jpg', '.jpeg')):
                file_path = os.path.join(task_dir, filename)

                # 生成归档文件名（page_N.png 格式）
                # 兼容重绘产生的版本化文件名（如 3_v1721450000000.png）
                try:
                    stem = filename.split('.')[0]
                    index = int(stem.split('_v')[0])
                    archive_name = f"page_{index + 1}.png"
                except ValueError:
                    archive_name = filename

                # 同页残留多个版本时避免 zip 内重名（正常清理后不会发生）
                if archive_name in used_names:
                    archive_name = filename
                used_names.add(archive_name)

                zf.write(file_path, archive_name)

        # 追加发布文案文本（无可用内容时保持旧行为，不加文件）
        publish_text = _build_publish_text(record)
        if publish_text:
            zf.writestr("发布文案.txt", publish_text.encode("utf-8"))

    # 将指针移到开始位置
    memory_file.seek(0)
    return memory_file


# AIGC 标注合规提醒：本产品内容均为 AI 生成，置于发布文案首行避免用户漏看
_AIGC_PUBLISH_NOTICE = (
    "⚠ 本内容由 AI 辅助生成，发布时请勾选平台的 AI 内容声明（未标注可能被限流）"
)


def _build_publish_text(record: dict = None) -> str:
    """
    从历史记录拼装「发布文案.txt」的文本内容

    首行固定为 AIGC 标注合规提醒；其后小节顺序：标题候选（每行一个）、
    正文文案、标签（#tag 空格连接）、——分隔线——、大纲原文。
    任何字段缺失则跳过对应小节；全部缺失时返回空字符串（调用方不加文件，
    此时也不单独输出提醒行）。

    Args:
        record: 历史记录（可为 None）

    Returns:
        str: 发布文案文本，无可用内容时为空字符串
    """
    if not isinstance(record, dict):
        return ""

    content = record.get("content")
    if not isinstance(content, dict):
        content = {}

    sections = []

    titles = content.get("titles")
    if isinstance(titles, list):
        title_lines = [t for t in titles if isinstance(t, str) and t.strip()]
        if title_lines:
            sections.append("【标题候选】\n" + "\n".join(title_lines))

    copywriting = content.get("copywriting")
    if isinstance(copywriting, str) and copywriting.strip():
        sections.append("【正文文案】\n" + copywriting.strip())

    tags = content.get("tags")
    if isinstance(tags, list):
        tag_items = [t.strip() for t in tags if isinstance(t, str) and t.strip()]
        if tag_items:
            sections.append("【标签】\n" + " ".join(f"#{t}" for t in tag_items))

    outline_raw = (record.get("outline") or {}).get("raw") \
        if isinstance(record.get("outline"), dict) else None
    if isinstance(outline_raw, str) and outline_raw.strip():
        sections.append("——分隔线——\n\n【大纲原文】\n" + outline_raw.strip())

    if not sections:
        return ""

    # 头部附 AIGC 声明提醒后再拼接各小节
    return _AIGC_PUBLISH_NOTICE + "\n\n" + "\n\n".join(sections) + "\n"


def _sanitize_filename(title: str) -> str:
    """
    清理文件名中的非法字符

    Args:
        title: 原始标题

    Returns:
        str: 安全的文件名
    """
    # 只保留字母、数字、空格、连字符、下划线和中文字符
    safe_title = "".join(
        c for c in title
        if c.isalnum() or c in (' ', '-', '_') or '\u4e00' <= c <= '\u9fff'
    ).strip()

    return safe_title if safe_title else 'images'
