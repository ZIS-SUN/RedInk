"""
内容日历升级测试：

- PlanItem 新字段 record_id / publish_time 的 create/update/旧数据兼容
- generate_week_plan（mock LLM：正常、坏 JSON、日期出界钳制、frequency 钳制、坏条目丢弃）
- POST /api/plans/generate-week 路由参数校验与透传

不发起真实 LLM 调用，不读写真实数据目录（get_data_root 指向 tmp_path）。
"""
import json
from datetime import datetime, timedelta

import pytest

from backend.routes import calendar_routes
from backend.services import calendar_plan as calendar_module
from backend.services.calendar_plan import CalendarService, generate_week_plan, next_monday


# ==================== 公共 fixtures / fakes ====================

@pytest.fixture
def service(tmp_path, monkeypatch):
    """存储指向临时目录的 CalendarService"""
    monkeypatch.setattr(calendar_module, "get_data_root", lambda: tmp_path)
    return CalendarService()


class FakeTextClient:
    """记录 prompt 并返回固定文本的假文本客户端"""

    def __init__(self, response_text):
        self.prompts = []
        self.response_text = response_text

    def generate_text(self, prompt, model, temperature, max_output_tokens, **kwargs):
        self.prompts.append(prompt)
        return self.response_text


def _mock_llm(monkeypatch, response_text):
    """把 calendar_plan 模块的 LLM 依赖替换为假实现"""
    client = FakeTextClient(response_text)
    monkeypatch.setattr(
        calendar_module, "load_text_config",
        lambda **kwargs: {
            "active_provider": "fake",
            "providers": {"fake": {"api_key": "test-key", "model": "fake-model"}},
        },
    )
    monkeypatch.setattr(calendar_module, "get_text_client", lambda cfg: client)
    return client


def _week_response(items):
    return json.dumps({"plans": items}, ensure_ascii=False)


START = "2026-07-27"  # 一个周一


# ==================== 新字段：create ====================

def test_create_plan_with_new_fields(service):
    plan = service.create_plan({
        "title": "夏日防晒合集",
        "publish_date": "2026-08-01",
        "publish_time": "19:30",
        "record_id": "rec-001",
    })

    assert plan["publish_time"] == "19:30"
    assert plan["record_id"] == "rec-001"

    # 落盘后读取也带新字段
    stored = service.get_plan(plan["id"])
    assert stored["publish_time"] == "19:30"
    assert stored["record_id"] == "rec-001"


def test_create_plan_defaults_new_fields_to_empty(service):
    plan = service.create_plan({"title": "无时间计划", "publish_date": "2026-08-01"})
    assert plan["publish_time"] == ""
    assert plan["record_id"] == ""


def test_create_plan_normalizes_loose_time(service):
    """宽松时间：H:MM、全角冒号、带秒都归一化为 HH:MM"""
    plan = service.create_plan({
        "title": "宽松时间", "publish_date": "2026-08-01", "publish_time": "9:5",
    })
    assert plan["publish_time"] == "09:05"

    plan2 = service.create_plan({
        "title": "全角冒号", "publish_date": "2026-08-01", "publish_time": "21：30：00",
    })
    assert plan2["publish_time"] == "21:30"


def test_create_plan_rejects_invalid_time(service):
    with pytest.raises(ValueError):
        service.create_plan({
            "title": "坏时间", "publish_date": "2026-08-01", "publish_time": "晚上八点",
        })
    with pytest.raises(ValueError):
        service.create_plan({
            "title": "越界时间", "publish_date": "2026-08-01", "publish_time": "25:00",
        })


# ==================== 新字段：update ====================

def test_update_plan_new_fields(service):
    plan = service.create_plan({"title": "初始", "publish_date": "2026-08-01"})

    updated = service.update_plan(plan["id"], {
        "publish_time": "18:00", "record_id": "rec-xyz",
    })
    assert updated["publish_time"] == "18:00"
    assert updated["record_id"] == "rec-xyz"

    # 清空
    cleared = service.update_plan(plan["id"], {"publish_time": "", "record_id": ""})
    assert cleared["publish_time"] == ""
    assert cleared["record_id"] == ""


