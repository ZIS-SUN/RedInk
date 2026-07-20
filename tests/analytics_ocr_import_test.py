"""
截图 OCR 智能回填（B3）测试：

- 图片入参校验（张数 / base64 合法性 / 10MB 上限 / data URL 前缀）
- 模型响应解析容错（纯 JSON 数组 / ```json 包裹与前后杂文本 / 对象包裹）
- 字段二次清洗（「1.2万」换算 / 千分位 / 日期归一化 / 缺失为 None）
- 模型不支持视觉或识别失败时的结构化错误（AppErrorException）
- /api/analytics/ocr-import 端点行为

全程 mock 模型响应（monkeypatch AnalyticsService._call_vision_model），
不发起任何真实 AI 调用；数据目录用 tmp_path 隔离。
"""
import base64
from pathlib import Path

import pytest

from backend.errors import AppErrorException
from backend.services.analytics import AnalyticsService


def make_service(tmp_path: Path) -> AnalyticsService:
    service = AnalyticsService.__new__(AnalyticsService)
    service.analytics_dir = str(tmp_path)
    service.store_file = str(tmp_path / "records.json")
    service._init_store()
    return service


# 一个合法的最小 PNG 头部即可（内容不参与断言，只要是合法 base64）
FAKE_IMAGE = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 100).decode()

FAKE_TEXT_CONFIG = {
    "active_provider": "mock",
    "providers": {
        "mock": {
            "type": "openai_compatible",
            "api_key": "test-key",
            "model": "mock-vision-model",
            "temperature": 0.4,
            "max_output_tokens": 3000,
        }
    },
}


@pytest.fixture
def ocr_service(tmp_path, monkeypatch):
    """构造数据目录隔离、文本配置 mock 好的服务实例。"""
    service = make_service(tmp_path)
    monkeypatch.setattr(
        AnalyticsService, "_load_text_config", staticmethod(lambda: dict(FAKE_TEXT_CONFIG))
    )
    return service


def mock_vision(monkeypatch, response_text: str):
    """把视觉调用 mock 成固定文本返回。"""
    monkeypatch.setattr(
        AnalyticsService,
        "_call_vision_model",
        staticmethod(lambda provider_config, **kwargs: response_text),
    )


# ==================== 响应解析与字段清洗 ====================

def test_ocr_import_clean_json_array(ocr_service, monkeypatch):
    """正常 JSON 数组：数字换算、日期归一化、缺失字段为 None。"""
    mock_vision(monkeypatch, (
        '[{"title": "敏感肌自救指南", "publish_date": "2026/7/1", "views": "1.2万",'
        ' "likes": "1,024", "collects": 300, "comments": null, "shares": "18",'
        ' "followers_gained": null},'
        ' {"title": "夏日穿搭", "publish_date": null, "views": 500, "likes": 20,'
        ' "collects": 5, "comments": 1, "shares": 0, "followers_gained": 2}]'
    ))

    result = ocr_service.ocr_import([FAKE_IMAGE])

    assert result["count"] == 2
    first = result["rows"][0]
    assert first["title"] == "敏感肌自救指南"
    assert first["publish_date"] == "2026-07-01"
    assert first["views"] == 12000
    assert first["likes"] == 1024
    assert first["collects"] == 300
    assert first["comments"] is None
    assert first["shares"] == 18
    assert first["followers_gained"] is None

    second = result["rows"][1]
    assert second["publish_date"] is None
    assert second["shares"] == 0


def test_ocr_import_fenced_json_with_noise(ocr_service, monkeypatch):
    """```json 代码块包裹 + 前后杂文本也能解析。"""
    mock_vision(monkeypatch, (
        "好的，以下是识别结果：\n```json\n"
        '[{"title": "A", "publish_date": "2026-07-02", "views": 100, "likes": 1,'
        ' "collects": 0, "comments": 0, "shares": 0, "followers_gained": 0}]'
        "\n```\n希望对你有帮助！"
    ))

    result = ocr_service.ocr_import([FAKE_IMAGE])
    assert result["count"] == 1
    assert result["rows"][0]["title"] == "A"
    assert result["rows"][0]["views"] == 100


def test_ocr_import_object_wrapped_rows(ocr_service, monkeypatch):
    """模型把数组包在 { rows: [...] } 对象里也能取出。"""
    mock_vision(monkeypatch, '{"rows": [{"title": "B", "views": "3.5w"}]}')

    result = ocr_service.ocr_import([FAKE_IMAGE])
    assert result["count"] == 1
    assert result["rows"][0]["title"] == "B"
    assert result["rows"][0]["views"] == 35000
    # 模型没给的字段补齐为 None
    assert result["rows"][0]["likes"] is None


def test_ocr_import_filters_all_null_rows_and_accepts_empty(ocr_service, monkeypatch):
    """全 None 的行被过滤；空数组返回 rows=[]（截图里没有数据是合法结果）。"""
    mock_vision(monkeypatch, (
        '[{"title": null, "views": null}, {"title": "有效行", "views": 10}]'
    ))
    result = ocr_service.ocr_import([FAKE_IMAGE])
    assert result["count"] == 1
    assert result["rows"][0]["title"] == "有效行"

    mock_vision(monkeypatch, "[]")
    assert ocr_service.ocr_import([FAKE_IMAGE]) == {
        "rows": [], "count": 0, "model": "mock-vision-model",
    }


