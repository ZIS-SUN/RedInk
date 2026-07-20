"""
数据复盘新增能力测试：
- 批量创建（service + /api/analytics/records/batch 端点）
- publish_time 宽松校验
- get_stats 的 time_slots 时段统计（只新增字段，旧字段保持兼容）

数据目录用 tmp_path 隔离（与 history 测试相同的 __new__ 构造方式），
端点测试通过 monkeypatch 替换路由模块里的 get_analytics_service。
"""
from pathlib import Path

import pytest

from backend.services.analytics import AnalyticsService


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
        "likes": 50,
        "collects": 30,
        "comments": 10,
        "shares": 10,
    }
    payload.update(overrides)
    return payload


# ==================== publish_time 校验 ====================

def test_publish_time_normalized_on_create(tmp_path):
    service = make_service(tmp_path)
    record = service.create_record(record_payload(publish_time="8:5"))
    assert record["publish_time"] == "08:05"


def test_publish_time_accepts_fullwidth_colon_and_seconds(tmp_path):
    service = make_service(tmp_path)
    assert service.create_record(record_payload(publish_time="21：30"))["publish_time"] == "21:30"
    assert service.create_record(record_payload(publish_time="09:15:59"))["publish_time"] == "09:15"


def test_publish_time_empty_is_allowed(tmp_path):
    service = make_service(tmp_path)
    assert service.create_record(record_payload())["publish_time"] == ""
    assert service.create_record(record_payload(publish_time=""))["publish_time"] == ""
    assert service.create_record(record_payload(publish_time=None))["publish_time"] == ""


@pytest.mark.parametrize("bad_time", ["25:00", "12:60", "abc", "12点30", "12"])
def test_publish_time_invalid_raises(tmp_path, bad_time):
    service = make_service(tmp_path)
    with pytest.raises(ValueError):
        service.create_record(record_payload(publish_time=bad_time))


def test_publish_time_update_and_clear(tmp_path):
    service = make_service(tmp_path)
    record = service.create_record(record_payload(publish_time="18:00"))

    updated = service.update_record(record["id"], {"publish_time": "22:30"})
    assert updated["publish_time"] == "22:30"

    cleared = service.update_record(record["id"], {"publish_time": ""})
    assert cleared["publish_time"] == ""

    with pytest.raises(ValueError):
        service.update_record(record["id"], {"publish_time": "99:99"})


# ==================== 批量创建（service 层） ====================

def test_batch_create_all_success(tmp_path):
    service = make_service(tmp_path)
    result = service.create_records_batch([
        record_payload(title="A"),
        record_payload(title="B", publish_time="20:00"),
    ])

    assert result["created"] == 2
    assert result["failed"] == []
    titles = {r["title"] for r in service.list_records()["records"]}
    assert titles == {"A", "B"}


def test_batch_create_partial_failure_reports_index(tmp_path):
    service = make_service(tmp_path)
    result = service.create_records_batch([
        record_payload(title="正常"),
        record_payload(title=""),  # 标题为空
        record_payload(title="时间非法", publish_time="99:00"),
        "不是对象",
    ])

    assert result["created"] == 1
    assert [f["index"] for f in result["failed"]] == [1, 2, 3]
    assert len(service.list_records()["records"]) == 1


def test_batch_create_over_limit_raises(tmp_path):
    service = make_service(tmp_path)
    with pytest.raises(ValueError):
        service.create_records_batch([record_payload() for _ in range(201)])
    # 超限时整批拒绝，不应有任何写入
    assert service.list_records()["records"] == []


@pytest.mark.parametrize("bad_items", [None, [], "not-a-list", {"a": 1}])
def test_batch_create_invalid_body_raises(tmp_path, bad_items):
    service = make_service(tmp_path)
    with pytest.raises(ValueError):
        service.create_records_batch(bad_items)


# ==================== 批量创建（端点） ====================

