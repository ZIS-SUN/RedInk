"""
禁用词扫描工具（backend/utils/banned_words.py）测试

纯函数测试：子串匹配、去重、空输入与非法项兜底。
"""
from backend.utils.banned_words import scan_banned_words


def test_scan_hits_substrings_in_order():
    text = "这款面霜真的绝绝子，用完直呼 yyds！"
    assert scan_banned_words(text, ["绝绝子", "yyds", "无中生有"]) == ["绝绝子", "yyds"]


def test_scan_no_hits_returns_empty():
    assert scan_banned_words("普通的一句话", ["绝绝子", "yyds"]) == []


def test_scan_empty_text_or_words_returns_empty():
    assert scan_banned_words("", ["绝绝子"]) == []
    assert scan_banned_words(None, ["绝绝子"]) == []
    assert scan_banned_words("有内容", []) == []
    assert scan_banned_words("有内容", None) == []


def test_scan_deduplicates_banned_words():
    # 禁用词列表重复、命中多次，结果只保留一次
    text = "绝绝子真的绝绝子"
    assert scan_banned_words(text, ["绝绝子", "绝绝子", " 绝绝子 "]) == ["绝绝子"]


def test_scan_ignores_blank_and_invalid_items():
    text = "含有 yyds 的文本"
    assert scan_banned_words(text, [None, "", "   ", "yyds"]) == ["yyds"]


def test_scan_matches_substring_inside_word():
    # 简单子串匹配：禁用词作为长词一部分也算命中
    assert scan_banned_words("这也太yyds了吧", ["yyds"]) == ["yyds"]
