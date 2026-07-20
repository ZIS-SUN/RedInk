"""
发布前体检清单（run_checklist + POST /api/checklist）测试

纯规则引擎不依赖 LLM：
- 服务层：覆盖各平台标题超长、禁用词命中位置、标签数边界、
  图片数 0/超限、敏感营销词 warn、未知平台报错、summary 统计
- 路由层：覆盖参数校验 400、成功 200、禁用词品牌档案降级
"""
import pytest

from backend.routes import checklist_routes
from backend.services.checklist import (
    PLATFORM_RULES,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARN,
    run_checklist,
)


def make_payload(**overrides):
    """构造一份各项都合规的小红书默认请求，按需覆盖字段。"""
    payload = {
        "platform": "xiaohongshu",
        "title": "秋季通勤穿搭分享",
        "body": "这是一段合规的正文文案。",
        "tags": ["穿搭", "秋天", "通勤"],
        "image_count": 4,
        "banned_words": [],
    }
    payload.update(overrides)
    return payload


def get_item(result, item_id):
    """按 id 取出检查项。"""
    for item in result["items"]:
        if item["id"] == item_id:
            return item
    raise AssertionError(f"缺少检查项: {item_id}")


# ==================== 基本结构与 summary ====================

def test_all_pass_structure_and_summary():
    result = run_checklist(make_payload())

    assert result["success"] is True
    assert result["platform"] == "xiaohongshu"
    assert len(result["items"]) == 6
    for item in result["items"]:
        assert set(item.keys()) == {"id", "label", "status", "detail"}
    assert result["summary"] == {"pass": 6, "warn": 0, "fail": 0}


def test_summary_counts_match_items():
    # 同时制造 fail（图片 0）与 warn（标签 0 个）
    result = run_checklist(make_payload(image_count=0, tags=[]))

    summary = result["summary"]
    assert summary["pass"] + summary["warn"] + summary["fail"] == len(result["items"])
    assert get_item(result, "image_count")["status"] == STATUS_FAIL
    assert get_item(result, "tags_count")["status"] == STATUS_WARN


# ==================== 标题长度：各平台边界 ====================

@pytest.mark.parametrize("platform, limit, over_status", [
    ("xiaohongshu", 20, STATUS_FAIL),   # 硬限制
    ("douyin", 30, STATUS_WARN),        # 建议值
    ("weixin", 64, STATUS_FAIL),
    ("bilibili", 80, STATUS_FAIL),
    ("weibo", 30, STATUS_FAIL),
])
def test_title_length_per_platform(platform, limit, over_status):
    # 恰好等于上限：通过
    at_limit = run_checklist(make_payload(platform=platform, title="字" * limit))
    assert get_item(at_limit, "title_length")["status"] == STATUS_PASS

    # 超出 1 字：按平台级别报警
    over = run_checklist(make_payload(platform=platform, title="字" * (limit + 1)))
    item = get_item(over, "title_length")
    assert item["status"] == over_status
    assert str(limit) in item["detail"]


def test_title_length_strips_whitespace():
    # 首尾空白不计入字数：20 字标题加空白仍应通过小红书检查
    result = run_checklist(make_payload(title="  " + "字" * 20 + "\n"))
    assert get_item(result, "title_length")["status"] == STATUS_PASS


def test_empty_title_warns():
    result = run_checklist(make_payload(title=""))
    assert get_item(result, "title_length")["status"] == STATUS_WARN


# ==================== 正文长度 ====================

def test_body_length_xiaohongshu_hard_limit():
    result = run_checklist(make_payload(body="字" * 1001))
    item = get_item(result, "body_length")
    assert item["status"] == STATUS_FAIL
    assert "1000" in item["detail"]


def test_body_length_douyin_soft_limit():
    result = run_checklist(make_payload(platform="douyin", body="字" * 301))
    assert get_item(result, "body_length")["status"] == STATUS_WARN


def test_body_length_weibo_hard_limit():
    result = run_checklist(make_payload(platform="weibo", body="字" * 2001))
    assert get_item(result, "body_length")["status"] == STATUS_FAIL


# ==================== 标签数量边界 ====================

def test_tags_zero_warns_on_xiaohongshu():
    result = run_checklist(make_payload(tags=[]))
    assert get_item(result, "tags_count")["status"] == STATUS_WARN


def test_tags_upper_boundary_xiaohongshu():
    # 10 个通过，11 个 warn
    ok = run_checklist(make_payload(tags=[f"标签{i}" for i in range(10)]))
    assert get_item(ok, "tags_count")["status"] == STATUS_PASS

    over = run_checklist(make_payload(tags=[f"标签{i}" for i in range(11)]))
    assert get_item(over, "tags_count")["status"] == STATUS_WARN


def test_tags_upper_boundary_douyin():
    over = run_checklist(make_payload(
        platform="douyin", tags=[f"标签{i}" for i in range(6)]
    ))
    assert get_item(over, "tags_count")["status"] == STATUS_WARN


def test_tags_filters_blank_items():
    # 空白标签不计数：有效标签 3 个，应通过
    result = run_checklist(make_payload(tags=["穿搭", "", "  ", None, "秋天", "通勤"]))
    assert get_item(result, "tags_count")["status"] == STATUS_PASS


# ==================== 图片数量 ====================

def test_image_count_zero_fails():
    result = run_checklist(make_payload(image_count=0))
    item = get_item(result, "image_count")
    assert item["status"] == STATUS_FAIL


