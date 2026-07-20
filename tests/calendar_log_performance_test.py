"""
发布闭环（日历一键转录到数据复盘）测试：

- analytics 表现记录新字段 record_id / calendar_plan_id 的 create/update/旧数据兼容
- AnalyticsService.upsert_record_for_plan 幂等写入（重复转录更新而非新建）
- CalendarService.log_performance 预填 title/platform/publish_date/publish_time/record_id
- POST /api/plans/<plan_id>/log-performance 路由（成功 / 重复转录 / 404 / 400）

不发起真实 LLM 调用，不读写真实数据目录（get_data_root 指向 tmp_path）。
"""
import json

import pytest

from backend.services import analytics as analytics_module
from backend.services import calendar_plan as calendar_module
from backend.services.analytics import AnalyticsService
from backend.services.calendar_plan import CalendarService


# ==================== 公共 fixtures ====================

@pytest.fixture
def analytics_service(tmp_path, monkeypatch):
    """存储指向临时目录的 AnalyticsService"""
    monkeypatch.setattr(analytics_module, "get_data_root", lambda: tmp_path)
    return AnalyticsService()


@pytest.fixture
def calendar_service(tmp_path, monkeypatch):
    """
    存储指向临时目录的 CalendarService。

    log_performance 内部通过 get_analytics_service() 单例访问复盘存储，
    因此同时把 analytics 的数据根与单例一并指向/重置到临时环境。
    """
    monkeypatch.setattr(calendar_module, "get_data_root", lambda: tmp_path)
    monkeypatch.setattr(analytics_module, "get_data_root", lambda: tmp_path)
    monkeypatch.setattr(analytics_module, "_service_instance", None)
    return CalendarService()


def record_payload(**overrides):
    payload = {
        "title": "测试标题",
        "platform": "小红书",
        "publish_date": "2026-07-01",
        "views": 1000,
        "likes": 50,
    }
    payload.update(overrides)
    return payload


# ==================== analytics 新字段：create / update ====================

def test_create_record_with_link_fields(analytics_service):
    record = analytics_service.create_record(record_payload(
        record_id="work-001", calendar_plan_id="plan-001",
    ))
    assert record["record_id"] == "work-001"
    assert record["calendar_plan_id"] == "plan-001"

    # 落盘后读取也带新字段
    stored = analytics_service.get_record(record["id"])
    assert stored["record_id"] == "work-001"
    assert stored["calendar_plan_id"] == "plan-001"


def test_create_record_defaults_link_fields_to_empty(analytics_service):
    record = analytics_service.create_record(record_payload())
    assert record["record_id"] == ""
    assert record["calendar_plan_id"] == ""


def test_update_record_link_fields(analytics_service):
    record = analytics_service.create_record(record_payload())

    updated = analytics_service.update_record(record["id"], {
        "record_id": "work-xyz", "calendar_plan_id": "plan-xyz",
    })
    assert updated["record_id"] == "work-xyz"
    assert updated["calendar_plan_id"] == "plan-xyz"

    # 清空
    cleared = analytics_service.update_record(record["id"], {
        "record_id": "", "calendar_plan_id": "",
    })
    assert cleared["record_id"] == ""
    assert cleared["calendar_plan_id"] == ""


def test_legacy_records_without_link_fields_read_ok(analytics_service):
    """旧数据（无 record_id / calendar_plan_id 字段）读取、统计、更新都不报错"""
    legacy = {
        "id": "legacy-1",
        "title": "旧记录",
        "platform": "小红书",
        "publish_date": "2026-06-01",
        "content_type": "",
        "views": 100,
        "likes": 10,
        "collects": 0,
        "comments": 0,
        "shares": 0,
        "followers_gained": 0,
        "notes": "",
        "created_at": "2026-06-01T00:00:00",
        "updated_at": "2026-06-01T00:00:00",
    }
    with open(analytics_service.store_file, "w", encoding="utf-8") as f:
        json.dump({"records": [legacy]}, f, ensure_ascii=False)

    records = analytics_service.list_records()["records"]
    assert len(records) == 1
    assert records[0]["id"] == "legacy-1"

    stats = analytics_service.get_stats()
    assert stats["total_records"] == 1

    # 部分更新老记录不报错，并可补写关联字段
    updated = analytics_service.update_record("legacy-1", {"calendar_plan_id": "plan-1"})
    assert updated["calendar_plan_id"] == "plan-1"


# ==================== upsert_record_for_plan 幂等写入 ====================

def test_upsert_creates_then_updates_same_record(analytics_service):
    first = analytics_service.upsert_record_for_plan("plan-1", record_payload(views=100))
    assert first["created"] is True
    assert first["record"]["calendar_plan_id"] == "plan-1"
    assert first["record"]["views"] == 100

    # 同一日历条目重复转录：更新已有记录而非新建
    second = analytics_service.upsert_record_for_plan(
        "plan-1", record_payload(views=999, likes=88),
    )
    assert second["created"] is False
    assert second["record"]["id"] == first["record"]["id"]
    assert second["record"]["views"] == 999
    assert second["record"]["likes"] == 88

    assert len(analytics_service.list_records()["records"]) == 1


def test_upsert_different_plans_create_separate_records(analytics_service):
    analytics_service.upsert_record_for_plan("plan-a", record_payload(title="A"))
    result = analytics_service.upsert_record_for_plan("plan-b", record_payload(title="B"))
    assert result["created"] is True
    assert len(analytics_service.list_records()["records"]) == 2


def test_upsert_empty_plan_id_raises(analytics_service):
    with pytest.raises(ValueError):
        analytics_service.upsert_record_for_plan("", record_payload())
    with pytest.raises(ValueError):
        analytics_service.upsert_record_for_plan(None, record_payload())


