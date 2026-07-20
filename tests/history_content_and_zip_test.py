"""
发布包相关测试：

- 历史记录 content（标题/文案/标签）的创建与更新落库
- 坏结构 content 静默忽略
- 旧记录（无 content 字段）读取向后兼容
- zip 发布包中「发布文案.txt」的有无与内容
"""
import io
import json
import zipfile
from pathlib import Path

from backend.services.history import HistoryService
from backend.routes.history_routes import _build_publish_text, _create_images_zip


def make_history_service(tmp_path: Path) -> HistoryService:
    service = HistoryService.__new__(HistoryService)
    service.history_dir = str(tmp_path)
    service.index_file = str(tmp_path / "index.json")
    service._init_index()
    return service


SAMPLE_OUTLINE = {
    "raw": "原始大纲文本",
    "pages": [
        {"index": 0, "type": "cover", "content": "封面"},
        {"index": 1, "type": "content", "content": "内容"},
    ],
}

SAMPLE_CONTENT = {
    "titles": ["推荐标题", "备选标题"],
    "copywriting": "正文文案第一段\n第二段",
    "tags": ["穿搭", "秋季"],
}


# ==================== content 落库 ====================

def test_create_record_with_content(tmp_path):
    service = make_history_service(tmp_path)
    record_id = service.create_record(
        "topic", SAMPLE_OUTLINE, content=SAMPLE_CONTENT
    )

    record = service.get_record(record_id)
    assert record["content"] == SAMPLE_CONTENT


def test_create_record_without_content_keeps_old_shape(tmp_path):
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    record = service.get_record(record_id)
    assert "content" not in record


def test_update_record_persists_content(tmp_path):
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    assert service.update_record(record_id, content=SAMPLE_CONTENT)

    record = service.get_record(record_id)
    assert record["content"] == SAMPLE_CONTENT

    # 再次更新覆盖旧值
    new_content = {"titles": ["新标题"], "copywriting": "新文案", "tags": []}
    assert service.update_record(record_id, content=new_content)
    assert service.get_record(record_id)["content"] == new_content


def test_update_record_ignores_bad_content_structure(tmp_path):
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE, content=SAMPLE_CONTENT)

    bad_contents = [
        "not-a-dict",
        ["titles"],
        {"titles": "应为数组", "copywriting": "x", "tags": []},
        {"titles": ["ok"], "copywriting": 123, "tags": []},
        {"titles": ["ok"], "copywriting": "x", "tags": [1, 2]},
        {"titles": [1], "copywriting": "x", "tags": []},
        {},
    ]
    for bad in bad_contents:
        # 更新本身成功（不报错），坏结构不写入、不覆盖已有值
        assert service.update_record(record_id, content=bad)
        assert service.get_record(record_id)["content"] == SAMPLE_CONTENT


def test_create_record_ignores_bad_content_structure(tmp_path):
    service = make_history_service(tmp_path)
    record_id = service.create_record(
        "topic", SAMPLE_OUTLINE, content={"titles": "bad"}
    )

    record = service.get_record(record_id)
    assert "content" not in record


def test_legacy_record_without_content_reads_fine(tmp_path):
    """旧版记录文件（无 content 字段）读取与更新不报错"""
    service = make_history_service(tmp_path)
    record_id = service.create_record("topic", SAMPLE_OUTLINE)

    # 模拟旧数据：直接改写记录文件，确保没有 content 键
    record_path = Path(service._get_record_path(record_id))
    legacy = json.loads(record_path.read_text(encoding="utf-8"))
    legacy.pop("content", None)
    record_path.write_text(
        json.dumps(legacy, ensure_ascii=False), encoding="utf-8"
    )

    record = service.get_record(record_id)
    assert record is not None
    assert "content" not in record

    # 常规更新（不带 content）也不受影响
    assert service.update_record(record_id, status="generating")
    assert service.get_record(record_id)["status"] == "generating"


# ==================== zip 发布包 ====================

