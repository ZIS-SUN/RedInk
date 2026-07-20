"""Google GenAI 客户端封装"""
import re
import time
import random
import logging
from functools import wraps
from google import genai
from google.genai import types

# 导入统一的错误解析函数
from ..generators.google_genai import parse_genai_error

logger = logging.getLogger(__name__)


# ==================== 重试白名单判定 ====================
# 每次重试都是一次完整计费的上游调用。历史实现是黑名单（除认证/参数/安全
# 之外全部重试 3 次），会把代码 bug（如 TypeError）、格式错误等确定性失败
# 也白跑 2 轮。这里改为白名单：仅限流(429/配额)、上游 5xx、超时和网络
# 连接类错误才重试，其余一律直接抛出。

# 可重试的 HTTP 状态码（异常携带 status_code/code 属性时优先使用）
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# 状态码词边界匹配，避免误命中模型名/ID 中的数字片段
_RETRYABLE_CODE_PATTERN = re.compile(r"\b(429|500|502|503|504)\b")

# 限流/配额类关键词（重试时使用更保守的指数退避）
_RATE_LIMIT_KEYWORDS = (
    "resource_exhausted",
    "rate limit",
    "rate_limit",
    "too many requests",
    "quota",
)

# 上游临时故障/网络类关键词
_TRANSIENT_KEYWORDS = (
    "internal error",
    "service unavailable",
    "unavailable",
    "deadline_exceeded",
    "deadline exceeded",
    "timeout",
    "timed out",
    "connection",
    "network",
)


