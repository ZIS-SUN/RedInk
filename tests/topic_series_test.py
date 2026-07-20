"""
系列拆解（POST /api/topic/series + TopicService.expand_series）测试

不发起真实 LLM 调用：
- 服务层测试 mock 掉文本客户端，验证 prompt 编排要求、正常解析、
  标题格式归一化与解析容错
- 路由层测试 mock 掉整个 TopicService，验证参数校验与 count 边界
"""
import json

import pytest

from backend.routes import topic_routes
from backend.services import topic as topic_module
from backend.services.topic import (
    DEFAULT_SERIES_COUNT,
    SERIES_MAX_COUNT,
    SERIES_MIN_COUNT,
    TopicService,
)


def make_series_response(series_name="新手化妆避坑", count=6):
    """构造一份合法的系列拆解 LLM 返回"""
    episodes = []
    for i in range(1, count + 1):
        episodes.append({
            "order": i,
            "title": f"{series_name}｜{i:02d} 第{i}集具体标题",
            "angle": f"第{i}集切入角度",
            "progression": f"第{i}集递进作用",
        })
    return json.dumps(
        {"series_name": series_name, "episodes": episodes}, ensure_ascii=False
    )


class FakeTextClient:
    """记录 prompt 并返回固定 JSON 的假文本客户端"""

    def __init__(self, response_text=None):
        self.prompts = []
        self.response_text = response_text or make_series_response()

    def generate_text(self, prompt, model, temperature, max_output_tokens, **kwargs):
        self.prompts.append(prompt)
        return self.response_text


@pytest.fixture
def fake_client(monkeypatch):
    """构造可用的 TopicService 所需的文本客户端与配置"""
    client = FakeTextClient()
    monkeypatch.setattr(
        topic_module.TopicService,
        "_load_text_config",
        lambda self: {
            "active_provider": "fake",
            "providers": {"fake": {"api_key": "test-key", "model": "fake-model"}},
        },
    )
    monkeypatch.setattr(topic_module.TopicService, "_get_client", lambda self: client)
    return client


# ==================== count 归一化 ====================

def test_clamp_series_count_within_range():
    assert TopicService.clamp_series_count(5) == 5
    assert TopicService.clamp_series_count(10) == 10
    assert TopicService.clamp_series_count(7) == 7


def test_clamp_series_count_out_of_range():
    assert TopicService.clamp_series_count(1) == SERIES_MIN_COUNT
    assert TopicService.clamp_series_count(99) == SERIES_MAX_COUNT
    assert TopicService.clamp_series_count(-3) == SERIES_MIN_COUNT


def test_clamp_series_count_invalid_type_falls_back_default():
    assert TopicService.clamp_series_count(None) == DEFAULT_SERIES_COUNT
    assert TopicService.clamp_series_count("abc") == DEFAULT_SERIES_COUNT
    # 数字字符串可以被 int() 接受
    assert TopicService.clamp_series_count("8") == 8


# ==================== 服务层：正常流程与 prompt 编排 ====================

def test_expand_series_success(fake_client):
    service = topic_module.TopicService()
    result = service.expand_series("新手化妆", count=6, niche="美妆", platform="小红书")

    assert result["success"] is True
    assert result["series_name"] == "新手化妆避坑"
    assert len(result["episodes"]) == 6
    first = result["episodes"][0]
    assert first["order"] == 1
    assert first["title"].startswith("新手化妆避坑｜01 ")
    assert first["angle"] == "第1集切入角度"
    assert first["progression"] == "第1集递进作用"


def test_series_prompt_contains_orchestration_rules(fake_client):
    """编排要求必须写进 prompt：首集立题引流/中段打痛点/末集收口/标题差异化"""
    service = topic_module.TopicService()
    service.expand_series("新手化妆", count=7, niche="美妆", platform="小红书")

    assert len(fake_client.prompts) == 1
    prompt = fake_client.prompts[0]
    assert "7 集" in prompt
    assert "立题引流" in prompt
    assert "逐层深入" in prompt and "痛点" in prompt
    assert "收口" in prompt
    assert "差异化" in prompt
    # 入参上下文均已注入
    assert "新手化妆" in prompt
    assert "美妆" in prompt
    assert "小红书" in prompt
    # 未指定系列名时要求 AI 起名
    assert "未指定系列名" in prompt


def test_series_prompt_uses_user_series_name(fake_client):
    """用户指定系列名时写入 prompt，且结果系列名以用户指定为准"""
    fake_client.response_text = make_series_response(series_name="AI乱起的名字")
    service = topic_module.TopicService()
    result = service.expand_series("新手化妆", series_name="我的化妆日记")

    prompt = fake_client.prompts[0]
    assert "我的化妆日记" in prompt
    assert "未指定系列名" not in prompt
    assert result["series_name"] == "我的化妆日记"