def test_image_count_over_limit_xiaohongshu_fails():
    # 18 张通过（平台上限），19 张 fail
    ok = run_checklist(make_payload(image_count=18))
    assert get_item(ok, "image_count")["status"] == STATUS_PASS

    over = run_checklist(make_payload(image_count=19))
    item = get_item(over, "image_count")
    assert item["status"] == STATUS_FAIL
    assert "18" in item["detail"]


def test_image_count_over_limit_weibo_warns():
    result = run_checklist(make_payload(platform="weibo", image_count=19))
    assert get_item(result, "image_count")["status"] == STATUS_WARN


def test_image_count_invalid_value_treated_as_zero():
    result = run_checklist(make_payload(image_count="not-a-number"))
    assert get_item(result, "image_count")["status"] == STATUS_FAIL


# ==================== 禁用词命中与位置 ====================

def test_banned_words_hit_reports_locations():
    result = run_checklist(make_payload(
        title="内含违禁词的标题",
        body="正文也提到了违禁词，还有另一个敏感品牌。",
        tags=["敏感品牌"],
        banned_words=["违禁词", "敏感品牌", "没出现的词"],
    ))

    item = get_item(result, "banned_words")
    assert item["status"] == STATUS_FAIL
    # 命中词与位置都要在 detail 中列出
    assert "违禁词" in item["detail"]
    assert "标题" in item["detail"]
    assert "正文" in item["detail"]
    assert "敏感品牌" in item["detail"]
    assert "标签" in item["detail"]
    # 未命中的词不应出现
    assert "没出现的词" not in item["detail"]


def test_banned_words_no_hit_passes():
    result = run_checklist(make_payload(banned_words=["违禁词"]))
    assert get_item(result, "banned_words")["status"] == STATUS_PASS


def test_banned_words_empty_list_passes():
    result = run_checklist(make_payload(banned_words=[]))
    assert get_item(result, "banned_words")["status"] == STATUS_PASS


# ==================== 敏感营销词软提示 ====================

def test_sensitive_marketing_words_warn():
    result = run_checklist(make_payload(
        title="全网第一的穿搭公式",
        body="百分百显瘦，绝对不踩雷。",
    ))

    item = get_item(result, "sensitive_words")
    assert item["status"] == STATUS_WARN
    assert "第一" in item["detail"]
    assert "百分百" in item["detail"]
    assert "绝对" in item["detail"]


def test_sensitive_words_clean_content_passes():
    result = run_checklist(make_payload())
    assert get_item(result, "sensitive_words")["status"] == STATUS_PASS


# ==================== 未知平台报错 ====================

@pytest.mark.parametrize("platform", ["", None, "zhihu", "XIAOHONGSHU"])
def test_unknown_platform_raises_value_error(platform):
    with pytest.raises(ValueError):
        run_checklist(make_payload(platform=platform))


def test_platform_rules_cover_all_five_platforms():
    assert set(PLATFORM_RULES.keys()) == {
        "xiaohongshu", "douyin", "weixin", "bilibili", "weibo",
    }


# ==================== 路由层 ====================

def test_route_missing_platform_returns_400(client):
    response = client.post("/api/checklist", json={"title": "标题"})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_route_unknown_platform_returns_400(client):
    response = client.post("/api/checklist", json={"platform": "zhihu"})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_route_success_returns_checklist(client):
    response = client.post("/api/checklist", json={
        "platform": "xiaohongshu",
        "title": "秋季穿搭",
        "body": "正文文案",
        "tags": ["穿搭", "秋天", "通勤"],
        "image_count": 4,
        "banned_words": [],
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["platform"] == "xiaohongshu"
    assert len(data["items"]) == 6
    assert data["summary"]["fail"] == 0


def test_route_explicit_banned_words_take_precedence(client, monkeypatch):
    # 显式传入 banned_words 时不应读品牌档案
    monkeypatch.setattr(
        checklist_routes, "_load_brand_banned_words",
        lambda: pytest.fail("显式传入禁用词时不应读取品牌档案"),
    )
    response = client.post("/api/checklist", json={
        "platform": "xiaohongshu",
        "title": "含品牌黑词的标题",
        "image_count": 1,
        "banned_words": ["品牌黑词"],
    })
    data = response.get_json()

    assert response.status_code == 200
    items = {item["id"]: item for item in data["items"]}
    assert items["banned_words"]["status"] == "fail"
    assert "品牌黑词" in items["banned_words"]["detail"]


def test_route_falls_back_to_brand_banned_words(client, monkeypatch):
    # 未传 banned_words 时自动读取品牌档案的禁用词
    monkeypatch.setattr(
        checklist_routes, "_load_brand_banned_words", lambda: ["档案黑词"],
    )
    response = client.post("/api/checklist", json={
        "platform": "douyin",
        "title": "标题里有档案黑词",
        "image_count": 1,
    })
    data = response.get_json()

    assert response.status_code == 200
    items = {item["id"]: item for item in data["items"]}
    assert items["banned_words"]["status"] == "fail"
    assert "档案黑词" in items["banned_words"]["detail"]


def test_route_brand_read_failure_degrades_silently(client, monkeypatch):
    # 品牌服务读取抛异常时静默降级为空列表，不影响 200 返回
    from backend.services import brand as brand_service_module

    class BrokenBrandService:
        def get_active_brand(self):
            raise RuntimeError("品牌数据文件损坏")

    monkeypatch.setattr(
        brand_service_module, "get_brand_service", lambda: BrokenBrandService(),
    )
    response = client.post("/api/checklist", json={
        "platform": "weibo",
        "title": "标题",
        "image_count": 1,
    })
    data = response.get_json()

    assert response.status_code == 200
    items = {item["id"]: item for item in data["items"]}
    assert items["banned_words"]["status"] == "pass"
