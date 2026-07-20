"""
prompt 模板护栏测试（B8：完读结构与互动钩子进大纲/体检 prompt）

大纲与体检模板都经 str.format 渲染，任何未转义的花括号或占位符丢失
都会在运行时崩溃；这里对真实模板做两类冒烟检查（不调用 LLM）：
- 占位符集合前后一致、format 渲染不报错、解析格式约定仍在
- 完读结构约束（第 2 页悬念承接 / 中段反转信息差 / 结尾互动引导）已落位
"""
import re

from backend.paths import resource_path

# 匹配单花括号占位符（跳过 {{ }} 转义的 JSON 花括号）
_PLACEHOLDER_PATTERN = r"(?<!\{)\{([a-z_]+)\}(?!\})"


def _read_prompt(name: str) -> str:
    path = resource_path(f"backend/prompts/{name}")
    return path.read_text(encoding="utf-8")


# ==================== 大纲模板 ====================

def test_outline_prompt_placeholders_and_format_intact():
    """占位符集合仍为 {topic}，format 渲染不因花括号崩溃，解析约定仍在"""
    template = _read_prompt("outline_prompt.txt")

    assert set(re.findall(_PLACEHOLDER_PATTERN, template)) == {"topic"}

    rendered = template.format(topic="秋季穿搭")
    assert "秋季穿搭" in rendered
    # 程序逐页解析依赖的格式约定不能被改掉
    assert "<page>" in rendered
    for marker in ("[封面]", "[内容]", "[总结]"):
        assert marker in rendered


def test_outline_prompt_contains_completion_structure_constraints():
    """完读结构三要素已写入大纲模板"""
    template = _read_prompt("outline_prompt.txt")

    # 第 2 页承接封面钩子抛悬念/冲突
    assert "第 2 页" in template
    assert "悬念" in template and "冲突" in template
    # 中段反转/对比/信息差
    assert "反转" in template and "信息差" in template
    # 结尾互动引导，给读者具体的评论理由
    assert "互动引导" in template
    assert "评论区聊聊" in template


# ==================== 体检模板 ====================

def test_review_prompt_placeholders_and_format_intact():
    """占位符集合与五个固定维度名保持不变，format 渲染不报错"""
    template = _read_prompt("review_prompt.txt")

    assert set(re.findall(_PLACEHOLDER_PATTERN, template)) == {
        "topic", "outline", "titles", "copywriting", "tags",
    }

    rendered = template.format(
        topic="主题", outline="大纲", titles="标题",
        copywriting="文案", tags="标签",
    )
    # 五个固定维度名不能变（后端归一化与前端展示依赖）
    for name in ("封面钩子", "标题吸引力", "内容结构", "情绪价值", "行动引导"):
        assert name in rendered
    # 维度数量约定仍是恰好 5 项（未新增维度）
    assert "恰好 5 项" in rendered


def test_review_prompt_content_structure_covers_completion_criteria():
    """「内容结构」维度评审要点包含完读结构标准"""
    template = _read_prompt("review_prompt.txt")

    assert "完读结构" in template
    assert "第 2 页" in template
    assert "反转" in template
    assert "互动钩子" in template
