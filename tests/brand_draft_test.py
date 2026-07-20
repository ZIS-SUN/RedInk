"""
新手账号定位向导（POST /api/brand/draft）测试

不发起真实 LLM 调用：
- 服务层测试 mock 掉 brand 模块内的 load_text_config / get_text_client，
  覆盖：正常 JSON / 代码块+杂文本包裹 / 缺字段容错 / 完全无效输出
- 路由层测试 mock 掉 generate_brand_draft，验证参数校验与结果透传
"""
import json

import pytest

from backend.routes import brand_routes
from backend.services import brand as brand_module


VALID_DRAFT = {
    "name": ["营养师阿真", "阿真的减脂厨房"],
    "positioning": "帮 25-35 岁想减脂的女生用三甲医院营养知识科学瘦下来",
    "tone": "亲切闺蜜风，专业但不端着",
    "catchphrases": ["姐妹们先别急", "记住这一句就够了"],
    "signature": "关注我，做你最懂营养的减脂搭子",
    "banned_words": ["根治", "绝对有效", "第一"],
    "niche_tags": ["减脂", "营养科普", "健康饮食"],
    "starter_topics": [
        {"title": "三甲营养科医生，为什么劝你别节食", "angle": "自我介绍+反常识立人设"},
        {"title": "减脂第一步不是迈开腿，是会看配料表", "angle": "新手第一步低门槛干货"},
    ],
}

VALID_LLM_RESPONSE = json.dumps(VALID_DRAFT, ensure_ascii=False)

ANSWERS = {
    "who": "三甲医院营养科医生",
    "audience": "25-35 岁想减脂的女生",
    "advantage": "有专业资质，亲身带过几百个减脂案例",
}


class FakeTextClient:
    """按顺序返回预设文本的假文本客户端（记录每次 prompt）"""

    def __init__(self, responses):
        self.prompts = []
        self.responses = list(responses)

    def generate_text(self, prompt, model, temperature, max_output_tokens, **kwargs):
        self.prompts.append(prompt)
        # 多次调用时依次弹出，最后一个响应可重复使用
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


def _install_fake_client(monkeypatch, responses):
    """把 brand 模块的配置加载与客户端构建替换为假实现"""
    client = FakeTextClient(responses)
    monkeypatch.setattr(
        brand_module,
        "load_text_config",
        lambda: {
            "active_provider": "fake",
            "providers": {"fake": {"api_key": "test-key", "model": "fake-model"}},
        },
    )
    monkeypatch.setattr(brand_module, "get_text_client", lambda config: client)
    return client


# ==================== 服务层 ====================

def test_generate_draft_valid_json(monkeypatch):
    """模型返回标准 JSON：成功，字段原样收敛，三个回答注入 prompt"""
    client = _install_fake_client(monkeypatch, [VALID_LLM_RESPONSE])

    result = brand_module.generate_brand_draft(**ANSWERS)

    assert result["success"] is True
    draft = result["draft"]
    assert draft["name"] == ["营养师阿真", "阿真的减脂厨房"]
    assert draft["positioning"] == VALID_DRAFT["positioning"]
    assert draft["tone"] == VALID_DRAFT["tone"]
    assert draft["catchphrases"] == VALID_DRAFT["catchphrases"]
    assert draft["signature"] == VALID_DRAFT["signature"]
    assert draft["banned_words"] == VALID_DRAFT["banned_words"]
    assert draft["niche_tags"] == VALID_DRAFT["niche_tags"]
    assert draft["starter_topics"] == VALID_DRAFT["starter_topics"]

    # 三个回答都应注入 prompt，且只调用一次
    assert len(client.prompts) == 1
    prompt = client.prompts[0]
    for answer in ANSWERS.values():
        assert answer in prompt


def test_generate_draft_wrapped_in_prose_and_code_block(monkeypatch):
    """模型输出被 ```json 代码块与前后解释文字包裹：解析容错，正常成功"""
    wrapped = (
        "好的，以下是为你生成的账号定位方案：\n\n"
        f"```json\n{VALID_LLM_RESPONSE}\n```\n\n"
        "希望这份方案对你的起号有帮助！"
    )
    client = _install_fake_client(monkeypatch, [wrapped])

    result = brand_module.generate_brand_draft(**ANSWERS)

    assert result["success"] is True
    assert result["draft"]["name"] == VALID_DRAFT["name"]
    assert result["draft"]["starter_topics"] == VALID_DRAFT["starter_topics"]
    # 一次就解析成功，不应触发格式纠正重试
    assert len(client.prompts) == 1


