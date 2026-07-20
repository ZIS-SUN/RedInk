"""
口播视频脚本生成（ScriptService + POST /api/script）测试

蓝图未在 create_app 中注册，路由层测试自建 Flask app 并注册蓝图。
不发起真实 LLM 调用：
- 服务层：用假 client 返回预设文本，覆盖归一化 / 分镜过滤 / JSON 容错 / 品牌注入
- 路由层：mock get_script_service，覆盖参数校验与成功/失败返回
"""
import json

import pytest
from flask import Flask

from backend.routes import script_routes
from backend.routes.script_routes import create_script_blueprint
from backend.services.script import ScriptService, normalize_segments


VALID_SCRIPT = {
    "title": "打工人 3 分钟搞定秋季穿搭",
    "hook": "还在为每天穿什么发愁？这条视频帮你彻底解决",
    "bgm_mood": "轻快好奇 → 干货递进 → 温暖收尾",
    "segments": [
        {
            "time_range": "0-3s",
            "visual": "真人出镜，正面近景，字卡「每天纠结穿什么？」",
            "voiceover": "还在为每天穿什么发愁？这条视频帮你彻底解决",
            "subtitle_notes": "还在为每天穿什么发愁 / 这条视频帮你彻底解决",
        },
        {
            "time_range": "3-15s",
            "visual": "切穿搭图片素材，逐条弹出要点字卡",
            "voiceover": "第一步，先定基础色，全身不超过三个颜色",
            "subtitle_notes": "第一步 / 先定基础色 / 全身不超过三个颜色",
        },
        {
            "time_range": "15-30s",
            "visual": "出镜总结，比出三根手指",
            "voiceover": "记住这三招，明天出门就能用上",
            "subtitle_notes": "记住这三招 / 明天出门就能用上",
        },
    ],
    "cta": "觉得有用的话点个关注，下期教你配鞋子",
}


class FakeTextClient:
    """返回固定文本的假 LLM 客户端"""

    def __init__(self, response_text):
        self.response_text = response_text
        self.calls = []

    def generate_text(self, prompt, model, temperature, max_output_tokens, **kwargs):
        self.calls.append({"prompt": prompt, "model": model})
        return self.response_text


def make_service(response_text):
    """绕过 __init__（避免读配置/建真实客户端），手工装配依赖"""
    service = ScriptService.__new__(ScriptService)
    service.text_config = {
        "active_provider": "fake",
        "providers": {"fake": {"model": "fake-model", "temperature": 0.5, "max_output_tokens": 4000}},
    }
    service.client = FakeTextClient(response_text)
    service.prompt_template = (
        "content: {content}\nduration: {duration_label}\nscene: {scene_label}"
    )
    return service


# ==================== 服务层：成功归一化 ====================

def test_generate_script_success_normalization():
    service = make_service(json.dumps(VALID_SCRIPT, ensure_ascii=False))

    result = service.generate_script("秋季穿搭图文正文", duration="30s", scene="voiceover")

    assert result["success"] is True
    script = result["script"]
    assert script["title"] == "打工人 3 分钟搞定秋季穿搭"
    assert script["hook"].startswith("还在为每天穿什么发愁")
    assert script["bgm_mood"] == "轻快好奇 → 干货递进 → 温暖收尾"
    assert script["duration"] == "30s"
    assert script["scene"] == "voiceover"
    assert len(script["segments"]) == 3
    assert script["segments"][0]["time_range"] == "0-3s"
    assert script["segments"][1]["subtitle_notes"] == "第一步 / 先定基础色 / 全身不超过三个颜色"
    assert script["cta"].startswith("觉得有用的话点个关注")

    # 输入与档位中文名拼进了 prompt
    prompt = service.client.calls[0]["prompt"]
    assert "秋季穿搭图文正文" in prompt
    assert "30 秒" in prompt
    assert "图文配音" in prompt


