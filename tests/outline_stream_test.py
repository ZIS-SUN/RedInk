"""
大纲流式生成（POST /api/outline/stream）与流式文本客户端测试

不发起真实 LLM 调用：
- 路由层测试 mock 掉 OutlineService 依赖与流式客户端工厂
- 客户端层测试 mock 掉 requests.post
"""
import json
import pytest

from backend.routes import outline_routes
from backend.services.outline import OutlineService
from backend.utils import text_stream
from backend.utils.text_stream import (
    StreamingNotSupportedError,
    TextStreamClient,
    get_text_stream_client,
)


# ==================== 测试工具 ====================

def parse_sse_events(body: str):
    """把 SSE 响应体解析为 (event, data_dict) 列表"""
    events = []
    for block in body.split('\n\n'):
        if not block.strip():
            continue
        event_type = 'message'
        data = None
        for line in block.split('\n'):
            if line.startswith('event: '):
                event_type = line[len('event: '):]
            elif line.startswith('data: '):
                data = json.loads(line[len('data: '):])
        events.append((event_type, data))
    return events


class FakeStreamClient:
    """假流式客户端：按预设增量产出，可在中途抛错；记录调用参数与关闭状态"""

    def __init__(self, deltas=None, error=None, error_after=None):
        self.deltas = deltas or []
        self.error = error
        # error_after=N 表示产出 N 个增量后抛错；None 表示不抛错
        self.error_after = error_after
        self.closed = False
        self.calls = []

    def stream_text(self, prompt, model, temperature, max_output_tokens, **kwargs):
        self.calls.append({
            "prompt": prompt,
            "model": model,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        })
        return self._gen()

    def _gen(self):
        try:
            for i, delta in enumerate(self.deltas):
                if self.error_after is not None and i >= self.error_after:
                    raise self.error
                yield delta
            if self.error_after is not None and self.error_after >= len(self.deltas):
                raise self.error
        finally:
            self.closed = True


