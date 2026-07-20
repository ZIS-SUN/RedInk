"""
爆款体检（ReviewService + POST /api/review）测试

不发起真实 LLM 调用：
- 服务层：用假 client 返回预设文本，覆盖归一化 / score 钳制 / JSON 容错 / 建议裁剪
- 路由层：mock get_review_service，覆盖参数校验与成功返回
"""
import json

import pytest

from backend.routes import review_routes
from backend.services.review import ReviewService


VALID_REVIEW = {
    "overall_score": 85,
    "verdict": "钩子不错，行动引导偏弱",
    "dimensions": [
        {"name": "封面钩子", "score": 90, "comment": "悬念感强"},
        {"name": "标题吸引力", "score": 82, "comment": "数字冲击到位"},
        {"name": "内容结构", "score": 80, "comment": "推进有节奏"},
        {"name": "情绪价值", "score": 88, "comment": "焦虑缓解明显"},
        {"name": "行动引导", "score": 60, "comment": "结尾缺少互动引导"},
    ],
    "suggestions": [
        {
            "target": "page",
            "page_index": 2,
            "issue": "第 3 页信息密度过低",
            "suggestion": "补充一个具体案例",
            "rewrite": "改写后的第 3 页文案",
        },
        {
            "target": "copywriting",
            "page_index": None,
            "issue": "文案结尾没有引导",
            "suggestion": "加一句互动提问",
            "rewrite": "改写后的发布文案",
        },
    ],
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
    service = ReviewService.__new__(ReviewService)
    service.text_config = {
        "active_provider": "fake",
        "providers": {"fake": {"model": "fake-model", "temperature": 0.5, "max_output_tokens": 4000}},
    }
    service.client = FakeTextClient(response_text)
    service.prompt_template = (
        "topic: {topic}\noutline: {outline}\ntitles: {titles}\n"
        "copywriting: {copywriting}\ntags: {tags}"
    )
    return service


SAMPLE_PAGES = [
    {"index": 0, "type": "cover", "content": "封面文案"},
    {"index": 1, "type": "content", "content": "内容页文案"},
]


# ==================== 服务层：成功归一化 ====================

def test_review_work_success_normalization():
    service = make_service(json.dumps(VALID_REVIEW, ensure_ascii=False))

    result = service.review_work(
        "秋季穿搭", SAMPLE_PAGES,
        titles=["标题A"], copywriting="发布文案", tags=["穿搭"],
    )

    assert result["success"] is True
    review = result["review"]
    assert review["overall_score"] == 85
    assert review["verdict"] == "钩子不错，行动引导偏弱"
    assert [d["name"] for d in review["dimensions"]] == [
        "封面钩子", "标题吸引力", "内容结构", "情绪价值", "行动引导",
    ]
    assert review["dimensions"][0]["score"] == 90
    assert len(review["suggestions"]) == 2
    assert review["suggestions"][0]["target"] == "page"
    assert review["suggestions"][0]["page_index"] == 2
    assert review["suggestions"][1]["page_index"] is None

    # 输入拼进了 prompt（含页码标记与可选内容）
    prompt = service.client.calls[0]["prompt"]
    assert "秋季穿搭" in prompt
    assert "第 1 页" in prompt
    assert "标题A" in prompt


def test_review_work_optional_fields_default_to_placeholder():
    service = make_service(json.dumps(VALID_REVIEW, ensure_ascii=False))

    result = service.review_work("主题", SAMPLE_PAGES)

    assert result["success"] is True
    prompt = service.client.calls[0]["prompt"]
    # 未生成的标题/文案/标签用占位符
    assert prompt.count("未生成") == 3


def test_review_work_missing_fields_get_defaults():
    # 缺 verdict / dimensions / suggestions 时补默认值
    service = make_service(json.dumps({"overall_score": 70}))

    result = service.review_work("主题", SAMPLE_PAGES)

    assert result["success"] is True
    review = result["review"]
    assert review["overall_score"] == 70
    assert review["verdict"] == ""
    assert len(review["dimensions"]) == 5
    assert all(d["score"] == 0 for d in review["dimensions"])
    assert review["suggestions"] == []


# ==================== 服务层：score 钳制 ====================

def test_review_work_clamps_scores():
    data = dict(VALID_REVIEW)
    data["overall_score"] = 150
    data["dimensions"] = [
        {"name": "封面钩子", "score": -20, "comment": "负分"},
        {"name": "标题吸引力", "score": 999, "comment": "超上限"},
        {"name": "内容结构", "score": "not-a-number", "comment": "非法"},
        {"name": "情绪价值", "score": 66.6, "comment": "浮点"},
        {"name": "行动引导", "score": 50, "comment": "正常"},
    ]
    service = make_service(json.dumps(data, ensure_ascii=False))

    result = service.review_work("主题", SAMPLE_PAGES)

    review = result["review"]
    assert review["overall_score"] == 100
    scores = {d["name"]: d["score"] for d in review["dimensions"]}
    assert scores["封面钩子"] == 0
    assert scores["标题吸引力"] == 100
    assert scores["内容结构"] == 0
    assert scores["情绪价值"] == 67
    assert scores["行动引导"] == 50


# ==================== 服务层：JSON 容错 ====================

def test_review_work_parses_json_wrapped_in_code_fence():
    wrapped = "好的，这是体检结果：\n```json\n" + json.dumps(VALID_REVIEW, ensure_ascii=False) + "\n```\n希望有帮助！"
    service = make_service(wrapped)

    result = service.review_work("主题", SAMPLE_PAGES)

    assert result["success"] is True
    assert result["review"]["overall_score"] == 85


def test_review_work_parses_json_with_surrounding_text():
    noisy = "前置说明 " + json.dumps(VALID_REVIEW, ensure_ascii=False) + " 后置说明"
    service = make_service(noisy)

    result = service.review_work("主题", SAMPLE_PAGES)

    assert result["success"] is True
    assert result["review"]["overall_score"] == 85


def test_review_work_unparseable_response_returns_error():
    service = make_service("这完全不是 JSON")

    result = service.review_work("主题", SAMPLE_PAGES)

    assert result["success"] is False
    assert "错误详情" in result["error"]


# ==================== 服务层：suggestions 裁剪与过滤 ====================

def test_review_work_trims_suggestions_to_five():
    data = dict(VALID_REVIEW)
    data["suggestions"] = [
        {"target": "page", "page_index": i, "issue": f"问题{i}", "suggestion": f"建议{i}", "rewrite": ""}
        for i in range(8)
    ]
    service = make_service(json.dumps(data, ensure_ascii=False))

    result = service.review_work("主题", SAMPLE_PAGES)

    suggestions = result["review"]["suggestions"]
    assert len(suggestions) == 5
    assert [s["page_index"] for s in suggestions] == [0, 1, 2, 3, 4]


def test_review_work_filters_invalid_suggestion_targets():
    data = dict(VALID_REVIEW)
    data["suggestions"] = [
        {"target": "unknown", "issue": "非法 target", "suggestion": "应被过滤", "rewrite": ""},
        {"target": "tags", "page_index": 3, "issue": "标签太少", "suggestion": "补充标签", "rewrite": ""},
        "不是字典",
    ]
    service = make_service(json.dumps(data, ensure_ascii=False))

    result = service.review_work("主题", SAMPLE_PAGES)

    suggestions = result["review"]["suggestions"]
    assert len(suggestions) == 1
    assert suggestions[0]["target"] == "tags"
    # 非 page 类建议的 page_index 强制为 None
    assert suggestions[0]["page_index"] is None


# ==================== 路由层 ====================

class FakeReviewService:
    """记录调用参数并返回固定结果的假体检服务"""

    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "success": True,
            "review": {
                "overall_score": 85,
                "verdict": "总评",
                "dimensions": [],
                "suggestions": [],
            },
        }

    def review_work(self, topic, pages, titles=None, copywriting=None, tags=None, brand=None):
        self.calls.append({
            "topic": topic, "pages": pages,
            "titles": titles, "copywriting": copywriting, "tags": tags,
            "brand": brand,
        })
        return self.result


