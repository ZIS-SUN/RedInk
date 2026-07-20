import pytest

from backend.errors import classify_error, error_payload
from backend.routes.image_routes import _normalize_sse_error
from backend.routes.utils import normalize_error_result


def test_classifies_fake_ip_tls_error():
    error = classify_error(
        "HTTPSConnectionPool(host='api.apiyi.com', port=443): "
        "Max retries exceeded with url: /v1/models "
        "(Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred')))",
        context={
            "provider": "APIYI",
            "base_url": "https://api.apiyi.com",
            "endpoint": "/v1/models",
        },
    )

    assert error.code == "NETWORK_FAKE_IP_TLS"
    assert error.retryable is True
    assert error.status == 400
    assert error.diagnostics["provider"] == "APIYI"
    assert error.diagnostics["endpoint"] == "/v1/models"


def test_classifies_proxy_unavailable():
    error = classify_error(
        "ProxyError('Unable to connect to proxy', "
        "NewConnectionError('<urllib3.connection.HTTPSConnection object>: "
        "Failed to establish a new connection: [Errno 61] Connection refused'))"
    )

    assert error.code == "PROXY_UNAVAILABLE"
    assert error.retryable is True
    assert error.status == 400


def test_classifies_model_endpoint_mismatch():
    error = classify_error(
        '{"error":{"message":"模型 nano-banana-pro 不支持 /v1/chat/completions 接口"}}'
    )

    assert error.code == "MODEL_ENDPOINT_MISMATCH"
    assert error.retryable is False
    assert error.status == 400


def test_classifies_405_html_as_endpoint_method_mismatch():
    error = classify_error(
        "HTTP 405: <html>\r\n<head><title>405 Not Allowed</title></head>\r\n"
        "<body><center><h1>405 Not Allowed</h1></center><hr>"
        "<center>nginx/1.27.5</center></body></html>",
        context={
            "base_url": "https://tokendance.space",
            "endpoint": "/v1/chat/completions",
            "model": "deepseek-v4-pro",
        },
    )

    assert error.code == "ENDPOINT_METHOD_MISMATCH"
    assert error.status == 400
    assert error.retryable is False
    assert "endpoint_type" in error.suggestion
    assert "<html>" not in error.diagnostics["raw"]


def test_classifies_common_http_statuses():
    assert classify_error("HTTP 401: invalid api key").code == "AUTH_OR_PERMISSION"
    assert classify_error("HTTP 403: forbidden").code == "AUTH_OR_PERMISSION"
    assert classify_error("HTTP 429: rate limit").code == "RATE_LIMITED"

    upstream = classify_error("HTTP 500: upstream exploded")
    assert upstream.code == "UPSTREAM_UNAVAILABLE"
    assert upstream.status == 502


# ==================== CONTENT_BLOCKED（内容安全拦截，不可重试） ====================

def test_classifies_google_safety_filter_message_as_content_blocked():
    """generators/google_genai.py parse_genai_error 的中文安全过滤文案应命中新分类"""
    error = classify_error(
        "🛡️ 内容被安全过滤器拦截\n\n"
        "【说明】\n您的提示词或生成内容触发了 Google 的安全过滤机制。"
    )

    assert error.code == "CONTENT_BLOCKED"
    assert error.retryable is False
    assert error.status == 400
    assert error.title == "内容被安全审核拦截"
    assert "文案" in error.suggestion


def test_classifies_openai_content_policy_as_content_blocked():
    error = classify_error(
        'HTTP 400: {"error":{"message":"Your request was rejected as a result '
        'of our safety system.","code":"content_policy_violation"}}'
    )

    assert error.code == "CONTENT_BLOCKED"
    assert error.retryable is False
    # detail 保留上游真实原因，前端补显时用户能看到
    assert "safety system" in error.detail


def test_content_blocked_with_400_status_not_stolen_by_invalid_request():
    """带 400 状态码的安全拦截不应被更宽泛的 INVALID_REQUEST 分支抢先"""
    error = classify_error(
        "HTTP 400 Bad Request: image generation blocked by safety filter"
    )

    assert error.code == "CONTENT_BLOCKED"
    assert error.retryable is False


def test_classifies_chinese_moderation_keywords_as_content_blocked():
    error = classify_error("生成失败：内容审核未通过，包含敏感内容")

    assert error.code == "CONTENT_BLOCKED"
    assert error.retryable is False


