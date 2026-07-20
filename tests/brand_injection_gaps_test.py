"""
品牌记忆注入缺口补齐测试

覆盖 4 个此前缺失品牌人设注入的工具（不发起真实 LLM 调用，mock 底层文本客户端）：
- 评论洞察（InsightService）：痛点选题生成注入品牌人设约束
- 对标拆解（BenchmarkService）：仅在生成仿写草稿（有 my_topic）时注入人设，
  拆解分析保持客观
- 链接转图文（LinkExtractService）：大纲提炼注入人设，与主流程 outline 同构
- 单页润色（OutlineService.polish_page）：润色约束保持人设语气、不引入禁用词
- 路由层：insight（激活档案回退）/ benchmark / link / outline polish
  把解析出的品牌透传给服务
"""
import json

import pytest

from backend.routes import (
    benchmark_routes,
    insight_routes,
    link_routes,
    outline_routes,
)
from backend.services.benchmark import BenchmarkService
from backend.services.insight import InsightService
from backend.services.link_extract import LinkExtractService
from backend.services.outline import OutlineService


# 测试用品牌档案（与 brand_injection_test.py 保持一致的字段口径）
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


# ==================== 评论洞察 ====================

INSIGHT_RESPONSE = json.dumps({
    "pain_points": [{
        "theme": "新手不会选相机",
        "summary": "预算有限不知道怎么选",
        "frequency": 3,
        "evidence": ["求推荐相机"],
        "topics": [{"title": "两千预算相机推荐", "angle": "按预算给结论",
                    "format": "图文", "heat": 80, "tags": ["摄影"]}],
    }]
}, ensure_ascii=False)

INSIGHT_TEMPLATE = "领域:{niche} 评论:{comments}"

SAMPLE_COMMENTS = ["求推荐相机", "参数怎么调", "蹲入门教程"]


def test_insight_injects_brand_constraint():
    service = _assemble(InsightService, INSIGHT_RESPONSE, INSIGHT_TEMPLATE)

    result = service.mine_insights(SAMPLE_COMMENTS, niche="摄影教学", brand=BRAND)

    assert result["success"] is True
    prompt = service.client.prompts[0]
    assert "品牌人设约束" in prompt
    assert "元气小张" in prompt
    assert "活泼种草" in prompt
    assert "绝绝子" in prompt  # 禁用词也进入约束
    # 追加的选题贴合人设指令
    assert "选题" in prompt.split("品牌人设约束")[1]


def test_insight_without_brand_prompt_unchanged():
    service = _assemble(InsightService, INSIGHT_RESPONSE, INSIGHT_TEMPLATE)

    result = service.mine_insights(SAMPLE_COMMENTS, brand=None)

    assert result["success"] is True
    assert "品牌人设约束" not in service.client.prompts[0]


def test_insight_with_empty_brand_dict_silently_skipped():
    """品牌档案无有效字段时静默跳过注入，不影响主流程"""
    service = _assemble(InsightService, INSIGHT_RESPONSE, INSIGHT_TEMPLATE)

    result = service.mine_insights(SAMPLE_COMMENTS, brand={})

    assert result["success"] is True
    assert "品牌人设约束" not in service.client.prompts[0]


# ==================== 对标拆解 ====================

BENCHMARK_RESPONSE = json.dumps({
    "analysis": {
        "hook": "悬念钩子", "opening": "反差开头", "structure": ["起", "承"],
        "emotion": "共鸣", "audience": "新手", "viral_elements": ["数字"],
        "reusable_template": "【钩子】+【干货】",
    },
    "draft": "仿写草稿正文",
}, ensure_ascii=False)

BENCHMARK_TEMPLATE = "内容:{content}{draft_section}"


