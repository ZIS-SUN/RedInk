"""
小红书搜索埋词（seo_keywords）全链路测试

不发起真实 LLM 调用（mock 底层文本客户端 / mock 服务实例）：
- 归一化：normalize_seo_keywords 过滤脏数据、去重、最多取前 3 个
- 大纲注入：build_outline_prompt / generate_outline 追加埋词要求；
  未提供搜索词时 prompt 与旧行为完全一致
- 内容注入：generate_content 追加标题/正文/标签埋词要求
- prompt 模板守护：outline/content 模板占位符集合不因本次改动变化
- 路由透传：/api/outline（JSON + multipart）、/api/outline/stream 校验、
  /api/content 把 seo_keywords 传给服务层
- 体检三项：seo_title / seo_body / seo_tags 的 pass/warn 判定、
  边界（前 15 字/前 80 字窗口）、未带搜索词时三项不出现
"""
import json

from backend.routes import content_routes, outline_routes
from backend.services import outline as outline_module
from backend.services.checklist import (
    SEO_BODY_WINDOW,
    SEO_TITLE_WINDOW,
    STATUS_PASS,
    STATUS_WARN,
    run_checklist,
)
from backend.services.content import ContentService, build_seo_content_constraint
from backend.services.outline import (
    OutlineService,
    build_seo_keywords_constraint,
    normalize_seo_keywords,
)


class FakeTextClient:
    """记录 prompt 并返回固定文本的假文本客户端（不发真实请求）"""

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

OUTLINE_RESPONSE = "[封面]\n标题：秋冬穿搭公式\n<page>\n[内容]\n第一条内容"

CONTENT_RESPONSE = json.dumps({
    "titles": ["秋冬穿搭公式来了", "备选标题2", "备选标题3"],
    "copywriting": "秋冬穿搭其实很简单……",
    "tags": ["秋冬穿搭", "穿搭技巧"],
}, ensure_ascii=False)


def _assemble(service_cls, response_text, prompt_template):
    """绕过 __init__（避免读取真实配置/API Key），手工装配服务依赖"""
    service = service_cls.__new__(service_cls)
    service.text_config = FAKE_TEXT_CONFIG
    service.client = FakeTextClient(response_text)
    service.prompt_template = prompt_template
    return service


# ==================== 归一化 ====================

def test_normalize_filters_dedupes_and_caps_at_three():
    raw = ["  秋冬穿搭 ", "", None, 123, "显瘦", "秋冬穿搭", "平价", "第四个词"]
    assert normalize_seo_keywords(raw) == ["秋冬穿搭", "显瘦", "平价"]


def test_normalize_non_list_returns_empty():
    for bad in (None, "秋冬穿搭", 42, {"a": 1}):
        assert normalize_seo_keywords(bad) == []


def test_constraint_empty_when_no_valid_keywords():
    assert build_seo_keywords_constraint(None) == ""
    assert build_seo_keywords_constraint([]) == ""
    assert build_seo_keywords_constraint(["  ", None]) == ""
    assert build_seo_content_constraint([]) == ""


# ==================== 大纲 prompt 注入 ====================

def _make_outline_service():
    return _assemble(OutlineService, OUTLINE_RESPONSE, "主题:{topic}")


def test_outline_prompt_injects_seo_constraint(monkeypatch):
    # 屏蔽创作偏好画像，保证比较基准确定
    monkeypatch.setattr(outline_module, "load_preference_snippet", lambda: "")
    service = _make_outline_service()

    without = service.build_outline_prompt("秋冬怎么穿")
    with_seo = service.build_outline_prompt(
        "秋冬怎么穿", seo_keywords=["秋冬穿搭", "显瘦穿搭"]
    )

    # 未带搜索词时 prompt 与旧行为完全一致
    assert "目标搜索词" not in without
    # 埋词要求以追加方式融入，前缀不变
    assert with_seo.startswith(without)
    assert "目标搜索词埋入要求" in with_seo
    assert "「秋冬穿搭」" in with_seo and "「显瘦穿搭」" in with_seo
    assert "核心词是「秋冬穿搭」" in with_seo
    assert "前 15 个字" in with_seo
    assert "第一个内容页" in with_seo
    assert "严禁堆砌" in with_seo


def test_outline_generate_passes_seo_to_prompt(monkeypatch):
    monkeypatch.setattr(outline_module, "load_preference_snippet", lambda: "")
    service = _make_outline_service()

    result = service.generate_outline("秋冬怎么穿", seo_keywords=["秋冬穿搭"])

    assert result["success"] is True
    assert "目标搜索词埋入要求" in service.client.prompts[0]