class FakeTextClient:
    """记录 prompt 的假非流式客户端（服务层 prompt 一致性测试用）"""

    def __init__(self, response_text="[封面]\n标题：测试"):
        self.response_text = response_text
        self.prompts = []

    def generate_text(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return self.response_text


def build_outline_service(response_text="[封面]\n标题：测试") -> OutlineService:
    """绕过 __init__（避免读取真实配置/API Key），手工装配依赖"""
    service = OutlineService.__new__(OutlineService)
    service.text_config = {
        'active_provider': 'test_provider',
        'providers': {
            'test_provider': {
                'type': 'openai_compatible',
                'model': 'test-model',
                'temperature': 0.8,
                'max_output_tokens': 4000,
                'api_key': 'sk-test',
            }
        }
    }
    service.client = FakeTextClient(response_text)
    service.prompt_template = "请为主题「{topic}」生成小红书图文大纲"
    return service


@pytest.fixture
def fake_service(monkeypatch):
    service = build_outline_service()
    monkeypatch.setattr(outline_routes, "get_outline_service", lambda: service)
    return service


@pytest.fixture
def fake_stream(monkeypatch, fake_service):
    client = FakeStreamClient(deltas=["[封面]\n标题：", "秋日穿搭", "\n<page>\n[内容]\n第二页内容"])
    monkeypatch.setattr(outline_routes, "get_text_stream_client", lambda cfg: client)
    return client


# ==================== 参数校验（与 /outline 一致的 400 规范） ====================

@pytest.mark.parametrize("payload", [
    {},
    {"topic": ""},
    {"topic": "   \n "},
    {"topic": None},
])
def test_stream_invalid_topic_returns_400(client, payload):
    response = client.post("/api/outline/stream", json=payload)
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert data["error_message"]


def test_stream_with_images_returns_400(client, fake_service):
    response = client.post("/api/outline/stream", json={
        "topic": "秋日穿搭",
        "images": ["aGVsbG8="],
    })
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert "不支持图片" in data["error"]["detail"]


# ==================== 不支持流式的服务商 ====================

def test_stream_not_supported_returns_explicit_error_code(client, fake_service, monkeypatch):
    def raise_not_supported(cfg):
        raise StreamingNotSupportedError("google_gemini")

    monkeypatch.setattr(outline_routes, "get_text_stream_client", raise_not_supported)

    response = client.post("/api/outline/stream", json={"topic": "秋日穿搭"})
    data = response.get_json()

    # 普通 JSON 响应（非 SSE），前端据此回退非流式接口
    assert response.status_code == 400
    assert response.mimetype == "application/json"
    assert data["success"] is False
    assert data["error"]["code"] == "STREAMING_NOT_SUPPORTED"
    assert data["error"]["retryable"] is False


def test_stream_config_error_returns_json_error(client, fake_service, monkeypatch):
    def raise_config_error(cfg):
        raise ValueError("文本服务商 test_provider 未配置 API Key")

    monkeypatch.setattr(outline_routes, "get_text_stream_client", raise_config_error)

    response = client.post("/api/outline/stream", json={"topic": "秋日穿搭"})
    data = response.get_json()

    assert response.mimetype == "application/json"
    assert data["success"] is False
    assert response.status_code >= 400


# ==================== 事件序列 ====================

def test_stream_success_event_sequence(client, fake_service, fake_stream):
    response = client.post("/api/outline/stream", json={"topic": "秋日穿搭"})

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"

    events = parse_sse_events(response.get_data(as_text=True))
    event_types = [e[0] for e in events]
    assert event_types == ["delta", "delta", "delta", "complete", "finish"]

    # delta：逐段文本增量
    assert [e[1]["text"] for e in events[:3]] == fake_stream.deltas

    # complete：完整文本 + 服务端解析好的结构化大纲（与 /outline 成功响应同构）
    complete = events[3][1]
    full_text = "".join(fake_stream.deltas)
    assert complete["success"] is True
    assert complete["outline"] == full_text
    assert complete["has_images"] is False
    assert len(complete["pages"]) == 2
    assert complete["pages"][0]["type"] == "cover"
    assert complete["pages"][1]["type"] == "content"
    # 解析结果与 OutlineService 的既有解析逻辑完全一致
    assert complete["pages"] == fake_service.parse_outline(full_text)

    # finish：成功标记
    assert events[4][1] == {"success": True}


def test_stream_passes_generation_params_from_config(client, fake_service, fake_stream):
    client.post("/api/outline/stream", json={"topic": "秋日穿搭"})

    call = fake_stream.calls[0]
    assert call["model"] == "test-model"
    assert call["temperature"] == 0.8
    assert call["max_output_tokens"] == 4000


def test_stream_empty_llm_output_yields_error_event(client, fake_service, monkeypatch):
    stream = FakeStreamClient(deltas=[])
    monkeypatch.setattr(outline_routes, "get_text_stream_client", lambda cfg: stream)

    response = client.post("/api/outline/stream", json={"topic": "秋日穿搭"})
    events = parse_sse_events(response.get_data(as_text=True))

    assert [e[0] for e in events] == ["error", "finish"]
    assert events[0][1]["success"] is False
    assert isinstance(events[0][1]["error"], dict)
    assert events[1][1] == {"success": False}


def test_stream_upstream_error_yields_structured_error(client, fake_service, monkeypatch):
    stream = FakeStreamClient(
        deltas=["第一段"],
        error=Exception("HTTP 429: rate limit exceeded"),
        error_after=1,
    )
    monkeypatch.setattr(outline_routes, "get_text_stream_client", lambda cfg: stream)

    response = client.post("/api/outline/stream", json={"topic": "秋日穿搭"})
    events = parse_sse_events(response.get_data(as_text=True))

    assert [e[0] for e in events] == ["delta", "error", "finish"]
    error_data = events[1][1]
    assert error_data["success"] is False
    assert error_data["error"]["code"] == "RATE_LIMITED"
    assert error_data["retryable"] is True
    assert error_data["message"]
    assert events[2][1] == {"success": False}


# ==================== prompt 组装复用（流式与非流式完全一致） ====================

def test_stream_prompt_identical_to_non_stream(client, fake_service, fake_stream):
    brand = {"name": "测试品牌", "tone": "活泼"}

    # 非流式：generate_outline 内部组装 prompt 并交给非流式客户端
    fake_service.generate_outline("秋日穿搭", brand=brand)
    non_stream_prompt = fake_service.client.prompts[0]

    # 流式端点走 build_outline_prompt（无 brand 时与非流式无图路径一致）
    client.post("/api/outline/stream", json={"topic": "秋日穿搭"})
    stream_prompt = fake_stream.calls[0]["prompt"]

    assert non_stream_prompt == fake_service.build_outline_prompt("秋日穿搭", brand=brand)
    assert stream_prompt == fake_service.build_outline_prompt("秋日穿搭")
    # 主题占位符已替换
    assert "秋日穿搭" in stream_prompt


def test_stream_brand_constraint_injected(client, fake_service, fake_stream, monkeypatch):
    brand = {"name": "测试品牌", "tone": "活泼"}
    monkeypatch.setattr(outline_routes, "_load_brand", lambda brand_id: brand)

    client.post("/api/outline/stream", json={"topic": "秋日穿搭", "brand_id": "b1"})

    stream_prompt = fake_stream.calls[0]["prompt"]
    assert stream_prompt == fake_service.build_outline_prompt("秋日穿搭", brand=brand)
    assert "测试品牌" in stream_prompt


# ==================== 客户端断开清理 ====================

def test_stream_client_disconnect_closes_upstream(app, fake_service, fake_stream):
    test_client = app.test_client()
    response = test_client.post(
        "/api/outline/stream",
        json={"topic": "秋日穿搭"},
        buffered=False,
    )

    iterator = response.response
    # 消费第一条事件后模拟客户端断开
    next(iter(iterator))
    response.close()

    assert fake_stream.closed is True


# ==================== 流式文本客户端（text_stream.py） ====================

class FakeHttpResponse:
    """模拟 requests 流式响应"""

    def __init__(self, lines=None, status_code=200, text=""):
        self.lines = lines or []
        self.status_code = status_code
        self.text = text
        self.closed = False

    def iter_lines(self, decode_unicode=False):
        yield from self.lines

    def close(self):
        self.closed = True


def _openai_chunk(content):
    return "data: " + json.dumps(
        {"choices": [{"delta": {"content": content}}]}, ensure_ascii=False
    )


def test_stream_client_parses_openai_chunks(monkeypatch):
    fake_response = FakeHttpResponse(lines=[
        _openai_chunk("你好"),
        "",  # keep-alive 空行
        ": comment",  # 注释行
        "data: not-json",  # 非法 JSON 跳过
        json.dumps({"foo": "bar"}),  # 非 data 行跳过
        "data: " + json.dumps({"choices": [{"delta": {"role": "assistant"}}]}),  # 无 content
        "data: " + json.dumps({"choices": []}),  # 空 choices
        _openai_chunk("，世界"),
        "data: [DONE]",
        _openai_chunk("不应出现"),  # [DONE] 之后的内容不再消费
    ])
    monkeypatch.setattr(
        text_stream.requests, "post", lambda *args, **kwargs: fake_response
    )

    client = TextStreamClient(api_key="sk-test", base_url="https://api.example.com")
    deltas = list(client.stream_text(prompt="hi", model="test-model"))

    assert deltas == ["你好", "，世界"]
    assert fake_response.closed is True


def test_stream_client_sends_stream_payload(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None, stream=None):
        captured.update({
            "url": url, "payload": json, "headers": headers,
            "timeout": timeout, "stream": stream,
        })
        return FakeHttpResponse(lines=["data: [DONE]"])

    monkeypatch.setattr(text_stream.requests, "post", fake_post)

    client = TextStreamClient(api_key="sk-test", base_url="https://api.example.com/v1")
    list(client.stream_text(
        prompt="hi", model="m1", temperature=0.5, max_output_tokens=1000,
        system_prompt="sys",
    ))

    # base_url 的 /v1 后缀被规整，端点默认 /v1/chat/completions
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["payload"]["stream"] is True
    assert captured["payload"]["model"] == "m1"
    assert captured["payload"]["temperature"] == 0.5
    assert captured["payload"]["max_tokens"] == 1000
    assert captured["payload"]["messages"][0] == {"role": "system", "content": "sys"}
    assert captured["payload"]["messages"][1] == {"role": "user", "content": "hi"}
    assert captured["stream"] is True
    assert captured["headers"]["Authorization"] == "Bearer sk-test"


def test_stream_client_non_200_raises_and_closes(monkeypatch):
    fake_response = FakeHttpResponse(status_code=429, text="rate limited")
    monkeypatch.setattr(
        text_stream.requests, "post", lambda *args, **kwargs: fake_response
    )

    client = TextStreamClient(api_key="sk-test")
    with pytest.raises(Exception) as exc_info:
        list(client.stream_text(prompt="hi", model="test-model"))

    assert "429" in str(exc_info.value)
    assert fake_response.closed is True


def test_stream_client_generator_close_closes_response(monkeypatch):
    """生成器被 close()（对应 SSE 客户端断开）时关闭底层 HTTP 连接"""
    fake_response = FakeHttpResponse(lines=[
        _openai_chunk("第一段"),
        _openai_chunk("第二段"),
    ])
    monkeypatch.setattr(
        text_stream.requests, "post", lambda *args, **kwargs: fake_response
    )

    client = TextStreamClient(api_key="sk-test")
    gen = client.stream_text(prompt="hi", model="test-model")
    assert next(gen) == "第一段"

    gen.close()
    assert fake_response.closed is True


def test_stream_client_requires_api_key():
    with pytest.raises(ValueError):
        TextStreamClient(api_key=None)


# ==================== 流式客户端工厂（配置解析） ====================

def test_factory_google_gemini_not_supported():
    config = {
        'active_provider': 'gemini',
        'providers': {
            'gemini': {'type': 'google_gemini', 'api_key': 'k'},
        }
    }
    with pytest.raises(StreamingNotSupportedError) as exc_info:
        get_text_stream_client(config)
    assert exc_info.value.provider_type == "google_gemini"


def test_factory_no_providers_raises():
    with pytest.raises(ValueError, match="未找到任何文本生成服务商配置"):
        get_text_stream_client({'active_provider': 'x', 'providers': {}})


def test_factory_unknown_active_provider_raises():
    config = {
        'active_provider': 'missing',
        'providers': {'other': {'type': 'openai_compatible', 'api_key': 'k'}},
    }
    with pytest.raises(ValueError, match="未找到文本生成服务商配置"):
        get_text_stream_client(config)


def test_factory_missing_api_key_raises():
    config = {
        'active_provider': 'p1',
        'providers': {'p1': {'type': 'openai_compatible'}},
    }
    with pytest.raises(ValueError, match="未配置 API Key"):
        get_text_stream_client(config)


def test_factory_builds_client_from_config():
    config = {
        'active_provider': 'p1',
        'providers': {
            'p1': {
                'type': 'openai_compatible',
                'api_key': 'sk-abc',
                'base_url': 'https://proxy.example.com/v1',
                'endpoint_type': 'v1/custom/completions',
            }
        }
    }
    client = get_text_stream_client(config)
    assert isinstance(client, TextStreamClient)
    assert client.api_key == 'sk-abc'
    assert client.chat_endpoint == 'https://proxy.example.com/v1/custom/completions'
