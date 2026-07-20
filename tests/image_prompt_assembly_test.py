"""
图片生成 prompt 组装链路测试（backend/services/image.py）

只针对代码侧的组装逻辑，不依赖 backend/prompts/ 模板的具体内容
（模板由另一条链路维护，本文件用极简模板字符串替代，仅验证占位符契约）。

覆盖：
- 占位符契约：page_content/page_type/full_outline/user_topic 进入最终 prompt
- 风格块以强调框架结构化注入（分节标题 + 最高优先级措辞 + 结尾重申）
- 品牌视觉约束位于风格块与结尾重申之间（组装顺序稳定）
- 单张重试（retry_single_image）追加质量反馈提示，且位于 prompt 最末端
- 常规生成与批量重试（retry_failed_images）不追加重试提示
"""
from pathlib import Path

from backend.services import brand as brand_module
from backend.services.history import HistoryService
from backend.services.image import ImageService
from backend.services.image_rate_limiter import ImageRateLimiter


# ==================== 测试辅助 ====================

class RecordingGenerator:
    """记录每次调用 prompt 的假生成器"""

    def __init__(self):
        self.prompts = []

    def generate_image(self, **kwargs):
        self.prompts.append(kwargs.get("prompt", ""))
        return b"image-bytes"


TEMPLATE = (
    "页面内容：{page_content}\n"
    "页面类型：{page_type}\n"
    "完整大纲：{full_outline}\n"
    "用户主题：{user_topic}"
)

PAGE = {"index": 1, "type": "content", "content": "第2页要点"}

STYLE = "手绘水彩风，低饱和莫兰迪配色"


def make_history_service(tmp_path: Path) -> HistoryService:
    service = HistoryService.__new__(HistoryService)
    service.history_dir = str(tmp_path)
    service.index_file = str(tmp_path / "index.json")
    service._init_index()
    return service


def make_image_service(tmp_path: Path) -> ImageService:
    image_service = ImageService.__new__(ImageService)
    image_service.generator = RecordingGenerator()
    image_service.provider_config = {"type": "image_api", "model": "gpt-image-2"}
    image_service.use_short_prompt = False
    image_service.prompt_template = TEMPLATE
    image_service.prompt_template_short = ""
    image_service.history_root_dir = str(tmp_path)
    image_service.rate_limiter = ImageRateLimiter(max_concurrent=1, interval_seconds=0)
    image_service.history_service = make_history_service(tmp_path / "records")
    image_service.worker_count = 1
    image_service._task_states = {}
    # 直接调用 _generate_single_image 时任务目录由调用方保证存在
    (tmp_path / "task_1").mkdir(parents=True, exist_ok=True)
    return image_service


def disable_brand(monkeypatch):
    """让品牌解析返回 None（不注入品牌视觉约束），保证测试确定性"""
    monkeypatch.setattr(
        brand_module, "resolve_brand_for_prompt", lambda brand_id=None: None
    )


def enable_brand(monkeypatch):
    """让品牌解析返回带主色调的品牌，触发品牌视觉约束注入"""
    monkeypatch.setattr(
        brand_module,
        "resolve_brand_for_prompt",
        lambda brand_id=None: {"name": "测试品牌", "primary_color": "#FF2442"},
    )


# ==================== 占位符契约 ====================

def test_template_placeholders_filled(tmp_path, monkeypatch):
    disable_brand(monkeypatch)
    service = make_image_service(tmp_path)

    result = service._generate_single_image(
        PAGE, "task_1",
        full_outline="<page>第1页<page>第2页",
        user_topic="露营好物分享",
    )

    assert result[1] is True
    prompt = service.generator.prompts[0]
    assert "页面内容：第2页要点" in prompt
    assert "页面类型：content" in prompt
    assert "完整大纲：<page>第1页<page>第2页" in prompt
    assert "用户主题：露营好物分享" in prompt


def test_empty_user_topic_falls_back_to_placeholder_text(tmp_path, monkeypatch):
    disable_brand(monkeypatch)
    service = make_image_service(tmp_path)

    service._generate_single_image(PAGE, "task_1")

    assert "用户主题：未提供" in service.generator.prompts[0]


# ==================== 风格块强调框架 ====================

def test_style_block_injected_with_priority_framing(tmp_path, monkeypatch):
    disable_brand(monkeypatch)
    service = make_image_service(tmp_path)

    service._generate_single_image(PAGE, "task_1", style_prompt=STYLE)

    prompt = service.generator.prompts[0]
    # 分节标题 + 最高优先级/覆盖措辞 + 风格正文
    assert "【视觉风格规范 · 最高优先级】" in prompt
    assert "优先级最高" in prompt
    assert "覆盖上文所有描述与模型默认审美" in prompt
    assert STYLE in prompt
    # 风格块在模板正文之后
    assert prompt.index("【视觉风格规范 · 最高优先级】") > prompt.index("页面内容：第2页要点")