def test_update_plan_invalid_time_raises(service):
    plan = service.create_plan({"title": "初始", "publish_date": "2026-08-01"})
    with pytest.raises(ValueError):
        service.update_plan(plan["id"], {"publish_time": "abc"})


# ==================== 旧数据兼容 ====================

def test_legacy_plans_without_new_fields_read_ok(service):
    """旧数据（无 record_id / publish_time 字段）读取、列表、更新都不报错"""
    legacy = {
        "id": "legacy-1",
        "title": "旧条目",
        "platform": "xiaohongshu",
        "publish_date": "2026-08-02",
        "status": "idea",
        "notes": "",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    with open(service.store_file, "w", encoding="utf-8") as f:
        json.dump({"plans": [legacy]}, f, ensure_ascii=False)

    plans = service.list_plans(month="2026-08")
    assert len(plans) == 1
    assert plans[0]["id"] == "legacy-1"

    assert service.get_plan("legacy-1")["title"] == "旧条目"

    # 部分更新老条目不报错，并可补写新字段
    updated = service.update_plan("legacy-1", {"publish_time": "20:00"})
    assert updated["publish_time"] == "20:00"

    stats = service.get_stats(month="2026-08")
    assert stats["total"] == 1


# ==================== generate_week_plan ====================

def test_generate_week_plan_success(monkeypatch):
    client = _mock_llm(monkeypatch, _week_response([
        {"title": "周一开更：3 天减脂餐清单", "publish_date": "2026-07-27",
         "publish_time": "18:30", "notes": "清单体，痛点切入"},
        {"title": "周三测评：平价蛋白粉横评", "publish_date": "2026-07-29",
         "publish_time": "19:00", "notes": "测评对比"},
        {"title": "周末合集：一周训练回顾", "publish_date": "2026-08-01",
         "publish_time": "20:00", "notes": "合集复盘"},
    ]))

    result = generate_week_plan("健身减脂", "douyin", START, 3)

    assert result["success"] is True
    assert result["account_context_used"] is False
    assert len(result["plans"]) == 3
    for p in result["plans"]:
        assert p["platform"] == "douyin"
        assert p["status"] == "idea"
        assert START <= p["publish_date"] <= "2026-08-02"

    # prompt 注入了领域、平台中文名、起始日期与条数
    prompt = client.prompts[0]
    assert "健身减脂" in prompt
    assert "抖音" in prompt
    assert START in prompt
    assert "3" in prompt
    assert "未提供" in prompt  # 未开启账号数据


def test_generate_week_plan_bad_json_returns_error(monkeypatch):
    _mock_llm(monkeypatch, "这不是 JSON，也没有大括号")

    result = generate_week_plan("健身减脂", "xiaohongshu", START, 3)

    assert result["success"] is False
    assert "一周排期生成失败" in result["error"]


def test_generate_week_plan_clamps_out_of_range_dates(monkeypatch):
    _mock_llm(monkeypatch, _week_response([
        {"title": "太早的计划", "publish_date": "2026-07-20", "publish_time": "18:00", "notes": "x"},
        {"title": "太晚的计划", "publish_date": "2026-09-15", "publish_time": "19:00", "notes": "y"},
    ]))

    result = generate_week_plan("健身减脂", "xiaohongshu", START, 2)

    assert result["success"] is True
    dates = [p["publish_date"] for p in result["plans"]]
    assert dates[0] == START            # 出界（早）钳到周一
    assert dates[1] == "2026-08-02"     # 出界（晚）钳到周日（start+6）


def test_generate_week_plan_drops_bad_items(monkeypatch):
    _mock_llm(monkeypatch, _week_response([
        {"title": "", "publish_date": START, "notes": "没标题，丢弃"},
        {"title": "日期坏掉，丢弃", "publish_date": "某天", "notes": "x"},
        "不是字典，丢弃",
        {"title": "好条目", "publish_date": START, "publish_time": "8点档", "notes": "时间坏掉置空"},
    ]))

    result = generate_week_plan("健身减脂", "xiaohongshu", START, 4)

    assert result["success"] is True
    assert len(result["plans"]) == 1
    assert result["plans"][0]["title"] == "好条目"
    assert result["plans"][0]["publish_time"] == ""  # 坏时间不丢条目，置空


def test_generate_week_plan_all_items_bad_returns_error(monkeypatch):
    _mock_llm(monkeypatch, _week_response([{"title": "", "publish_date": START}]))

    result = generate_week_plan("健身减脂", "xiaohongshu", START, 3)
    assert result["success"] is False


def test_generate_week_plan_clamps_frequency(monkeypatch):
    items = [
        {"title": f"计划 {i}", "publish_date": START, "publish_time": "18:00", "notes": "x"}
        for i in range(10)
    ]
    client = _mock_llm(monkeypatch, _week_response(items))

    # 99 钳到 7：prompt 里要求 7 条，返回超过 7 条时截断
    result = generate_week_plan("健身减脂", "xiaohongshu", START, 99)
    assert result["success"] is True
    assert len(result["plans"]) == 7
    assert "7" in client.prompts[0]

    # 0 钳到 1
    result_low = generate_week_plan("健身减脂", "xiaohongshu", START, 0)
    assert len(result_low["plans"]) == 1

    # 无法解析回退默认 3
    result_bad = generate_week_plan("健身减脂", "xiaohongshu", START, "abc")
    assert len(result_bad["plans"]) == 3


def test_generate_week_plan_validates_params(monkeypatch):
    _mock_llm(monkeypatch, _week_response([]))

    with pytest.raises(ValueError):
        generate_week_plan("", "xiaohongshu", START, 3)
    with pytest.raises(ValueError):
        generate_week_plan("健身减脂", "weibo", START, 3)
    with pytest.raises(ValueError):
        generate_week_plan("健身减脂", "xiaohongshu", "2026/07/27", 3)


def test_generate_week_plan_account_context(monkeypatch):
    """use_account_data=True 且有时段数据时：画像注入 prompt 并点名高互动时段"""
    client = _mock_llm(monkeypatch, _week_response([
        {"title": "计划", "publish_date": START, "publish_time": "19:00", "notes": "x"},
    ]))

    import backend.services.analytics as analytics_module

    class FakeAnalyticsService:
        def get_stats(self):
            return {
                "total_records": 4,
                "avg_engagement_rate": 6.0,
                "content_types": [
                    {"name": "干货教程", "count": 2, "engagement_rate": 8.0},
                ],
                "time_slots": [
                    {"name": "上午 9-12", "count": 1, "avg_engagement": 3.0},
                    {"name": "晚间 18-22", "count": 3, "avg_engagement": 9.5},
                ],
            }

    monkeypatch.setattr(analytics_module, "get_analytics_service", lambda: FakeAnalyticsService())

    result = generate_week_plan("健身减脂", "xiaohongshu", START, 1, use_account_data=True)

    assert result["success"] is True
    assert result["account_context_used"] is True
    prompt = client.prompts[0]
    assert "晚间 18-22" in prompt
    assert "publish_time 安排在互动率最高的时段" in prompt
    assert "已发布内容共 4 篇" in prompt


def test_generate_week_plan_does_not_persist(monkeypatch, tmp_path):
    """只返回预览：生成后 plans.json 保持为空库"""
    monkeypatch.setattr(calendar_module, "get_data_root", lambda: tmp_path)
    service = CalendarService()

    _mock_llm(monkeypatch, _week_response([
        {"title": "预览条目", "publish_date": START, "publish_time": "18:00", "notes": "x"},
    ]))
    result = generate_week_plan("健身减脂", "xiaohongshu", START, 1)
    assert result["success"] is True

    assert service.list_plans() == []


def test_next_monday_is_a_future_monday():
    date = datetime.strptime(next_monday(), "%Y-%m-%d")
    assert date.weekday() == 0
    assert date > datetime.now() - timedelta(days=1)


# ==================== 路由层 ====================

@pytest.fixture
def route_store(tmp_path, monkeypatch):
    """路由测试：CRUD 存储指向临时目录（重置单例）"""
    monkeypatch.setattr(calendar_module, "get_data_root", lambda: tmp_path)
    monkeypatch.setattr(calendar_module, "_service_instance", None)
    return tmp_path


def test_route_create_and_update_pass_new_fields(client, route_store):
    resp = client.post("/api/plans", json={
        "title": "路由新字段",
        "publish_date": "2026-08-01",
        "publish_time": "18:30",
        "record_id": "rec-route",
    })
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["plan"]["publish_time"] == "18:30"
    assert data["plan"]["record_id"] == "rec-route"

    plan_id = data["plan"]["id"]
    resp2 = client.put(f"/api/plans/{plan_id}", json={"publish_time": "20:00"})
    assert resp2.status_code == 200
    assert resp2.get_json()["plan"]["publish_time"] == "20:00"
    # 未传的字段保持不变
    assert resp2.get_json()["plan"]["record_id"] == "rec-route"


def test_route_create_invalid_time_returns_400(client, route_store):
    resp = client.post("/api/plans", json={
        "title": "坏时间", "publish_date": "2026-08-01", "publish_time": "abc",
    })
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


class FakeWeekPlanCall:
    """记录 generate_week_plan 调用参数并返回固定结果"""

    def __init__(self, result=None, exc=None):
        self.calls = []
        self.result = result or {
            "success": True,
            "plans": [{
                "title": "路由预览", "platform": "xiaohongshu",
                "publish_date": "2026-07-27", "publish_time": "18:00",
                "notes": "x", "status": "idea",
            }],
            "account_context_used": False,
        }
        self.exc = exc

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return self.result


def test_generate_week_route_requires_niche(client):
    resp = client.post("/api/plans/generate-week", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "niche" in data["error"]["detail"]


def test_generate_week_route_defaults(client, monkeypatch):
    fake = FakeWeekPlanCall()
    monkeypatch.setattr(calendar_routes, "generate_week_plan", fake)

    resp = client.post("/api/plans/generate-week", json={"niche": "健身减脂"})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    assert fake.calls == [{
        "niche": "健身减脂",
        "platform": "xiaohongshu",
        "start_date": None,  # 缺省交给服务层取下周一
        "frequency": 3,
        "use_account_data": False,
    }]


def test_generate_week_route_passes_params(client, monkeypatch):
    fake = FakeWeekPlanCall()
    monkeypatch.setattr(calendar_routes, "generate_week_plan", fake)

    resp = client.post("/api/plans/generate-week", json={
        "niche": "职场干货",
        "platform": "bilibili",
        "start_date": "2026-07-27",
        "frequency": 5,
        "use_account_data": True,
    })
    assert resp.status_code == 200
    assert fake.calls[0] == {
        "niche": "职场干货",
        "platform": "bilibili",
        "start_date": "2026-07-27",
        "frequency": 5,
        "use_account_data": True,
    }


def test_generate_week_route_service_valueerror_returns_400(client, monkeypatch):
    fake = FakeWeekPlanCall(exc=ValueError("平台取值非法：weibo"))
    monkeypatch.setattr(calendar_routes, "generate_week_plan", fake)

    resp = client.post("/api/plans/generate-week", json={
        "niche": "健身减脂", "platform": "weibo",
    })
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_generate_week_route_service_failure_returns_error_object(client, monkeypatch):
    fake = FakeWeekPlanCall(result={"success": False, "error": "一周排期生成失败。\n错误详情: boom"})
    monkeypatch.setattr(calendar_routes, "generate_week_plan", fake)

    resp = client.post("/api/plans/generate-week", json={"niche": "健身减脂"})
    data = resp.get_json()
    assert resp.status_code == 500
    assert data["success"] is False
    assert isinstance(data["error"], dict)
    assert data["error"].get("code")