def test_outline_generate_without_seo_prompt_unchanged(monkeypatch):
    monkeypatch.setattr(outline_module, "load_preference_snippet", lambda: "")
    service = _make_outline_service()

    result = service.generate_outline("秋冬怎么穿")

    assert result["success"] is True
    assert "目标搜索词" not in service.client.prompts[0]


# ==================== 内容 prompt 注入 ====================

def _make_content_service():
    return _assemble(ContentService, CONTENT_RESPONSE, "主题:{topic} 大纲:{outline}")


def test_content_prompt_injects_seo_constraint():
    service = _make_content_service()

    result = service.generate_content(
        "主题", "大纲", seo_keywords=["秋冬穿搭", "显瘦穿搭"]
    )

    assert result["success"] is True
    prompt = service.client.prompts[0]
    assert "目标搜索词埋入要求" in prompt
    assert "核心词是「秋冬穿搭」" in prompt
    assert "前 15 个字" in prompt      # 标题埋词
    assert "前 80 个字" in prompt      # 正文埋词
    assert "长尾组合词" in prompt      # 标签埋词
    assert "严禁堆砌" in prompt


def test_content_without_seo_prompt_unchanged():
    service = _make_content_service()

    result = service.generate_content("主题", "大纲")

    assert result["success"] is True
    assert "目标搜索词" not in service.client.prompts[0]


def test_content_invalid_seo_keywords_silently_ignored():
    """脏数据（非列表/全空白）静默忽略，不影响生成主流程"""
    service = _make_content_service()

    result = service.generate_content("主题", "大纲", seo_keywords="不是列表")

    assert result["success"] is True
    assert "目标搜索词" not in service.client.prompts[0]


# ==================== prompt 模板占位符守护 ====================

def _template_placeholders(rel_path):
    """提取模板中的 format 占位符集合（{{ }} 转义不计入）"""
    from string import Formatter
    from backend.paths import resource_path

    text = resource_path(rel_path).read_text(encoding="utf-8")
    return {field for _, field, _, _ in Formatter().parse(text) if field}


def test_outline_prompt_placeholders_unchanged():
    assert _template_placeholders("backend/prompts/outline_prompt.txt") == {"topic"}


def test_content_prompt_placeholders_unchanged():
    assert _template_placeholders("backend/prompts/content_prompt.txt") == {
        "topic", "outline",
    }


def test_prompt_files_mention_seo_requirement():
    """模板中以条件从句方式提到埋词要求（动态关键词由服务层追加）"""
    from backend.paths import resource_path

    outline_text = resource_path("backend/prompts/outline_prompt.txt").read_text(encoding="utf-8")
    content_text = resource_path("backend/prompts/content_prompt.txt").read_text(encoding="utf-8")
    assert "目标搜索词埋入要求" in outline_text
    assert "目标搜索词埋入要求" in content_text


# ==================== 路由透传 ====================

class FakeOutlineService:
    """记录调用参数并返回固定成功结果的假大纲服务"""

    def __init__(self):
        self.calls = []

    def generate_outline(self, topic, images=None, brand=None, seo_keywords=None):
        self.calls.append({
            "topic": topic,
            "images": images,
            "brand": brand,
            "seo_keywords": seo_keywords,
        })
        return {
            "success": True,
            "outline": "[封面]\n标题：测试",
            "pages": [{"index": 0, "type": "cover", "content": "[封面]\n标题：测试"}],
            "has_images": bool(images),
        }


def test_outline_route_passes_seo_keywords_json(client, monkeypatch):
    fake = FakeOutlineService()
    monkeypatch.setattr(outline_routes, "get_outline_service", lambda: fake)

    response = client.post("/api/outline", json={
        "topic": "秋冬怎么穿",
        "seo_keywords": ["秋冬穿搭", "显瘦穿搭"],
    })

    assert response.status_code == 200
    assert fake.calls[0]["seo_keywords"] == ["秋冬穿搭", "显瘦穿搭"]


def test_outline_route_without_seo_keywords_json(client, monkeypatch):
    fake = FakeOutlineService()
    monkeypatch.setattr(outline_routes, "get_outline_service", lambda: fake)

    response = client.post("/api/outline", json={"topic": "秋冬怎么穿"})

    assert response.status_code == 200
    assert fake.calls[0]["seo_keywords"] is None