def test_generate_script_defaults_to_60s_talking_head():
    service = make_service(json.dumps(VALID_SCRIPT, ensure_ascii=False))

    result = service.generate_script("主题")

    assert result["success"] is True
    assert result["script"]["duration"] == "60s"
    assert result["script"]["scene"] == "talking_head"
    prompt = service.client.calls[0]["prompt"]
    assert "60 秒" in prompt
    assert "口播出镜" in prompt


def test_generate_script_missing_optional_fields_get_defaults():
    # 缺 title / hook / bgm_mood / cta 时补空字符串，segments 有效即成功
    data = {"segments": VALID_SCRIPT["segments"]}
    service = make_service(json.dumps(data, ensure_ascii=False))

    result = service.generate_script("主题")

    assert result["success"] is True
    script = result["script"]
    assert script["title"] == ""
    assert script["hook"] == ""
    assert script["bgm_mood"] == ""
    assert script["cta"] == ""
    assert len(script["segments"]) == 3


def test_generate_script_injects_brand_constraint():
    service = make_service(json.dumps(VALID_SCRIPT, ensure_ascii=False))
    brand = {
        "name": "测试品牌",
        "tone": "毒舌但真诚",
        "catchphrases": ["家人们"],
        "banned_words": ["绝绝子"],
    }

    result = service.generate_script("主题", brand=brand)

    assert result["success"] is True
    prompt = service.client.calls[0]["prompt"]
    assert "品牌人设约束" in prompt
    assert "毒舌但真诚" in prompt
    assert "绝绝子" in prompt


def test_generate_script_without_brand_has_no_constraint():
    service = make_service(json.dumps(VALID_SCRIPT, ensure_ascii=False))

    result = service.generate_script("主题", brand=None)

    assert result["success"] is True
    assert "品牌人设约束" not in service.client.calls[0]["prompt"]


# ==================== 服务层：segments 归一化与过滤 ====================

def test_normalize_segments_filters_invalid_items():
    segments = normalize_segments([
        "不是字典",
        {"time_range": "0-3s", "visual": "画面", "voiceover": "", "subtitle_notes": ""},
        {"time_range": "3-6s", "visual": "画面", "voiceover": "  有效台词  ", "subtitle_notes": None},
        {"voiceover": "只有台词"},
    ])

    assert len(segments) == 2
    assert segments[0]["voiceover"] == "有效台词"
    assert segments[0]["subtitle_notes"] == ""
    assert segments[1] == {
        "time_range": "", "visual": "", "voiceover": "只有台词", "subtitle_notes": "",
    }


def test_normalize_segments_non_list_returns_empty():
    assert normalize_segments(None) == []
    assert normalize_segments("不是列表") == []
    assert normalize_segments({"time_range": "0-3s"}) == []


def test_generate_script_empty_segments_returns_error():
    data = dict(VALID_SCRIPT)
    data["segments"] = []
    service = make_service(json.dumps(data, ensure_ascii=False))

    result = service.generate_script("主题")

    assert result["success"] is False
    assert "错误详情" in result["error"]


# ==================== 服务层：JSON 容错 ====================

def test_generate_script_parses_json_wrapped_in_code_fence():
    wrapped = "好的，脚本如下：\n```json\n" + json.dumps(VALID_SCRIPT, ensure_ascii=False) + "\n```\n祝拍摄顺利！"
    service = make_service(wrapped)

    result = service.generate_script("主题")

    assert result["success"] is True
    assert len(result["script"]["segments"]) == 3


def test_generate_script_parses_json_with_surrounding_text():
    noisy = "前置说明 " + json.dumps(VALID_SCRIPT, ensure_ascii=False) + " 后置说明"
    service = make_service(noisy)

    result = service.generate_script("主题")

    assert result["success"] is True
    assert result["script"]["title"] == "打工人 3 分钟搞定秋季穿搭"


