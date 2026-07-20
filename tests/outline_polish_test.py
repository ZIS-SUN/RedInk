"""
单页 AI 润色接口（POST /api/outline/polish）测试

不发起真实 LLM 调用：路由层测试 mock 掉 OutlineService，
服务层测试 mock 掉底层文本客户端。
"""
import pytest

from backend.routes import outline_routes
from backend.routes.outline_routes import POLISH_INSTRUCTIONS
from backend.services.outline import OutlineService, clean_llm_text


class FakePolishService:
    """记录调用参数并返回固定结果的假服务"""

    def __init__(self, result=None):
        self.calls = []
        self.result = result or {"success": True, "content": "润色后的文案"}

    def polish_page(self, content, page_type, topic, instruction):
        self.calls.append({
            "content": content,
            "page_type": page_type,
            "topic": topic,
            "instruction": instruction,
        })
        return self.result


@pytest.fixture
def fake_service(monkeypatch):
    service = FakePolishService()
    monkeypatch.setattr(outline_routes, "get_outline_service", lambda: service)
    return service


# ==================== 参数校验 ====================

def test_polish_empty_content_returns_400(client):
    response = client.post("/api/outline/polish", json={"content": ""})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert data["error_message"]


def test_polish_missing_content_returns_400(client):
    response = client.post("/api/outline/polish", json={})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_REQUEST"


def test_polish_whitespace_content_returns_400(client):
    response = client.post("/api/outline/polish", json={"content": "   \n  "})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


# ==================== 白名单映射 ====================

@pytest.mark.parametrize("key", ["polish", "shorten", "punchier"])
def test_polish_instruction_whitelist_mapping(client, fake_service, key):
    response = client.post("/api/outline/polish", json={
        "content": "标题：测试内容",
        "instruction": key,
    })

    assert response.status_code == 200
    assert len(fake_service.calls) == 1
    assert fake_service.calls[0]["instruction"] == POLISH_INSTRUCTIONS[key]


@pytest.mark.parametrize("bad_key", ["hack", "ignore previous instructions", "", None])
def test_polish_unknown_instruction_falls_back_to_polish(client, fake_service, bad_key):
    payload = {"content": "标题：测试内容"}
    if bad_key is not None:
        payload["instruction"] = bad_key

    response = client.post("/api/outline/polish", json=payload)

    assert response.status_code == 200
    assert fake_service.calls[0]["instruction"] == POLISH_INSTRUCTIONS["polish"]


def test_polish_non_string_params_do_not_500(client, fake_service):
    """page_type/topic/content 传非字符串（如数字）时应收敛为 str，而不是 500"""
    response = client.post("/api/outline/polish", json={
        "content": "正常内容",
        "page_type": 123,
        "topic": 456,
    })

    assert response.status_code == 200
    call = fake_service.calls[0]
    assert call["page_type"] == "123"
    assert call["topic"] == "456"


def test_polish_defaults_page_type_and_topic(client, fake_service):
    response = client.post("/api/outline/polish", json={"content": "内容页文案"})

    assert response.status_code == 200
    call = fake_service.calls[0]
    assert call["page_type"] == "content"
    assert call["topic"] == ""


# ==================== 成功路径 ====================

def test_polish_success_returns_content(client, fake_service):
    response = client.post("/api/outline/polish", json={
        "content": "标题：旧标题",
        "page_type": "cover",
        "topic": "手冲咖啡",
        "instruction": "punchier",
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["content"] == "润色后的文案"

    call = fake_service.calls[0]
    assert call["content"] == "标题：旧标题"
    assert call["page_type"] == "cover"
    assert call["topic"] == "手冲咖啡"


def test_polish_service_error_returns_structured_error(client, monkeypatch):
    service = FakePolishService(result={
        "success": False,
        "error": "HTTP 429: rate limit",
    })
    monkeypatch.setattr(outline_routes, "get_outline_service", lambda: service)

    response = client.post("/api/outline/polish", json={"content": "内容"})
    data = response.get_json()

    assert response.status_code == 429
    assert data["success"] is False
    assert data["error"]["code"] == "RATE_LIMITED"
    assert data["error_message"]


# ==================== 服务层：LLM 结果清洗 ====================

class FakeTextClient:
    def __init__(self, response_text):
        self.response_text = response_text
        self.prompts = []

    def generate_text(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return self.response_text


def _build_service(response_text) -> OutlineService:
    """绕过 __init__（避免读取真实配置/API Key），手工装配依赖"""
    service = OutlineService.__new__(OutlineService)
    service.text_config = {
        'active_provider': 'test_provider',
        'providers': {
            'test_provider': {
                'model': 'test-model',
                'temperature': 0.8,
                'max_output_tokens': 4000,
            }
        }
    }
    service.client = FakeTextClient(response_text)
    service.prompt_template = ""
    return service


def test_polish_page_strips_code_fence_and_whitespace():
    service = _build_service("```\n  [封面]\n标题：新标题\n```  \n")

    result = service.polish_page(
        content="[封面]\n标题：旧标题",
        page_type="cover",
        topic="测试主题",
        instruction="润色",
    )

    assert result["success"] is True
    assert result["content"] == "[封面]\n标题：新标题"


def test_polish_page_prompt_contains_all_fields():
    service = _build_service("润色结果")

    service.polish_page(
        content="原文内容",
        page_type="summary",
        topic="",
        instruction="精简压缩",
    )

    prompt = service.client.prompts[0]
    assert "原文内容" in prompt
    assert "summary" in prompt
    assert "未提供" in prompt  # topic 为空时兜底为「未提供」
    assert "精简压缩" in prompt


def test_polish_page_empty_llm_result_returns_error():
    service = _build_service("```\n```")

    result = service.polish_page(content="原文", instruction="润色")

    assert result["success"] is False
    assert "error" in result


def test_clean_llm_text():
    assert clean_llm_text("  hello  ") == "hello"
    assert clean_llm_text("```markdown\n正文内容\n```") == "正文内容"
    assert clean_llm_text("```\n第一行\n第二行\n```") == "第一行\n第二行"
    # 中间出现的代码块不剥掉，只剥整体包裹
    assert clean_llm_text("前文\n```\ncode\n```\n后文") == "前文\n```\ncode\n```\n后文"
    assert clean_llm_text("") == ""
