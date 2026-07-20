"""
禁用词扫描工具

对生成结果做轻量的禁用词硬校验：简单子串匹配、按禁用词去重，
返回命中的禁用词列表（保持禁用词原有顺序），供前端做红色警示展示。
"""

from typing import Iterable, List, Optional


def scan_banned_words(text: Optional[str], banned_words: Optional[Iterable]) -> List[str]:
    """
    扫描文本中命中的禁用词（简单子串匹配，结果去重）

    参数：
        text: 待扫描文本（None / 空串视为无命中）
        banned_words: 禁用词列表（非法项/空白项自动忽略）

    返回：
        命中的禁用词列表（按禁用词出现顺序去重）
    """
    if not text or not banned_words:
        return []

    content = str(text)
    hits: List[str] = []
    seen = set()
    for word in banned_words:
        if word is None:
            continue
        keyword = str(word).strip()
        if not keyword or keyword in seen:
            continue
        if keyword in content:
            hits.append(keyword)
            seen.add(keyword)
    return hits
