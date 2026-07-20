"""
评论洞察选题挖掘（InsightService + POST /api/insight）测试

不发起真实 LLM 调用：
- 服务层：用假 client 返回预设文本，覆盖归一化 / 钳制 / JSON 容错 / 裁剪
- 路由层：insight 蓝图不会被 create_app 注册，这里自建 Flask app 注册蓝图，
  mock get_insight_service，覆盖参数校验与成功/失败返回
"""
import json

import pytest
from flask import Flask

from backend.routes import insight_routes
from backend.routes.insight_routes import create_insight_blueprint
from backend.services.insight import (
    MAX_COMMENTS,
    MAX_PAIN_POINTS,
    InsightService,
)


VALID_INSIGHT = {
    "pain_points": [
        {
            "theme": "不知道新手该买什么装备",
            "summary": "新手怕买错浪费钱，希望有一份直接抄作业的清单",
            "frequency": 3,
            "evidence": ["博主用的是什么相机呀？", "新手预算两千求推荐"],
            "topics": [
                {
                    "title": "新手拍照装备避坑清单，两千预算直接抄作业",
                    "angle": "直接回应新手怕买错的焦虑，给可执行清单",
                    "format": "清单",
                    "heat": 88,
                    "tags": ["摄影", "新手入门", "装备推荐"],
                },
                {
                    "title": "我劝你别急着买相机：手机先拍好这3类照片",
                    "angle": "反差观点制造讨论，降低新手行动门槛",
                    "format": "图文",
                    "heat": 82,
                    "tags": ["摄影", "手机摄影"],
                },
            ],
        },
        {
            "theme": "学了教程还是拍不好",
            "summary": "粉丝看了很多教程仍无从下手，需要拆解到步骤的示范",
            "frequency": 2,
            "evidence": ["为什么我照着调参数还是拍得很丑"],
            "topics": [
                {
                    "title": "跟拍一次就懂：同一场景我是怎么拍出氛围感的",
                    "angle": "用一次完整跟拍示范代替抽象参数讲解",
                    "format": "教程",
                    "heat": 90,
                    "tags": ["摄影", "教程", "氛围感"],
                },
            ],
        },
        {
            "theme": "更新太慢蹲不到干货",
            "summary": "老粉催更，希望内容更成体系、更新更规律",
            "frequency": 1,
            "evidence": ["蹲一个系统的入门系列！"],
            "topics": [
                {
                    "title": "摄影入门30天计划：从零到出片的完整路线图",
                    "angle": "把催更诉求转化为系列化内容承诺，锁住老粉",
                    "format": "合集",
                    "heat": 85,
                    "tags": ["摄影", "入门计划"],
                },
            ],
        },
    ]
}


SAMPLE_COMMENTS = [
    "博主用的是什么相机呀？",
    "新手预算两千求推荐",
    "为什么我照着调参数还是拍得很丑",
    "蹲一个系统的入门系列！",
]


class FakeTextClient:
    """返回固定文本的假 LLM 客户端"""

    def __init__(self, response_text):
        self.response_text = response_text
        self.calls = []

    def generate_text(self, prompt, model, temperature, max_output_tokens):
        self.calls.append({"prompt": prompt, "model": model})
        return self.response_text


def make_service(response_text):
    """绕过 __init__（避免读配置/建真实客户端），手工装配依赖"""
    service = InsightService.__new__(InsightService)
    service.text_config = {
        "active_provider": "fake",
        "providers": {"fake": {"model": "fake-model", "temperature": 0.5, "max_output_tokens": 4000}},
    }
    service.client = FakeTextClient(response_text)
    service.prompt_template = "niche: {niche}\ncomments:\n{comments}"
    return service


# ==================== 服务层：成功归一化 ====================

def test_mine_insights_success_normalization():
    service = make_service(json.dumps(VALID_INSIGHT, ensure_ascii=False))

    result = service.mine_insights(SAMPLE_COMMENTS, niche="摄影教学")

    assert result["success"] is True
    assert result["comment_count"] == 4
    pain_points = result["pain_points"]
    assert [p["theme"] for p in pain_points] == [
        "不知道新手该买什么装备", "学了教程还是拍不好", "更新太慢蹲不到干货",
    ]
    first = pain_points[0]
    assert first["frequency"] == 3
    assert first["evidence"] == ["博主用的是什么相机呀？", "新手预算两千求推荐"]
    assert len(first["topics"]) == 2
    topic = first["topics"][0]
    # 选题结构对齐 topic 服务的 schema
    assert set(topic.keys()) == {"title", "angle", "format", "heat", "tags"}
    assert topic["format"] == "清单"
    assert topic["heat"] == 88
    assert topic["tags"] == ["摄影", "新手入门", "装备推荐"]

    # 输入拼进了 prompt（含序号与赛道）
    prompt = service.client.calls[0]["prompt"]
    assert "摄影教学" in prompt
    assert "1. 博主用的是什么相机呀？" in prompt