def test_style_reinforcement_repeated_at_prompt_tail(tmp_path, monkeypatch):
    disable_brand(monkeypatch)
    service = make_image_service(tmp_path)

    service._generate_single_image(PAGE, "task_1", style_prompt=STYLE)

    prompt = service.generator.prompts[0]
    # 结尾重申句存在，且位于风格正文之后、prompt 最末端
    assert "再次强调" in prompt
    assert prompt.index("再次强调") > prompt.index(STYLE)
    assert prompt.rstrip().endswith("一律以该规范为准。")


def test_no_style_prompt_adds_no_style_sections(tmp_path, monkeypatch):
    disable_brand(monkeypatch)
    service = make_image_service(tmp_path)

    service._generate_single_image(PAGE, "task_1", style_prompt="")

    prompt = service.generator.prompts[0]
    assert "【视觉风格规范 · 最高优先级】" not in prompt
    assert "再次强调" not in prompt


def test_apply_style_prompt_blank_style_returns_prompt_unchanged():
    assert ImageService._apply_style_prompt("基础 prompt", "   ") == "基础 prompt"
    assert ImageService._apply_style_prompt("基础 prompt", None) == "基础 prompt"


# ==================== 组装顺序：模板 → 风格块 → 品牌 → 重申 → 重试提示 ====================

def test_brand_block_sits_between_style_block_and_reinforcement(tmp_path, monkeypatch):
    enable_brand(monkeypatch)
    service = make_image_service(tmp_path)

    service._generate_single_image(PAGE, "task_1", style_prompt=STYLE)

    prompt = service.generator.prompts[0]
    assert "品牌视觉约束" in prompt
    assert "#FF2442" in prompt
    # 顺序：模板正文 < 风格块 < 品牌块 < 结尾重申
    assert (
        prompt.index("页面内容：第2页要点")
        < prompt.index("【视觉风格规范 · 最高优先级】")
        < prompt.index("品牌视觉约束")
        < prompt.index("再次强调")
    )


def test_full_assembly_order_with_retry_hint(tmp_path, monkeypatch):
    enable_brand(monkeypatch)
    service = make_image_service(tmp_path)

    result = service.retry_single_image(
        "task_1", PAGE, use_reference=False, style_prompt=STYLE
    )

    assert result["success"] is True
    prompt = service.generator.prompts[0]
    # 完整顺序：模板正文 < 风格块 < 品牌块 < 风格重申 < 重试质量提示（最末端）
    assert (
        prompt.index("页面内容：第2页要点")
        < prompt.index("【视觉风格规范 · 最高优先级】")
        < prompt.index("品牌视觉约束")
        < prompt.index("再次强调")
        < prompt.index("本次为重新生成")
    )
    assert prompt.rstrip().endswith("排版必须工整、对齐、留白合理。")


# ==================== 重试路径的 prompt 变异 ====================

def test_retry_single_image_appends_quality_hint(tmp_path, monkeypatch):
    disable_brand(monkeypatch)
    service = make_image_service(tmp_path)

    result = service.retry_single_image("task_1", PAGE, use_reference=False)

    assert result["success"] is True
    prompt = service.generator.prompts[0]
    assert "本次为重新生成" in prompt
    assert "逐字一致" in prompt
    assert prompt.rstrip().endswith("排版必须工整、对齐、留白合理。")


def test_regenerate_image_appends_quality_hint(tmp_path, monkeypatch):
    """regenerate_image 委托 retry_single_image，同样带上重试提示"""
    disable_brand(monkeypatch)
    service = make_image_service(tmp_path)

    result = service.regenerate_image("task_1", PAGE, use_reference=False)

    assert result["success"] is True
    assert "本次为重新生成" in service.generator.prompts[0]


def test_normal_generation_has_no_retry_hint(tmp_path, monkeypatch):
    disable_brand(monkeypatch)
    service = make_image_service(tmp_path)

    service._generate_single_image(PAGE, "task_1", style_prompt=STYLE)

    assert "本次为重新生成" not in service.generator.prompts[0]


def test_batch_retry_failed_images_has_no_retry_hint(tmp_path, monkeypatch):
    """批量重试通常源于 API 失败而非质量问题，保持 prompt 不变异"""
    disable_brand(monkeypatch)
    service = make_image_service(tmp_path)

    events = list(service.retry_failed_images("task_1", [PAGE]))

    assert events[-1]["data"]["success"] is True
    assert "本次为重新生成" not in service.generator.prompts[0]
