"""
批量大纲变体（抖音图文量产，B12）全链路测试

不发起真实 LLM 调用（mock 底层文本客户端 / mock 服务实例）：
- 维度归一化：normalize_variant_dimensions 过滤非法值并回落默认全选
- 标签与指令组装：build_variant_label / build_variant_instruction 轮转取指令，
  多套之间两两不同；未注入变体指令时 prompt 与旧行为完全一致
- 标题预览：extract_title_hint 取封面页首行并剥「标题：」前缀
- 服务层：generate_outline_variants 全成功 / 部分失败不中断整批（串行继续）
- 路由层：topic / count 参数校验（统一 400 错误响应）、默认值、
  brand_id / seo_keywords 透传
- 草稿建档：每套成功变体调用历史服务现有 create_record（标题带变体标注、
  outline 为 {raw, pages}），失败套不建档；建档抛异常计为该套失败；
  真实 HistoryService（临时目录）建档后状态为 draft
- 全部失败时走统一错误响应（非 200）
"""
import json

from backend.routes import outline_routes
from backend.services import history as history_module
from backend.services import outline as outline_module
from backend.services.outline import (
    DEFAULT_VARIANT_DIMENSIONS,
    OutlineService,
    VARIANT_INSTRUCTION_POOLS,
    build_variant_instruction,
    build_variant_label,
    extract_title_hint,
    normalize_variant_dimensions,
)


# ==================== 测试替身 ====================

class FakeTextClient:
    """记录 prompt 并返回固定文本的假文本客户端，可指定某几次调用抛错"""

    def __init__(self, response_text, fail_on_calls=()):
        self.prompts = []
        self.response_text = response_text
        # 第 N 次调用（1 起）抛错，模拟单套 LLM 调用失败
        self.fail_on_calls = set(fail_on_calls)

    def generate_text(self, prompt, model, temperature, max_output_tokens, **kwargs):
        self.prompts.append(prompt)
        if len(self.prompts) in self.fail_on_calls:
            raise RuntimeError("上游服务临时不可用")
        return self.response_text


FAKE_TEXT_CONFIG = {
    "active_provider": "fake",
    "providers": {"fake": {"api_key": "test-key", "model": "fake-model"}},
}

OUTLINE_RESPONSE = (
    "[封面]\n标题：秋冬穿搭公式\n副标题：新手友好\n"
    "<page>\n[内容]\n第一条内容\n"
    "<page>\n[总结]\n收尾互动"
)


def make_outline_service(fail_on_calls=()):
    """绕过 __init__（避免读取真实配置/API Key），手工装配服务依赖"""
    service = OutlineService.__new__(OutlineService)
    service.text_config = FAKE_TEXT_CONFIG
    service.client = FakeTextClient(OUTLINE_RESPONSE, fail_on_calls=fail_on_calls)
    service.prompt_template = "主题:{topic}"
    return service


class FakeVariantOutlineService:
    """记录调用参数并返回预设批量结果的假大纲服务（路由层测试用）"""

    def __init__(self, fail_indices=()):
        self.calls = []
        self.fail_indices = set(fail_indices)

    def generate_outline_variants(self, topic, count=3, dimensions=None,
                                  brand=None, seo_keywords=None):
        self.calls.append({
            "topic": topic,
            "count": count,
            "dimensions": dimensions,
            "brand": brand,
            "seo_keywords": seo_keywords,
        })
        dims = normalize_variant_dimensions(dimensions)
        variants = []
        for i in range(count):
            label = build_variant_label(i, dims)
            if i in self.fail_indices:
                variants.append({
                    "variant_index": i,
                    "variant_label": label,
                    "success": False,
                    "error": "API 认证失败。\n错误详情: 401 unauthorized",
                })
            else:
                variants.append({
                    "variant_index": i,
                    "variant_label": label,
                    "success": True,
                    "outline": OUTLINE_RESPONSE,
                    "pages": [
                        {"index": 0, "type": "cover",
                         "content": "[封面]\n标题：秋冬穿搭公式\n副标题：新手友好"},
                        {"index": 1, "type": "content", "content": "[内容]\n第一条内容"},
                        {"index": 2, "type": "summary", "content": "[总结]\n收尾互动"},
                    ],
                })
        succeeded = sum(1 for v in variants if v["success"])
        return {
            "success": True,
            "variants": variants,
            "succeeded": succeeded,
            "failed": count - succeeded,
        }