def test_generate_draft_missing_fields_tolerated(monkeypatch):
    """模型漏字段/字段类型不标准：缺失项容错为默认值，不报错"""
    partial = json.dumps({
        # name 返回单个字符串而非数组 → 应包装成单元素列表
        "name": "营养师阿真",
        "positioning": "帮想减脂的女生科学瘦下来",
        # starter_topics 混入字符串条目与非法条目 → 字符串视为纯标题，非法丢弃
        "starter_topics": [
            {"title": "我是谁：三甲营养科医生的自我介绍"},
            "减脂新手最容易犯的 3 个错",
            {"angle": "没有标题的非法条目"},
            42,
        ],
        # tone/catchphrases/signature/banned_words/niche_tags 全部缺失
    }, ensure_ascii=False)
    _install_fake_client(monkeypatch, [partial])

    result = brand_module.generate_brand_draft(**ANSWERS)

    assert result["success"] is True
    draft = result["draft"]
    assert draft["name"] == ["营养师阿真"]
    assert draft["positioning"] == "帮想减脂的女生科学瘦下来"
    # 缺失字段的默认值
    assert draft["tone"] == ""
    assert draft["signature"] == ""
    assert draft["catchphrases"] == []
    assert draft["banned_words"] == []
    assert draft["niche_tags"] == []
    # 起号选题：缺 angle 容错为空串，字符串条目保留，非法条目丢弃
    assert draft["starter_topics"] == [
        {"title": "我是谁：三甲营养科医生的自我介绍", "angle": ""},
        {"title": "减脂新手最容易犯的 3 个错", "angle": ""},
    ]


def test_generate_draft_core_fields_all_empty_fails(monkeypatch):
    """JSON 合法但核心字段全空：视为无效输出，返回失败而非空草稿"""
    _install_fake_client(monkeypatch, [json.dumps({"foo": "bar"})])

    result = brand_module.generate_brand_draft(**ANSWERS)

    assert result["success"] is False
    assert "账号定位草稿生成失败" in result["error"]


def test_generate_draft_unparseable_output_fails_after_retry(monkeypatch):
    """两次输出都不是 JSON：带纠正提示重试一次后失败，错误文案可读"""
    client = _install_fake_client(monkeypatch, ["这不是 JSON", "重试后还不是 JSON"])

    result = brand_module.generate_brand_draft(**ANSWERS)

    assert result["success"] is False
    assert "账号定位草稿生成失败" in result["error"]
    # generate_and_parse_json 应自动带格式纠正提示重试一次
    assert len(client.prompts) == 2
    assert "格式纠正" in client.prompts[1]


# ==================== 路由层 ====================

class FakeDraftFn:
    """记录调用参数并返回固定结果的假 generate_brand_draft"""

    def __init__(self, result):
        self.calls = []
        self.result = result

    def __call__(self, who, audience, advantage):
        self.calls.append({"who": who, "audience": audience, "advantage": advantage})
        return self.result


@pytest.fixture
def fake_draft_success(monkeypatch):
    fake = FakeDraftFn({
        "success": True,
        "draft": brand_module.normalize_brand_draft(VALID_DRAFT),
    })
    monkeypatch.setattr(brand_routes, "generate_brand_draft", fake)
    return fake


def test_draft_route_success_passthrough(client, fake_draft_success):
    """三个回答齐全：200，draft 透传，入参去除首尾空白"""
    response = client.post("/api/brand/draft", json={
        "who": "  三甲医院营养科医生  ",
        "audience": "25-35 岁想减脂的女生",
        "advantage": "有专业资质，亲身带过几百个减脂案例",
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["draft"]["name"] == VALID_DRAFT["name"]
    assert data["draft"]["starter_topics"] == VALID_DRAFT["starter_topics"]
    assert fake_draft_success.calls == [ANSWERS]


@pytest.mark.parametrize("missing_key", ["who", "audience", "advantage"])
def test_draft_route_missing_answer_returns_400(client, fake_draft_success, missing_key):
    """任一回答缺失/空白：400 参数校验错误，不触发生成"""
    payload = {**ANSWERS, missing_key: "   "}
    response = client.post("/api/brand/draft", json=payload)
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert fake_draft_success.calls == []


def test_draft_route_service_error_normalized(client, monkeypatch):
    """服务层失败：错误被归一化为统一错误对象，状态码 500"""
    fake = FakeDraftFn({"success": False, "error": "账号定位草稿生成失败。\n错误详情: mock"})
    monkeypatch.setattr(brand_routes, "generate_brand_draft", fake)

    response = client.post("/api/brand/draft", json=ANSWERS)
    data = response.get_json()

    assert response.status_code == 500
    assert data["success"] is False
    assert isinstance(data["error"], dict)
    assert data["error"].get("code")
    assert data.get("error_message")
