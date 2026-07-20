"""OpenAI 兼容协议的流式文本客户端

与 text_client.py 的非流式客户端并行存在（不修改后者）：
- TextStreamClient.stream_text 以 stream: true 调用 /chat/completions，
  逐 chunk yield 文本增量（choices[0].delta.content）
- get_text_stream_client 按 text_providers.yaml 配置解析激活服务商，
  配置解析口径与 llm_utils.get_text_client 一致；
  google_gemini 服务商暂不支持流式，抛出 StreamingNotSupportedError
  作为明确的"不支持"信号，调用方据此回退非流式接口
"""
import json
import logging
import requests

logger = logging.getLogger(__name__)

# 与 text_client.TextChatClient 一致的默认端点与超时
DEFAULT_BASE_URL = "https://api.openai.com"
DEFAULT_ENDPOINT = "/v1/chat/completions"
DEFAULT_TIMEOUT = 300  # 5 分钟；流式下为「相邻两个数据块之间」的读超时


class StreamingNotSupportedError(Exception):
    """当前激活服务商不支持流式输出（如 google_gemini）"""

    def __init__(self, provider_type: str):
        super().__init__(
            f"文本服务商类型 [{provider_type}] 暂不支持流式输出。\n"
            "解决方案：使用非流式接口，或在系统设置中切换到 OpenAI 兼容服务商"
        )
        self.provider_type = provider_type


class TextStreamClient:
    """OpenAI 兼容协议的流式文本客户端"""

    def __init__(self, api_key: str = None, base_url: str = None,
                 endpoint_type: str = None, timeout: int = DEFAULT_TIMEOUT):
        self.api_key = api_key
        if not self.api_key:
            raise ValueError(
                "Text API Key 未配置。\n"
                "解决方案：在系统设置页面编辑文本生成服务商，填写 API Key"
            )

        # URL 规整逻辑与 text_client.TextChatClient 保持一致
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip('/')
        if self.base_url.endswith('/v1'):
            self.base_url = self.base_url[:-3]

        endpoint = endpoint_type or DEFAULT_ENDPOINT
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        self.chat_endpoint = f"{self.base_url}{endpoint}"
        self.timeout = timeout

    def stream_text(
        self,
        prompt: str,
        model: str,
        temperature: float = 1.0,
        max_output_tokens: int = 8000,
        system_prompt: str = None,
    ):
        """
        流式生成文本：逐 chunk yield 文本增量（str）

        - 上游按 OpenAI SSE 协议返回 `data: {...}` 行，取
          choices[0].delta.content 作为增量
        - 收到 `data: [DONE]` 或流结束时停止
        - 生成器被 close()（客户端断开）时关闭底层 HTTP 连接，停止上游流
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "stream": True,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self.api_key}",
        }

        response = requests.post(
            self.chat_endpoint,
            json=payload,
            headers=headers,
            timeout=self.timeout,
            stream=True,
        )

        if response.status_code != 200:
            try:
                error_detail = response.text[:500]
            finally:
                response.close()
            # 错误消息带上状态码与原始内容，交由 errors.classify_error 归类
            raise Exception(
                f"❌ 流式文本 API 请求失败 (状态码: {response.status_code})\n"
                f"【原始错误】{error_detail}\n"
                f"【请求地址】{self.chat_endpoint}\n"
                f"【模型】{model}"
            )

        try:
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                if not raw_line.startswith('data:'):
                    continue
                data = raw_line[len('data:'):].strip()
                if data == '[DONE]':
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning(f"跳过无法解析的流式 chunk: {data[:100]}")
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = (choices[0] or {}).get("delta") or {}
                text = delta.get("content")
                if text:
                    yield text
        finally:
            # 正常结束 / 异常 / 生成器被 close()（客户端断开）都关闭上游连接
            response.close()


def get_text_stream_client(text_config: dict) -> TextStreamClient:
    """
    根据文本生成配置构建流式客户端。

    配置解析口径与 llm_utils.get_text_client 一致：
    激活服务商 / api_key / base_url / endpoint_type。

    Raises:
        StreamingNotSupportedError: 激活服务商类型不支持流式（google_gemini）
        ValueError: 无服务商配置 / 激活服务商不存在 / 未配置 API Key
    """
    active_provider = text_config.get('active_provider', 'google_gemini')
    providers = text_config.get('providers', {})

    if not providers:
        raise ValueError(
            "未找到任何文本生成服务商配置。\n"
            "解决方案：\n"
            "1. 在系统设置页面添加文本生成服务商\n"
            "2. 或手动编辑 text_providers.yaml 文件"
        )

    if active_provider not in providers:
        available = ', '.join(providers.keys())
        raise ValueError(
            f"未找到文本生成服务商配置: {active_provider}\n"
            f"可用的服务商: {available}\n"
            "解决方案：在系统设置中选择一个可用的服务商"
        )

    provider_config = providers.get(active_provider, {})
    provider_type = provider_config.get('type', 'openai_compatible')

    if provider_type == 'google_gemini':
        # Google GenAI SDK 客户端暂未接入流式，返回明确的"不支持"信号
        raise StreamingNotSupportedError(provider_type)

    if not provider_config.get('api_key'):
        raise ValueError(
            f"文本服务商 {active_provider} 未配置 API Key\n"
            "解决方案：在系统设置页面编辑该服务商，填写 API Key"
        )

    logger.info(f"使用流式文本服务商: {active_provider} (type={provider_type})")
    return TextStreamClient(
        api_key=provider_config.get('api_key'),
        base_url=provider_config.get('base_url'),
        endpoint_type=provider_config.get('endpoint_type'),
    )