def _extract_status_code(error: Exception):
    """尽力从异常对象提取 HTTP 状态码（genai APIError 携带 code 属性）"""
    for attr in ("status_code", "code", "status"):
        value = getattr(error, attr, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _is_rate_limit_error(error: Exception) -> bool:
    if _extract_status_code(error) == 429:
        return True
    text = str(error).lower()
    return "429" in _RETRYABLE_CODE_PATTERN.findall(text) or any(
        keyword in text for keyword in _RATE_LIMIT_KEYWORDS
    )


def _is_retryable_error(error: Exception) -> bool:
    """白名单判定：仅 429/配额、5xx、超时、网络连接类错误可重试"""
    status = _extract_status_code(error)
    if status is not None:
        # 有明确状态码时以状态码为准（400/401/403/404 等直接不重试）
        return status in _RETRYABLE_STATUS_CODES
    text = str(error).lower()
    if _RETRYABLE_CODE_PATTERN.search(text):
        return True
    return any(keyword in text for keyword in _RATE_LIMIT_KEYWORDS) or any(
        keyword in text for keyword in _TRANSIENT_KEYWORDS
    )


def retry_on_429(max_retries=3, base_delay=2):
    """限流/临时故障自动重试装饰器（白名单重试 + 智能错误解析）"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    if not _is_retryable_error(e):
                        # 白名单之外（认证/参数/安全拦截/代码错误等）：
                        # 重试大概率仍失败且每次都计费，直接抛出
                        raise Exception(parse_genai_error(e))

                    # 可重试的错误
                    if attempt < max_retries - 1:
                        if _is_rate_limit_error(e):
                            wait_time = (base_delay ** attempt) + random.uniform(0, 1)
                            logger.warning(f"[重试] 遇到资源限制，{wait_time:.1f}秒后重试 (尝试 {attempt + 2}/{max_retries})")
                        else:
                            wait_time = min(2 ** attempt, 10) + random.uniform(0, 1)
                            logger.warning(f"[重试] 请求失败，{wait_time:.1f}秒后重试 (尝试 {attempt + 2}/{max_retries})")
                        time.sleep(wait_time)
                        continue

                    # 重试次数耗尽
                    raise Exception(parse_genai_error(e))

            # 理论上不会到这里，但保险起见
            raise Exception(parse_genai_error(last_error))
        return wrapper
    return decorator


def _is_json_mime_type_unsupported(error: Exception) -> bool:
    """
    判断异常是否是"上游不支持 response_mime_type=application/json"类错误。

    仅在主动开启 json_mode 时调用；错误文本点名该参数（或其取值）
    即认为是参数不被支持，与文本侧 response_format 的降级判定思路一致。
    """
    text = str(error).lower()
    return "response_mime_type" in text or "responsemimetype" in text or (
        "mime" in text and "json" in text
    )


class GenAIClient:
    """GenAI 客户端封装类（已弃用，请使用 GoogleGenAIGenerator）"""

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key
        if not self.api_key:
            raise ValueError(
                "Google Cloud API Key 未配置。\n"
                "解决方案：在系统设置页面编辑该服务商，填写 API Key"
            )

        # 构建客户端参数
        # 统一 300 秒超时（genai SDK 的 timeout 单位为毫秒），
        # 与 image_api_client / text_client 的 300 秒对齐，避免请求无限期挂起
        client_kwargs = {
            "api_key": self.api_key,
            "http_options": {"timeout": 300_000},
        }

        # 如果有 base_url，使用 http_options
        if base_url:
            client_kwargs["http_options"].update({
                "base_url": base_url,
                "api_version": "v1beta"
            })

        # 默认使用 Gemini API (vertexai=False)，因为大多数用户使用 Google AI Studio 的 API Key
        # Vertex AI 需要 OAuth2 认证，不支持 API Key
        client_kwargs["vertexai"] = False

        self.client = genai.Client(**client_kwargs)

        # 默认安全设置：全部关闭
        self.default_safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ]

    @retry_on_429(max_retries=3, base_delay=2)
    def generate_text(
        self,
        prompt: str,
        model: str = "gemini-3-pro-preview",
        temperature: float = 1.0,
        max_output_tokens: int = 8000,
        use_search: bool = False,
        use_thinking: bool = False,
        images: list = None,
        system_prompt: str = None,
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """
        生成文本

        Args:
            prompt: 提示词
            model: 模型名称
            temperature: 温度
            max_output_tokens: 最大输出 token
            use_search: 是否使用搜索
            use_thinking: 是否启用思考模式
            images: 图片列表（暂不支持）
            system_prompt: 系统提示词（暂不支持）
            json_mode: 是否注入 response_mime_type="application/json"
                要求模型只输出 JSON；上游返回"不支持该参数"类错误时
                自动移除后重试一次（与文本侧 response_format 降级策略一致）

        Returns:
            生成的文本
        """
        parts = [types.Part(text=prompt)]

        if images:
            for img_data in images:
                if isinstance(img_data, bytes):
                    parts.append(types.Part(
                        inline_data=types.Blob(
                            mime_type="image/png",
                            data=img_data
                        )
                    ))

        contents = [
            types.Content(
                role="user",
                parts=parts
            )
        ]

        config_kwargs = {
            "temperature": temperature,
            "top_p": 0.95,
            "max_output_tokens": max_output_tokens,
            "safety_settings": self.default_safety_settings,
        }

        # 添加搜索工具
        if use_search:
            config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]

        # 添加思考配置
        if use_thinking:
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="HIGH")

        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"

        def _stream_once(kwargs_for_config: dict) -> str:
            generate_content_config = types.GenerateContentConfig(**kwargs_for_config)
            text = ""
            for chunk in self.client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
            ):
                if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
                    continue
                # 思考模型的 chunk 可能只含 thought 部件，此时 .text 为 None；
                # 直接拼接会抛 TypeError 并被误当可重试错误再跑几轮（重复计费）
                chunk_text = chunk.text
                if chunk_text:
                    text += chunk_text
            return text

        try:
            return _stream_once(config_kwargs)
        except Exception as e:
            # 上游不支持 response_mime_type：移除后降级重试一次
            if json_mode and _is_json_mime_type_unsupported(e):
                logger.warning("上游不支持 response_mime_type，移除后重试一次")
                downgraded_kwargs = dict(config_kwargs)
                downgraded_kwargs.pop("response_mime_type", None)
                return _stream_once(downgraded_kwargs)
            raise

    @retry_on_429(max_retries=5, base_delay=3)  # 图片生成重试更多次
    def generate_image(
        self,
        prompt: str,
        model: str = "gemini-3-pro-image-preview",
        aspect_ratio: str = "3:4",
        temperature: float = 1.0,
    ) -> bytes:
        """
        生成图片

        Args:
            prompt: 提示词
            model: 模型名称
            aspect_ratio: 宽高比
            temperature: 温度

        Returns:
            图片二进制数据
        """
        contents = [
            types.Content(
                role="user",
                parts=[types.Part(text=prompt)]
            )
        ]

        generate_content_config = types.GenerateContentConfig(
            temperature=temperature,
            top_p=0.95,
            max_output_tokens=32768,
            response_modalities=["TEXT", "IMAGE"],
            safety_settings=self.default_safety_settings,
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                output_mime_type="image/png",
            ),
        )

        image_data = None
        for chunk in self.client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                for part in chunk.candidates[0].content.parts:
                    # 检查是否有图片数据
                    if hasattr(part, 'inline_data') and part.inline_data:
                        image_data = part.inline_data.data
                        break
            # 拿到第一张有效图后停止消费流，避免后续 chunk 覆盖已获取的图片
            if image_data is not None:
                break

        if not image_data:
            raise ValueError(
                "❌ 图片生成失败：API 返回为空\n\n"
                "【可能原因】\n"
                "1. 提示词触发了安全过滤（最常见）\n"
                "2. 模型不支持当前的图片生成请求\n"
                "3. 网络传输过程中数据丢失\n\n"
                "【解决方案】\n"
                "1. 修改提示词，避免敏感内容：\n"
                "   - 避免涉及暴力、血腥、色情等内容\n"
                "   - 避免涉及真实人物（明星、政治人物等）\n"
                "   - 使用更中性、积极的描述\n"
                "2. 尝试简化提示词\n"
                "3. 检查网络连接后重试"
            )

        return image_data


# 全局客户端实例
_client_instance = None

def get_genai_client() -> GenAIClient:
    """获取全局 GenAI 客户端实例"""
    global _client_instance
    if _client_instance is None:
        _client_instance = GenAIClient()
    return _client_instance
