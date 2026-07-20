"""
创作偏好画像（PreferenceService + GET /api/preference/profile）测试

不调 LLM、不动真实数据：
- 服务层：用临时目录装配 HistoryService（__new__ 绕过 __init__），
  覆盖样本不足 / 高分偏好聚合 / 编辑信号 / prompt 片段与 200 字上限
- 路由层：自建 Flask app 注册蓝图 + mock get_preference_service
- outline 注入：画像为空字符串时完全不改变现有 prompt
"""
from pathlib import Path

import pytest
from flask import Flask

from backend.routes import preference_routes
from backend.routes.preference_routes import create_preference_blueprint
from backend.services.history import HistoryService
from backend.services.outline import OutlineService
from backend.services.preference import (
    MIN_RATED_SAMPLES,
    PROMPT_SNIPPET_MAX_LEN,
    PreferenceService,
)


# ==================== 测试工具 ====================

def make_history_service(tmp_path: Path) -> HistoryService:
    """与 feedback_loop_test 一致：绕过 __init__，指向临时目录"""
    service = HistoryService.__new__(HistoryService)
    service.history_dir = str(tmp_path)
    service.index_file = str(tmp_path / "index.json")
    service._init_index()
    return service


def make_outline(page_count: int) -> dict:
    return {
        "raw": "原始大纲",
        "pages": [
            {"index": i, "type": "content", "content": f"第 {i} 页"}
            for i in range(page_count)
        ],
    }


def add_record(history, topic: str, page_count: int = 5, rating=None) -> str:
    """创建一条历史记录，可选打分"""
    record_id = history.create_record(topic, make_outline(page_count))
    if rating is not None:
        history.set_rating(record_id, rating)
    return record_id


def add_edit(history, record_id: str, original: str, edited: str):
    """给记录追加一条编辑留痕"""
    assert history.update_record(record_id, edit_trace={
        "page_index": 0,
        "original_text": original,
        "edited_text": edited,
        "source": "manual",
    })


@pytest.fixture
def history(tmp_path):
    return make_history_service(tmp_path)


@pytest.fixture
def service(history):
    return PreferenceService(history_service=history)


# ==================== 样本不足 ====================

def test_empty_history_is_insufficient(service):
    profile = service.build_profile()

    assert profile["insufficient"] is True
    assert profile["sample_count"] == 0
    assert profile["min_samples"] == MIN_RATED_SAMPLES
    assert profile["liked_topics"] == []
    assert profile["preferred_page_count"] is None


def test_less_than_min_rated_samples_is_insufficient(history, service):
    # 2 条评分 + 1 条未评分：已评分样本 2 < 3，仍视为不足
    add_record(history, "主题A", rating=5)
    add_record(history, "主题B", rating=4)
    add_record(history, "主题C")

    profile = service.build_profile()

    assert profile["insufficient"] is True
    assert profile["sample_count"] == 2
    # 样本不足时不输出任何结论
    assert profile["liked_count"] == 0
    assert profile["liked_topics"] == []


def test_insufficient_profile_yields_empty_snippet(history, service):
    add_record(history, "主题A", rating=5)

    assert service.build_prompt_snippet() == ""


# ==================== 正常画像聚合 ====================

def test_profile_aggregates_liked_topics_and_page_count(history, service):
    add_record(history, "秋日穿搭", page_count=6, rating=5)
    add_record(history, "手冲咖啡入门", page_count=6, rating=4)
    add_record(history, "极简收纳", page_count=4, rating=4)
    # 低分与未评分作品不进入高分偏好
    add_record(history, "翻车的主题", page_count=9, rating=2)
    add_record(history, "未评分主题", page_count=9)

    profile = service.build_profile()

    assert profile["insufficient"] is False
    assert profile["sample_count"] == 4
    assert profile["liked_count"] == 3
    assert profile["liked_topics"] == ["极简收纳", "手冲咖啡入门", "秋日穿搭"]
    assert "翻车的主题" not in profile["liked_topics"]
    # 高分作品页数众数：6 页出现 2 次
    assert profile["preferred_page_count"] == 6
    assert profile["page_count_distribution"] == {"4": 1, "6": 2}


def test_profile_deduplicates_liked_topics(history, service):
    for _ in range(3):
        add_record(history, "重复主题", rating=5)

    profile = service.build_profile()

    assert profile["liked_topics"] == ["重复主题"]
    assert profile["liked_count"] == 3


# ==================== 编辑信号 ====================

def rated_baseline(history):
    """先凑够 3 条评分让画像可输出结论，返回其中一条记录 id"""
    add_record(history, "主题A", rating=4)
    add_record(history, "主题B", rating=4)
    return add_record(history, "主题C", rating=5)


def test_editing_signal_shorten(history, service):
    record_id = rated_baseline(history)
    add_edit(history, record_id, "这是一段特别特别啰嗦冗长的原始文案内容", "精简后")
    add_edit(history, record_id, "又一段明显过长需要大幅压缩的表达", "短句")

    signal = service.build_profile()["editing_signal"]

    assert signal["edit_count"] == 2
    assert signal["tendency"] == "shorten"
    assert signal["avg_change_ratio"] < 0


