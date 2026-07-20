"""
JSON 输出链路加固测试

覆盖三层加固：
1. parse_llm_json 的保守修复层：尾逗号 / 单引号键值 / 字符串内裸换行与
   控制字符 / 截断括号补全，以及"修不了就报错、绝不改语义"的边界
2. json_mode：TextChatClient 注入 response_format 与 4xx 不支持时的降级重试；
   GenAIClient 注入 response_mime_type 与不支持时的降级重试
3. generate_and_parse_json：解析失败自动带纠正提示重试一次，
   两次失败才抛结构化错误；服务层（title）端到端走通该链路
"""
import json

import pytest

from backend.utils.llm_utils import (
    JSON_RETRY_PROMPT_SUFFIX,
    generate_and_parse_json,
    parse_llm_json,
)


# ==================== 第 1 层：JSON 修复 ====================

class TestJsonRepairTrailingComma:
    def test_trailing_comma_in_object(self):
        assert parse_llm_json('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}

    def test_trailing_comma_in_array(self):
        assert parse_llm_json('{"tags": ["a", "b",]}') == {"tags": ["a", "b"]}

    def test_trailing_comma_with_whitespace(self):
        assert parse_llm_json('{"a": [1, 2, ]\n,\n}') == {"a": [1, 2]}

    def test_trailing_comma_inside_code_fence(self):
        text = '```json\n{"x": 1,}\n```'
        assert parse_llm_json(text) == {"x": 1}


class TestJsonRepairSingleQuotes:
    def test_single_quoted_keys_and_values(self):
        assert parse_llm_json("{'title': '你好', 'score': 90}") == {
            "title": "你好", "score": 90,
        }

    def test_single_quoted_array_items(self):
        assert parse_llm_json("{'tags': ['穿搭', '秋季']}") == {
            "tags": ["穿搭", "秋季"],
        }

    def test_single_quoted_value_containing_double_quote(self):
        assert parse_llm_json("{'a': '他说\"好\"'}") == {"a": '他说"好"'}

    def test_single_quoted_value_with_escaped_single_quote(self):
        assert parse_llm_json(r"{'a': 'it\'s ok'}") == {"a": "it's ok"}

    def test_apostrophe_inside_double_quoted_string_untouched(self):
        # 双引号字符串内部的单引号不是定界符，不能被改写
        assert parse_llm_json('{"a": "it\'s ok", "b": 1,}') == {
            "a": "it's ok", "b": 1,
        }


class TestJsonRepairBareControlChars:
    def test_bare_newline_in_string(self):
        assert parse_llm_json('{"text": "第一行\n第二行"}') == {
            "text": "第一行\n第二行",
        }

    def test_bare_crlf_and_tab_in_string(self):
        assert parse_llm_json('{"text": "a\r\n\tb"}') == {"text": "a\r\n\tb"}

    def test_other_control_char_in_string(self):
        assert parse_llm_json('{"text": "a\x0bb"}') == {"text": "a\x0bb"}

    def test_existing_escapes_preserved(self):
        # 已合法转义的 \n 不能被二次转义
        assert parse_llm_json('{"text": "第一行\\n第二行\n尾行"}') == {
            "text": "第一行\n第二行\n尾行",
        }


class TestJsonRepairTruncated:
    def test_truncated_array(self):
        assert parse_llm_json('{"a": {"b": 1}, "c": [2, 3') == {
            "a": {"b": 1}, "c": [2, 3],
        }

    def test_truncated_string(self):
        assert parse_llm_json('{"a": "未完的字符串') == {"a": "未完的字符串"}

    def test_truncated_dangling_key(self):
        # 悬空的 "key": 被整体丢弃，保留已完整的键值对
        assert parse_llm_json('{"a": 1, "key":') == {"a": 1}

    def test_truncated_nested(self):
        assert parse_llm_json('{"pages": [{"index": 0, "content": "文案') == {
            "pages": [{"index": 0, "content": "文案"}],
        }


class TestJsonRepairConservative:
    def test_totally_invalid_still_raises(self):
        with pytest.raises(ValueError, match="AI 返回的内容格式不正确，无法解析"):
            parse_llm_json("完全不是 JSON 的内容")

    def test_multiple_commas_still_raises(self):
        # 多重逗号超出保守修复范围，宁可报错也不猜语义
        with pytest.raises(ValueError, match="AI 返回的内容格式不正确，无法解析"):
            parse_llm_json('```json\n{"a": 1,,,}\n```')

    def test_valid_json_passes_through_unchanged(self):
        data = {"a": [1, 2], "b": {"c": "文,案}"}}
        assert parse_llm_json(json.dumps(data, ensure_ascii=False)) == data

    def test_string_content_with_braces_and_commas_untouched(self):
        # 字符串内容里的 ,} 不能被当成尾逗号删掉
        assert parse_llm_json('{"a": "x,}",}') == {"a": "x,}"}


# ==================== 第 2 层：json_mode ====================

class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)

    def json(self):
        return self._payload