def test_benchmark_draft_injects_brand_constraint():
    service = _assemble(BenchmarkService, BENCHMARK_RESPONSE, BENCHMARK_TEMPLATE)

    result = service.analyze_benchmark("对标爆款正文", my_topic="30 天学会短视频", brand=BRAND)

    assert result["success"] is True
    assert result["draft"] == "仿写草稿正文"
    prompt = service.client.prompts[0]
    assert "品牌人设约束" in prompt
    assert "元气小张" in prompt
    assert "关注小张不迷路" in prompt
    assert "绝绝子" in prompt
    # 明确限定人设只作用于仿写草稿，拆解保持客观
    assert "作用于「仿写草稿」" in prompt
    assert "客观中立" in prompt


def test_benchmark_without_my_topic_skips_brand_injection():
    """不生成仿写草稿时不注入人设，避免干扰对别人内容的客观拆解"""
    service = _assemble(BenchmarkService, BENCHMARK_RESPONSE, BENCHMARK_TEMPLATE)

    result = service.analyze_benchmark("对标爆款正文", my_topic=None, brand=BRAND)

    assert result["success"] is True
    assert "品牌人设约束" not in service.client.prompts[0]


def test_benchmark_without_brand_prompt_unchanged():
    service = _assemble(BenchmarkService, BENCHMARK_RESPONSE, BENCHMARK_TEMPLATE)

    result = service.analyze_benchmark("对标爆款正文", my_topic="我的主题", brand=None)

    assert result["success"] is True
    assert "品牌人设约束" not in service.client.prompts[0]


# ==================== 链接转图文 ====================

LINK_RESPONSE = (
    "主题：手冲咖啡入门\n"
    "[封面]\n标题：手冲咖啡入门\n"
    "<page>\n[内容]\n第一步：磨豆\n"
    "<page>\n[总结]\n记住这三点"
)

LINK_TEMPLATE = "正文:{article_text}"


def test_link_extract_injects_brand_constraint():
    service = _assemble(LinkExtractService, LINK_RESPONSE, LINK_TEMPLATE)

    result = service.extract_outline(raw_text="一篇关于手冲咖啡的长文章" * 5, brand=BRAND)

    assert result["success"] is True
    assert len(result["pages"]) == 3
    prompt = service.client.prompts[0]
    assert "品牌人设约束" in prompt
    assert "元气小张" in prompt
    assert "绝绝子" in prompt


def test_link_extract_without_brand_prompt_unchanged():
    service = _assemble(LinkExtractService, LINK_RESPONSE, LINK_TEMPLATE)

    result = service.extract_outline(raw_text="一篇关于手冲咖啡的长文章" * 5, brand=None)

    assert result["success"] is True
    assert "品牌人设约束" not in service.client.prompts[0]


# ==================== 单页润色 ====================

def _polish_service(response_text) -> OutlineService:
    # polish_page 每次调用都从 prompts 目录加载真实润色模板，
    # 因此这里的 prompt_template 只是占位
    return _assemble(OutlineService, response_text, "")


def test_polish_page_injects_brand_constraint():
    service = _polish_service("润色后的文案")

    result = service.polish_page(
        content="原文内容", page_type="content", topic="主题",
        instruction="润色", brand=BRAND,
    )

    assert result["success"] is True
    prompt = service.client.prompts[0]
    assert "品牌人设约束" in prompt
    assert "活泼种草" in prompt
    assert "绝绝子" in prompt
    # 追加的润色专属指令：保持人设语气、不引入禁用词
    tail = prompt.split("品牌人设约束")[1]
    assert "语气" in tail
    assert "禁用词" in tail


def test_polish_page_without_brand_prompt_unchanged():
    service = _polish_service("润色后的文案")

    result = service.polish_page(content="原文内容", instruction="润色", brand=None)

    assert result["success"] is True
    assert "品牌人设约束" not in service.client.prompts[0]


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


def test_insight_route_passes_active_brand(client, monkeypatch):
    """insight 未传 brand_id 时回退「当前启用」档案（与 topic 路由同构）"""
    service = RecordingService("mine_insights", {
        "success": True,
        "pain_points": [{"theme": "t", "summary": "", "frequency": 1,
                         "evidence": [], "topics": [{"title": "x", "angle": "",
                                                     "format": "图文", "heat": 1,
                                                     "tags": []}]}],
        "comment_count": 1,
    })
    resolved = []

    def fake_resolve(brand_id=None):
        resolved.append(brand_id)
        return BRAND

    monkeypatch.setattr(insight_routes, "get_insight_service", lambda: service)
    monkeypatch.setattr(insight_routes, "resolve_brand_for_prompt", fake_resolve)

    response = client.post("/api/insight", json={"comments": ["求推荐相机"]})

    assert response.status_code == 200
    assert resolved == [None]  # 未传 brand_id，由解析函数回退激活档案
    assert service.calls[0]["kwargs"]["brand"] == BRAND


