"""
大纲生成相关 API 路由

包含功能：
- 生成大纲（支持图片上传）
- 单页 AI 润色
"""

import time
import json
import base64
import logging
from flask import Blueprint, request, jsonify, Response
from backend.errors import AppError, ensure_app_error
from backend.services.outline import get_outline_service
from backend.services.brand import get_brand_service
from backend.utils.text_stream import (
    StreamingNotSupportedError,
    get_text_stream_client,
)
from .utils import (
    api_error_response,
    log_request,
    log_error,
    normalize_error_result,
    validation_error,
)

logger = logging.getLogger(__name__)

# 单页润色指令白名单：前端只传 key，后端映射为完整中文指令，防止 prompt 注入
POLISH_INSTRUCTIONS = {
    'polish': "在保持原意和结构的前提下润色，让表达更生动吸引人",
    'shorten': "精简压缩，保留核心信息，字数减少约三分之一",
    'punchier': "改写得更有网感、更抓眼球，多用小红书风格的表达",
}
DEFAULT_POLISH_INSTRUCTION = 'polish'


def create_outline_blueprint():
    """创建大纲路由蓝图（工厂函数，支持多次调用）"""
    outline_bp = Blueprint('outline', __name__)

    @outline_bp.route('/outline', methods=['POST'])
    def generate_outline():
        """
        生成大纲（支持图片上传）

        请求格式：
        1. multipart/form-data（带图片文件）
           - topic: 主题文本
           - images: 图片文件列表

        2. application/json（无图片或 base64 图片）
           - topic: 主题文本
           - images: base64 编码的图片数组（可选）

        两种格式均支持可选字段 brand_id（品牌档案 ID），
        提供且有效时会把品牌人设约束注入生成 prompt。

        返回：
        - success: 是否成功
        - outline: 原始大纲文本
        - pages: 解析后的页面列表
        """
        start_time = time.time()

        try:
            # 解析请求数据
            topic, images, brand_id = _parse_outline_request()

            log_request('/outline', {'topic': topic, 'images': images})

            # 验证必填参数
            if not topic:
                logger.warning("大纲生成请求缺少 topic 参数")
                return api_error_response(
                    validation_error("topic 不能为空", "请输入要生成图文的主题内容。"),
                    context={"endpoint": "/api/outline"},
                )

            # 按 brand_id 取品牌档案（取不到/异常一律置 None，静默忽略）
            brand = _load_brand(brand_id)

            # 调用大纲生成服务
            logger.info(f"🔄 开始生成大纲，主题: {topic[:50]}...")
            outline_service = get_outline_service()
            result = outline_service.generate_outline(
                topic, images if images else None, brand=brand
            )

            # 记录结果
            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 大纲生成成功，耗时 {elapsed:.2f}s，共 {len(result.get('pages', []))} 页")
                return jsonify(result), 200
            else:
                logger.error(f"❌ 大纲生成失败: {result.get('error', '未知错误')}")
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/outline"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/outline', e)
            return api_error_response(e, context={"endpoint": "/api/outline"})

    @outline_bp.route('/outline/stream', methods=['POST'])
    def generate_outline_stream():
        """
        流式生成大纲（SSE），把用户感知等待降到首字级

        请求体（application/json，不支持图片；带图请走 POST /outline）：
        - topic: 主题文本（必填）
        - brand_id: 品牌档案 ID（可选），提供且有效时注入品牌人设约束

        返回 SSE 事件流（事件格式与图片管线一致）：
        - delta: {"text": "..."} 文本增量
        - complete: 最终完整文本 + 服务端解析好的结构化大纲
          （与 POST /outline 成功响应同构：success/outline/pages/has_images）
        - error: 结构化错误（error 为 AppError 字典）
        - finish: {"success": bool} 流结束标记

        激活服务商不支持流式时，返回 400 + code=STREAMING_NOT_SUPPORTED
        的普通 JSON 响应，前端据此回退到非流式接口。
        """
        start_time = time.time()

        try:
            data = request.get_json(silent=True) or {}
            topic = data.get('topic')
            brand_id = data.get('brand_id')

            log_request('/outline/stream', {'topic': topic})

            # 参数校验与 /outline 一致（400 规范）
            if not topic or not isinstance(topic, str) or not topic.strip():
                logger.warning("流式大纲生成请求缺少 topic 参数")
                return api_error_response(
                    validation_error("topic 不能为空", "请输入要生成图文的主题内容。"),
                    context={"endpoint": "/api/outline/stream"},
                )

            # 流式版只支持无图路径；带图请求应由前端走既有 POST /outline
            if data.get('images'):
                logger.warning("流式大纲生成请求携带了图片，拒绝处理")
                return api_error_response(
                    validation_error(
                        "流式大纲生成不支持图片",
                        "带参考图片时请使用非流式接口 POST /api/outline。",
                    ),
                    context={"endpoint": "/api/outline/stream"},
                )

            # 按 brand_id 取品牌档案（取不到/异常一律置 None，静默忽略）
            brand = _load_brand(brand_id)

            # 流开始前完成所有可能失败的准备工作，
            # 让配置类错误以普通 JSON 响应返回（前端可据此回退非流式）
            outline_service = get_outline_service()
            try:
                stream_client = get_text_stream_client(outline_service.text_config)
            except StreamingNotSupportedError as e:
                logger.info(f"激活服务商不支持流式输出: {e}")
                return api_error_response(AppError(
                    code="STREAMING_NOT_SUPPORTED",
                    title="当前服务商不支持流式输出",
                    detail=str(e),
                    suggestion="请使用非流式接口，或在系统设置中切换到 OpenAI 兼容服务商。",
                    status=400,
                    retryable=False,
                ), context={"endpoint": "/api/outline/stream"})

            # prompt 组装复用 OutlineService，保证与非流式产出完全一致
            prompt = outline_service.build_outline_prompt(topic, brand=brand)
            model, temperature, max_output_tokens = outline_service.get_generation_params()

            logger.info(f"🔄 开始流式生成大纲，主题: {topic[:50]}...")

            def generate():
                """SSE 事件生成器：delta* → complete → finish（出错：error → finish）"""
                chunks = []
                upstream = stream_client.stream_text(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )
                try:
                    for delta in upstream:
                        chunks.append(delta)
                        yield _sse_event('delta', {'text': delta})

                    outline_text = ''.join(chunks)
                    if not outline_text.strip():
                        raise ValueError("AI 返回的大纲内容为空")

                    # 解析复用 OutlineService 的既有逻辑，与非流式结果同构
                    pages = outline_service.parse_outline(outline_text)
                    elapsed = time.time() - start_time
                    logger.info(f"✅ 流式大纲生成成功，耗时 {elapsed:.2f}s，共 {len(pages)} 页")

                    yield _sse_event('complete', {
                        'success': True,
                        'outline': outline_text,
                        'pages': pages,
                        'has_images': False,
                    })
                    yield _sse_event('finish', {'success': True})
                except GeneratorExit:
                    # 客户端断开（SSE 断连）：关闭上游流式生成器，
                    # 触发其 finally 关闭底层 HTTP 连接，停止上游流
                    upstream.close()
                    raise
                except Exception as e:
                    log_error('/outline/stream', e)
                    app_error = ensure_app_error(
                        e, context={"endpoint": "/api/outline/stream"}
                    )
                    yield _sse_event('error', {
                        'success': False,
                        'error': app_error.to_dict(),
                        'message': app_error.to_message(),
                        'retryable': app_error.retryable,
                    })
                    yield _sse_event('finish', {'success': False})

            return Response(
                generate(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                }
            )

        except Exception as e:
            log_error('/outline/stream', e)
            return api_error_response(e, context={"endpoint": "/api/outline/stream"})

    @outline_bp.route('/outline/polish', methods=['POST'])
    def polish_page():
        """
        单页 AI 润色：对大纲中某一页的文案按指令重写

        请求体（application/json）：
        - content: 该页原文（必填，非空）
        - page_type: 页面类型 cover/content/summary（默认 "content"）
        - topic: 整篇主题（默认 ""）
        - instruction: 润色指令 key：polish/shorten/punchier（其他值按 polish 处理）
        - brand_id: 品牌档案 ID（可选），提供且有效时约束润色结果保持人设语气、
          不引入禁用词；档案不存在则忽略

        返回：
        - success: 是否成功
        - content: 润色后的该页文案
        """
        start_time = time.time()

        try:
            data = request.get_json(silent=True) or {}

            # 参数类型收敛：传入非字符串（数字/对象等）时统一转 str，防止后续处理 500
            content = data.get('content')
            if not isinstance(content, str):
                content = str(content) if content is not None else ''
            content = content.strip()
            page_type = data.get('page_type') or 'content'
            if not isinstance(page_type, str):
                page_type = str(page_type)
            topic = data.get('topic') or ''
            if not isinstance(topic, str):
                topic = str(topic)
            instruction_key = data.get('instruction') or DEFAULT_POLISH_INSTRUCTION
            brand_id = data.get('brand_id')

            log_request('/outline/polish', {
                'content_length': len(content),
                'page_type': page_type,
                'instruction': instruction_key,
            })

            if not content:
                logger.warning("单页润色请求缺少 content 参数")
                return api_error_response(
                    validation_error("content 不能为空", "请提供要润色的页面文案。"),
                    context={"endpoint": "/api/outline/polish"},
                )

            # 白名单映射：未知指令一律按 polish 处理，防止注入
            instruction = POLISH_INSTRUCTIONS.get(
                instruction_key, POLISH_INSTRUCTIONS[DEFAULT_POLISH_INSTRUCTION]
            )

            # 按 brand_id 取品牌档案（取不到/异常一律置 None，静默忽略）
            brand = _load_brand(brand_id)

            logger.info(f"🔄 开始单页润色，指令: {instruction_key}")
            outline_service = get_outline_service()
            result = outline_service.polish_page(
                content=content,
                page_type=page_type,
                topic=topic,
                instruction=instruction,
                brand=brand,
            )

            elapsed = time.time() - start_time
            if result["success"]:
                logger.info(f"✅ 单页润色成功，耗时 {elapsed:.2f}s")
                return jsonify(result), 200
            else:
                logger.error(f"❌ 单页润色失败: {result.get('error', '未知错误')}")
                result = normalize_error_result(
                    result,
                    context={"endpoint": "/api/outline/polish"},
                    fallback_status=500,
                )
                return jsonify(result), result["error"].get("status", 500)

        except Exception as e:
            log_error('/outline/polish', e)
            return api_error_response(e, context={"endpoint": "/api/outline/polish"})

    return outline_bp


