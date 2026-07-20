"""
行业基准红绿灯（B10）测试：

- rate_by_benchmark 阈值评级（red / yellow / green / None）
- analytics_benchmarks.json 加载与损坏回退（回退内置默认值）
- get_stats 纯增量字段：metric_ratings / benchmarks_meta / 分组 engagement_rating
- list_records 每条记录附带 metrics 评级（不落盘）
- AI 洞察 prompt 注入基准表（模板占位符 + 生成时拼装）

数据目录用 tmp_path 隔离，AI 调用全 mock。
"""
import json
from pathlib import Path

import pytest

from backend.services import analytics as analytics_module
from backend.services.analytics import (
    ANALYTICS_BENCHMARKS,
    ANALYTICS_BENCHMARKS_META,
    AnalyticsService,
    RATING_GREEN,
    RATING_RED,
    RATING_YELLOW,
    _load_benchmarks,
    _validate_benchmarks_data,
    rate_by_benchmark,
)


def make_service(tmp_path: Path) -> AnalyticsService:
    service = AnalyticsService.__new__(AnalyticsService)
    service.analytics_dir = str(tmp_path)
    service.store_file = str(tmp_path / "records.json")
    service._init_store()
    return service


def record_payload(**overrides):
    payload = {
        "title": "测试标题",
        "platform": "小红书",
        "publish_date": "2026-07-01",
        "views": 1000,
        "likes": 30,
        "collects": 20,
        "comments": 5,
        "shares": 5,
    }
    payload.update(overrides)
    return payload


# ==================== 阈值评级 ====================

def test_rate_by_benchmark_thresholds():
    """engagement_rate：≥5 绿、3-5 黄、<3 红（阈值来自 JSON）。"""
    assert rate_by_benchmark("engagement_rate", 5.0) == RATING_GREEN
    assert rate_by_benchmark("engagement_rate", 8.2) == RATING_GREEN
    assert rate_by_benchmark("engagement_rate", 3.0) == RATING_YELLOW
    assert rate_by_benchmark("engagement_rate", 4.99) == RATING_YELLOW
    assert rate_by_benchmark("engagement_rate", 2.99) == RATING_RED
    assert rate_by_benchmark("engagement_rate", 0.0) == RATING_RED


def test_rate_by_benchmark_none_and_unknown_metric():
    assert rate_by_benchmark("engagement_rate", None) is None
    assert rate_by_benchmark("不存在的指标", 5.0) is None


# ==================== JSON 加载与回退 ====================

def test_benchmarks_loaded_from_json():
    """随包分发的 JSON 正常加载：四个指标齐全、来源标注仅供参考。"""
    for key in ("engagement_rate", "like_rate", "collect_rate", "comment_rate"):
        assert key in ANALYTICS_BENCHMARKS
        assert ANALYTICS_BENCHMARKS[key]["red_below"] <= ANALYTICS_BENCHMARKS[key]["green_at"]
    assert "仅供参考" in ANALYTICS_BENCHMARKS_META["source"]
    assert ANALYTICS_BENCHMARKS_META["version"] != "builtin"


def test_load_benchmarks_fallback_on_missing_file(monkeypatch):
    """JSON 读不到时整体回退内置默认值（version=builtin）。"""
    monkeypatch.setattr(
        analytics_module, "resource_path",
        lambda rel: "/nonexistent/analytics_benchmarks.json",
    )
    metrics, meta = _load_benchmarks()
    assert meta["version"] == "builtin"
    assert "engagement_rate" in metrics


