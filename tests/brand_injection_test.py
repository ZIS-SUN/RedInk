"""
品牌记忆全链路贯通测试

覆盖新增的品牌注入点（不发起真实 LLM 调用，mock 底层文本客户端）：
- 选题灵感（TopicService）：品牌人设约束注入 prompt，软失败
- 评论助手（ReplyService）：口头禅/签名明确注入回复 prompt
- 爆款体检（ReviewService）：有品牌时追加「人设一致性」第 6 维度
- 封面 A/B（CoverService）：人设约束 + 品牌视觉约束（主色调）
- AI 一周排期（generate_week_plan）：自动读激活品牌，软失败
- 图片生成（ImageService._apply_brand_visual_prompt）：品牌视觉约束，软失败
- 标题/内容生成：banned_word_hits 禁用词命中字段
- 品牌解析（resolve_brand_for_prompt）：brand_id / 激活档案回退 / 异常软失败
- 路由层：topic/reply/cover 路由把解析出的品牌透传给服务
"""
import json

import pytest

from backend.routes import cover_routes, reply_routes, topic_routes
from backend.services import brand as brand_module
from backend.services import calendar_plan as calendar_module
from backend.services.content import ContentService
from backend.services.cover import CoverService
from backend.services.image import ImageService
from backend.services.reply import ReplyService
from backend.services.review import ReviewService
from backend.services.rewrite import build_brand_visual_constraint
from backend.services.title import TitleService
from backend.services.topic import TopicService


# 测试用品牌档案（含人设与视觉字段）
BRAND = {
    "id": "brand-001",
    "name": "元气小张",
    "tagline": "打工人的能量补给站",
    "audience": "一线城市上班族",
    "tone": "活泼种草",
    "catchphrases": ["家人们谁懂啊"],
    "signature": "关注小张不迷路",
    "primary_color": "#FF2442",
    "banned_words": ["绝绝子", "yyds"],
    "notes": "",
}

# 只有人设、没有任何视觉字段的品牌
BRAND_NO_VISUAL = {k: v for k, v in BRAND.items() if k != "primary_color"}


class FakeTextClient:
    """记录 prompt 并返回固定文本的假文本客户端"""

    def __init__(self, response_text):
        self.prompts = []
        self.response_text = response_text

    def generate_text(self, prompt, model, temperature, max_output_tokens, **kwargs):
        self.prompts.append(prompt)
        return self.response_text


FAKE_TEXT_CONFIG = {
    "active_provider": "fake",
    "providers": {"fake": {"api_key": "test-key", "model": "fake-model"}},
}


def _assemble(service_cls, response_text, prompt_template):
    """绕过 __init__（避免读取真实配置/API Key），手工装配服务依赖"""
    service = service_cls.__new__(service_cls)
    service.text_config = FAKE_TEXT_CONFIG
    service.client = FakeTextClient(response_text)
    service.prompt_template = prompt_template
    return service


# ==================== 选题灵感 ====================

TOPIC_RESPONSE = json.dumps({
    "topics": [{"title": "测试选题", "angle": "角度", "format": "图文",
                "heat": 80, "tags": ["标签"]}]
}, ensure_ascii=False)


def test_topic_injects_brand_constraint():
    service = _assemble(TopicService, TOPIC_RESPONSE, "领域:{niche} 平台:{platform} 条数:{count}")

    result = service.generate_topics("健身减脂", "小红书", brand=BRAND)

    assert result["success"] is True
    prompt = service.client.prompts[0]
    assert "品牌人设约束" in prompt
    assert "元气小张" in prompt
    assert "活泼种草" in prompt
    assert "绝绝子" in prompt  # 禁用词也进入约束


def test_topic_without_brand_prompt_unchanged():
    service = _assemble(TopicService, TOPIC_RESPONSE, "领域:{niche} 平台:{platform} 条数:{count}")

    result = service.generate_topics("健身减脂", "小红书", brand=None)

    assert result["success"] is True
    assert "品牌人设约束" not in service.client.prompts[0]


