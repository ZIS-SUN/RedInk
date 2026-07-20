"""
热点节点（营销日历图层）测试：

- 服务层：日期区间过滤、排序、农历对照表抽查（2026 春节 2/17 等）、
  超出对照表年份的优雅降级、参数校验、默认区间归一化
- 路由层：GET /api/hotspots 成功 / 参数校验 400 / 无参数默认未来 60 天

蓝图不经 create_app 注册（避免与其他功能的路由注册耦合），
测试自建 Flask app 注册 create_hotspot_blueprint()。
纯本地静态数据，不发起任何 LLM/外部调用。
"""

from datetime import date, timedelta

import pytest
from flask import Flask

from backend.routes.hotspot_routes import create_hotspot_blueprint
from backend.services.hotspot import (
    DEFAULT_RANGE_DAYS,
    HOTSPOT_TYPES,
    LUNAR_YEARS,
    get_hotspots,
    resolve_range,
)


# ==================== 服务层：区间过滤与排序 ====================

def test_range_filter_includes_boundaries():
    """区间过滤含端点：情人节当天作为 start/end 都能命中。"""
    hotspots = get_hotspots("2026-02-14", "2026-02-14")
    assert [n["name"] for n in hotspots] == ["情人节"]


def test_range_filter_excludes_outside_dates():
    """区间外的节点不返回。"""
    hotspots = get_hotspots("2026-02-15", "2026-02-16")
    assert hotspots == []


def test_nodes_sorted_by_date_ascending():
    dates = [n["date"] for n in get_hotspots("2026-01-01", "2026-12-31")]
    assert dates == sorted(dates)


def test_cross_year_range_returns_both_years():
    hotspots = get_hotspots("2026-12-20", "2027-01-05")
    names = {(n["date"], n["name"]) for n in hotspots}
    assert ("2026-12-25", "圣诞节") in names
    assert ("2027-01-01", "元旦") in names


def test_node_fields_complete_and_valid():
    """每个节点都带完整字段，类型与备稿天数在约定范围内。"""
    hotspots = get_hotspots("2026-01-01", "2026-12-31")
    assert len(hotspots) > 0
    for node in hotspots:
        assert node["id"]
        assert node["name"]
        assert node["date"].startswith("2026-")
        assert node["type"] in HOTSPOT_TYPES
        assert 3 <= node["prep_days"] <= 14
        assert node["platform_hint"]
        assert node["niche_hint"]


def test_all_three_types_present_in_full_year():
    types = {n["type"] for n in get_hotspots("2026-01-01", "2026-12-31")}
    assert types == set(HOTSPOT_TYPES)


# ==================== 服务层：农历对照表抽查 ====================

@pytest.mark.parametrize("day, name", [
    ("2026-02-17", "春节"),
    ("2026-03-03", "元宵节"),
    ("2026-06-19", "端午节"),
    ("2026-08-19", "七夕节"),
    ("2026-09-25", "中秋节"),
    ("2026-10-18", "重阳节"),
    ("2027-02-06", "春节"),
    ("2027-09-15", "中秋节"),
    ("2028-01-26", "春节"),
    ("2028-08-26", "七夕节"),
    ("2028-10-03", "中秋节"),
    ("2028-10-26", "重阳节"),
])
def test_lunar_festival_dates(day, name):
    """农历节日公历对照抽查（对照公开万年历 2026-2028）。"""
    hotspots = get_hotspots(day, day)
    assert name in [n["name"] for n in hotspots]


def test_lunar_festival_count_within_covered_years():
    """对照表覆盖年份内，全年应有 6 个农历节日。"""
    for year in LUNAR_YEARS:
        lunar_names = {
            n["name"] for n in get_hotspots(f"{year}-01-01", f"{year}-12-31")
            if n["name"] in ("春节", "元宵节", "端午节", "七夕节", "中秋节", "重阳节")
        }
        assert len(lunar_names) == 6, f"{year} 年农历节日缺失: {lunar_names}"


def test_year_beyond_lunar_table_degrades_gracefully():
    """超出对照表范围的年份：无农历节点，但公历/规则节点照常返回。"""
    beyond_year = max(LUNAR_YEARS) + 2  # 2030
    hotspots = get_hotspots(f"{beyond_year}-01-01", f"{beyond_year}-12-31")

    names = [n["name"] for n in hotspots]
    assert "春节" not in names
    assert "中秋节" not in names
    # 公历固定节点与周期性节点仍然齐全
    assert "元旦" in names
    assert "双 11" in names
    assert "年终总结季" in names


# ==================== 服务层：参数校验与默认区间 ====================

@pytest.mark.parametrize("start, end", [
    ("2026/01/01", "2026-02-01"),
    ("2026-01-01", "abc"),
    ("", "2026-02-01"),
    ("2026-13-01", "2026-02-01"),
])
def test_get_hotspots_invalid_date_raises(start, end):
    with pytest.raises(ValueError):
        get_hotspots(start, end)


def test_get_hotspots_start_after_end_raises():
    with pytest.raises(ValueError):
        get_hotspots("2026-03-01", "2026-02-01")


def test_resolve_range_defaults_to_next_60_days():
    today = date(2026, 2, 1)
    start, end = resolve_range(None, None, today=today)
    assert start == "2026-02-01"
    assert end == (today + timedelta(days=DEFAULT_RANGE_DAYS)).isoformat()


def test_resolve_range_missing_end_defaults_from_start():
    start, end = resolve_range("2026-05-01", None, today=date(2026, 2, 1))
    assert start == "2026-05-01"
    assert end == "2026-06-30"


def test_resolve_range_keeps_explicit_range():
    assert resolve_range("2026-01-01", "2026-01-31") == ("2026-01-01", "2026-01-31")


def test_resolve_range_invalid_or_reversed_raises():
    with pytest.raises(ValueError):
        resolve_range("2026-1-1", None)
    with pytest.raises(ValueError):
        resolve_range("2026-03-01", "2026-02-01")


# ==================== 路由层 ====================

@pytest.fixture
def client():
    """自建 Flask app 注册蓝图（不经 create_app）。"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_hotspot_blueprint(), url_prefix="/api")
    return app.test_client()


def test_hotspots_route_with_range(client):
    resp = client.get("/api/hotspots?start=2026-02-01&end=2026-02-28")
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["success"] is True
    assert data["start"] == "2026-02-01"
    assert data["end"] == "2026-02-28"

    by_name = {n["name"]: n for n in data["hotspots"]}
    assert by_name["春节"]["date"] == "2026-02-17"
    assert by_name["情人节"]["date"] == "2026-02-14"


def test_hotspots_route_default_range_is_next_60_days(client):
    resp = client.get("/api/hotspots")
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["success"] is True

    today = date.today()
    assert data["start"] == today.isoformat()
    assert data["end"] == (today + timedelta(days=DEFAULT_RANGE_DAYS)).isoformat()
    for node in data["hotspots"]:
        assert data["start"] <= node["date"] <= data["end"]


@pytest.mark.parametrize("query", [
    "start=2026-1-1",
    "end=20260201",
    "start=2026-02-30&end=2026-03-01",
    "start=2026-03-01&end=2026-02-01",
])
def test_hotspots_route_invalid_params_return_400(client, query):
    resp = client.get(f"/api/hotspots?{query}")
    data = resp.get_json()

    assert resp.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