def test_outline_route_passes_seo_keywords_multipart(client, monkeypatch):
    """multipart 表单同名字段逐个提交，后端 getlist 取回列表"""
    fake = FakeOutlineService()
    monkeypatch.setattr(outline_routes, "get_outline_service", lambda: fake)

    response = client.post(
        "/api/outline",
        data={"topic": "秋冬怎么穿", "seo_keywords": ["秋冬穿搭", "显瘦穿搭"]},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert fake.calls[0]["seo_keywords"] == ["秋冬穿搭", "显瘦穿搭"]


class FakeContentService:
    """记录调用参数并返回固定成功结果的假内容服务"""

    def __init__(self):
        self.calls = []

    def generate_content(self, topic, outline, brand=None, seo_keywords=None):
        self.calls.append({
            "topic": topic,
            "outline": outline,
            "brand": brand,
            "seo_keywords": seo_keywords,
        })
        return {
            "success": True,
            "titles": ["标题1"],
            "copywriting": "正文",
            "tags": ["标签"],
        }


def test_content_route_passes_seo_keywords(client, monkeypatch):
    fake = FakeContentService()
    monkeypatch.setattr(content_routes, "get_content_service", lambda: fake)

    response = client.post("/api/content", json={
        "topic": "秋冬怎么穿",
        "outline": "大纲内容",
        "seo_keywords": ["秋冬穿搭"],
    })

    assert response.status_code == 200
    assert fake.calls[0]["seo_keywords"] == ["秋冬穿搭"]


def test_content_route_without_seo_keywords(client, monkeypatch):
    fake = FakeContentService()
    monkeypatch.setattr(content_routes, "get_content_service", lambda: fake)

    response = client.post("/api/content", json={
        "topic": "秋冬怎么穿",
        "outline": "大纲内容",
    })

    assert response.status_code == 200
    assert fake.calls[0]["seo_keywords"] is None


# ==================== 体检：搜索埋词三项 ====================

def make_checklist_payload(**overrides):
    """构造一份埋词全部达标的小红书体检请求，按需覆盖字段。"""
    payload = {
        "platform": "xiaohongshu",
        "title": "秋冬穿搭公式大公开",
        "body": "秋冬穿搭最重要的是层次感，这篇讲透基础三件套。",
        "tags": ["秋冬穿搭", "通勤穿搭"],
        "image_count": 4,
        "banned_words": [],
        "seo_keywords": ["秋冬穿搭"],
    }
    payload.update(overrides)
    return payload


def get_item(result, item_id):
    """按 id 取出检查项。"""
    for item in result["items"]:
        if item["id"] == item_id:
            return item
    raise AssertionError(f"缺少检查项: {item_id}")


def item_ids(result):
    return [item["id"] for item in result["items"]]


def test_checklist_seo_items_present_with_keywords():
    result = run_checklist(make_checklist_payload())

    ids = item_ids(result)
    assert "seo_title" in ids and "seo_body" in ids and "seo_tags" in ids
    # 6 项常规 + 3 项埋词 + 1 项常驻 AIGC 声明
    assert len(result["items"]) == 10
    # AIGC 声明保持常驻在最后
    assert ids[-1] == "aigc_declaration"
    # summary 计数覆盖全部检查项
    summary = result["summary"]
    assert summary["pass"] + summary["warn"] + summary["fail"] == len(result["items"])


def test_checklist_seo_items_absent_without_keywords():
    for overrides in ({"seo_keywords": []}, {"seo_keywords": None}):
        result = run_checklist(make_checklist_payload(**overrides))
        ids = item_ids(result)
        assert "seo_title" not in ids
        assert "seo_body" not in ids
        assert "seo_tags" not in ids
        assert len(result["items"]) == 7

    # 完全不带该字段（旧调用方）同样不出现
    payload = make_checklist_payload()
    payload.pop("seo_keywords")
    assert len(run_checklist(payload)["items"]) == 7


def test_checklist_seo_all_pass():
    result = run_checklist(make_checklist_payload())

    assert get_item(result, "seo_title")["status"] == STATUS_PASS
    assert get_item(result, "seo_body")["status"] == STATUS_PASS
    assert get_item(result, "seo_tags")["status"] == STATUS_PASS


def test_seo_title_window_boundary():
    # 核心词最后一个字落在第 15 字：命中
    at_edge = "字" * (SEO_TITLE_WINDOW - 1) + "词"
    result = run_checklist(make_checklist_payload(
        title=at_edge, seo_keywords=["词"],
    ))
    assert get_item(result, "seo_title")["status"] == STATUS_PASS

    # 核心词从第 16 字开始：不命中，warn 且提示前移
    beyond = "字" * SEO_TITLE_WINDOW + "词"
    result = run_checklist(make_checklist_payload(
        title=beyond, seo_keywords=["词"],
    ))
    item = get_item(result, "seo_title")
    assert item["status"] == STATUS_WARN
    assert "挪到标题开头" in item["detail"]


def test_seo_title_missing_keyword_suggests_core_word():
    result = run_checklist(make_checklist_payload(
        title="完全无关的一个标题", seo_keywords=["秋冬穿搭"],
    ))
    item = get_item(result, "seo_title")
    assert item["status"] == STATUS_WARN
    assert "「秋冬穿搭」" in item["detail"]


def test_seo_title_empty_title_warns():
    result = run_checklist(make_checklist_payload(title="", seo_keywords=["秋冬穿搭"]))
    item = get_item(result, "seo_title")
    assert item["status"] == STATUS_WARN
    assert "「秋冬穿搭」" in item["detail"]


def test_seo_body_window_boundary():
    # 核心词最后一个字落在第 80 字：命中
    at_edge = "字" * (SEO_BODY_WINDOW - 1) + "词"
    result = run_checklist(make_checklist_payload(body=at_edge, seo_keywords=["词"]))
    assert get_item(result, "seo_body")["status"] == STATUS_PASS

    # 核心词从第 81 字开始：不命中，warn 且提示在开头带到
    beyond = "字" * SEO_BODY_WINDOW + "词"
    result = run_checklist(make_checklist_payload(body=beyond, seo_keywords=["词"]))
    item = get_item(result, "seo_body")
    assert item["status"] == STATUS_WARN
    assert "开头" in item["detail"]


def test_seo_body_missing_and_empty_warn():
    missing = run_checklist(make_checklist_payload(
        body="通篇没有出现目标词的正文。", seo_keywords=["秋冬穿搭"],
    ))
    assert get_item(missing, "seo_body")["status"] == STATUS_WARN

    empty = run_checklist(make_checklist_payload(body="", seo_keywords=["秋冬穿搭"]))
    assert get_item(empty, "seo_body")["status"] == STATUS_WARN


def test_seo_tags_substring_hit_passes():
    # 标签是核心词的长尾组合（包含核心词）也算命中
    result = run_checklist(make_checklist_payload(
        tags=["学生党秋冬穿搭指南"], seo_keywords=["秋冬穿搭"],
    ))
    assert get_item(result, "seo_tags")["status"] == STATUS_PASS


def test_seo_tags_missing_warns_with_suggestion():
    result = run_checklist(make_checklist_payload(
        tags=["无关标签"], seo_keywords=["秋冬穿搭"],
    ))
    item = get_item(result, "seo_tags")
    assert item["status"] == STATUS_WARN
    assert "「秋冬穿搭」" in item["detail"]
    assert "长尾" in item["detail"]


def test_seo_keywords_capped_at_three():
    """超过 3 个词时只取前 3 个：第 4 个词命中不算数"""
    result = run_checklist(make_checklist_payload(
        title="第四词开头的标题",
        body="正文没有前三个词。",
        tags=["无关标签"],
        seo_keywords=["词一", "词二", "词三", "第四词"],
    ))
    assert get_item(result, "seo_title")["status"] == STATUS_WARN
    assert get_item(result, "seo_body")["status"] == STATUS_WARN
    assert get_item(result, "seo_tags")["status"] == STATUS_WARN


def test_seo_keywords_any_of_multiple_hits():
    """三个词里任一命中即 pass（标题命中第二个词）"""
    result = run_checklist(make_checklist_payload(
        title="显瘦穿搭的秘密",
        seo_keywords=["秋冬穿搭", "显瘦穿搭"],
    ))
    item = get_item(result, "seo_title")
    assert item["status"] == STATUS_PASS
    assert "「显瘦穿搭」" in item["detail"]


def test_checklist_route_passes_seo_keywords(client):
    response = client.post("/api/checklist", json={
        "platform": "xiaohongshu",
        "title": "秋冬穿搭公式大公开",
        "body": "秋冬穿搭最重要的是层次感。",
        "tags": ["秋冬穿搭"],
        "image_count": 4,
        "banned_words": [],
        "seo_keywords": ["秋冬穿搭"],
    })
    data = response.get_json()

    assert response.status_code == 200
    items = {item["id"]: item for item in data["items"]}
    assert items["seo_title"]["status"] == "pass"
    assert items["seo_body"]["status"] == "pass"
    assert items["seo_tags"]["status"] == "pass"
    assert len(data["items"]) == 10


def test_checklist_route_without_seo_keywords_unchanged(client):
    response = client.post("/api/checklist", json={
        "platform": "xiaohongshu",
        "title": "秋季穿搭",
        "body": "正文文案",
        "tags": ["穿搭"],
        "image_count": 4,
        "banned_words": [],
    })
    data = response.get_json()

    assert response.status_code == 200
    ids = [item["id"] for item in data["items"]]
    assert "seo_title" not in ids
    assert len(data["items"]) == 7
