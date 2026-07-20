"""图片 Prompt 模板自定义功能测试

覆盖：
- ImageService._load_prompt_template 的自定义模板优先级（自定义 > 包内默认）
- /api/config/image-prompt 的 GET / PUT / DELETE
- PUT 缺少必需占位符时返回 400

用 tmp_path + monkeypatch 隔离 get_data_root，避免污染真实数据目录。
"""
import pytest

from backend.services.image import ImageService


CUSTOM_TEMPLATE = "自定义模板：{page_content} / {page_type}"


@pytest.fixture
def isolated_data_root(tmp_path, monkeypatch):
    """把可写数据根目录隔离到 tmp_path"""
    monkeypatch.setattr(
        "backend.services.image.get_data_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "backend.routes.config_routes.get_data_root", lambda: tmp_path
    )
    return tmp_path


def _load_template(short: bool = False) -> str:
    """不经过完整 __init__（避免依赖服务商配置）直接调用模板加载"""
    service = ImageService.__new__(ImageService)
    return service._load_prompt_template(short=short)


# ==================== _load_prompt_template 优先级 ====================

def test_load_prompt_template_falls_back_to_default(isolated_data_root):
    """无自定义文件时返回包内默认模板"""
    template = _load_template()
    assert "{page_content}" in template
    assert "{page_type}" in template


def test_load_prompt_template_prefers_custom(isolated_data_root):
    """写入自定义模板后优先返回自定义内容"""
    custom_dir = isolated_data_root / "custom_prompts"
    custom_dir.mkdir(parents=True)
    (custom_dir / "image_prompt.txt").write_text(CUSTOM_TEMPLATE, encoding="utf-8")

    assert _load_template() == CUSTOM_TEMPLATE


def test_load_prompt_template_ignores_empty_custom(isolated_data_root):
    """自定义文件为空白时回退默认模板"""
    custom_dir = isolated_data_root / "custom_prompts"
    custom_dir.mkdir(parents=True)
    (custom_dir / "image_prompt.txt").write_text("   \n", encoding="utf-8")

    template = _load_template()
    assert template != "   \n"
    assert "{page_content}" in template


def test_load_prompt_template_reverts_after_delete(isolated_data_root):
    """删除自定义文件后回退默认模板"""
    custom_dir = isolated_data_root / "custom_prompts"
    custom_dir.mkdir(parents=True)
    custom_file = custom_dir / "image_prompt.txt"
    custom_file.write_text(CUSTOM_TEMPLATE, encoding="utf-8")
    assert _load_template() == CUSTOM_TEMPLATE

    custom_file.unlink()
    template = _load_template()
    assert template != CUSTOM_TEMPLATE
    assert "{page_content}" in template


def test_load_short_prompt_template_prefers_custom(isolated_data_root):
    """短模板同样支持自定义覆盖"""
    custom_dir = isolated_data_root / "custom_prompts"
    custom_dir.mkdir(parents=True)
    short_template = "短模板：{page_type} {page_content}"
    (custom_dir / "image_prompt_short.txt").write_text(short_template, encoding="utf-8")

    assert _load_template(short=True) == short_template


# ==================== API 端点 ====================

def test_get_image_prompt_default(isolated_data_root, client):
    response = client.get("/api/config/image-prompt")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["is_custom"] is False
    assert "{page_content}" in data["template"]
    assert data["placeholders"] == [
        "page_content", "page_type", "user_topic", "full_outline"
    ]


def test_put_image_prompt_and_get_custom(isolated_data_root, client):
    response = client.put(
        "/api/config/image-prompt",
        json={"template": CUSTOM_TEMPLATE},
    )
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    # 文件已写入隔离目录
    custom_file = isolated_data_root / "custom_prompts" / "image_prompt.txt"
    assert custom_file.read_text(encoding="utf-8") == CUSTOM_TEMPLATE

    # GET 返回自定义模板
    response = client.get("/api/config/image-prompt")
    data = response.get_json()
    assert data["is_custom"] is True
    assert data["template"] == CUSTOM_TEMPLATE


def test_put_image_prompt_missing_placeholder_returns_400(isolated_data_root, client):
    response = client.put(
        "/api/config/image-prompt",
        json={"template": "只有内容占位符 {page_content}，缺少类型"},
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "{page_type}" in data["error"]["detail"]

    # 校验失败不应写入文件
    assert not (isolated_data_root / "custom_prompts" / "image_prompt.txt").exists()


def test_put_image_prompt_empty_returns_400(isolated_data_root, client):
    response = client.put("/api/config/image-prompt", json={"template": "  "})
    assert response.status_code == 400


def test_put_image_prompt_unknown_placeholder_returns_400(isolated_data_root, client):
    """多余占位符（渲染时会 KeyError）应被保存前校验拦截"""
    response = client.put(
        "/api/config/image-prompt",
        json={"template": "{page_content} {page_type} {not_a_field}"},
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "{not_a_field}" in data["error"]["detail"]

    # 校验失败不应写入文件
    assert not (isolated_data_root / "custom_prompts" / "image_prompt.txt").exists()


def test_put_image_prompt_unbalanced_brace_returns_400(isolated_data_root, client):
    """裸大括号/未配对大括号（渲染时会 ValueError）应返回 400"""
    response = client.put(
        "/api/config/image-prompt",
        json={"template": "{page_content} {page_type} 输出 JSON {"},
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert not (isolated_data_root / "custom_prompts" / "image_prompt.txt").exists()


def test_put_image_prompt_all_four_placeholders_ok(isolated_data_root, client):
    """合法四占位符模板仍可保存"""
    template = "内容{page_content} 类型{page_type} 主题{user_topic} 大纲{full_outline}"
    response = client.put("/api/config/image-prompt", json={"template": template})
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    custom_file = isolated_data_root / "custom_prompts" / "image_prompt.txt"
    assert custom_file.read_text(encoding="utf-8") == template


def test_put_image_prompt_escaped_braces_ok(isolated_data_root, client):
    """含 {{ }} 转义（输出大括号本身）的模板可保存"""
    template = '{page_content} {page_type} 请输出 JSON：{{"title": "xxx"}}'
    response = client.put("/api/config/image-prompt", json={"template": template})
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    custom_file = isolated_data_root / "custom_prompts" / "image_prompt.txt"
    assert custom_file.read_text(encoding="utf-8") == template


def test_delete_image_prompt_restores_default(isolated_data_root, client):
    # 先保存自定义模板
    client.put("/api/config/image-prompt", json={"template": CUSTOM_TEMPLATE})
    assert (isolated_data_root / "custom_prompts" / "image_prompt.txt").exists()

    # 删除恢复默认
    response = client.delete("/api/config/image-prompt")
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert not (isolated_data_root / "custom_prompts" / "image_prompt.txt").exists()

    response = client.get("/api/config/image-prompt")
    data = response.get_json()
    assert data["is_custom"] is False
    assert "{page_content}" in data["template"]


def test_delete_image_prompt_idempotent(isolated_data_root, client):
    """没有自定义文件时删除也应成功（幂等）"""
    response = client.delete("/api/config/image-prompt")
    assert response.status_code == 200
    assert response.get_json()["success"] is True
