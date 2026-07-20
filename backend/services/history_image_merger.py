"""历史图片列表合并与状态计算。"""
import os
import re
from typing import Dict, List, Optional

# 页面图片文件名主干：{index} 或单张重绘产生的 {index}_v{毫秒时间戳}
# （与 services/image.py 的版本化命名保持一致）
_PAGE_IMAGE_STEM_PATTERN = re.compile(r"^(\d+)(?:_v(\d+))?$")


class HistoryImageMerger:
    """处理 index-aligned images.generated。"""

    @staticmethod
    def has_images(generated: Optional[List[str]]) -> bool:
        return any(bool(item) for item in (generated or []))

    @staticmethod
    def merge_generated(
        existing: Optional[List[str]],
        page_index: int,
        filename: str,
        total_count: Optional[int] = None,
    ) -> List[str]:
        generated = [item or "" for item in (existing or [])]
        target_len = max(len(generated), page_index + 1, total_count or 0)
        while len(generated) < target_len:
            generated.append("")
        generated[page_index] = filename
        return generated

    @staticmethod
    def merge_many(
        existing: Optional[List[str]],
        files_by_index: Dict[int, str],
        total_count: Optional[int] = None,
    ) -> List[str]:
        generated = [item or "" for item in (existing or [])]
        target_len = max(len(generated), total_count or 0)
        if files_by_index:
            target_len = max(target_len, max(files_by_index.keys()) + 1)
        while len(generated) < target_len:
            generated.append("")
        for index, filename in files_by_index.items():
            generated[index] = filename
        return generated

    @staticmethod
    def compute_status(generated: Optional[List[str]], total_count: int) -> str:
        completed = sum(1 for item in (generated or []) if item)
        if completed == 0:
            return "draft"
        if total_count > 0 and completed >= total_count:
            return "completed"
        return "partial"

    @staticmethod
    def first_image(generated: Optional[List[str]]) -> Optional[str]:
        for item in generated or []:
            if item:
                return item
        return None

    @staticmethod
    def files_by_index(history_dir: str, task_id: str) -> Dict[int, str]:
        """
        扫描任务目录，返回 index -> 文件名 映射。

        同一页存在多个版本（如旧的 "0.png" 与重绘产生的 "0_v<时间戳>.png"
        并存，通常是旧版本清理失败）时取版本号最大者，避免目录同步把
        旧文件名合并回历史记录、覆盖重绘结果。
        """
        task_dir = os.path.join(history_dir, task_id)
        if not os.path.isdir(task_dir):
            return {}

        files: Dict[int, str] = {}
        versions: Dict[int, int] = {}
        for filename in os.listdir(task_dir):
            if filename.startswith("thumb_"):
                continue
            if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            match = _PAGE_IMAGE_STEM_PATTERN.match(filename.rsplit(".", 1)[0])
            if not match:
                continue
            index = int(match.group(1))
            version = int(match.group(2) or 0)  # 无版本后缀视为版本 0
            if index not in files or version > versions[index]:
                files[index] = filename
                versions[index] = version
        return dict(sorted(files.items()))