class FakeHistoryService:
    """记录建档调用并返回可预期 record_id 的假历史服务，可指定某几次调用抛错"""

    def __init__(self, fail_on_calls=()):
        self.calls = []
        # 第 N 次调用（1 起）抛错，模拟草稿建档失败
        self.fail_on_calls = set(fail_on_calls)

    def create_record(self, topic, outline, task_id=None, content=None):
        self.calls.append({"topic": topic, "outline": outline, "task_id": task_id})
        if len(self.calls) in self.fail_on_calls:
            raise RuntimeError("磁盘写入失败")
        return f"record-{len(self.calls)}"


def install_fakes(monkeypatch, outline_service=None, history_service=None):
    """把路由层依赖替换为测试替身，返回 (outline_service, history_service)"""
    outline_service = outline_service or FakeVariantOutlineService()
    history_service = history_service or FakeHistoryService()
    monkeypatch.setattr(
        outline_routes, "get_outline_service", lambda: outline_service
    )
    monkeypatch.setattr(
        outline_routes, "get_history_service", lambda: history_service
    )
    return outline_service, history_service


# ==================== 维度归一化与标签 ====================

def test_normalize_dimensions_default_when_missing_or_invalid():
    # 非列表 / 空列表 / 全非法值一律回落为默认全选
    for bad in (None, "hook", 42, [], ["nope", 1]):
        assert normalize_variant_dimensions(bad) == list(DEFAULT_VARIANT_DIMENSIONS)


def test_normalize_dimensions_keeps_order_and_dedupes():
    # 合法子集按默认顺序去重（与标签展示顺序一致）
    assert normalize_variant_dimensions(["format", "hook", "hook"]) == ["hook", "format"]
    assert normalize_variant_dimensions(["angle"]) == ["angle"]


def test_build_variant_label():
    assert build_variant_label(0, ["hook", "angle", "format"]) == "变体1·换钩子+换角度+换形式"
    assert build_variant_label(1, ["angle"]) == "变体2·换角度"
    # 非法维度回落默认全选
    assert build_variant_label(2, None) == "变体3·换钩子+换角度+换形式"


# ==================== 变体指令组装 ====================

def instruction_body(text):
    """去掉带套数序号的标题行，只留指令正文（用于比较套间差异）"""
    return "\n".join(text.splitlines()[2:])


def test_instruction_pools_have_three_to_four_entries_each():
    # 产品约定：三个维度各备 3-4 条具体中文指令
    assert set(VARIANT_INSTRUCTION_POOLS) == {"hook", "angle", "format"}
    for pool in VARIANT_INSTRUCTION_POOLS.values():
        assert 3 <= len(pool) <= 4
        assert all(isinstance(item, str) and item.startswith("本套") for item in pool)


def test_instruction_contains_one_entry_per_selected_dimension():
    text = build_variant_instruction(0, ["hook", "angle", "format"])
    assert "第 1 套变体" in text
    assert VARIANT_INSTRUCTION_POOLS["hook"][0] in text
    assert VARIANT_INSTRUCTION_POOLS["angle"][1] in text
    assert VARIANT_INSTRUCTION_POOLS["format"][2] in text


def test_instructions_pairwise_distinct_for_default_dimensions():
    # 默认全选三维度时，2-5 套的指令正文两两不同（错位轮转保证）
    bodies = [
        instruction_body(build_variant_instruction(i, None)) for i in range(5)
    ]
    assert len(set(bodies)) == 5


