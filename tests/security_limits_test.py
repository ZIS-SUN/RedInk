"""限流超时、请求体/图片大小限制与错误分类收窄测试（修复 4、6、9、11）"""
import base64

import pytest

from backend.errors import AppErrorException, classify_error, ensure_app_error
from backend.routes.image_routes import _parse_base64_images
from backend.services.image_rate_limiter import ImageRateLimiter


# ==================== 修复 4：限流器超时获取 ====================

def test_rate_limiter_acquire_times_out_instead_of_blocking_forever():
    limiter = ImageRateLimiter(max_concurrent=1, interval_seconds=0)

    with limiter.acquire():
        # 额度被占满时，第二次获取应在超时后抛错，而不是无限期阻塞
        with pytest.raises(TimeoutError) as exc_info:
            with limiter.acquire(timeout=0.05):
                pass

    # 排队超时归类为"可重试"的 QUEUE_TIMEOUT（本机排队饱和，
    # 而不是误导用户查网络的 NETWORK_TIMEOUT）
    app_error = ensure_app_error(exc_info.value)
    assert app_error.code == "QUEUE_TIMEOUT"
    assert app_error.retryable is True


def test_rate_limiter_normal_acquire_release_cycle():
    limiter = ImageRateLimiter(
        max_concurrent=1, interval_seconds=0, acquire_timeout_seconds=1
    )

    with limiter.acquire():
        pass
    # 释放后可以再次获取
    with limiter.acquire():
        pass


# ==================== 修复 9：请求体与图片限制 ====================

def test_app_sets_max_content_length(app):
    assert app.config["MAX_CONTENT_LENGTH"] == 50 * 1024 * 1024


def test_parse_base64_images_rejects_too_many_images():
    one_pixel = base64.b64encode(b"x").decode()

    with pytest.raises(AppErrorException) as exc_info:
        _parse_base64_images([one_pixel] * 6)

    assert ensure_app_error(exc_info.value).status == 400


def test_parse_base64_images_rejects_invalid_base64():
    with pytest.raises(AppErrorException) as exc_info:
        _parse_base64_images(["this is !!! not base64"])

    app_error = ensure_app_error(exc_info.value)
    assert app_error.status == 400
    assert app_error.code == "INVALID_REQUEST"


def test_parse_base64_images_rejects_oversized_image(monkeypatch):
    from backend.routes import image_routes

    # 缩小上限便于测试（避免构造 20MB 数据）
    monkeypatch.setattr(image_routes, "_MAX_USER_IMAGE_BYTES", 8)
    big = base64.b64encode(b"x" * 9).decode()

    with pytest.raises(AppErrorException) as exc_info:
        _parse_base64_images([big])

    assert ensure_app_error(exc_info.value).status == 400


def test_parse_base64_images_accepts_data_url_and_plain_base64():
    payload = base64.b64encode(b"hello").decode()

    images = _parse_base64_images([
        f"data:image/png;base64,{payload}",
        payload,
    ])

    assert images == [b"hello", b"hello"]


def test_generate_route_returns_400_on_invalid_user_images(client):
    response = client.post("/api/generate", json={
        "pages": [{"index": 0, "type": "cover", "content": "c"}],
        "task_id": "task_abc12345",
        "user_images": ["this is !!! not base64"],
    })
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


# ==================== 修复 11：404 分类收窄 ====================

def test_resource_not_found_phrases_still_classified_as_404():
    for message in [
        "历史记录不存在：rec-1",
        "任务不存在：task_1",
        "任务目录不存在: task_1",
        "表现记录不存在：rec-2",
        "品牌档案不存在：brand-1",
    ]:
        error = classify_error(message)
        assert error.code == "RESOURCE_NOT_FOUND", message
        assert error.status == 404, message


def test_config_style_messages_are_not_classified_as_404():
    for message in [
        "text_providers.yaml 不存在，使用默认配置",
        "图片配置文件不存在: /data/image_providers.yaml",
    ]:
        error = classify_error(message)
        assert error.code != "RESOURCE_NOT_FOUND", message
        assert error.status != 404, message


# ==================== 修复 6：Host 头校验（防 DNS rebinding） ====================

def test_host_guard_allows_localhost(client):
    response = client.get("/api/health")
    assert response.status_code == 200


def test_host_guard_blocks_unknown_host(client):
    response = client.get(
        "/api/health", headers={"Host": "evil.example.com:12398"}
    )
    data = response.get_json()

    assert response.status_code == 403
    assert data["success"] is False
    assert data["error"]["code"] == "FORBIDDEN_HOST"


def test_host_guard_respects_allowed_hosts_env(monkeypatch):
    monkeypatch.setenv("REDINK_ALLOWED_HOSTS", "myredink.local")
    from backend.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    assert client.get(
        "/api/health", headers={"Host": "myredink.local:12398"}
    ).status_code == 200
    assert client.get(
        "/api/health", headers={"Host": "evil.example.com"}
    ).status_code == 403
