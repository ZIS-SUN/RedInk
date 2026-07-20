"""
共享 LLM 工具层（backend/utils/llm_utils）单元测试

覆盖：
- parse_llm_json 的各种输入：裸 JSON、```json 代码块包裹、前后杂文、坏 JSON
- classify_llm_error 的错误分类映射（认证/模型/网络/配额/兜底）
- load_text_config 的默认配置两种形态与 YAML 错误
- get_text_client 的配置校验错误
- resolve_generation_params 的参数解析与默认值
"""

import pytest

from backend.utils.llm_utils import (
    classify_llm_error,
    get_text_client,
    load_text_config,
    parse_llm_json,
    resolve_generation_params,
)


# ==================== parse_llm_json ====================

class TestParseLlmJson:
    def test_bare_json(self):
        assert parse_llm_json('{"a": 1, "b": "文"}') == {"a": 1, "b": "文"}

    def test_json_code_fence(self):
        text = '```json\n{"titles": ["标题一"]}\n```'
        assert parse_llm_json(text) == {"titles": ["标题一"]}

    def test_plain_code_fence(self):
        text = '```\n{"ok": true}\n```'
        assert parse_llm_json(text) == {"ok": True}

    def test_json_with_surrounding_prose(self):
        text = '好的，以下是结果：\n{"result": "内容"}\n希望对你有帮助！'
        assert parse_llm_json(text) == {"result": "内容"}

    def test_code_fence_with_surrounding_prose(self):
        text = '这是生成结果：\n```json\n{"x": [1, 2]}\n```\n以上。'
        assert parse_llm_json(text) == {"x": [1, 2]}

    def test_nested_braces_extraction(self):
        text = '前置说明 {"outer": {"inner": 3}} 后置说明'
        assert parse_llm_json(text) == {"outer": {"inner": 3}}

    def test_bad_json_raises_value_error(self):
        with pytest.raises(ValueError, match="AI 返回的内容格式不正确，无法解析"):
            parse_llm_json("完全不是 JSON 的内容")

    def test_broken_json_in_fence_raises(self):
        with pytest.raises(ValueError, match="AI 返回的内容格式不正确，无法解析"):
            parse_llm_json('```json\n{"a": 1,,,}\n```')

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_llm_json("")


# ==================== classify_llm_error ====================

class TestClassifyLlmError:
    def test_auth_error_by_401(self):
        msg = classify_llm_error(Exception("HTTP 401 unauthorized"), task_label="X失败")
        assert msg.startswith("API 认证失败。")
        assert "错误详情: HTTP 401 unauthorized" in msg
        assert "在系统设置页面检查并更新 API Key" in msg

    def test_auth_error_by_api_key_keyword(self):
        msg = classify_llm_error("Invalid API_KEY provided", task_label="X失败")
        assert msg.startswith("API 认证失败。")

    def test_model_error_by_404(self):
        msg = classify_llm_error(Exception("404 not found"), task_label="X失败")
        assert msg.startswith("模型访问失败。")
        assert "在系统设置页面检查模型名称配置" in msg

    def test_network_error_by_timeout(self):
        msg = classify_llm_error(Exception("Request Timeout after 300s"), task_label="X失败")
        assert msg.startswith("网络连接失败。")
        assert "检查网络连接，稍后重试" in msg

    def test_network_error_by_chinese_keyword(self):
        msg = classify_llm_error(Exception("无法建立连接"), task_label="X失败")
        assert msg.startswith("网络连接失败。")

    def test_rate_limit_by_429(self):
        msg = classify_llm_error(Exception("HTTP 429 too many requests"), task_label="X失败")
        assert msg.startswith("API 配额限制。")
        assert "等待配额重置，或升级 API 套餐" in msg

    def test_rate_limit_by_quota_keyword(self):
        msg = classify_llm_error(Exception("Quota exceeded"), task_label="X失败")
        assert msg.startswith("API 配额限制。")

    def test_fallback_uses_task_label(self):
        msg = classify_llm_error(Exception("some unknown failure"), task_label="选题灵感生成失败")
        assert msg.startswith("选题灵感生成失败。\n")
        assert "错误详情: some unknown failure" in msg
        assert "建议：检查配置文件 text_providers.yaml" in msg

    def test_classification_priority_auth_over_rate(self):
        # 同时命中认证与限流关键词时，按原服务的分支顺序应归类为认证失败
        msg = classify_llm_error(Exception("401 rate limited"), task_label="X失败")
        assert msg.startswith("API 认证失败。")