@pytest.fixture
def patched_service(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(
        "backend.routes.analytics_routes.get_analytics_service",
        lambda: service,
    )
    return service


def test_batch_endpoint_success(client, patched_service):
    resp = client.post("/api/analytics/records/batch", json={
        "records": [record_payload(title="A"), record_payload(title="B")],
    })

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["created"] == 2
    assert data["failed"] == []


def test_batch_endpoint_partial_failure(client, patched_service):
    resp = client.post("/api/analytics/records/batch", json={
        "records": [record_payload(title="A"), record_payload(platform="")],
    })

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["created"] == 1
    assert data["failed"][0]["index"] == 1
    assert "平台" in data["failed"][0]["error"]


def test_batch_endpoint_over_limit_returns_400(client, patched_service):
    resp = client.post("/api/analytics/records/batch", json={
        "records": [record_payload() for _ in range(201)],
    })
    assert resp.status_code == 400


def test_batch_endpoint_missing_records_returns_400(client, patched_service):
    assert client.post("/api/analytics/records/batch", json={}).status_code == 400
    assert client.post(
        "/api/analytics/records/batch", json={"records": "abc"}
    ).status_code == 400


# ==================== time_slots 统计 ====================

def test_time_slots_grouping_and_avg_engagement(tmp_path):
    service = make_service(tmp_path)
    # 晚间 18-22：两条，总曝光 2000，总互动 100+100=200 -> 10%
    service.create_record(record_payload(
        publish_time="18:00", views=1000, likes=100, collects=0, comments=0, shares=0))
    service.create_record(record_payload(
        publish_time="21:59", views=1000, likes=100, collects=0, comments=0, shares=0))
    # 早晨 6-9：一条，1000 曝光 50 互动 -> 5%
    service.create_record(record_payload(
        publish_time="06:00", views=1000, likes=50, collects=0, comments=0, shares=0))
    # 深夜 22-6（跨零点两侧）
    service.create_record(record_payload(publish_time="22:00", views=100, likes=1,
                                         collects=0, comments=0, shares=0))
    service.create_record(record_payload(publish_time="05:59", views=100, likes=1,
                                         collects=0, comments=0, shares=0))
    # 无 publish_time：不计入
    service.create_record(record_payload(views=999999, likes=0,
                                         collects=0, comments=0, shares=0))

    slots = {s["name"]: s for s in service.get_stats()["time_slots"]}

    assert slots["晚间 18-22"]["count"] == 2
    assert slots["晚间 18-22"]["avg_engagement"] == 10.0
    assert slots["早晨 6-9"]["count"] == 1
    assert slots["早晨 6-9"]["avg_engagement"] == 5.0
    assert slots["深夜 22-6"]["count"] == 2
    # 未填时间的记录不出现在任何时段
    assert sum(s["count"] for s in slots.values()) == 5


def test_time_slots_empty_when_no_publish_time(tmp_path):
    service = make_service(tmp_path)
    service.create_record(record_payload())
    assert service.get_stats()["time_slots"] == []


def test_get_stats_keeps_existing_fields(tmp_path):
    """向后兼容：旧字段一个都不能少、类型不变。"""
    service = make_service(tmp_path)
    service.create_record(record_payload(publish_time="19:00"))
    stats = service.get_stats()

    for key in ("total_records", "total_views", "total_likes", "total_collects",
                "total_comments", "total_shares", "total_followers_gained",
                "avg_engagement_rate"):
        assert key in stats
    assert isinstance(stats["platforms"], list)
    assert isinstance(stats["content_types"], list)
    assert isinstance(stats["trend"], list)
    # 旧分组字段一个都不能少（服务契约允许新增字段，如 B10 的 engagement_rating）
    assert set(stats["platforms"][0].keys()) >= {
        "name", "count", "views", "likes", "collects",
        "comments", "shares", "followers_gained", "engagement_rate",
    }


def test_data_summary_includes_time_slots(tmp_path):
    service = make_service(tmp_path)
    service.create_record(record_payload(publish_time="19:00"))
    summary = service._build_data_summary(service.list_records()["records"])
    assert "发布时段表现" in summary
    assert "晚间 18-22" in summary


def test_data_summary_omits_time_slots_without_data(tmp_path):
    service = make_service(tmp_path)
    service.create_record(record_payload())
    summary = service._build_data_summary(service.list_records()["records"])
    assert "发布时段表现" not in summary