def test_topic_with_empty_brand_dict_silently_skipped():
    """品牌档案无有效字段时静默跳过注入，不影响主流程"""
    service = _assemble(TopicService, TOPIC_RESPONSE, "领域:{niche} 平台:{platform} 条数:{count}")

    result = service.generate_topics("健身减脂", "小红书", brand={})

    assert result["success"] is True
    assert "品牌人设约束" not in service.client.prompts[0]


# ==================== 评论助手 ====================

REPLY_RESPONSE = json.dumps({
    "replies": [{"comment": "好实用！", "suggestions": ["回复1", "回复2"]}],
    "pinned_comment": "",
}, ensure_ascii=False)

REPLY_TEMPLATE = "{tone}|{tone_hint}|{comments}|{pinned_requirement}"


def test_reply_injects_catchphrase_and_signature():
    service = _assemble(ReplyService, REPLY_RESPONSE, REPLY_TEMPLATE)

    result = service.generate_replies(["好实用！"], tone="热情", brand=BRAND)

    assert result["success"] is True
    prompt = service.client.prompts[0]
    assert "品牌人设约束" in prompt
    # 口头禅/签名被明确要求用进回复
    assert "家人们谁懂啊" in prompt
    assert "关注小张不迷路" in prompt
    assert "回复身份要求" in prompt
    assert "博主本人的身份和口吻" in prompt


def test_reply_without_brand_prompt_unchanged():
    service = _assemble(ReplyService, REPLY_RESPONSE, REPLY_TEMPLATE)

    result = service.generate_replies(["好实用！"], tone="热情", brand=None)

    assert result["success"] is True
    assert "回复身份要求" not in service.client.prompts[0]


# ==================== 爆款体检 ====================

SAMPLE_PAGES = [
    {"index": 0, "type": "cover", "content": "封面文案"},
    {"index": 1, "type": "content", "content": "内容页文案"},
]

REVIEW_TEMPLATE = (
    "topic: {topic}\noutline: {outline}\ntitles: {titles}\n"
    "copywriting: {copywriting}\ntags: {tags}"
)


def _review_response(with_brand_dim: bool):
    dims = [
        {"name": "封面钩子", "score": 90, "comment": "a"},
        {"name": "标题吸引力", "score": 82, "comment": "b"},
        {"name": "内容结构", "score": 80, "comment": "c"},
        {"name": "情绪价值", "score": 88, "comment": "d"},
        {"name": "行动引导", "score": 60, "comment": "e"},
    ]
    if with_brand_dim:
        dims.append({"name": "人设一致性", "score": 75, "comment": "语气基本贴合人设"})
    return json.dumps({
        "overall_score": 85, "verdict": "总评", "dimensions": dims, "suggestions": [],
    }, ensure_ascii=False)


def test_review_with_brand_adds_persona_dimension():
    service = _assemble(ReviewService, _review_response(True), REVIEW_TEMPLATE)

    result = service.review_work("主题", SAMPLE_PAGES, brand=BRAND)

    assert result["success"] is True
    prompt = service.client.prompts[0]
    assert "品牌人设约束" in prompt
    assert "人设一致性" in prompt
    assert "禁用词" in prompt

    dims = result["review"]["dimensions"]
    assert len(dims) == 6
    assert dims[-1]["name"] == "人设一致性"
    assert dims[-1]["score"] == 75


def test_review_with_brand_missing_sixth_dim_defaults():
    """AI 没按要求返回第 6 维度时，归一化补默认项而不是报错"""
    service = _assemble(ReviewService, _review_response(False), REVIEW_TEMPLATE)

    result = service.review_work("主题", SAMPLE_PAGES, brand=BRAND)

    dims = result["review"]["dimensions"]
    assert len(dims) == 6
    assert dims[-1] == {"name": "人设一致性", "score": 0, "comment": ""}


def test_review_without_brand_keeps_five_dimensions():
    service = _assemble(ReviewService, _review_response(False), REVIEW_TEMPLATE)

    result = service.review_work("主题", SAMPLE_PAGES)

    assert result["success"] is True
    assert "人设一致性" not in service.client.prompts[0]
    assert len(result["review"]["dimensions"]) == 5


# ==================== 封面 A/B ====================