def _sse_event(event_type: str, data: dict) -> str:
    """格式化单条 SSE 事件（与图片管线的事件写法一致）"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _load_brand(brand_id):
    """按 brand_id 取品牌档案，取不到或异常时返回 None（静默忽略）。"""
    if not brand_id or not isinstance(brand_id, str):
        return None
    try:
        return get_brand_service().get_brand(brand_id)
    except Exception as e:
        logger.warning(f"获取品牌档案失败，忽略 brand_id={brand_id}: {e}")
        return None


def _parse_outline_request():
    """
    解析大纲生成请求

    支持两种格式：
    1. multipart/form-data - 用于文件上传
    2. application/json - 用于 base64 图片

    返回：
        tuple: (topic, images, brand_id) - 主题、图片列表和品牌档案 ID（可能为 None）
    """
    # 检查是否是 multipart/form-data（带图片文件）
    if request.content_type and 'multipart/form-data' in request.content_type:
        topic = request.form.get('topic')
        brand_id = request.form.get('brand_id')
        images = []

        # 获取上传的图片文件
        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename:
                    image_data = file.read()
                    images.append(image_data)

        return topic, images, brand_id

    # JSON 请求（无图片或 base64 图片）
    data = request.get_json()
    topic = data.get('topic')
    brand_id = data.get('brand_id')
    images = []

    # 支持 base64 格式的图片
    images_base64 = data.get('images', [])
    if images_base64:
        for img_b64 in images_base64:
            # 移除可能的 data URL 前缀
            if ',' in img_b64:
                img_b64 = img_b64.split(',')[1]
            images.append(base64.b64decode(img_b64))

    return topic, images, brand_id