def _make_task_dir(tmp_path: Path) -> Path:
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    (task_dir / "0.png").write_bytes(b"png-0")
    (task_dir / "1.png").write_bytes(b"png-1")
    (task_dir / "thumb_0.png").write_bytes(b"thumb")
    return task_dir


def test_zip_contains_publish_text_when_content_exists(tmp_path):
    task_dir = _make_task_dir(tmp_path)
    record = {
        "outline": SAMPLE_OUTLINE,
        "content": SAMPLE_CONTENT,
    }

    buffer = _create_images_zip(str(task_dir), record)
    with zipfile.ZipFile(io.BytesIO(buffer.read())) as zf:
        names = zf.namelist()
        assert sorted(n for n in names if n.endswith(".png")) == ["page_1.png", "page_2.png"]
        assert "发布文案.txt" in names

        text = zf.read("发布文案.txt").decode("utf-8")
        # 首行必须是 AIGC 标注合规提醒（B1 合规护栏）
        assert "AI 辅助生成" in text.splitlines()[0]
        assert "【标题候选】\n推荐标题\n备选标题" in text
        assert "【正文文案】\n正文文案第一段\n第二段" in text
        assert "【标签】\n#穿搭 #秋季" in text
        assert "——分隔线——" in text
        assert "【大纲原文】\n原始大纲文本" in text


def test_zip_has_no_publish_text_without_content_or_outline(tmp_path):
    task_dir = _make_task_dir(tmp_path)

    # record 为 None（保持旧调用行为）
    buffer = _create_images_zip(str(task_dir))
    with zipfile.ZipFile(io.BytesIO(buffer.read())) as zf:
        assert "发布文案.txt" not in zf.namelist()

    # record 无 content 且大纲原文为空
    record = {"outline": {"raw": "", "pages": []}}
    buffer = _create_images_zip(str(task_dir), record)
    with zipfile.ZipFile(io.BytesIO(buffer.read())) as zf:
        assert "发布文案.txt" not in zf.namelist()


def test_zip_outline_only_record_still_gets_publish_text(tmp_path):
    """旧记录只有大纲：发布文案.txt 仅含分隔线 + 大纲原文小节"""
    task_dir = _make_task_dir(tmp_path)
    record = {"outline": SAMPLE_OUTLINE}

    buffer = _create_images_zip(str(task_dir), record)
    with zipfile.ZipFile(io.BytesIO(buffer.read())) as zf:
        text = zf.read("发布文案.txt").decode("utf-8")
        assert "【标题候选】" not in text
        assert "【正文文案】" not in text
        assert "【标签】" not in text
        assert "【大纲原文】\n原始大纲文本" in text


def test_publish_text_starts_with_aigc_notice():
    """发布文案.txt 首行是 AIGC 标注提醒；无内容时依旧不产出文件（B1）"""
    record = {"outline": SAMPLE_OUTLINE, "content": SAMPLE_CONTENT}
    text = _build_publish_text(record)

    first_line = text.splitlines()[0]
    assert "AI 辅助生成" in first_line
    assert "AI 内容声明" in first_line
    assert "限流" in first_line

    # 只有大纲的旧记录同样带提醒
    outline_only = _build_publish_text({"outline": SAMPLE_OUTLINE})
    assert "AI 辅助生成" in outline_only.splitlines()[0]

    # 完全没有可用内容时仍返回空串（不会只输出一行提醒）
    assert _build_publish_text(None) == ""
    assert _build_publish_text({}) == ""


def test_build_publish_text_skips_missing_sections():
    # 只有标签 + 大纲
    record = {
        "outline": {"raw": "raw-text", "pages": []},
        "content": {"titles": [], "copywriting": "", "tags": ["a"]},
    }
    text = _build_publish_text(record)
    assert "【标题候选】" not in text
    assert "【正文文案】" not in text
    assert "【标签】\n#a" in text
    assert "【大纲原文】\nraw-text" in text

    # 完全没有内容
    assert _build_publish_text(None) == ""
    assert _build_publish_text({}) == ""
