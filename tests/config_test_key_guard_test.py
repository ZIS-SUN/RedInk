"""/api/config/test API Key 回填防护测试（修复 2：base_url 变化时拒绝回填已存 Key）"""
import yaml


SAVED_BASE_URL = "https://api.example.com"
SAVED_API_KEY = "sk-secret-123"


def _install_text_config(tmp_path, monkeypatch):
    """写入一份含真实 Key 的文本服务商配置，并指向 config_routes 的配置路径"""
    from backend.routes import config_routes

    config_path = tmp_path / "text_providers.yaml"
    config_path.write_text(yaml.dump({
        "active_provider": "myprov",
        "providers": {
            "myprov": {
                "type": "openai_compatible",
                "api_key": SAVED_API_KEY,
                "base_url": SAVED_BASE_URL,
                "model": "m1",
            },
        },
    }, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(config_routes, "TEXT_CONFIG_PATH", config_path)


def _capture_test_connection(monkeypatch):
    """替换真实连接测试，记录传入的配置"""
    from backend.routes import config_routes

    captured = {}

    def fake_test(provider_type, config):
        captured["provider_type"] = provider_type
        captured["config"] = dict(config)
        return {"success": True, "message": "ok"}

    monkeypatch.setattr(config_routes, "_test_provider_connection", fake_test)
    return captured


def test_changed_base_url_without_api_key_is_rejected(client, tmp_path, monkeypatch):
    _install_text_config(tmp_path, monkeypatch)
    captured = _capture_test_connection(monkeypatch)

    response = client.post("/api/config/test", json={
        "type": "openai_compatible",
        "provider_name": "myprov",
        "base_url": "https://attacker.example.net",
        "model": "m1",
    })
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert "重新输入" in data["error_message"]
    # 已存密钥不得被转发到新地址（连接测试根本不应发生）
    assert captured == {}


def test_same_base_url_still_backfills_saved_key(client, tmp_path, monkeypatch):
    _install_text_config(tmp_path, monkeypatch)
    captured = _capture_test_connection(monkeypatch)

    response = client.post("/api/config/test", json={
        "type": "openai_compatible",
        "provider_name": "myprov",
        "base_url": SAVED_BASE_URL,
        "model": "m1",
    })

    assert response.status_code == 200
    assert captured["config"]["api_key"] == SAVED_API_KEY
    assert captured["config"]["base_url"] == SAVED_BASE_URL


def test_omitted_base_url_backfills_saved_key_and_url(client, tmp_path, monkeypatch):
    _install_text_config(tmp_path, monkeypatch)
    captured = _capture_test_connection(monkeypatch)

    response = client.post("/api/config/test", json={
        "type": "openai_compatible",
        "provider_name": "myprov",
    })

    assert response.status_code == 200
    assert captured["config"]["api_key"] == SAVED_API_KEY
    assert captured["config"]["base_url"] == SAVED_BASE_URL


def test_explicit_api_key_with_new_base_url_is_allowed(client, tmp_path, monkeypatch):
    _install_text_config(tmp_path, monkeypatch)
    captured = _capture_test_connection(monkeypatch)

    response = client.post("/api/config/test", json={
        "type": "openai_compatible",
        "provider_name": "myprov",
        "api_key": "sk-new-key",
        "base_url": "https://new.example.org",
        "model": "m1",
    })

    assert response.status_code == 200
    assert captured["config"]["api_key"] == "sk-new-key"
    assert captured["config"]["base_url"] == "https://new.example.org"