# ==================== load_text_config ====================

class TestLoadTextConfig:
    @pytest.fixture
    def isolated_data_root(self, tmp_path, monkeypatch):
        import backend.utils.llm_utils as llm_utils
        monkeypatch.setattr(llm_utils, "get_data_root", lambda: tmp_path)
        return tmp_path

    def test_missing_file_default_with_providers(self, isolated_data_root):
        config = load_text_config()
        assert config["active_provider"] == "google_gemini"
        assert "google_gemini" in config["providers"]

    def test_missing_file_default_without_providers(self, isolated_data_root):
        config = load_text_config(default_providers=False)
        assert config["active_provider"] == "google_gemini"
        assert config["providers"] == {}

    def test_reads_existing_yaml(self, isolated_data_root):
        (isolated_data_root / "text_providers.yaml").write_text(
            "active_provider: openai\n"
            "providers:\n"
            "  openai:\n"
            "    type: openai_compatible\n"
            "    api_key: sk-test\n",
            encoding="utf-8",
        )
        config = load_text_config()
        assert config["active_provider"] == "openai"
        assert config["providers"]["openai"]["api_key"] == "sk-test"

    def test_invalid_yaml_raises_value_error(self, isolated_data_root):
        (isolated_data_root / "text_providers.yaml").write_text(
            "active_provider: [broken\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="文本配置文件格式错误"):
            load_text_config()


# ==================== get_text_client ====================

class TestGetTextClient:
    def test_no_providers_raises(self):
        with pytest.raises(ValueError, match="未找到任何文本生成服务商配置"):
            get_text_client({"active_provider": "openai", "providers": {}})

    def test_active_provider_missing_raises(self):
        config = {
            "active_provider": "nonexistent",
            "providers": {"openai": {"type": "openai_compatible", "api_key": "k"}},
        }
        with pytest.raises(ValueError, match="未找到文本生成服务商配置: nonexistent"):
            get_text_client(config)

    def test_missing_api_key_raises(self):
        config = {
            "active_provider": "openai",
            "providers": {"openai": {"type": "openai_compatible"}},
        }
        with pytest.raises(ValueError, match="未配置 API Key"):
            get_text_client(config)

    def test_valid_config_returns_client(self):
        config = {
            "active_provider": "openai",
            "providers": {
                "openai": {
                    "type": "openai_compatible",
                    "api_key": "sk-test",
                    "base_url": "https://example.com",
                }
            },
        }
        client = get_text_client(config)
        assert client is not None
        assert client.api_key == "sk-test"


# ==================== resolve_generation_params ====================

class TestResolveGenerationParams:
    def test_reads_configured_values(self):
        config = {
            "active_provider": "openai",
            "providers": {
                "openai": {
                    "model": "gpt-x",
                    "temperature": 0.5,
                    "max_output_tokens": 1234,
                }
            },
        }
        assert resolve_generation_params(config) == ("gpt-x", 0.5, 1234)

    def test_defaults_when_provider_missing(self):
        model, temperature, max_tokens = resolve_generation_params(
            {}, default_max_output_tokens=4000
        )
        assert model == "gemini-2.0-flash-exp"
        assert temperature == 1.0
        assert max_tokens == 4000

    def test_default_max_output_tokens_is_8000(self):
        _, _, max_tokens = resolve_generation_params(
            {"active_provider": "p", "providers": {"p": {}}}
        )
        assert max_tokens == 8000
