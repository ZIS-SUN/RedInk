"""
选题灵感「结合我的账号数据」（use_account_data）测试

不发起真实 LLM 调用，不读真实账号数据：
- 服务层测试 mock 掉文本客户端与 analytics 的 get_stats
- 路由层测试 mock 掉整个 TopicService，验证 use_account_data 透传与响应字段
"""
import json

import pytest

from backend.routes import topic_routes
from backend.services import topic as topic_module


VALID_LLM_RESPONSE = json.dumps({
    "topics": [
        {
            "title": "测试选题标题",
            "angle": "测试切入角度",
            "format": "图文",
            "heat": 88,
            "tags": ["标签1", "标签2"],
        }
    ]
}, ensure_ascii=False)


STATS_WITH_RECORDS = {
    "total_records": 5,
    "total_views": 10000,
    "avg_engagement_rate": 6.5,
    "platforms": [
        {"name": "小红书", "count": 3, "views": 8000, "engagement_rate": 7.2},
        {"name": "抖音", "count": 2, "views": 2000, "engagement_rate": 3.1},
    ],
    "content_types": [
        {"name": "干货教程", "count": 2, "views": 6000, "engagement_rate": 8.0},
        {"name": "好物种草", "count": 2, "views": 3000, "engagement_rate": 5.0},
        {"name": "日常分享", "count": 1, "views": 1000, "engagement_rate": 2.0},
    ],
    "trend": [
        {"month": "2026-05", "count": 2, "views": 3000, "engagements": 100},
        {"month": "2026-06", "count": 3, "views": 7000, "engagements": 300},
    ],
}


STATS_EMPTY = {
    "total_records": 0,
    "total_views": 0,
    "avg_engagement_rate": 0.0,
    "platforms": [],
    "content_types": [],
    "trend": [],
}


class FakeTextClient:
    """记录 prompt 并返回固定 JSON 的假文本客户端"""

    def __init__(self, response_text=VALID_LLM_RESPONSE):
        self.prompts = []
        self.response_text = response_text

    def generate_text(self, prompt, model, temperature, max_output_tokens, **kwargs):
        self.prompts.append(prompt)
        return self.response_text


class FakeAnalyticsService:
    """记录调用次数并返回固定统计数据的假 analytics 服务"""

    def __init__(self, stats):
        self.stats = stats
        self.calls = 0

    def get_stats(self):
        self.calls += 1
        if isinstance(self.stats, Exception):
            raise self.stats
        return self.stats


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


def _mock_stats(monkeypatch, stats):
    """把 analytics 的 get_analytics_service 替换成假服务（topic 是惰性导入）"""
    import backend.services.analytics as analytics_module

    fake = FakeAnalyticsService(stats)
    monkeypatch.setattr(analytics_module, "get_analytics_service", lambda: fake)
    return fake


# ==================== 服务层 ====================

def test_use_account_data_with_records_injects_context(fake_client, monkeypatch):
    """有账号数据时：画像注入 prompt，account_context_used=True"""
    fake_analytics = _mock_stats(monkeypatch, STATS_WITH_RECORDS)

    service = topic_module.TopicService()
    result = service.generate_topics("健身减脂", "小红书", use_account_data=True)

    assert result["success"] is True
    assert result["account_context_used"] is True
    assert fake_analytics.calls == 1

    assert len(fake_client.prompts) == 1
    prompt = fake_client.prompts[0]
    assert "账号画像" in prompt
    assert "共 5 篇" in prompt
    # 表现最好的平台按互动率排序：小红书 > 抖音
    assert "小红书" in prompt
    assert "干货教程" in prompt
    # 近期月趋势方向：300 > 100 → 上升
    assert "上升" in prompt


def test_use_account_data_without_records_silently_ignored(fake_client, monkeypatch):
    """无账号数据时：静默忽略，prompt 不含画像，account_context_used=False"""
    fake_analytics = _mock_stats(monkeypatch, STATS_EMPTY)

    service = topic_module.TopicService()
    result = service.generate_topics("健身减脂", "小红书", use_account_data=True)

    assert result["success"] is True
    assert result["account_context_used"] is False
    assert fake_analytics.calls == 1

    prompt = fake_client.prompts[0]
    assert "账号画像" not in prompt


def test_use_account_data_stats_error_silently_ignored(fake_client, monkeypatch):
    """get_stats 抛异常时：不中断主流程，account_context_used=False"""
    _mock_stats(monkeypatch, RuntimeError("数据文件损坏"))

    service = topic_module.TopicService()
    result = service.generate_topics("健身减脂", "小红书", use_account_data=True)

    assert result["success"] is True
    assert result["account_context_used"] is False
    assert "账号画像" not in fake_client.prompts[0]


def test_default_does_not_touch_account_data(fake_client, monkeypatch):
    """默认（不传 use_account_data）：不调用 get_stats"""
    fake_analytics = _mock_stats(monkeypatch, STATS_WITH_RECORDS)

    service = topic_module.TopicService()
    result = service.generate_topics("健身减脂", "小红书")

    assert result["success"] is True
    assert result["account_context_used"] is False
    assert fake_analytics.calls == 0
    assert "账号画像" not in fake_client.prompts[0]


# ==================== 路由层 ====================

class FakeTopicService:
    """记录调用参数并返回固定结果的假选题服务"""

    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "success": True,
            "topics": [
                {"title": "路由测试选题", "angle": "角度", "format": "图文",
                 "heat": 80, "tags": ["标签"]}
            ],
            "account_context_used": True,
        }

    def generate_topics(self, niche, platform, use_account_data=False, brand=None,
                        hot_topics=None):
        # hot_topics 仅为兼容路由新增参数，本测试不关心其值
        self.calls.append({
            "niche": niche,
            "platform": platform,
            "use_account_data": use_account_data,
            "brand": brand,
        })
        return self.result


@pytest.fixture
def fake_route_service(monkeypatch):
    service = FakeTopicService()
    monkeypatch.setattr(topic_routes, "get_topic_service", lambda: service)
    # 路由层测试不依赖真实品牌数据：品牌解析固定返回 None
    monkeypatch.setattr(topic_routes, "resolve_brand_for_prompt", lambda brand_id=None: None)
    return service


def test_route_passes_use_account_data_true(client, fake_route_service):
    response = client.post("/api/topic", json={
        "niche": "健身减脂",
        "platform": "小红书",
        "use_account_data": True,
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["account_context_used"] is True
    assert fake_route_service.calls == [
        {"niche": "健身减脂", "platform": "小红书", "use_account_data": True, "brand": None}
    ]


def test_route_defaults_use_account_data_false(client, fake_route_service):
    response = client.post("/api/topic", json={
        "niche": "健身减脂",
        "platform": "小红书",
    })

    assert response.status_code == 200
    assert fake_route_service.calls[0]["use_account_data"] is False