def test_ocr_import_negative_and_bad_numbers_become_none(ocr_service, monkeypatch):
    """负数 / 无法解析的数字清洗为 None，不误存为 0。"""
    mock_vision(monkeypatch, '[{"title": "C", "views": -5, "likes": "abc"}]')
    row = ocr_service.ocr_import([FAKE_IMAGE])["rows"][0]
    assert row["views"] is None
    assert row["likes"] is None


# ==================== 识别失败的结构化错误 ====================

def raise_vision_error(monkeypatch, message: str):
    def _boom(provider_config, **kwargs):
        raise Exception(message)
    monkeypatch.setattr(AnalyticsService, "_call_vision_model", staticmethod(_boom))


def test_ocr_import_model_failure_raises_structured_error(ocr_service, monkeypatch):
    """模型不支持视觉（上游 4xx）→ AppErrorException，建议改用手动录入。"""
    raise_vision_error(monkeypatch, "视觉识别请求失败 (HTTP 400)：image input not supported")

    with pytest.raises(AppErrorException) as exc_info:
        ocr_service.ocr_import([FAKE_IMAGE])

    app_error = exc_info.value.app_error
    assert app_error.code == "VISION_OCR_FAILED"
    assert app_error.status == 400
    assert app_error.retryable is False
    assert "当前模型不支持图片识别或识别失败，请改用手动录入" in app_error.suggestion
    assert "image input not supported" in app_error.detail
    assert app_error.diagnostics["model"] == "mock-vision-model"


def test_ocr_import_unparsable_output_raises_structured_error(ocr_service, monkeypatch):
    """模型输出完全不是 JSON → 同样归类为结构化识别失败错误。"""
    mock_vision(monkeypatch, "抱歉，我无法识别这张图片的内容。")

    with pytest.raises(AppErrorException) as exc_info:
        ocr_service.ocr_import([FAKE_IMAGE])
    assert exc_info.value.app_error.code == "VISION_OCR_FAILED"


# ==================== 入参校验 ====================

@pytest.mark.parametrize("bad_images", [None, [], "not-a-list", {}])
def test_ocr_import_invalid_images_arg_raises(ocr_service, bad_images):
    with pytest.raises(ValueError):
        ocr_service.ocr_import(bad_images)


def test_ocr_import_too_many_images_raises(ocr_service):
    with pytest.raises(ValueError, match="最多"):
        ocr_service.ocr_import([FAKE_IMAGE] * 4)


def test_ocr_import_invalid_base64_raises(ocr_service):
    with pytest.raises(ValueError, match="base64"):
        ocr_service.ocr_import(["这不是base64!!!"])


def test_ocr_import_oversized_image_raises(ocr_service):
    oversized = base64.b64encode(b"0" * (10 * 1024 * 1024 + 1)).decode()
    with pytest.raises(ValueError, match="10MB"):
        ocr_service.ocr_import([oversized])


def test_ocr_import_accepts_data_url_prefix(ocr_service, monkeypatch):
    """FileReader 产出的 data URL 前缀应被剥离后正常解码。"""
    captured = {}

    def _capture(provider_config, **kwargs):
        captured["images"] = kwargs["images"]
        return '[{"title": "D", "views": 1}]'

    monkeypatch.setattr(AnalyticsService, "_call_vision_model", staticmethod(_capture))
    result = ocr_service.ocr_import([f"data:image/png;base64,{FAKE_IMAGE}"])

    assert result["count"] == 1
    assert captured["images"][0].startswith(b"\x89PNG")


def test_ocr_import_missing_provider_config_raises_value_error(tmp_path, monkeypatch):
    """无服务商配置属于配置类错误（ValueError -> 400），不是识别失败。"""
    service = make_service(tmp_path)
    monkeypatch.setattr(
        AnalyticsService,
        "_load_text_config",
        staticmethod(lambda: {"active_provider": "x", "providers": {}}),
    )
    with pytest.raises(ValueError, match="服务商"):
        service.ocr_import([FAKE_IMAGE])


# ==================== 端点 ====================

@pytest.fixture
def patched_service(ocr_service, monkeypatch):
    monkeypatch.setattr(
        "backend.routes.analytics_routes.get_analytics_service",
        lambda: ocr_service,
    )
    return ocr_service


def test_ocr_endpoint_success(client, patched_service, monkeypatch):
    mock_vision(monkeypatch, '[{"title": "端点行", "views": "1.2万"}]')

    resp = client.post("/api/analytics/ocr-import", json={"images": [FAKE_IMAGE]})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["count"] == 1
    assert data["rows"][0]["title"] == "端点行"
    assert data["rows"][0]["views"] == 12000
    assert data["rows"][0]["likes"] is None


def test_ocr_endpoint_missing_images_returns_400(client, patched_service):
    assert client.post("/api/analytics/ocr-import", json={}).status_code == 400
    assert client.post(
        "/api/analytics/ocr-import", json={"images": []}
    ).status_code == 400


def test_ocr_endpoint_too_many_images_returns_400(client, patched_service):
    resp = client.post(
        "/api/analytics/ocr-import", json={"images": [FAKE_IMAGE] * 4}
    )
    assert resp.status_code == 400


def test_ocr_endpoint_vision_failure_returns_structured_error(
    client, patched_service, monkeypatch
):
    raise_vision_error(monkeypatch, "model does not support vision")

    resp = client.post("/api/analytics/ocr-import", json={"images": [FAKE_IMAGE]})

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "VISION_OCR_FAILED"
    assert "请改用手动录入" in data["error"]["suggestion"]
    assert "请改用手动录入" in data["error_message"]
