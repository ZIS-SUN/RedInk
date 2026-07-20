"""
选题灵感「蹭热点」（hot_topics）参数测试

不发起真实 LLM 调用：
- 服务层测试 mock 掉文本客户端，验证热点注入 prompt、归一化与增量字段透传
- 路由层测试 mock 掉整个 TopicService，验证 hot_topics 透传
"""
import json

import pytest

from backend.routes import topic_routes
from backend.services import topic as topic_module
from backend.services.topic import MAX_HOT_TOPICS, MAX_HOT_TOPIC_LEN, TopicService


VALID_LLM_RESPONSE = json.dumps({
    "topics": [
        {
            "title": "测试选题标题",
            "angle": "测试蹭点角度",
            "format": "图文",
            "heat": 88,
            "tags": ["标签1"],
            "hot_topic": "某热点词",
            "publish_window": "48 小时内",
            "relevance": "高：与赛道强相关",
        }
    ]
}, ensure_ascii=False)


class FakeTextClient:
    """记录 prompt 并返回固定 JSON 的假文本客户端"""

    def __init__(self, response_text=VALID_LLM_RESPONSE):
        self.prompts = []
        self.response_text = response_text

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


# ==================== 热点列表归一化 ====================

def test_normalize_hot_topics_strips_and_drops_empty():
    result = TopicService.normalize_hot_topics(["  词A  ", "", "   ", None, "词B"])
    assert result == ["词A", "词B"]


def test_normalize_hot_topics_non_list_returns_empty():
    assert TopicService.normalize_hot_topics(None) == []
    assert TopicService.normalize_hot_topics("词A\n词B") == []
    assert TopicService.normalize_hot_topics({"a": 1}) == []


def test_normalize_hot_topics_caps_count_and_length():
    many = [f"热点{i}" for i in range(MAX_HOT_TOPICS + 10)]
    assert len(TopicService.normalize_hot_topics(many)) == MAX_HOT_TOPICS

    long_word = "长" * (MAX_HOT_TOPIC_LEN + 50)
    result = TopicService.normalize_hot_topics([long_word])
    assert len(result[0]) == MAX_HOT_TOPIC_LEN


# ==================== 服务层：prompt 注入 ====================

def test_hot_topics_injected_into_prompt(fake_client):
    service = topic_module.TopicService()
    result = service.generate_topics(
        "健身减脂", "小红书", hot_topics=["秋天的第一杯奶茶", "全民健身周"]
    )

    assert result["success"] is True
    assert len(fake_client.prompts) == 1
    prompt = fake_client.prompts[0]
    # 热点词与蹭点要求均已注入
    assert "蹭热点模式" in prompt
    assert "1. 秋天的第一杯奶茶" in prompt
    assert "2. 全民健身周" in prompt
    assert "publish_window" in prompt
    assert "relevance" in prompt
    # 常规参数不受影响
    assert "健身减脂" in prompt


def test_without_hot_topics_prompt_unchanged(fake_client):
    """常规模式：prompt 不含任何蹭热点指令，行为与改动前一致"""
    service = topic_module.TopicService()
    result = service.generate_topics("健身减脂", "小红书")

    assert result["success"] is True
    prompt = fake_client.prompts[0]
    assert "蹭热点模式" not in prompt
    assert "publish_window" not in prompt


def test_empty_or_invalid_hot_topics_fall_back_to_normal(fake_client):
    """空列表 / 全空白 / 非列表：等同常规模式，不注入"""
    service = topic_module.TopicService()
    for value in ([], ["", "  "], "不是列表"):
        service.generate_topics("健身减脂", "小红书", hot_topics=value)

    for prompt in fake_client.prompts:
        assert "蹭热点模式" not in prompt


# ==================== 服务层：增量字段透传 ====================

def test_hotspot_extra_fields_passed_through(fake_client):
    service = topic_module.TopicService()
    result = service.generate_topics("健身减脂", "小红书", hot_topics=["某热点词"])

    topic = result["topics"][0]
    assert topic["hot_topic"] == "某热点词"
    assert topic["publish_window"] == "48 小时内"
    assert topic["relevance"] == "高：与赛道强相关"


def test_extra_fields_absent_when_llm_omits_them(fake_client):
    """AI 未返回增量字段时，结果结构与现有选题完全一致（无多余键）"""
    fake_client.response_text = json.dumps({
        "topics": [
            {"title": "常规选题", "angle": "角度", "format": "图文",
             "heat": 70, "tags": ["标签"]}
        ]
    }, ensure_ascii=False)

    service = topic_module.TopicService()
    result = service.generate_topics("健身减脂", "小红书")

    topic = result["topics"][0]
    assert "hot_topic" not in topic
    assert "publish_window" not in topic
    assert "relevance" not in topic


# ==================== 路由层 ====================

class FakeTopicService:
    """记录调用参数并返回固定结果的假选题服务"""

    def __init__(self):
        self.calls = []

    def generate_topics(self, niche, platform, use_account_data=False,
                        brand=None, hot_topics=None):
        self.calls.append({
            "niche": niche,
            "platform": platform,
            "use_account_data": use_account_data,
            "brand": brand,
            "hot_topics": hot_topics,
        })
        return {
            "success": True,
            "topics": [
                {"title": "路由测试选题", "angle": "角度", "format": "图文",
                 "heat": 80, "tags": ["标签"]}
            ],
            "account_context_used": False,
        }


@pytest.fixture
def fake_route_service(monkeypatch):
    service = FakeTopicService()
    monkeypatch.setattr(topic_routes, "get_topic_service", lambda: service)
    # 路由层测试不依赖真实品牌数据：品牌解析固定返回 None
    monkeypatch.setattr(topic_routes, "resolve_brand_for_prompt", lambda brand_id=None: None)
    return service


def test_route_passes_hot_topics(client, fake_route_service):
    response = client.post("/api/topic", json={
        "niche": "健身减脂",
        "platform": "小红书",
        "hot_topics": ["热点A", "热点B"],
    })

    assert response.status_code == 200
    assert fake_route_service.calls[0]["hot_topics"] == ["热点A", "热点B"]


def test_route_defaults_hot_topics_none(client, fake_route_service):
    response = client.post("/api/topic", json={
        "niche": "健身减脂",
        "platform": "小红书",
    })

    assert response.status_code == 200
    assert fake_route_service.calls[0]["hot_topics"] is None


def test_route_invalid_hot_topics_type_does_not_error(client, fake_route_service):
    """非法类型（如字符串）原样传给服务层，由 normalize 归一化为空列表，不报错"""
    response = client.post("/api/topic", json={
        "niche": "健身减脂",
        "hot_topics": "不是数组",
    })

    assert response.status_code == 200
    assert fake_route_service.calls[0]["hot_topics"] == "不是数组"