COVER_RESPONSE = json.dumps({
    "directions": [{
        "title": "封面标题", "subtitle": "副标题", "visual_concept": "视觉概念",
        "style": "极简大字报", "score": 90, "reason": "理由",
    }]
}, ensure_ascii=False)

COVER_TEMPLATE = "主题:{topic} 内容:{content}"


def test_cover_injects_persona_and_visual_constraint():
    service = _assemble(CoverService, COVER_RESPONSE, COVER_TEMPLATE)

    result = service.generate_cover_directions("秋季穿搭", brand=BRAND)

    assert result["success"] is True
    prompt = service.client.prompts[0]
    assert "品牌人设约束" in prompt
    assert "品牌视觉约束" in prompt
    assert "#FF2442" in prompt


def test_cover_brand_without_visual_fields_skips_visual_section():
    """品牌未设置视觉字段（主色调）时，只注入人设、不注入视觉约束"""
    service = _assemble(CoverService, COVER_RESPONSE, COVER_TEMPLATE)

    result = service.generate_cover_directions("秋季穿搭", brand=BRAND_NO_VISUAL)

    assert result["success"] is True
    prompt = service.client.prompts[0]
    assert "品牌人设约束" in prompt
    assert "品牌视觉约束" not in prompt


def test_cover_without_brand_prompt_unchanged():
    service = _assemble(CoverService, COVER_RESPONSE, COVER_TEMPLATE)

    result = service.generate_cover_directions("秋季穿搭")

    assert result["success"] is True
    prompt = service.client.prompts[0]
    assert "品牌人设约束" not in prompt
    assert "品牌视觉约束" not in prompt


# ==================== 品牌视觉约束构建 ====================

def test_build_brand_visual_constraint_requires_visual_fields():
    assert build_brand_visual_constraint(None) == ""
    assert build_brand_visual_constraint({}) == ""
    assert build_brand_visual_constraint(BRAND_NO_VISUAL) == ""

    constraint = build_brand_visual_constraint(BRAND)
    assert "品牌视觉约束" in constraint
    assert "#FF2442" in constraint
    assert "元气小张" in constraint


# ==================== AI 一周排期 ====================

WEEK_RESPONSE = json.dumps({
    "plans": [{"title": "周一计划", "publish_date": "2026-07-27",
               "publish_time": "18:00", "notes": "x"}]
}, ensure_ascii=False)

START = "2026-07-27"  # 一个周一


def _mock_calendar_llm(monkeypatch):
    client = FakeTextClient(WEEK_RESPONSE)
    monkeypatch.setattr(calendar_module, "load_text_config", lambda **kwargs: FAKE_TEXT_CONFIG)
    monkeypatch.setattr(calendar_module, "get_text_client", lambda cfg: client)
    return client


def test_week_plan_injects_active_brand(monkeypatch):
    client = _mock_calendar_llm(monkeypatch)
    # 排期是服务层自动读激活品牌（惰性导入），mock 品牌模块的解析函数
    monkeypatch.setattr(brand_module, "resolve_brand_for_prompt", lambda brand_id=None: BRAND)

    result = calendar_module.generate_week_plan("健身减脂", "xiaohongshu", START, 1)

    assert result["success"] is True
    prompt = client.prompts[0]
    assert "品牌人设约束" in prompt
    assert "元气小张" in prompt


def test_week_plan_brand_read_error_is_soft(monkeypatch):
    """品牌读取抛异常时静默跳过注入，排期主流程不受影响"""
    client = _mock_calendar_llm(monkeypatch)

    def _boom(brand_id=None):
        raise RuntimeError("品牌数据损坏")

    monkeypatch.setattr(brand_module, "resolve_brand_for_prompt", _boom)

    result = calendar_module.generate_week_plan("健身减脂", "xiaohongshu", START, 1)

    assert result["success"] is True
    assert "品牌人设约束" not in client.prompts[0]


def test_week_plan_no_active_brand_prompt_unchanged(monkeypatch):
    client = _mock_calendar_llm(monkeypatch)
    monkeypatch.setattr(brand_module, "resolve_brand_for_prompt", lambda brand_id=None: None)

    result = calendar_module.generate_week_plan("健身减脂", "xiaohongshu", START, 1)

    assert result["success"] is True
    assert "品牌人设约束" not in client.prompts[0]


