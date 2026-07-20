"""
对标拆解接口（POST /api/benchmark）url 模式测试

不发起真实网络请求与 LLM 调用：
- mock get_link_extract_service().fetch_article_text 模拟抓取成功/失败
- mock get_benchmark_service().analyze_benchmark 模拟 LLM 拆解
"""
import pytest

from backend.routes import benchmark_routes


FAKE_ANALYSIS = {
    "hook": "悬念钩子",
    "opening": "开头制造反差",
    "structure": ["抛出问题", "给出方法", "总结升华"],
    "emotion": "焦虑缓解",
    "audience": "新手创作者",
    "viral_elements": ["数字标题", "对比冲突"],
    "reusable_template": "【痛点】+【方法】+【结果】",
}


class FakeBenchmarkService:
    """记录调用参数并返回固定结果的假拆解服务"""

    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "success": True,
            "analysis": FAKE_ANALYSIS,
            "draft": "",
        }

    def analyze_benchmark(self, content, my_topic=None):
        self.calls.append({"content": content, "my_topic": my_topic})
        return self.result


class FakeLinkService:
    """模拟 link_extract 服务：可配置抓取返回文本或抛出 ValueError"""

    def __init__(self, text=None, error=None):
        self.calls = []
        self.text = text
        self.error = error

    def fetch_article_text(self, url):
        self.calls.append(url)
        if self.error is not None:
            raise ValueError(self.error)
        return self.text


@pytest.fixture
def fake_benchmark(monkeypatch):
    service = FakeBenchmarkService()
    monkeypatch.setattr(benchmark_routes, "get_benchmark_service", lambda: service)
    return service


# ==================== 参数校验 ====================

def test_content_and_url_both_empty_returns_400(client):
    response = client.post("/api/benchmark", json={})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert data["error_message"]


def test_whitespace_content_and_url_returns_400(client):
    response = client.post("/api/benchmark", json={"content": "  \n ", "url": "  "})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_url_too_long_returns_400(client, fake_benchmark):
    response = client.post("/api/benchmark", json={"url": "https://a.com/" + "x" * 3000})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


# ==================== url 模式：抓取成功 ====================

def test_url_mode_fetch_success_analyzes_fetched_text(client, fake_benchmark, monkeypatch):
    link_service = FakeLinkService(text="爆款标题\n\n这是抓取到的正文内容，足够分析。")
    monkeypatch.setattr(benchmark_routes, "get_link_extract_service", lambda: link_service)

    response = client.post("/api/benchmark", json={
        "url": "https://example.com/article",
        "my_topic": "我的新主题",
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["analysis"]["hook"] == FAKE_ANALYSIS["hook"]

    # 抓取到的正文被送入拆解服务，my_topic 原样透传
    assert link_service.calls == ["https://example.com/article"]
    assert len(fake_benchmark.calls) == 1
    assert fake_benchmark.calls[0]["content"] == "爆款标题\n\n这是抓取到的正文内容，足够分析。"
    assert fake_benchmark.calls[0]["my_topic"] == "我的新主题"


def test_url_mode_truncates_overlong_article(client, fake_benchmark, monkeypatch):
    """抓取到的超长正文应截断到 MAX_ARTICLE_CHARS 再送入拆解服务"""
    from backend.routes.benchmark_routes import MAX_ARTICLE_CHARS

    link_service = FakeLinkService(text="正" * 30000)
    monkeypatch.setattr(benchmark_routes, "get_link_extract_service", lambda: link_service)

    response = client.post("/api/benchmark", json={"url": "https://example.com/long"})

    assert response.status_code == 200
    assert len(fake_benchmark.calls) == 1
    assert len(fake_benchmark.calls[0]["content"]) == MAX_ARTICLE_CHARS


def test_content_takes_precedence_over_url(client, fake_benchmark, monkeypatch):
    link_service = FakeLinkService(text="不应该被用到的正文")
    monkeypatch.setattr(benchmark_routes, "get_link_extract_service", lambda: link_service)

    response = client.post("/api/benchmark", json={
        "content": "用户直接粘贴的内容",
        "url": "https://example.com/article",
    })

    assert response.status_code == 200
    # 有 content 时不抓取链接
    assert link_service.calls == []
    assert fake_benchmark.calls[0]["content"] == "用户直接粘贴的内容"


# ==================== url 模式：抓取失败 ====================

def test_url_fetch_failure_passes_through_original_error(client, fake_benchmark, monkeypatch):
    original_error = "无法访问该链接，请检查链接是否正确，或直接粘贴文章内容"
    link_service = FakeLinkService(error=original_error)
    monkeypatch.setattr(benchmark_routes, "get_link_extract_service", lambda: link_service)

    response = client.post("/api/benchmark", json={"url": "https://example.com/blocked"})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    # link_extract 的原始错误提示透传给前端
    assert original_error in data["error"]["detail"]
    # 抓取失败时不应调用 LLM 拆解
    assert fake_benchmark.calls == []


def test_url_fetch_ssrf_rejection_passes_through(client, fake_benchmark, monkeypatch):
    original_error = "不允许抓取私网、环回或保留地址"
    link_service = FakeLinkService(error=original_error)
    monkeypatch.setattr(benchmark_routes, "get_link_extract_service", lambda: link_service)

    response = client.post("/api/benchmark", json={"url": "http://127.0.0.1/admin"})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert original_error in data["error"]["detail"]


def test_url_fetch_returns_empty_text_returns_error(client, fake_benchmark, monkeypatch):
    link_service = FakeLinkService(text="   \n ")
    monkeypatch.setattr(benchmark_routes, "get_link_extract_service", lambda: link_service)

    response = client.post("/api/benchmark", json={"url": "https://example.com/empty"})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert "粘贴" in data["error"]["detail"]
    assert fake_benchmark.calls == []


# ==================== content 模式回归 ====================

def test_content_mode_still_works(client, fake_benchmark):
    response = client.post("/api/benchmark", json={"content": "一篇爆款内容"})
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert fake_benchmark.calls[0]["content"] == "一篇爆款内容"
    assert fake_benchmark.calls[0]["my_topic"] is None