def test_load_benchmarks_fallback_on_corrupted_structure(tmp_path, monkeypatch):
    """结构不完整（缺阈值/类型不对）视为损坏，整体回退。"""
    bad_file = tmp_path / "analytics_benchmarks.json"
    bad_file.write_text(
        json.dumps({"metrics": {"engagement_rate": {"label": "互动率", "red_below": "三"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(analytics_module, "resource_path", lambda rel: str(bad_file))
    metrics, meta = _load_benchmarks()
    assert meta["version"] == "builtin"
    assert isinstance(metrics["engagement_rate"]["red_below"], float)


@pytest.mark.parametrize("bad_metrics", [
    None, {}, "not-a-dict",
    {"engagement_rate": {"label": "", "red_below": 1.0, "green_at": 2.0}},   # label 为空
    {"engagement_rate": {"label": "互动率", "red_below": True, "green_at": 2.0}},  # bool 不算数值
    {"engagement_rate": {"label": "互动率", "red_below": 5.0, "green_at": 3.0}},   # 红线高于达标线
])
def test_validate_benchmarks_data_rejects_bad_structures(bad_metrics):
    assert _validate_benchmarks_data(bad_metrics) is False


# ==================== get_stats 增量字段 ====================

def test_stats_metric_ratings_and_meta(tmp_path):
    service = make_service(tmp_path)
    # 曝光 1000，互动 60 -> 互动率 6%（绿）；点赞率 3%（绿）；
    # 收藏率 2%（黄）；评论率 0.5%（绿）
    service.create_record(record_payload(likes=30, collects=20, comments=5, shares=5))
    stats = service.get_stats()

    ratings = stats["metric_ratings"]
    assert ratings["engagement_rate"]["value"] == 6.0
    assert ratings["engagement_rate"]["rating"] == RATING_GREEN
    assert ratings["collect_rate"]["value"] == 2.0
    assert ratings["collect_rate"]["rating"] == RATING_YELLOW
    assert ratings["comment_rate"]["rating"] == RATING_GREEN
    # 附带阈值与说明，供前端 hover 展示
    assert ratings["engagement_rate"]["green_at"] == 5.0
    assert ratings["engagement_rate"]["label"] == "互动率"
    assert ratings["engagement_rate"]["note"]

    assert "仅供参考" in stats["benchmarks_meta"]["source"]


def test_stats_metric_ratings_none_without_views(tmp_path):
    """无曝光数据时评级为 None（区别于 0% 的红灯）。"""
    service = make_service(tmp_path)
    service.create_record(record_payload(views=0, likes=0, collects=0, comments=0, shares=0))
    ratings = service.get_stats()["metric_ratings"]
    assert ratings["engagement_rate"]["value"] is None
    assert ratings["engagement_rate"]["rating"] is None


def test_stats_group_summary_has_engagement_rating(tmp_path):
    service = make_service(tmp_path)
    service.create_record(record_payload(platform="小红书", likes=60, collects=0, comments=0, shares=0))
    service.create_record(record_payload(platform="抖音", views=1000, likes=10, collects=0, comments=0, shares=0))

    platforms = {p["name"]: p for p in service.get_stats()["platforms"]}
    assert platforms["小红书"]["engagement_rating"] == RATING_GREEN   # 6%
    assert platforms["抖音"]["engagement_rating"] == RATING_RED      # 1%


def test_stats_old_fields_unchanged(tmp_path):
    """向后兼容：旧字段仍在，新字段为纯增量。"""
    service = make_service(tmp_path)
    service.create_record(record_payload())
    stats = service.get_stats()
    for key in ("total_records", "total_views", "avg_engagement_rate",
                "platforms", "content_types", "trend", "time_slots"):
        assert key in stats
    # 旧分组字段仍齐全（新加 engagement_rating）
    assert set(stats["platforms"][0].keys()) >= {
        "name", "count", "views", "likes", "collects",
        "comments", "shares", "followers_gained", "engagement_rate",
    }


# ==================== list_records 附带评级 ====================

def test_list_records_carries_metrics(tmp_path):
    service = make_service(tmp_path)
    service.create_record(record_payload(likes=60, collects=0, comments=0, shares=0))
    record = service.list_records()["records"][0]

    assert record["metrics"]["engagement_rate"]["value"] == 6.0
    assert record["metrics"]["engagement_rate"]["rating"] == RATING_GREEN
    assert record["metrics"]["like_rate"]["rating"] == RATING_GREEN


def test_list_records_metrics_not_persisted(tmp_path):
    """metrics 是响应计算字段，不能写回存储文件。"""
    service = make_service(tmp_path)
    service.create_record(record_payload())
    service.list_records()

    with open(service.store_file, "r", encoding="utf-8") as f:
        stored = json.load(f)
    assert "metrics" not in stored["records"][0]


def test_record_without_views_rating_none(tmp_path):
    service = make_service(tmp_path)
    service.create_record(record_payload(views=0, likes=0, collects=0, comments=0, shares=0))
    record = service.list_records()["records"][0]
    assert record["metrics"]["engagement_rate"]["rating"] is None


# ==================== AI 洞察 prompt 注入基准 ====================

class FakeClient:
    """捕获 prompt 并返回固定 JSON 的假客户端。"""

    def __init__(self):
        self.prompts = []

    def generate_text(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return '{"summary": "总结", "highlights": ["洞察"], "suggestions": ["建议"]}'


def test_generate_insight_prompt_includes_benchmarks(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    # 互动率 1%（红），距达标线 5% 差 4 个百分点
    service.create_record(record_payload(likes=10, collects=0, comments=0, shares=0))

    client = FakeClient()
    monkeypatch.setattr(
        AnalyticsService, "_load_text_config",
        staticmethod(lambda: {
            "active_provider": "mock",
            "providers": {"mock": {"type": "openai_compatible", "api_key": "k", "model": "m"}},
        }),
    )
    monkeypatch.setattr(AnalyticsService, "_get_client", staticmethod(lambda cfg: client))

    result = service.generate_insight()

    assert result["success"] is True
    prompt = client.prompts[0]
    # 基准表已注入（真实模板 + 真实基准 JSON 的端到端组合）
    assert "行业基准" in prompt
    assert "仅供参考" in prompt
    assert "互动率" in prompt and "达标线" in prompt
    assert "距达标线还差 4.0 个百分点" in prompt
    # 模板对洞察/建议提出基准对照要求
    assert "距离达标线还差多少" in prompt
    assert "最优先" in prompt


def test_build_benchmark_block_without_views(tmp_path):
    service = make_service(tmp_path)
    block = service._build_benchmark_block([record_payload(views=0)])
    assert "无曝光数据，无法评级" in block