# ==================== 图片生成视觉约束 ====================

def test_image_prompt_appends_brand_visual(monkeypatch):
    monkeypatch.setattr(brand_module, "resolve_brand_for_prompt", lambda brand_id=None: BRAND)

    prompt = ImageService._apply_brand_visual_prompt("基础 prompt")

    assert prompt.startswith("基础 prompt")
    assert "品牌视觉约束" in prompt
    assert "#FF2442" in prompt


def test_image_prompt_unchanged_without_visual_fields(monkeypatch):
    monkeypatch.setattr(
        brand_module, "resolve_brand_for_prompt", lambda brand_id=None: BRAND_NO_VISUAL
    )
    assert ImageService._apply_brand_visual_prompt("基础 prompt") == "基础 prompt"


def test_image_prompt_brand_read_error_is_soft(monkeypatch):
    def _boom(brand_id=None):
        raise RuntimeError("品牌数据损坏")

    monkeypatch.setattr(brand_module, "resolve_brand_for_prompt", _boom)
    assert ImageService._apply_brand_visual_prompt("基础 prompt") == "基础 prompt"


# ==================== 禁用词命中字段：标题 / 内容 ====================

TITLE_RESPONSE = json.dumps({
    "titles": [
        {"text": f"普通标题 {i}", "score": 70, "elements": ["数字"]} for i in range(9)
    ] + [{"text": "这款真的绝绝子", "score": 88, "elements": ["情绪"]}]
}, ensure_ascii=False)


def test_title_results_carry_banned_word_hits():
    service = _assemble(
        TitleService, TITLE_RESPONSE, "主题:{topic} 平台:{platform} 风格:{style} 条数:{count}"
    )

    result = service.generate_titles("主题", "小红书", "综合", brand=BRAND)

    assert result["success"] is True
    titles = result["titles"]
    # 每个候选标题都带 banned_word_hits 字段
    assert all("banned_word_hits" in t for t in titles)
    hits = {t["text"]: t["banned_word_hits"] for t in titles}
    assert hits["这款真的绝绝子"] == ["绝绝子"]
    assert hits["普通标题 0"] == []


def test_title_results_no_hits_field_without_brand():
    service = _assemble(
        TitleService, TITLE_RESPONSE, "主题:{topic} 平台:{platform} 风格:{style} 条数:{count}"
    )

    result = service.generate_titles("主题", "小红书", "综合", brand=None)

    assert result["success"] is True
    assert all("banned_word_hits" not in t for t in result["titles"])


CONTENT_RESPONSE = json.dumps({
    "titles": ["标题一", "含 yyds 的标题"],
    "copywriting": "正文里出现了绝绝子这个词",
    "tags": ["穿搭"],
}, ensure_ascii=False)


def test_content_result_carries_banned_word_hits():
    service = _assemble(ContentService, CONTENT_RESPONSE, "主题:{topic} 大纲:{outline}")

    result = service.generate_content("主题", "大纲", brand=BRAND)

    assert result["success"] is True
    # 标题命中 yyds、正文命中 绝绝子（按禁用词顺序去重）
    assert result["banned_word_hits"] == ["绝绝子", "yyds"]


def test_content_result_no_hits_field_without_banned_words():
    service = _assemble(ContentService, CONTENT_RESPONSE, "主题:{topic} 大纲:{outline}")

    # 品牌存在但没设禁用词：不扫描、不加字段
    brand = {k: v for k, v in BRAND.items() if k != "banned_words"}
    result = service.generate_content("主题", "大纲", brand=brand)

    assert result["success"] is True
    assert "banned_word_hits" not in result

    result_none = service.generate_content("主题", "大纲", brand=None)
    assert "banned_word_hits" not in result_none


# ==================== resolve_brand_for_prompt ====================