def _ok_response(content='{"ok": true}'):
    return _FakeResponse(200, {"choices": [{"message": {"content": content}}]})


class TestTextClientJsonMode:
    def _make_client(self):
        from backend.utils.text_client import TextChatClient
        return TextChatClient(api_key="sk-test", base_url="https://api.example.com")

    def test_json_mode_injects_response_format(self, monkeypatch):
        import backend.utils.text_client as text_client
        payloads = []

        def fake_post(url, json=None, headers=None, timeout=None):
            payloads.append(json)
            return _ok_response()

        monkeypatch.setattr(text_client.requests, "post", fake_post)
        client = self._make_client()
        result = client.generate_text(prompt="p", model="m", json_mode=True)

        assert result == '{"ok": true}'
        assert payloads[0]["response_format"] == {"type": "json_object"}

    def test_default_has_no_response_format(self, monkeypatch):
        import backend.utils.text_client as text_client
        payloads = []

        def fake_post(url, json=None, headers=None, timeout=None):
            payloads.append(json)
            return _ok_response()

        monkeypatch.setattr(text_client.requests, "post", fake_post)
        client = self._make_client()
        client.generate_text(prompt="p", model="m")

        assert "response_format" not in payloads[0]

    def test_unsupported_response_format_downgrades_once(self, monkeypatch):
        import backend.utils.text_client as text_client
        payloads = []

        def fake_post(url, json=None, headers=None, timeout=None):
            payloads.append(dict(json))
            if len(payloads) == 1:
                return _FakeResponse(
                    400,
                    text='{"error":{"message":"Unknown parameter: response_format"}}',
                )
            return _ok_response()

        monkeypatch.setattr(text_client.requests, "post", fake_post)
        client = self._make_client()
        result = client.generate_text(prompt="p", model="m", json_mode=True)

        assert result == '{"ok": true}'
        assert len(payloads) == 2
        assert "response_format" in payloads[0]
        assert "response_format" not in payloads[1]

    def test_unrelated_400_does_not_downgrade(self, monkeypatch):
        import backend.utils.text_client as text_client
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append(json)
            return _FakeResponse(400, text='{"error":{"message":"bad prompt"}}')

        monkeypatch.setattr(text_client.requests, "post", fake_post)
        client = self._make_client()

        with pytest.raises(Exception, match="API 请求失败"):
            client.generate_text(prompt="p", model="m", json_mode=True)
        assert len(calls) == 1


class TestGenAIClientJsonMode:
    def _make_client(self, stream_fn):
        """绕过 __init__ 手工装配（避免真实建连），注入假流式接口"""
        from backend.utils.genai_client import GenAIClient

        class _FakeModels:
            def __init__(self):
                self.configs = []

            def generate_content_stream(self, model=None, contents=None, config=None):
                self.configs.append(config)
                return stream_fn(config)

        class _FakeInner:
            def __init__(self):
                self.models = _FakeModels()

        client = GenAIClient.__new__(GenAIClient)
        client.default_safety_settings = []
        client.client = _FakeInner()
        return client

    @staticmethod
    def _chunk(text):
        class _Part:
            pass

        class _Content:
            parts = [_Part()]

        class _Candidate:
            content = _Content()

        class _Chunk:
            candidates = [_Candidate()]

        chunk = _Chunk()
        chunk.text = text
        return chunk

    def test_json_mode_sets_response_mime_type(self):
        def stream_fn(config):
            assert config.response_mime_type == "application/json"
            yield self._chunk('{"ok": 1}')

        client = self._make_client(stream_fn)
        assert client.generate_text(prompt="p", model="m", json_mode=True) == '{"ok": 1}'

    def test_default_has_no_response_mime_type(self):
        def stream_fn(config):
            assert config.response_mime_type is None
            yield self._chunk("text")

        client = self._make_client(stream_fn)
        assert client.generate_text(prompt="p", model="m") == "text"

    def test_unsupported_mime_type_downgrades_once(self):
        attempts = []

        def stream_fn(config):
            attempts.append(config.response_mime_type)
            if config.response_mime_type == "application/json":
                raise Exception("response_mime_type is not supported for this model")
            yield self._chunk('{"ok": 1}')

        client = self._make_client(stream_fn)
        result = client.generate_text(prompt="p", model="m", json_mode=True)

        assert result == '{"ok": 1}'
        assert attempts == ["application/json", None]