def test_editing_signal_expand(history, service):
    record_id = rated_baseline(history)
    add_edit(history, record_id, "太短", "用户把内容扩写成了一大段丰富具体的文案表达")

    signal = service.build_profile()["editing_signal"]

    assert signal["tendency"] == "expand"
    assert signal["avg_change_ratio"] > 0


def test_no_edits_yields_null_tendency(history, service):
    rated_baseline(history)

    signal = service.build_profile()["editing_signal"]

    assert signal == {"edit_count": 0, "avg_change_ratio": 0.0, "tendency": None}


# ==================== prompt 片段 ====================

def test_snippet_contains_conclusions_and_is_chinese(history, service):
    record_id = rated_baseline(history)
    add_edit(history, record_id, "这是一段特别特别啰嗦冗长的原始文案内容", "精简后")

    snippet = service.build_prompt_snippet()

    assert snippet
    assert "用户创作偏好" in snippet
    assert "页左右的篇幅" in snippet
    assert "主题A" in snippet
    assert "讨厌冗长表达" in snippet


def test_snippet_respects_max_length_with_long_topics(history, service):
    # 超长主题：验证片段被主题截断 + 硬上限双重约束在 200 字内
    for i in range(5):
        add_record(history, f"超长主题{i}" + "字" * 120, rating=5)

    snippet = service.build_prompt_snippet()

    assert snippet
    assert len(snippet) <= PROMPT_SNIPPET_MAX_LEN


# ==================== 路由层 ====================

class FakePreferenceService:
    def __init__(self, profile=None, error=None):
        self.profile = profile
        self.error = error

    def build_profile(self):
        if self.error is not None:
            raise self.error
        return self.profile


@pytest.fixture
def preference_client():
    """蓝图独立可测：自建 Flask app 并以 /api 前缀注册蓝图"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_preference_blueprint(), url_prefix="/api")
    return app.test_client()


def test_route_get_profile_success(preference_client, monkeypatch):
    profile = {
        "insufficient": False,
        "sample_count": 4,
        "min_samples": 3,
        "liked_count": 3,
        "liked_topics": ["秋日穿搭"],
        "preferred_page_count": 6,
        "page_count_distribution": {"6": 2},
        "editing_signal": {"edit_count": 0, "avg_change_ratio": 0.0, "tendency": None},
    }
    monkeypatch.setattr(
        preference_routes,
        "get_preference_service",
        lambda: FakePreferenceService(profile=profile),
    )

    response = preference_client.get("/api/preference/profile")
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["profile"] == profile


def test_route_get_profile_service_error_returns_structured_error(
    preference_client, monkeypatch
):
    monkeypatch.setattr(
        preference_routes,
        "get_preference_service",
        lambda: FakePreferenceService(error=RuntimeError("磁盘炸了")),
    )

    response = preference_client.get("/api/preference/profile")
    data = response.get_json()

    assert response.status_code >= 500
    assert data["success"] is False
    assert data["error"]["code"]


def test_route_registered_in_app(client, monkeypatch):
    """蓝图已接入 create_app：真实应用里 GET /api/preference/profile 可达"""
    monkeypatch.setattr(
        preference_routes,
        "get_preference_service",
        lambda: FakePreferenceService(profile={"insufficient": True, "sample_count": 0}),
    )

    response = client.get("/api/preference/profile")

    assert response.status_code == 200
    assert response.get_json()["success"] is True


# ==================== outline 注入 ====================

def build_outline_service() -> OutlineService:
    """绕过 __init__（避免读取真实配置/API Key），手工装配依赖"""
    service = OutlineService.__new__(OutlineService)
    service.text_config = {"active_provider": "test", "providers": {}}
    service.client = None
    service.prompt_template = "请为主题「{topic}」生成小红书图文大纲"
    return service


def test_outline_prompt_unchanged_when_snippet_empty(monkeypatch):
    from backend.services import outline as outline_module

    service = build_outline_service()
    monkeypatch.setattr(outline_module, "load_preference_snippet", lambda: "")

    prompt = service.build_outline_prompt("秋日穿搭")

    # 画像为空字符串时完全不影响现有 prompt
    assert prompt == "请为主题「秋日穿搭」生成小红书图文大纲"


def test_outline_prompt_appends_snippet_when_present(monkeypatch):
    from backend.services import outline as outline_module

    service = build_outline_service()
    snippet = "【用户创作偏好】偏好 6 页左右的篇幅。"
    monkeypatch.setattr(outline_module, "load_preference_snippet", lambda: snippet)

    prompt = service.build_outline_prompt("秋日穿搭")

    # 片段以独立段落追加在原 prompt 之后
    assert prompt == "请为主题「秋日穿搭」生成小红书图文大纲\n\n" + snippet


def test_load_preference_snippet_swallows_service_errors(monkeypatch):
    """画像服务异常时降级为空字符串，不影响大纲生成主链路"""
    from backend.services import outline as outline_module
    from backend.services import preference as preference_module

    def boom():
        raise RuntimeError("历史目录损坏")

    monkeypatch.setattr(preference_module, "get_preference_service", boom)

    assert outline_module.load_preference_snippet() == ""