def test_instructions_rotate_within_single_dimension():
    # 单选一个维度时按池子轮转：池内条数范围内两两不同
    bodies = [
        instruction_body(build_variant_instruction(i, ["hook"])) for i in range(4)
    ]
    assert len(set(bodies)) == 4


def test_prompt_unchanged_without_variant_instruction(monkeypatch):
    # 屏蔽创作偏好画像，保证比较基准确定
    monkeypatch.setattr(outline_module, "load_preference_snippet", lambda: "")
    service = make_outline_service()

    base = service.build_outline_prompt("秋冬怎么穿")
    with_variant = service.build_outline_prompt(
        "秋冬怎么穿", variant_instruction=build_variant_instruction(0, None)
    )

    # 未注入变体指令时 prompt 与旧行为完全一致；注入时以追加方式融入
    assert "差异化要求" not in base
    assert with_variant.startswith(base)
    assert "本套大纲的差异化要求" in with_variant


# ==================== 标题预览 ====================

def test_extract_title_hint_from_cover_page():
    pages = [
        {"index": 0, "type": "cover", "content": "[封面]\n标题：五分钟学会手冲咖啡\n副标题：xx"},
        {"index": 1, "type": "content", "content": "[内容]\n正文"},
    ]
    assert extract_title_hint(pages) == "五分钟学会手冲咖啡"


def test_extract_title_hint_falls_back_to_first_page():
    # 无封面页时取第一页首行非空文案（无「标题：」前缀则原样返回）
    pages = [{"index": 0, "type": "content", "content": "[内容]\n直接就是正文首行"}]
    assert extract_title_hint(pages) == "直接就是正文首行"


def test_extract_title_hint_bad_structure_returns_empty():
    for bad in (None, [], [{"type": "cover"}], [{"type": "cover", "content": 42}]):
        assert extract_title_hint(bad) == ""


# ==================== 服务层：批量生成 ====================

def test_generate_variants_all_success(monkeypatch):
    monkeypatch.setattr(outline_module, "load_preference_snippet", lambda: "")
    service = make_outline_service()

    result = service.generate_outline_variants("秋冬怎么穿", count=3)

    assert result["success"] is True
    assert result["succeeded"] == 3 and result["failed"] == 0
    assert [v["variant_index"] for v in result["variants"]] == [0, 1, 2]
    for v in result["variants"]:
        assert v["success"] is True
        assert v["outline"] == OUTLINE_RESPONSE
        # 大纲已按 <page> 解析为页面列表
        assert [p["type"] for p in v["pages"]] == ["cover", "content", "summary"]

    # 串行 3 次付费调用，每次注入的差异化指令两两不同
    assert len(service.client.prompts) == 3
    assert len(set(service.client.prompts)) == 3
    for prompt in service.client.prompts:
        assert "本套大纲的差异化要求" in prompt


def test_generate_variants_partial_failure_continues(monkeypatch):
    monkeypatch.setattr(outline_module, "load_preference_snippet", lambda: "")
    # 第 2 次 LLM 调用抛错：该套失败，整批继续
    service = make_outline_service(fail_on_calls=(2,))

    result = service.generate_outline_variants("秋冬怎么穿", count=3)

    assert result["success"] is True
    assert result["succeeded"] == 2 and result["failed"] == 1
    assert [v["success"] for v in result["variants"]] == [True, False, True]
    assert "上游服务临时不可用" in result["variants"][1]["error"]
    # 失败不中断：3 次调用全部发生
    assert len(service.client.prompts) == 3


def test_generate_variants_passes_brand_and_seo(monkeypatch):
    monkeypatch.setattr(outline_module, "load_preference_snippet", lambda: "")
    service = make_outline_service()
    brand = {"name": "测试品牌", "tone": "亲切"}

    result = service.generate_outline_variants(
        "秋冬怎么穿", count=2, brand=brand, seo_keywords=["秋冬穿搭"]
    )

    assert result["succeeded"] == 2
    for prompt in service.client.prompts:
        # 品牌人设与搜索埋词按现有机制注入每一套
        assert "测试品牌" in prompt
        assert "目标搜索词埋入要求" in prompt


