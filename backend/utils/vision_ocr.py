"""
多模态视觉识别调用（数据复盘「截图导入」等场景专用）

作为独立于 text_client.TextChatClient / genai_client.GenAIClient 的新增能力，
不改动既有客户端的任何函数：
- openai_compatible：POST chat completions，用户消息 content 使用
  [{type: text}, {type: image_url, image_url: {url: data URL}}] 多模态格式
- google_gemini：google-genai SDK 的 contents 图片 part（inline_data Blob）

设计要点：
- requests / google-genai / PIL 等三方依赖全部在函数内惰性导入，
  保证纯 CRUD 调用路径不因导入本模块而引入这些依赖
- 发送前对超大截图做温和压缩（1MB 上限，2048px 长边），
  平衡 OCR 清晰度与上游请求体大小；压缩失败时原图直传
- 不做自动重试：视觉识别调用较贵，失败直接抛出由调用方分类处理
"""

import base64
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# 发送给上游前的单图压缩上限（KB）。截图以文字为主，
# 1MB 内的 JPEG（2048px 长边）足够 OCR 清晰
_MAX_UPLOAD_KB = 1000

# 与 text_client / genai_client 对齐的 300 秒请求超时
_REQUEST_TIMEOUT_SECONDS = 300

# 常见图片格式的魔数 -> MIME（识别不了时按 PNG 处理）
_MAGIC_MIME_TYPES: Tuple[Tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF8", "image/gif"),
)


def _sniff_mime(data: bytes) -> str:
    """按魔数嗅探图片 MIME 类型（WEBP 的 RIFF 头单独判断）。"""
    for magic, mime in _MAGIC_MIME_TYPES:
        if data.startswith(magic):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _prepare_image(data: bytes) -> Tuple[bytes, str]:
    """
    发送前预处理单张截图，返回 (图片数据, MIME 类型)。

    超过压缩上限时转成 JPEG（compress_image 的输出格式）；
    未触发压缩或压缩失败时保持原图原格式。
    """
    from .image_compressor import compress_image

    try:
        prepared = compress_image(data, max_size_kb=_MAX_UPLOAD_KB)
    except Exception as e:
        logger.warning("截图压缩失败，按原图直传: %s", e)
        prepared = data

    if prepared is data:
        return data, _sniff_mime(data)
    return prepared, "image/jpeg"


def generate_vision_text(
    provider_config: dict,
    *,
    prompt: str,
    images: List[bytes],
    model: str,
    temperature: float = 0.1,
    max_output_tokens: int = 4000,
) -> str:
    """
    携带图片调用文本模型，返回模型输出文本。

    Args:
        provider_config: 服务商配置（type / api_key / base_url / endpoint_type）
        prompt: 文本提示词
        images: 图片二进制列表（1 张以上）
        model: 模型名称
        temperature: 温度（识别类任务默认 0.1，追求确定性输出）
        max_output_tokens: 最大输出 token

    Raises:
        ValueError: API Key 未配置 / images 为空
        Exception: 上游调用失败（模型不支持视觉输入时通常表现为 4xx 错误）
    """
    if not images:
        raise ValueError("视觉识别至少需要 1 张图片")
    if not provider_config.get("api_key"):
        raise ValueError(
            "Text API Key 未配置。\n"
            "解决方案：在系统设置页面编辑文本生成服务商，填写 API Key"
        )

    provider_type = provider_config.get("type", "openai_compatible")
    if provider_type == "google_gemini":
        return _generate_via_google_gemini(
            provider_config, prompt, images, model, temperature, max_output_tokens
        )
    return _generate_via_openai_compatible(
        provider_config, prompt, images, model, temperature, max_output_tokens
    )


def _generate_via_openai_compatible(
    provider_config: dict,
    prompt: str,
    images: List[bytes],
    model: str,
    temperature: float,
    max_output_tokens: int,
) -> str:
    """OpenAI 兼容接口：chat messages 的 image_url(data URL) 多模态格式。"""
    import requests

    # Base URL / 端点拼接规则与 TextChatClient 保持一致
    base_url = (provider_config.get("base_url") or "https://api.openai.com").rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
    endpoint = provider_config.get("endpoint_type") or "/v1/chat/completions"
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    chat_endpoint = f"{base_url}{endpoint}"

    content = [{"type": "text", "text": prompt}]
    for image in images:
        data, mime = _prepare_image(image)
        encoded = base64.b64encode(data).decode("utf-8")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{encoded}"},
        })

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": temperature,
        "max_tokens": max_output_tokens,
        "stream": False,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {provider_config.get('api_key')}",
    }

    response = requests.post(
        chat_endpoint, json=payload, headers=headers, timeout=_REQUEST_TIMEOUT_SECONDS
    )
    if response.status_code != 200:
        # 不支持视觉输入的模型通常返回 4xx（invalid content type / image 不被支持等），
        # 原样带出错误详情，由调用方统一归类为「模型不支持图片识别或识别失败」
        raise Exception(
            f"视觉识别请求失败 (HTTP {response.status_code})：{response.text[:300]}\n"
            f"【请求地址】{chat_endpoint}\n【模型】{model}"
        )

    result = response.json()
    choices = result.get("choices") or []
    message_content = (choices[0].get("message") or {}).get("content") if choices else None
    if not message_content:
        raise Exception(
            f"视觉识别响应格式异常：未找到生成的文本。响应数据: {str(result)[:300]}"
        )
    return message_content


def _generate_via_google_gemini(
    provider_config: dict,
    prompt: str,
    images: List[bytes],
    model: str,
    temperature: float,
    max_output_tokens: int,
) -> str:
    """Google Gemini：contents 的图片 part（inline_data Blob）多模态格式。"""
    from google import genai
    from google.genai import types

    # 客户端构建参数与 GenAIClient 保持一致（超时/自定义 base_url/关闭 vertexai）
    client_kwargs = {
        "api_key": provider_config.get("api_key"),
        "http_options": {"timeout": _REQUEST_TIMEOUT_SECONDS * 1000},
        "vertexai": False,
    }
    base_url = provider_config.get("base_url")
    if base_url:
        client_kwargs["http_options"].update({
            "base_url": base_url,
            "api_version": "v1beta",
        })
    client = genai.Client(**client_kwargs)

    parts = [types.Part(text=prompt)]
    for image in images:
        data, mime = _prepare_image(image)
        parts.append(types.Part(inline_data=types.Blob(mime_type=mime, data=data)))

    config = types.GenerateContentConfig(
        temperature=temperature,
        top_p=0.95,
        max_output_tokens=max_output_tokens,
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
    )

    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=parts)],
        config=config,
    )
    text = getattr(response, "text", None)
    if not text:
        raise Exception("视觉识别返回为空（模型可能不支持图片输入，或图片触发了安全过滤）")
    return text