def test_expand_series_clamps_count_in_prompt(fake_client):
    """服务层越界集数钳制后再拼 prompt"""
    service = topic_module.TopicService()
    service.expand_series("新手化妆", count=99)
    assert f"{SERIES_MAX_COUNT} 集" in fake_client.prompts[0]

    service2 = topic_module.TopicService()
    service2.expand_series("新手化妆", count=1)
    assert f"{SERIES_MIN_COUNT} 集" in fake_client.prompts[1]


def test_expand_series_empty_theme_fails(fake_client):
    service = topic_module.TopicService()
    result = service.expand_series("   ")
    assert result["success"] is False
    assert "系列主题不能为空" in result["error"]


# ==================== 服务层：归一化与容错 ====================

def test_episode_title_reformatted_when_llm_breaks_format(fake_client):
    """AI 没按「系列名｜0X 标题」输出时，归一化补齐统一格式"""
    fake_client.response_text = json.dumps({
        "series_name": "避坑指南",
        "episodes": [
            # 裸标题（无前缀）
            {"order": 1, "title": "底妆怎么选", "angle": "a", "progression": "p"},
            # 自带「第N集」式编号
            {"order": 2, "title": "第2集：眉毛画法", "angle": "a", "progression": "p"},
            # 半角竖线 + 数字编号
            {"order": 3, "title": "避坑指南|03 口红色号", "angle": "a", "progression": "p"},
        ],
    }, ensure_ascii=False)

    service = topic_module.TopicService()
    result = service.expand_series("新手化妆")

    titles = [ep["title"] for ep in result["episodes"]]
    assert titles == [
        "避坑指南｜01 底妆怎么选",
        "避坑指南｜02 眉毛画法",
        "避坑指南｜03 口红色号",
    ]


def test_episode_order_fallback_and_renumbering(fake_client):
    """order 缺失/非法回退位置序号；乱序集按 order 排序后重排为连续编号"""
    fake_client.response_text = json.dumps({
        "series_name": "避坑指南",
        "episodes": [
            {"order": 5, "title": "最后一集", "angle": "", "progression": ""},
            {"order": "bad", "title": "编号非法的一集", "angle": "", "progression": ""},
            {"title": "没有编号的一集", "angle": "", "progression": ""},
        ],
    }, ensure_ascii=False)

    service = topic_module.TopicService()
    result = service.expand_series("新手化妆")

    episodes = result["episodes"]
    assert [ep["order"] for ep in episodes] == [1, 2, 3]
    # order=5 的排最后并重编号为 03，标题编号同步刷新
    assert episodes[-1]["title"] == "避坑指南｜03 最后一集"
    # 非法/缺失 order 的按位置回退（2、3），排序后为 01、02
    assert episodes[0]["title"] == "避坑指南｜01 编号非法的一集"
    assert episodes[1]["title"] == "避坑指南｜02 没有编号的一集"


def test_expand_series_parses_json_in_code_fence(fake_client):
    """解析容错：LLM 返回带 ```json 代码块与说明文字时仍能解析"""
    fake_client.response_text = (
        "好的，以下是拆解结果：\n```json\n"
        + make_series_response(series_name="避坑指南", count=5)
        + "\n```\n希望对你有帮助！"
    )
    service = topic_module.TopicService()
    result = service.expand_series("新手化妆", count=5)

    assert result["success"] is True
    assert result["series_name"] == "避坑指南"
    assert len(result["episodes"]) == 5


def test_expand_series_retries_on_invalid_json(fake_client, monkeypatch):
    """解析容错：首次输出无法解析时带纠正提示自动重试一次"""
    responses = ["这不是 JSON", make_series_response(count=5)]

    def fake_generate(prompt, model, temperature, max_output_tokens, **kwargs):
        fake_client.prompts.append(prompt)
        return responses.pop(0)

    monkeypatch.setattr(fake_client, "generate_text", fake_generate)

    service = topic_module.TopicService()
    result = service.expand_series("新手化妆", count=5)

    assert result["success"] is True
    assert len(fake_client.prompts) == 2
    # 重试的 prompt 带格式纠正提示
    assert "格式纠正" in fake_client.prompts[1]


def test_expand_series_all_invalid_episodes_fails(fake_client):
    """episodes 全部无效（缺 title / 非 dict）时返回失败而非空列表"""
    fake_client.response_text = json.dumps({
        "series_name": "避坑指南",
        "episodes": [{"order": 1, "title": "  "}, "不是字典", 123],
    }, ensure_ascii=False)

    service = topic_module.TopicService()
    result = service.expand_series("新手化妆")

    assert result["success"] is False
    assert "未返回有效的系列内容" in result["error"]