@pytest.fixture
def fake_review(monkeypatch):
    service = FakeReviewService()
    monkeypatch.setattr(review_routes, "get_review_service", lambda: service)
    # 路由层测试不依赖真实品牌数据：品牌解析固定返回 None
    monkeypatch.setattr(review_routes, "resolve_brand_for_prompt", lambda brand_id=None: None)
    return service


def test_route_empty_pages_returns_400(client, fake_review):
    response = client.post("/api/review", json={"topic": "主题", "pages": []})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    # 参数不合法时不应触发 LLM 调用
    assert fake_review.calls == []


def test_route_missing_pages_returns_400(client, fake_review):
    response = client.post("/api/review", json={"topic": "主题"})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_route_success_passes_params_through(client, fake_review):
    response = client.post("/api/review", json={
        "topic": "秋季穿搭",
        "pages": SAMPLE_PAGES,
        "titles": ["标题A", "标题B"],
        "copywriting": "发布文案",
        "tags": ["穿搭", "秋天"],
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["review"]["overall_score"] == 85

    call = fake_review.calls[0]
    assert call["topic"] == "秋季穿搭"
    assert len(call["pages"]) == 2
    assert call["titles"] == ["标题A", "标题B"]
    assert call["copywriting"] == "发布文案"
    assert call["tags"] == ["穿搭", "秋天"]


def test_route_optional_fields_default_to_none(client, fake_review):
    response = client.post("/api/review", json={"topic": "主题", "pages": SAMPLE_PAGES})

    assert response.status_code == 200
    call = fake_review.calls[0]
    assert call["titles"] is None
    assert call["copywriting"] is None
    assert call["tags"] is None


def test_route_service_failure_returns_500(client, monkeypatch):
    service = FakeReviewService(result={"success": False, "error": "LLM 挂了"})
    monkeypatch.setattr(review_routes, "get_review_service", lambda: service)
    monkeypatch.setattr(review_routes, "resolve_brand_for_prompt", lambda brand_id=None: None)

    response = client.post("/api/review", json={"topic": "主题", "pages": SAMPLE_PAGES})
    data = response.get_json()

    assert response.status_code == 500
    assert data["success"] is False
    assert data["error_message"]