@pytest.fixture
def isolated_brand_store(tmp_path, monkeypatch):
    """品牌存储指向临时目录并重置单例，保证测试不读写真实数据"""
    monkeypatch.setattr(brand_module, "get_data_root", lambda: tmp_path)
    monkeypatch.setattr(brand_module, "_service_instance", None)
    return brand_module.BrandService()


def test_resolve_brand_for_prompt_by_id_and_active(isolated_brand_store, monkeypatch):
    service = isolated_brand_store
    monkeypatch.setattr(brand_module, "get_brand_service", lambda: service)

    first = service.create_brand({"name": "档案一"})   # 首个档案自动启用
    second = service.create_brand({"name": "档案二"})

    # 按 brand_id 查找
    assert brand_module.resolve_brand_for_prompt(second["id"])["name"] == "档案二"
    # 未提供 brand_id 时回退当前启用档案
    assert brand_module.resolve_brand_for_prompt()["name"] == "档案一"
    assert brand_module.resolve_brand_for_prompt("")["name"] == "档案一"
    # 档案不存在时返回 None
    assert brand_module.resolve_brand_for_prompt("not-exist") is None
    assert first["id"] != second["id"]


def test_resolve_brand_for_prompt_no_active_returns_none(isolated_brand_store, monkeypatch):
    service = isolated_brand_store
    monkeypatch.setattr(brand_module, "get_brand_service", lambda: service)

    assert brand_module.resolve_brand_for_prompt() is None


def test_resolve_brand_for_prompt_store_error_is_soft(monkeypatch):
    class BoomService:
        def get_active_brand(self):
            raise RuntimeError("数据文件损坏")

        def get_brand(self, brand_id):
            raise RuntimeError("数据文件损坏")

    monkeypatch.setattr(brand_module, "get_brand_service", lambda: BoomService())

    assert brand_module.resolve_brand_for_prompt() is None
    assert brand_module.resolve_brand_for_prompt("any-id") is None


# ==================== 路由层：品牌透传 ====================

class RecordingService:
    """记录 kwargs 并返回固定结果的通用假服务"""

    def __init__(self, method_name, result):
        self.calls = []
        self.result = result
        setattr(self, method_name, self._record)

    def _record(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return self.result


def test_topic_route_passes_active_brand(client, monkeypatch):
    service = RecordingService("generate_topics", {
        "success": True, "topics": [{"title": "t", "angle": "", "format": "图文",
                                     "heat": 1, "tags": []}],
        "account_context_used": False,
    })
    monkeypatch.setattr(topic_routes, "get_topic_service", lambda: service)
    monkeypatch.setattr(topic_routes, "resolve_brand_for_prompt", lambda brand_id=None: BRAND)

    response = client.post("/api/topic", json={"niche": "健身减脂"})

    assert response.status_code == 200
    assert service.calls[0]["kwargs"]["brand"] == BRAND


def test_reply_route_passes_active_brand(client, monkeypatch):
    service = RecordingService("generate_replies", {
        "success": True,
        "replies": [{"comment": "好", "suggestions": ["回"]}],
        "pinned_comment": "",
    })
    monkeypatch.setattr(reply_routes, "get_reply_service", lambda: service)
    monkeypatch.setattr(reply_routes, "resolve_brand_for_prompt", lambda brand_id=None: BRAND)

    response = client.post("/api/reply", json={"comments": ["好"]})

    assert response.status_code == 200
    assert service.calls[0]["kwargs"]["brand"] == BRAND


def test_cover_route_passes_brand_id(client, monkeypatch):
    service = RecordingService("generate_cover_directions", {
        "success": True,
        "directions": [{"title": "t", "subtitle": "", "visual_concept": "",
                        "style": "", "score": 1, "reason": ""}],
    })
    resolved = []

    def fake_resolve(brand_id=None):
        resolved.append(brand_id)
        return BRAND

    monkeypatch.setattr(cover_routes, "get_cover_service", lambda: service)
    monkeypatch.setattr(cover_routes, "resolve_brand_for_prompt", fake_resolve)

    response = client.post("/api/cover", json={"topic": "主题", "brand_id": "brand-001"})

    assert response.status_code == 200
    assert resolved == ["brand-001"]
    assert service.calls[0]["kwargs"]["brand"] == BRAND