def test_expand_series_missing_series_name_falls_back_to_theme(fake_client):
    """AI 没返回 series_name 且用户未指定时回退大主题"""
    fake_client.response_text = json.dumps({
        "episodes": [
            {"order": 1, "title": "第一集", "angle": "a", "progression": "p"},
        ],
    }, ensure_ascii=False)

    service = topic_module.TopicService()
    result = service.expand_series("新手化妆")

    assert result["success"] is True
    assert result["series_name"] == "新手化妆"
    assert result["episodes"][0]["title"] == "新手化妆｜01 第一集"


# ==================== 路由层 ====================

class FakeTopicService:
    """记录调用参数并返回固定结果的假选题服务"""

    def __init__(self):
        self.calls = []

    def expand_series(self, theme, count=DEFAULT_SERIES_COUNT, niche='',
                      platform='', series_name=''):
        self.calls.append({
            "theme": theme,
            "count": count,
            "niche": niche,
            "platform": platform,
            "series_name": series_name,
        })
        return {
            "success": True,
            "series_name": "路由测试系列",
            "episodes": [
                {"order": 1, "title": "路由测试系列｜01 第一集",
                 "angle": "角度", "progression": "递进"},
            ],
        }


@pytest.fixture
def fake_route_service(monkeypatch):
    service = FakeTopicService()
    monkeypatch.setattr(topic_routes, "get_topic_service", lambda: service)
    return service


def test_series_route_success(client, fake_route_service):
    response = client.post("/api/topic/series", json={
        "theme": "新手化妆",
        "count": 8,
        "niche": "美妆",
        "platform": "小红书",
        "series_name": "避坑指南",
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["series_name"] == "路由测试系列"
    assert len(data["episodes"]) == 1

    call = fake_route_service.calls[0]
    assert call["theme"] == "新手化妆"
    assert call["count"] == 8
    assert call["niche"] == "美妆"
    assert call["platform"] == "小红书"
    assert call["series_name"] == "避坑指南"


def test_series_route_defaults(client, fake_route_service):
    """只传 theme 时其余参数走默认值"""
    response = client.post("/api/topic/series", json={"theme": "新手化妆"})

    assert response.status_code == 200
    call = fake_route_service.calls[0]
    assert call["count"] == DEFAULT_SERIES_COUNT
    assert call["niche"] == ""
    assert call["platform"] == ""
    assert call["series_name"] == ""


def test_series_route_missing_theme_returns_400(client, fake_route_service):
    response = client.post("/api/topic/series", json={"count": 6})

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "theme" in data["error"]["detail"]
    assert fake_route_service.calls == []


def test_series_route_blank_theme_returns_400(client, fake_route_service):
    response = client.post("/api/topic/series", json={"theme": "   "})

    assert response.status_code == 400
    assert fake_route_service.calls == []


def test_series_route_non_numeric_count_returns_400(client, fake_route_service):
    response = client.post("/api/topic/series", json={
        "theme": "新手化妆",
        "count": "很多集",
    })

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "count" in data["error"]["detail"]
    assert fake_route_service.calls == []


def test_series_route_count_boundary_passthrough(client, fake_route_service):
    """count 边界：5 / 10 原样透传；数字字符串可接受"""
    for value in (SERIES_MIN_COUNT, SERIES_MAX_COUNT, str(SERIES_MAX_COUNT)):
        response = client.post("/api/topic/series", json={
            "theme": "新手化妆",
            "count": value,
        })
        assert response.status_code == 200

    counts = [call["count"] for call in fake_route_service.calls]
    assert counts == [SERIES_MIN_COUNT, SERIES_MAX_COUNT, SERIES_MAX_COUNT]


def test_series_route_out_of_range_count_clamped_by_service(client, fake_route_service, monkeypatch):
    """count 越界：路由放行数字，由服务层钳制（与一周排期 frequency 行为一致）"""
    response = client.post("/api/topic/series", json={
        "theme": "新手化妆",
        "count": 99,
    })

    assert response.status_code == 200
    # 路由层原样透传数字（钳制职责在服务层，clamp 行为已在上方单测覆盖）
    assert fake_route_service.calls[0]["count"] == 99
    assert TopicService.clamp_series_count(99) == SERIES_MAX_COUNT


def test_series_route_service_failure_returns_error(client, monkeypatch):
    """服务层失败时走统一错误响应结构"""
    class FailingService:
        def expand_series(self, *args, **kwargs):
            return {"success": False, "error": "系列拆解失败。\n错误详情: boom"}

    monkeypatch.setattr(topic_routes, "get_topic_service", lambda: FailingService())

    response = client.post("/api/topic/series", json={"theme": "新手化妆"})

    assert response.status_code == 500
    data = response.get_json()
    assert data["success"] is False
    assert "error" in data and "error_message" in data