def test_mine_insights_without_niche_uses_placeholder():
    service = make_service(json.dumps(VALID_INSIGHT, ensure_ascii=False))

    result = service.mine_insights(SAMPLE_COMMENTS)

    assert result["success"] is True
    prompt = service.client.calls[0]["prompt"]
    assert "未提供" in prompt


def test_mine_insights_caps_comment_count():
    service = make_service(json.dumps(VALID_INSIGHT, ensure_ascii=False))
    comments = [f"评论{i}" for i in range(MAX_COMMENTS + 10)]

    result = service.mine_insights(comments)

    assert result["success"] is True
    assert result["comment_count"] == MAX_COMMENTS
    prompt = service.client.calls[0]["prompt"]
    assert f"{MAX_COMMENTS}. 评论{MAX_COMMENTS - 1}" in prompt
    assert f"评论{MAX_COMMENTS}" not in prompt


def test_mine_insights_empty_comments_returns_error():
    service = make_service(json.dumps(VALID_INSIGHT, ensure_ascii=False))

    result = service.mine_insights(["   ", ""])

    assert result["success"] is False
    assert "错误详情" in result["error"]
    # 参数不合法时不应触发 LLM 调用
    assert service.client.calls == []


# ==================== 服务层：归一化钳制与过滤 ====================

def test_mine_insights_clamps_frequency_and_trims_evidence():
    data = {
        "pain_points": [
            {
                "theme": "痛点A",
                "summary": "说明",
                "frequency": 999,
                "evidence": ["摘录1", "摘录2", "摘录3", "摘录4", "  "],
                "topics": [{"title": "选题A", "angle": "", "format": "图文", "heat": 70, "tags": []}],
            },
            {
                "theme": "痛点B",
                "summary": "说明",
                "frequency": "not-a-number",
                "evidence": "单条字符串摘录",
                "topics": [{"title": "选题B", "angle": "", "format": "图文", "heat": 70, "tags": []}],
            },
        ]
    }
    service = make_service(json.dumps(data, ensure_ascii=False))

    result = service.mine_insights(SAMPLE_COMMENTS)

    pain_points = result["pain_points"]
    # frequency 钳制到 [1, 评论总数]
    assert pain_points[0]["frequency"] == len(SAMPLE_COMMENTS)
    assert pain_points[1]["frequency"] == 1
    # evidence 裁剪到 3 条，且字符串输入收敛为列表
    assert pain_points[0]["evidence"] == ["摘录1", "摘录2", "摘录3"]
    assert pain_points[1]["evidence"] == ["单条字符串摘录"]


def test_mine_insights_normalizes_topics():
    data = {
        "pain_points": [
            {
                "theme": "痛点A",
                "summary": "说明",
                "frequency": 2,
                "evidence": ["摘录"],
                "topics": [
                    {"title": "热度超界", "angle": "角度", "format": "直播", "heat": 150, "tags": "标签1, 标签2"},
                    {"title": "", "angle": "无标题应被过滤", "format": "图文", "heat": 50, "tags": []},
                    "不是字典",
                    {"title": "第4条", "angle": "", "format": "图文", "heat": -5, "tags": ["#带井号"]},
                    {"title": "第5条超出上限应被裁掉", "angle": "", "format": "图文", "heat": 60, "tags": []},
                ],
            },
        ]
    }
    service = make_service(json.dumps(data, ensure_ascii=False))

    result = service.mine_insights(SAMPLE_COMMENTS)

    topics = result["pain_points"][0]["topics"]
    # 无标题/非字典被过滤后按序保留，最多 3 条
    assert [t["title"] for t in topics] == ["热度超界", "第4条", "第5条超出上限应被裁掉"]
    # 非法 format 回退图文，heat 钳制 0-100，tags 兼容逗号字符串并去 # 号
    assert topics[0]["format"] == "图文"
    assert topics[0]["heat"] == 100
    assert topics[0]["tags"] == ["标签1", "标签2"]
    assert topics[1]["heat"] == 0
    assert topics[1]["tags"] == ["带井号"]