def test_generate_script_unparseable_response_returns_error():
    service = make_service("这完全不是 JSON")

    result = service.generate_script("主题")

    assert result["success"] is False
    assert "错误详情" in result["error"]


# ==================== 路由层 ====================

class FakeScriptService:
    """记录调用参数并返回固定结果的假脚本服务"""

    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "success": True,
            "script": {
                "title": "片名",
                "hook": "钩子",
                "bgm_mood": "轻快",
                "duration": "60s",
                "scene": "talking_head",
                "segments": [
                    {"time_range": "0-3s", "visual": "画面", "voiceover": "台词", "subtitle_notes": "断句"},
                ],
                "cta": "关注我",
            },
        }

    def generate_script(self, content, duration, scene, brand=None):
        self.calls.append({
            "content": content, "duration": duration, "scene": scene, "brand": brand,
        })
        return self.result


@pytest.fixture
def script_client():
    """蓝图未接入 create_app：自建 Flask app 并以 /api 前缀注册蓝图"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_script_blueprint(), url_prefix="/api")
    return app.test_client()


@pytest.fixture
def fake_script(monkeypatch):
    service = FakeScriptService()
    monkeypatch.setattr(script_routes, "get_script_service", lambda: service)
    # 路由层测试不依赖真实品牌数据：品牌解析固定返回 None
    monkeypatch.setattr(script_routes, "resolve_brand", lambda brand_id=None: None)
    return service


def test_route_empty_content_returns_400(script_client, fake_script):
    response = script_client.post("/api/script", json={"content": "  "})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    # 参数不合法时不应触发 LLM 调用
    assert fake_script.calls == []


def test_route_invalid_duration_returns_400(script_client, fake_script):
    response = script_client.post("/api/script", json={"content": "主题", "duration": "5min"})

    assert response.status_code == 400
    assert response.get_json()["success"] is False
    assert fake_script.calls == []


def test_route_invalid_scene_returns_400(script_client, fake_script):
    response = script_client.post("/api/script", json={"content": "主题", "scene": "vlog"})

    assert response.status_code == 400
    assert response.get_json()["success"] is False
    assert fake_script.calls == []


def test_route_success_passes_params_through(script_client, fake_script):
    response = script_client.post("/api/script", json={
        "content": "秋季穿搭正文",
        "duration": "3min",
        "scene": "drama",
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["script"]["title"] == "片名"
    assert len(data["script"]["segments"]) == 1

    call = fake_script.calls[0]
    assert call["content"] == "秋季穿搭正文"
    assert call["duration"] == "3min"
    assert call["scene"] == "drama"
    assert call["brand"] is None


def test_route_optional_fields_use_defaults(script_client, fake_script):
    response = script_client.post("/api/script", json={"content": "主题"})

    assert response.status_code == 200
    call = fake_script.calls[0]
    assert call["duration"] == "60s"
    assert call["scene"] == "talking_head"


def test_route_passes_resolved_brand_to_service(script_client, monkeypatch):
    service = FakeScriptService()
    brand = {"id": "b1", "name": "测试品牌"}
    monkeypatch.setattr(script_routes, "get_script_service", lambda: service)
    monkeypatch.setattr(script_routes, "resolve_brand", lambda brand_id=None: brand)

    response = script_client.post("/api/script", json={"content": "主题", "brand_id": "b1"})

    assert response.status_code == 200
    assert service.calls[0]["brand"] == brand


def test_route_service_failure_returns_500(script_client, monkeypatch):
    service = FakeScriptService(result={"success": False, "error": "LLM 挂了"})
    monkeypatch.setattr(script_routes, "get_script_service", lambda: service)
    monkeypatch.setattr(script_routes, "resolve_brand", lambda brand_id=None: None)

    response = script_client.post("/api/script", json={"content": "主题"})
    data = response.get_json()

    assert response.status_code == 500
    assert data["success"] is False
    assert data["error_message"]