# ==================== 路由层：参数校验 ====================

def test_variants_route_requires_topic(client, monkeypatch):
    fake_outline, fake_history = install_fakes(monkeypatch)

    for payload in ({}, {"topic": ""}, {"topic": "   "}, {"topic": 123}):
        response = client.post("/api/outline/variants", json=payload)
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_REQUEST"

    # 校验失败不应产生任何 LLM 调用或建档
    assert fake_outline.calls == []
    assert fake_history.calls == []


def test_variants_route_rejects_invalid_count(client, monkeypatch):
    fake_outline, fake_history = install_fakes(monkeypatch)

    # 越界 / 非整数 / 布尔（bool 是 int 子类）一律 400
    for bad_count in (1, 6, 0, -3, "3", 3.5, True, None):
        response = client.post("/api/outline/variants", json={
            "topic": "秋冬怎么穿", "count": bad_count,
        })
        assert response.status_code == 400, f"count={bad_count!r} 应被拒绝"
        data = response.get_json()
        assert data["error"]["code"] == "INVALID_REQUEST"

    assert fake_outline.calls == []
    assert fake_history.calls == []


def test_variants_route_count_defaults_to_three(client, monkeypatch):
    fake_outline, _ = install_fakes(monkeypatch)

    response = client.post("/api/outline/variants", json={"topic": "秋冬怎么穿"})

    assert response.status_code == 200
    assert fake_outline.calls[0]["count"] == 3
    assert response.get_json()["total"] == 3


def test_variants_route_passes_dimensions_brand_and_seo(client, monkeypatch):
    fake_outline, _ = install_fakes(monkeypatch)
    # brand_id 经 _load_brand 解析后透传给服务层
    fake_brand = {"name": "测试品牌"}
    monkeypatch.setattr(
        outline_routes, "_load_brand",
        lambda brand_id: fake_brand if brand_id == "brand-1" else None,
    )

    response = client.post("/api/outline/variants", json={
        "topic": "秋冬怎么穿",
        "count": 2,
        "dimensions": ["hook", "format"],
        "brand_id": "brand-1",
        "seo_keywords": ["秋冬穿搭"],
    })

    assert response.status_code == 200
    call = fake_outline.calls[0]
    assert call["count"] == 2
    assert call["dimensions"] == ["hook", "format"]
    assert call["brand"] == fake_brand
    assert call["seo_keywords"] == ["秋冬穿搭"]


# ==================== 路由层：草稿建档与统计 ====================