# ==================== CalendarService.log_performance ====================

def test_log_performance_prefills_from_plan(calendar_service):
    plan = calendar_service.create_plan({
        "title": "夏日防晒合集",
        "platform": "douyin",
        "publish_date": "2026-08-01",
        "publish_time": "19:30",
        "record_id": "work-007",
    })

    result = calendar_service.log_performance(plan["id"], {"views": 5000, "likes": 300})

    assert result["created"] is True
    record = result["record"]
    assert record["title"] == "夏日防晒合集"
    assert record["platform"] == "抖音"          # 平台 code 转中文名
    assert record["publish_date"] == "2026-08-01"
    assert record["publish_time"] == "19:30"
    assert record["record_id"] == "work-007"     # 回写作品关联
    assert record["calendar_plan_id"] == plan["id"]  # 回写日历条目关联
    assert record["views"] == 5000
    assert record["likes"] == 300


def test_log_performance_user_fields_override_prefill(calendar_service):
    plan = calendar_service.create_plan({
        "title": "计划标题", "platform": "xiaohongshu",
        "publish_date": "2026-08-01", "publish_time": "10:00",
    })

    result = calendar_service.log_performance(plan["id"], {
        "title": "实际发布标题",
        "publish_date": "2026-08-02",
        "publish_time": "21:00",
        "content_type": "干货教程",
    })

    record = result["record"]
    assert record["title"] == "实际发布标题"
    assert record["publish_date"] == "2026-08-02"
    assert record["publish_time"] == "21:00"
    assert record["content_type"] == "干货教程"
    assert record["platform"] == "小红书"  # 未覆盖的仍用预填


def test_log_performance_plan_without_record_id_leaves_link_empty(calendar_service):
    plan = calendar_service.create_plan({
        "title": "未关联作品的计划", "publish_date": "2026-08-01",
    })
    record = calendar_service.log_performance(plan["id"], {})["record"]
    assert record["record_id"] == ""
    assert record["calendar_plan_id"] == plan["id"]


def test_log_performance_repeat_updates_existing(calendar_service):
    plan = calendar_service.create_plan({
        "title": "重复转录", "publish_date": "2026-08-01",
    })

    first = calendar_service.log_performance(plan["id"], {"views": 100})
    second = calendar_service.log_performance(plan["id"], {"views": 2000})

    assert first["created"] is True
    assert second["created"] is False
    assert second["record"]["id"] == first["record"]["id"]
    assert second["record"]["views"] == 2000

    from backend.services.analytics import get_analytics_service
    assert len(get_analytics_service().list_records()["records"]) == 1


def test_log_performance_missing_plan_returns_none(calendar_service):
    assert calendar_service.log_performance("no-such-plan", {"views": 1}) is None


def test_log_performance_invalid_time_raises(calendar_service):
    plan = calendar_service.create_plan({
        "title": "坏时间", "publish_date": "2026-08-01",
    })
    with pytest.raises(ValueError):
        calendar_service.log_performance(plan["id"], {"publish_time": "晚上八点"})


# ==================== 路由层 ====================

@pytest.fixture
def route_store(tmp_path, monkeypatch):
    """路由测试：日历与复盘存储都指向临时目录（重置两侧单例）"""
    monkeypatch.setattr(calendar_module, "get_data_root", lambda: tmp_path)
    monkeypatch.setattr(calendar_module, "_service_instance", None)
    monkeypatch.setattr(analytics_module, "get_data_root", lambda: tmp_path)
    monkeypatch.setattr(analytics_module, "_service_instance", None)
    return tmp_path


def _create_plan_via_api(client, **overrides):
    payload = {
        "title": "路由转录计划",
        "platform": "xiaohongshu",
        "publish_date": "2026-08-01",
        "publish_time": "18:30",
    }
    payload.update(overrides)
    resp = client.post("/api/plans", json=payload)
    assert resp.status_code == 200
    return resp.get_json()["plan"]


def test_log_performance_route_success(client, route_store):
    plan = _create_plan_via_api(client, record_id="work-r1")

    resp = client.post(
        f"/api/plans/{plan['id']}/log-performance",
        json={"views": 1200, "likes": 66},
    )
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["success"] is True
    assert data["created"] is True
    record = data["record"]
    assert record["title"] == "路由转录计划"
    assert record["platform"] == "小红书"
    assert record["publish_date"] == "2026-08-01"
    assert record["publish_time"] == "18:30"
    assert record["record_id"] == "work-r1"
    assert record["calendar_plan_id"] == plan["id"]
    assert record["views"] == 1200

    # 转录结果出现在复盘记录列表中
    records_resp = client.get("/api/analytics/records")
    records = records_resp.get_json()["records"]
    assert len(records) == 1
    assert records[0]["calendar_plan_id"] == plan["id"]


def test_log_performance_route_repeat_updates(client, route_store):
    plan = _create_plan_via_api(client)

    first = client.post(f"/api/plans/{plan['id']}/log-performance", json={"views": 10})
    second = client.post(f"/api/plans/{plan['id']}/log-performance", json={"views": 500})

    assert first.get_json()["created"] is True
    assert second.get_json()["created"] is False
    assert second.get_json()["record"]["id"] == first.get_json()["record"]["id"]

    records = client.get("/api/analytics/records").get_json()["records"]
    assert len(records) == 1
    assert records[0]["views"] == 500


def test_log_performance_route_missing_plan_returns_404(client, route_store):
    resp = client.post("/api/plans/no-such-plan/log-performance", json={"views": 1})
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_log_performance_route_invalid_time_returns_400(client, route_store):
    plan = _create_plan_via_api(client)
    resp = client.post(
        f"/api/plans/{plan['id']}/log-performance",
        json={"publish_time": "abc"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False