def test_blocked_api_key_still_classified_as_auth():
    """"blocked" 出现在认证语境时仍归类为认证错误，不误判成内容拦截"""
    error = classify_error("HTTP 403: your api key has been blocked")

    assert error.code == "AUTH_OR_PERMISSION"
    assert error.retryable is False


def test_connection_blocked_still_classified_as_network():
    """"blocked" 出现在网络语境时仍归类为网络错误"""
    error = classify_error("ConnectionError: connection blocked by firewall")

    assert error.code == "NETWORK_ERROR"
    assert error.retryable is True


def test_content_blocked_sse_error_event_is_structured():
    """SSE error 事件归一化后携带 CONTENT_BLOCKED 分类与不可重试标记"""
    data = _normalize_sse_error(
        "error",
        {"index": 1, "status": "error", "message": "🛡️ 内容被安全过滤器拦截"},
        {"endpoint": "/api/generate", "task_id": "task_1"},
    )

    assert data["error"]["code"] == "CONTENT_BLOCKED"
    assert data["error"]["retryable"] is False
    assert data["message"].startswith("内容被安全审核拦截")


# ==================== QUEUE_TIMEOUT（本机排队超时，区别于网络超时） ====================

def test_classifies_queue_timeout_distinct_from_network_timeout():
    from backend.services.image_rate_limiter import ImageQueueTimeoutError

    error = classify_error(ImageQueueTimeoutError(
        "图片生成排队超时：等待并发额度超过 600 秒（本机排队任务过多），"
        "请减少页数或稍后重试"
    ))

    assert error.code == "QUEUE_TIMEOUT"
    assert error.title == "图片生成排队超时"
    assert error.retryable is True
    assert error.status == 503
    # 建议指向减页数/关高并发，而不是误导用户查网络
    assert "高并发" in error.suggestion
    assert "网络" not in error.suggestion


def test_classifies_legacy_queue_timeout_message():
    """兼容旧版限流器消息（升级期间的历史日志/序列化错误）"""
    error = classify_error("等待图片生成并发额度超时（600 秒），请稍后重试")

    assert error.code == "QUEUE_TIMEOUT"


def test_generic_timeout_still_classified_as_network_timeout():
    """普通超时不受 QUEUE_TIMEOUT 新分支影响"""
    error = classify_error("Request timed out after 300 seconds")

    assert error.code == "NETWORK_TIMEOUT"
    assert error.retryable is True


def test_error_payload_keeps_compat_error_message():
    payload = error_payload(classify_error("HTTP 429: rate limit"))

    assert payload["success"] is False
    assert payload["error"]["code"] == "RATE_LIMITED"
    assert payload["error_message"].startswith("上游限流或配额不足")


def test_normalize_error_result_wraps_legacy_service_error():
    result = normalize_error_result(
        {"success": False, "error": "SSLEOFError: UNEXPECTED_EOF_WHILE_READING"},
        context={"endpoint": "/api/generate"},
    )

    assert result["error"]["code"] == "NETWORK_FAKE_IP_TLS"
    assert result["error"]["diagnostics"]["endpoint"] == "/api/generate"
    assert "error_message" in result


def test_config_test_missing_type_returns_structured_error(client):
    response = client.post("/api/config/test", json={})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert data["error_message"]


def test_config_test_without_json_content_type_returns_structured_error(client):
    response = client.post("/api/config/test")
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert data["error_message"]


def test_config_test_preserves_classified_http_status(client, monkeypatch):
    from backend.routes import config_routes

    def raise_rate_limit(provider_type, config):
        raise Exception('HTTP 429: {"error":{"message":"rate limit"}}')

    monkeypatch.setattr(config_routes, "_test_provider_connection", raise_rate_limit)

    response = client.post("/api/config/test", json={
        "type": "openai_compatible",
        "api_key": "test-key",
        "base_url": "https://api.example.com",
        "model": "text-model",
    })
    data = response.get_json()

    assert response.status_code == 429
    assert data["error"]["code"] == "RATE_LIMITED"
    assert data["error_message"].startswith("上游限流或配额不足")