def test_variants_route_creates_draft_per_success(client, monkeypatch):
    fake_outline, fake_history = install_fakes(monkeypatch)

    response = client.post("/api/outline/variants", json={
        "topic": "秋冬怎么穿", "count": 3,
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["total"] == 3
    assert data["succeeded"] == 3 and data["failed"] == 0

    # 每套成功变体各建一条草稿，标题带变体标注
    assert len(fake_history.calls) == 3
    assert fake_history.calls[0]["topic"] == "秋冬怎么穿【变体1·换钩子+换角度+换形式】"
    assert fake_history.calls[1]["topic"] == "秋冬怎么穿【变体2·换钩子+换角度+换形式】"
    for call in fake_history.calls:
        # 建档 outline 结构与现有建档方式一致：{raw, pages}
        assert call["outline"]["raw"] == OUTLINE_RESPONSE
        assert len(call["outline"]["pages"]) == 3

    # 响应逐套包含 record_id / variant_label / title_hint / page_count
    for i, variant in enumerate(data["variants"]):
        assert variant["success"] is True
        assert variant["record_id"] == f"record-{i + 1}"
        assert variant["variant_label"] == f"变体{i + 1}·换钩子+换角度+换形式"
        assert variant["title_hint"] == "秋冬穿搭公式"
        assert variant["page_count"] == 3


def test_variants_route_partial_failure_stats(client, monkeypatch):
    # 第 2 套 LLM 生成失败：如实统计成功/失败，失败套不建档
    fake_outline = FakeVariantOutlineService(fail_indices=(1,))
    _, fake_history = install_fakes(monkeypatch, outline_service=fake_outline)

    response = client.post("/api/outline/variants", json={
        "topic": "秋冬怎么穿", "count": 3,
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["succeeded"] == 2 and data["failed"] == 1
    # 只有成功的 2 套建档
    assert len(fake_history.calls) == 2

    failed_variant = data["variants"][1]
    assert failed_variant["success"] is False
    assert failed_variant["variant_label"] == "变体2·换钩子+换角度+换形式"
    assert "API 认证失败" in failed_variant["error"]
    assert "record_id" not in failed_variant


def test_variants_route_archive_failure_counts_as_failed(client, monkeypatch):
    # LLM 全成功，但第 2 次建档抛异常：该套计为失败，整批继续
    fake_history = FakeHistoryService(fail_on_calls=(2,))
    install_fakes(monkeypatch, history_service=fake_history)

    response = client.post("/api/outline/variants", json={
        "topic": "秋冬怎么穿", "count": 3,
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["succeeded"] == 2 and data["failed"] == 1
    # 3 次建档尝试都发生（失败不中断后续建档）
    assert len(fake_history.calls) == 3
    assert data["variants"][1]["success"] is False
    assert "草稿保存失败" in data["variants"][1]["error"]


def test_variants_route_all_failed_returns_error(client, monkeypatch):
    # 整批全部失败：走统一错误响应（非 200），错误结构化
    fake_outline = FakeVariantOutlineService(fail_indices=(0, 1))
    _, fake_history = install_fakes(monkeypatch, outline_service=fake_outline)

    response = client.post("/api/outline/variants", json={
        "topic": "秋冬怎么穿", "count": 2,
    })
    data = response.get_json()

    assert response.status_code >= 400
    assert data["success"] is False
    assert data["error"]["code"]
    assert data["error_message"]
    assert fake_history.calls == []


def test_variants_route_real_history_service_creates_draft(client, monkeypatch, tmp_path):
    """用真实 HistoryService（临时目录）验证草稿建档：status=draft、标题带标注"""
    fake_outline = FakeVariantOutlineService()
    monkeypatch.setattr(outline_routes, "get_outline_service", lambda: fake_outline)
    # 历史服务指向临时目录并重置单例（不触碰真实用户数据）
    monkeypatch.setattr(history_module, "get_data_root", lambda: tmp_path)
    monkeypatch.setattr(history_module, "_service_instance", None)

    response = client.post("/api/outline/variants", json={
        "topic": "秋冬怎么穿", "count": 2,
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["succeeded"] == 2

    service = history_module.get_history_service()
    for variant in data["variants"]:
        record = service.get_record(variant["record_id"])
        assert record is not None
        # 现有建档方式：初始状态即草稿
        assert record["status"] == "draft"
        assert record["title"].startswith("秋冬怎么穿【变体")
        assert len(record["outline"]["pages"]) == 3

    # 索引同样落了 2 条草稿记录
    listing = service.list_records(status="draft")
    assert listing["total"] == 2


def test_variants_route_response_is_json_serializable(client, monkeypatch):
    """响应体可完整 JSON 序列化（防止 pages 等复杂结构漏进响应）"""
    install_fakes(monkeypatch)

    response = client.post("/api/outline/variants", json={
        "topic": "秋冬怎么穿", "count": 2,
    })

    payload = json.loads(response.get_data(as_text=True))
    # 成功套只暴露约定的四个业务字段 + success 标记
    for variant in payload["variants"]:
        assert set(variant.keys()) == {
            "success", "record_id", "variant_label", "title_hint", "page_count",
        }