def test_mine_insights_trims_pain_points_and_drops_invalid():
    data = {
        "pain_points": [
            "不是字典",
            {"theme": "", "topics": [{"title": "无主题应作废"}]},
            {"theme": "没有有效选题应作废", "topics": []},
        ] + [
            {
                "theme": f"痛点{i}",
                "summary": "",
                "frequency": 1,
                "evidence": [],
                "topics": [{"title": f"选题{i}", "angle": "", "format": "图文", "heat": 60, "tags": []}],
            }
            for i in range(MAX_PAIN_POINTS + 2)
        ]
    }
    service = make_service(json.dumps(data, ensure_ascii=False))

    result = service.mine_insights(SAMPLE_COMMENTS)

    pain_points = result["pain_points"]
    assert len(pain_points) == MAX_PAIN_POINTS
    assert pain_points[0]["theme"] == "痛点0"


# ==================== 服务层：JSON 容错 ====================

def test_mine_insights_parses_json_wrapped_in_code_fence():
    wrapped = "好的，洞察结果如下：\n```json\n" + json.dumps(VALID_INSIGHT, ensure_ascii=False) + "\n```\n希望有帮助！"
    service = make_service(wrapped)

    result = service.mine_insights(SAMPLE_COMMENTS)

    assert result["success"] is True
    assert len(result["pain_points"]) == 3


def test_mine_insights_parses_json_with_surrounding_text():
    noisy = "前置说明 " + json.dumps(VALID_INSIGHT, ensure_ascii=False) + " 后置说明"
    service = make_service(noisy)

    result = service.mine_insights(SAMPLE_COMMENTS)

    assert result["success"] is True
    assert len(result["pain_points"]) == 3


def test_mine_insights_unparseable_response_returns_error():
    service = make_service("这完全不是 JSON")

    result = service.mine_insights(SAMPLE_COMMENTS)

    assert result["success"] is False
    assert "错误详情" in result["error"]


def test_mine_insights_no_valid_pain_points_returns_error():
    service = make_service(json.dumps({"pain_points": "不是列表"}))

    result = service.mine_insights(SAMPLE_COMMENTS)

    assert result["success"] is False
    assert "错误详情" in result["error"]


# ==================== 路由层 ====================

class FakeInsightService:
    """记录调用参数并返回固定结果的假洞察服务"""

    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "success": True,
            "pain_points": VALID_INSIGHT["pain_points"],
            "comment_count": 4,
        }

    def mine_insights(self, comments, niche=""):
        self.calls.append({"comments": comments, "niche": niche})
        return self.result


@pytest.fixture
def insight_client():
    """insight 蓝图未接入 create_app，自建 Flask app 注册蓝图"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(create_insight_blueprint(), url_prefix='/api')
    return app.test_client()


@pytest.fixture
def fake_insight(monkeypatch):
    service = FakeInsightService()
    monkeypatch.setattr(insight_routes, "get_insight_service", lambda: service)
    return service


def test_route_empty_comments_returns_400(insight_client, fake_insight):
    response = insight_client.post("/api/insight", json={"comments": []})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    # 参数不合法时不应触发 LLM 调用
    assert fake_insight.calls == []


def test_route_missing_comments_returns_400(insight_client, fake_insight):
    response = insight_client.post("/api/insight", json={})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_route_blank_comments_returns_400(insight_client, fake_insight):
    response = insight_client.post("/api/insight", json={"comments": ["  ", "\t"]})

    assert response.status_code == 400
    assert fake_insight.calls == []


def test_route_success_passes_params_through(insight_client, fake_insight):
    response = insight_client.post("/api/insight", json={
        "comments": SAMPLE_COMMENTS,
        "niche": "摄影教学",
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert len(data["pain_points"]) == 3
    assert data["comment_count"] == 4

    call = fake_insight.calls[0]
    assert call["comments"] == SAMPLE_COMMENTS
    assert call["niche"] == "摄影教学"


def test_route_accepts_multiline_string_comments(insight_client, fake_insight):
    response = insight_client.post("/api/insight", json={
        "comments": "第一条评论\n\n  第二条评论  \n第三条评论",
    })

    assert response.status_code == 200
    call = fake_insight.calls[0]
    assert call["comments"] == ["第一条评论", "第二条评论", "第三条评论"]
    assert call["niche"] == ""


def test_route_service_failure_returns_500(insight_client, monkeypatch):
    service = FakeInsightService(result={"success": False, "error": "LLM 挂了"})
    monkeypatch.setattr(insight_routes, "get_insight_service", lambda: service)

    response = insight_client.post("/api/insight", json={"comments": SAMPLE_COMMENTS})
    data = response.get_json()

    assert response.status_code == 500
    assert data["success"] is False
    assert data["error_message"]