def test_benchmark_route_passes_brand_id(client, monkeypatch):
    service = RecordingService("analyze_benchmark", {
        "success": True,
        "analysis": {"hook": "", "opening": "", "structure": [], "emotion": "",
                     "audience": "", "viral_elements": [], "reusable_template": ""},
        "draft": "草稿",
    })
    resolved = []

    def fake_resolve(brand_id):
        resolved.append(brand_id)
        return BRAND

    monkeypatch.setattr(benchmark_routes, "get_benchmark_service", lambda: service)
    monkeypatch.setattr(benchmark_routes, "resolve_brand", fake_resolve)

    response = client.post("/api/benchmark", json={
        "content": "对标内容", "my_topic": "我的主题", "brand_id": "brand-001",
    })

    assert response.status_code == 200
    assert resolved == ["brand-001"]
    assert service.calls[0]["kwargs"]["brand"] == BRAND


def test_benchmark_route_without_brand_id_passes_none(client, monkeypatch):
    """benchmark 与 rewrite 同构：缺省 brand_id 时不回退激活档案"""
    service = RecordingService("analyze_benchmark", {
        "success": True,
        "analysis": {"hook": "", "opening": "", "structure": [], "emotion": "",
                     "audience": "", "viral_elements": [], "reusable_template": ""},
        "draft": "",
    })
    monkeypatch.setattr(benchmark_routes, "get_benchmark_service", lambda: service)

    response = client.post("/api/benchmark", json={"content": "对标内容"})

    assert response.status_code == 200
    assert service.calls[0]["kwargs"]["brand"] is None


def test_link_route_passes_brand_id(client, monkeypatch):
    service = RecordingService("extract_outline", {
        "success": True, "topic": "主题", "outline": "[封面]\n标题",
        "pages": [{"index": 0, "type": "cover", "content": "[封面]\n标题"}],
    })
    resolved = []

    def fake_resolve(brand_id):
        resolved.append(brand_id)
        return BRAND

    monkeypatch.setattr(link_routes, "get_link_extract_service", lambda: service)
    monkeypatch.setattr(link_routes, "resolve_brand", fake_resolve)

    response = client.post("/api/link/outline", json={
        "text": "一篇长文章内容", "brand_id": "brand-001",
    })

    assert response.status_code == 200
    assert resolved == ["brand-001"]
    assert service.calls[0]["kwargs"]["brand"] == BRAND


def test_polish_route_passes_brand(client, monkeypatch):
    service = RecordingService("polish_page", {"success": True, "content": "润色后"})
    resolved = []

    def fake_load_brand(brand_id):
        resolved.append(brand_id)
        return BRAND

    monkeypatch.setattr(outline_routes, "get_outline_service", lambda: service)
    monkeypatch.setattr(outline_routes, "_load_brand", fake_load_brand)

    response = client.post("/api/outline/polish", json={
        "content": "原文", "brand_id": "brand-001",
    })

    assert response.status_code == 200
    assert resolved == ["brand-001"]
    assert service.calls[0]["kwargs"]["brand"] == BRAND


def test_polish_route_without_brand_id_passes_none(client, monkeypatch):
    """polish 与 /outline 主流程同构：缺省 brand_id 时不回退激活档案"""
    service = RecordingService("polish_page", {"success": True, "content": "润色后"})
    monkeypatch.setattr(outline_routes, "get_outline_service", lambda: service)

    response = client.post("/api/outline/polish", json={"content": "原文"})

    assert response.status_code == 200
    assert service.calls[0]["kwargs"]["brand"] is None