def test_openai_compatible_test_uses_configured_endpoint_for_real_llm_request(monkeypatch):
    import requests
    from backend.routes import config_routes

    captured = {}

    class Response:
        status_code = 200
        text = '{"choices":[{"message":{"content":"红墨连接测试成功"}}]}'

        def json(self):
            return {"choices": [{"message": {"content": "红墨连接测试成功"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(requests, "post", fake_post)

    result = config_routes._test_openai_compatible({
        "api_key": "test-key",
        "base_url": "https://tokendance.space/v1",
        "endpoint_type": "/custom/chat/completions",
        "model": "deepseek-v4-pro",
    }, "ping")

    assert result["success"] is True
    assert captured["url"] == "https://tokendance.space/custom/chat/completions"
    assert captured["json"]["model"] == "deepseek-v4-pro"
    assert captured["json"]["messages"][0]["content"] == "ping"
    assert captured["json"]["stream"] is False
    assert captured["json"]["max_tokens"] == 256
    assert "temperature" not in captured["json"]


def test_openai_compatible_test_accepts_reasoning_only_response(monkeypatch):
    import requests
    from backend.routes import config_routes

    class Response:
        status_code = 200
        text = '{"choices":[{"message":{"content":"","reasoning_content":"我们需要判断用户要求。"},"finish_reason":"length"}]}'

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": "",
                        "reasoning_content": "我们需要判断用户要求。"
                    },
                    "finish_reason": "length"
                }]
            }

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: Response())

    result = config_routes._test_openai_compatible({
        "api_key": "test-key",
        "base_url": "https://api.apiyi.com",
        "endpoint_type": "/v1/chat/completions",
        "model": "deepseek-v4-pro",
    }, "ping")

    assert result["success"] is True
    assert result["warning"] is True
    assert result["status"] == "warning"
    assert "推理过程" in result["message"]
    assert "输出预算已耗尽" in result["message"]
    assert "我们需要判断用户要求" not in result["message"]


def test_openai_compatible_test_accepts_hidden_reasoning_token_response(monkeypatch):
    import requests
    from backend.routes import config_routes

    class Response:
        status_code = 200
        text = '{"choices":[{"message":{"content":""},"finish_reason":"length"}],"usage":{"completion_tokens_details":{"reasoning_tokens":256}}}'

        def json(self):
            return {
                "choices": [{
                    "message": {"content": ""},
                    "finish_reason": "length"
                }],
                "usage": {
                    "completion_tokens_details": {
                        "reasoning_tokens": 256
                    }
                }
            }

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: Response())

    result = config_routes._test_openai_compatible({
        "api_key": "test-key",
        "base_url": "https://api.example.com",
        "endpoint_type": "/v1/chat/completions",
        "model": "reasoning-model",
    }, "ping")

    assert result["success"] is True
    assert result["warning"] is True
    assert "推理过程" in result["message"]


def test_openai_compatible_test_retries_with_max_completion_tokens(monkeypatch):
    import requests
    from backend.routes import config_routes

    calls = []

    class BadResponse:
        status_code = 400
        text = '{"error":{"message":"max_tokens is not compatible with this model. Use max_completion_tokens instead."}}'

    class GoodResponse:
        status_code = 200
        text = '{"choices":[{"message":{"content":"红墨连接测试成功"}}]}'

        def json(self):
            return {"choices": [{"message": {"content": "红墨连接测试成功"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json)
        return BadResponse() if len(calls) == 1 else GoodResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    result = config_routes._test_openai_compatible({
        "api_key": "test-key",
        "base_url": "https://api.example.com",
        "endpoint_type": "/v1/chat/completions",
        "model": "o-series-model",
    }, "ping")

    assert result["success"] is True
    assert calls[0]["max_tokens"] == 256
    assert "max_completion_tokens" not in calls[0]
    assert calls[1]["max_completion_tokens"] == 256
    assert "max_tokens" not in calls[1]


def test_image_api_chat_test_does_not_treat_405_as_success(monkeypatch):
    import requests
    from backend.routes import config_routes

    class Response:
        status_code = 405
        text = "<html><body><h1>405 Not Allowed</h1></body></html>"

        def json(self):
            return {}

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: Response())

    with pytest.raises(Exception, match="HTTP 405"):
        config_routes._test_image_api({
            "api_key": "test-key",
            "base_url": "https://tokendance.space",
            "endpoint_type": "/v1/chat/completions",
            "model": "deepseek-v4-pro",
        })


def test_outline_missing_topic_returns_structured_error(client):
    response = client.post("/api/outline", json={"topic": ""})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert data["error_message"]


def test_sse_error_event_is_structured():
    data = _normalize_sse_error(
        "error",
        {"index": 2, "status": "error", "message": "HTTP 429: rate limit"},
        {"endpoint": "/api/generate", "task_id": "task_1"},
    )

    assert data["error"]["code"] == "RATE_LIMITED"
    assert data["message"].startswith("上游限流或配额不足")
    assert data["retryable"] is True