# ==================== 第 3 层：解析失败重试 ====================

class TestGenerateAndParseJson:
    def test_first_call_success_no_retry(self):
        calls = []

        def call_fn(suffix):
            calls.append(suffix)
            return '{"a": 1}'

        assert generate_and_parse_json(call_fn) == {"a": 1}
        assert calls == [""]

    def test_retry_with_correction_hint_then_success(self):
        calls = []

        def call_fn(suffix):
            calls.append(suffix)
            if len(calls) == 1:
                return "完全不是 JSON 的输出"
            return '{"a": 2}'

        assert generate_and_parse_json(call_fn) == {"a": 2}
        assert len(calls) == 2
        assert calls[0] == ""
        assert calls[1] == JSON_RETRY_PROMPT_SUFFIX
        assert "不是合法 JSON" in calls[1]

    def test_both_calls_fail_raises_structured_error(self):
        calls = []

        def call_fn(suffix):
            calls.append(suffix)
            return "还是不是 JSON"

        with pytest.raises(ValueError, match="AI 返回的内容格式不正确，无法解析"):
            generate_and_parse_json(call_fn)
        assert len(calls) == 2

    def test_repairable_output_does_not_trigger_retry(self):
        # 修复层能救回来的输出不应浪费一次重试
        calls = []

        def call_fn(suffix):
            calls.append(suffix)
            return '{"a": 1,}'

        assert generate_and_parse_json(call_fn) == {"a": 1}
        assert calls == [""]


# ==================== 服务层端到端（以 title 为例） ====================

class _RetryFakeClient:
    """第一次返回坏 JSON、第二次返回好 JSON 的假客户端"""

    def __init__(self, bad_text, good_text):
        self.responses = [bad_text, good_text]
        self.calls = []

    def generate_text(self, prompt, model, temperature, max_output_tokens, **kwargs):
        self.calls.append({"prompt": prompt, "kwargs": kwargs})
        return self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]


def _make_title_service(client):
    from backend.services.title import TitleService

    service = TitleService.__new__(TitleService)
    service.text_config = {
        "active_provider": "fake",
        "providers": {"fake": {"model": "fake-model"}},
    }
    service.client = client
    service.prompt_template = "topic: {topic} platform: {platform} style: {style} count: {count}"
    return service


VALID_TITLES = json.dumps(
    {"titles": [{"text": f"标题{i}", "score": 80, "elements": ["悬念"]} for i in range(10)]},
    ensure_ascii=False,
)


def test_title_service_passes_json_mode():
    client = _RetryFakeClient(VALID_TITLES, VALID_TITLES)
    service = _make_title_service(client)

    result = service.generate_titles("秋季穿搭", "小红书", "悬念型")

    assert result["success"] is True
    assert len(client.calls) == 1
    assert client.calls[0]["kwargs"].get("json_mode") is True


def test_title_service_retries_on_bad_json_then_succeeds():
    client = _RetryFakeClient("模型抽风输出了散文", VALID_TITLES)
    service = _make_title_service(client)

    result = service.generate_titles("秋季穿搭", "小红书", "悬念型")

    assert result["success"] is True
    assert len(result["titles"]) == 10
    assert len(client.calls) == 2
    # 重试时在原 prompt 末尾追加了纠正提示
    assert client.calls[1]["prompt"].endswith(JSON_RETRY_PROMPT_SUFFIX)
    assert client.calls[1]["prompt"].startswith(client.calls[0]["prompt"])


def test_title_service_two_bad_outputs_return_classified_error():
    client = _RetryFakeClient("第一次坏输出", "第二次也是坏输出")
    service = _make_title_service(client)

    result = service.generate_titles("秋季穿搭", "小红书", "悬念型")

    assert result["success"] is False
    assert len(client.calls) == 2
    # 错误分类行为保持不变（走兜底分支的详细文案）
    assert result["error"].startswith("爆款标题生成失败。")
    assert "AI 返回的内容格式不正确，无法解析" in result["error"]
