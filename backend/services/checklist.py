"""
发布前体检清单服务（纯规则引擎，不调用 LLM）

对成品的标题/正文/标签/图片按目标平台的发布规范做合规性检查：
- 标题长度、正文长度、标签数量、图片数量
- 禁用词命中（调用方传入，通常来自品牌档案的 banned_words）
- 通用敏感营销词软提示（广告法高风险词，warn 级）

所有规则均为纯函数计算，便于单元测试；字数按字符数统计（中文一个字
算一个字符），统计前去除首尾空白。
"""

from typing import Dict, List

# 检查项状态常量
STATUS_PASS = "pass"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"

# 平台发布规范常量表
# 注意：以下数值整理自各平台公开的发布规范常识（产品页面提示/帮助中心），
# 并非官方 API 返回值，平台调整规则时需要同步维护。
# - level 表示超限时的严重程度：fail=平台硬性限制，warn=建议值
PLATFORM_RULES: Dict[str, Dict] = {
    "xiaohongshu": {
        "name": "小红书",
        # 标题上限 20 字（平台硬限制）
        "title": {"max": 20, "level": STATUS_FAIL},
        # 正文上限 1000 字（平台硬限制）
        "body": {"max": 1000, "level": STATUS_FAIL},
        # 标签建议 3-10 个：0 个提醒补充，超过 10 个提醒精简
        "tags": {"min": 3, "max": 10, "level": STATUS_WARN},
        # 图文笔记最多 18 张图（平台硬限制）
        "images": {"max": 18, "level": STATUS_FAIL},
    },
    "douyin": {
        "name": "抖音",
        # 标题建议 30 字以内（超出为建议级提醒）
        "title": {"max": 30, "level": STATUS_WARN},
        # 短文案建议 300 字以内，过长影响完读率
        "body": {"max": 300, "level": STATUS_WARN},
        # 话题标签建议不超过 5 个
        "tags": {"min": 1, "max": 5, "level": STATUS_WARN},
        # 图文最多 35 张图（平台硬限制）
        "images": {"max": 35, "level": STATUS_FAIL},
    },
    "weixin": {
        "name": "微信公众号",
        # 图文消息标题上限 64 字（平台硬限制）
        "title": {"max": 64, "level": STATUS_FAIL},
        # 正文常识性建议上限（正文过长影响阅读体验）
        "body": {"max": 20000, "level": STATUS_WARN},
        # 文章标签建议不超过 5 个
        "tags": {"min": 0, "max": 5, "level": STATUS_WARN},
        # 单篇图片建议不超过 20 张，过多影响加载
        "images": {"max": 20, "level": STATUS_WARN},
    },
    "bilibili": {
        "name": "B站",
        # 稿件/专栏标题上限 80 字（平台硬限制）
        "title": {"max": 80, "level": STATUS_FAIL},
        # 动态类正文建议 2000 字以内
        "body": {"max": 2000, "level": STATUS_WARN},
        # 话题标签上限 10 个
        "tags": {"min": 1, "max": 10, "level": STATUS_WARN},
        # 图片动态最多 9 张
        "images": {"max": 9, "level": STATUS_WARN},
    },
    "weibo": {
        "name": "微博",
        # 头条文章标题建议 30 字以内
        "title": {"max": 30, "level": STATUS_FAIL},
        # 普通微博正文上限 2000 字（平台硬限制）
        "body": {"max": 2000, "level": STATUS_FAIL},
        # 话题建议不超过 3 个，过多稀释权重
        "tags": {"min": 0, "max": 3, "level": STATUS_WARN},
        # 单条微博最多 18 张图
        "images": {"max": 18, "level": STATUS_WARN},
    },
}

# 通用敏感营销词（广告法高风险用语，命中仅做 warn 级软提示）
SENSITIVE_MARKETING_WORDS = (
    "最", "第一", "国家级", "百分百", "绝对",
    "顶级", "独家", "全网最低", "零风险", "秒杀",
)

# 命中位置的中文展示名
_LOCATION_TITLE = "标题"
_LOCATION_BODY = "正文"
_LOCATION_TAGS = "标签"


def _text_len(value: str) -> int:
    """按字符数统计文本长度（中文一个字算一个字符），先去除首尾空白。"""
    return len(value.strip())


def _normalize_str(value) -> str:
    """归一化为去首尾空白的字符串，None 视为空串。"""
    if value is None:
        return ""
    return str(value).strip()


def _normalize_str_list(value) -> List[str]:
    """归一化为非空字符串列表，非法输入视为空列表。"""
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = _normalize_str(item)
        if text:
            result.append(text)
    return result


def _find_word_locations(word: str, title: str, body: str, tags: List[str]) -> List[str]:
    """返回某个词命中的位置列表（标题/正文/标签），未命中返回空列表。"""
    locations = []
    if word in title:
        locations.append(_LOCATION_TITLE)
    if word in body:
        locations.append(_LOCATION_BODY)
    if any(word in tag for tag in tags):
        locations.append(_LOCATION_TAGS)
    return locations


def _format_word_hits(hits: List[Dict]) -> str:
    """把命中词列表格式化为「词（位置1、位置2）」形式的说明文字。"""
    return "；".join(
        f"「{hit['word']}」（{'、'.join(hit['locations'])}）" for hit in hits
    )


def _check_title(rules: Dict, title: str) -> Dict:
    """标题长度检查。"""
    rule = rules["title"]
    length = _text_len(title)
    if length == 0:
        return {
            "id": "title_length",
            "label": "标题长度",
            "status": STATUS_WARN,
            "detail": "尚未生成标题，建议补充后再发布。",
        }
    if length > rule["max"]:
        hard_limit = rule["level"] == STATUS_FAIL
        return {
            "id": "title_length",
            "label": "标题长度",
            "status": rule["level"],
            "detail": (
                f"标题 {length} 字，超出{rules['name']}"
                f"{'上限' if hard_limit else '建议值'} {rule['max']} 字，"
                f"{'发布时会被截断或拒绝' if hard_limit else '建议精简'}。"
            ),
        }
    return {
        "id": "title_length",
        "label": "标题长度",
        "status": STATUS_PASS,
        "detail": f"标题 {length} 字，符合{rules['name']}要求（≤{rule['max']} 字）。",
    }


def _check_body(rules: Dict, body: str) -> Dict:
    """正文长度检查。"""
    rule = rules["body"]
    length = _text_len(body)
    if length == 0:
        return {
            "id": "body_length",
            "label": "正文长度",
            "status": STATUS_WARN,
            "detail": "尚未生成正文文案，建议补充后再发布。",
        }
    if length > rule["max"]:
        hard_limit = rule["level"] == STATUS_FAIL
        return {
            "id": "body_length",
            "label": "正文长度",
            "status": rule["level"],
            "detail": (
                f"正文 {length} 字，超出{rules['name']}"
                f"{'上限' if hard_limit else '建议值'} {rule['max']} 字，"
                f"{'发布时会被截断或拒绝' if hard_limit else '建议精简'}。"
            ),
        }
    return {
        "id": "body_length",
        "label": "正文长度",
        "status": STATUS_PASS,
        "detail": f"正文 {length} 字，符合{rules['name']}要求（≤{rule['max']} 字）。",
    }


def _check_tags(rules: Dict, tags: List[str]) -> Dict:
    """标签数量检查。"""
    rule = rules["tags"]
    count = len(tags)
    suggest = (
        f"建议 {rule['min']}-{rule['max']} 个"
        if rule["min"] > 0 else f"建议不超过 {rule['max']} 个"
    )
    if count == 0 and rule["min"] > 0:
        return {
            "id": "tags_count",
            "label": "标签数量",
            "status": STATUS_WARN,
            "detail": f"尚未添加标签，{rules['name']}{suggest}，有助于获得推荐流量。",
        }
    if count > rule["max"]:
        return {
            "id": "tags_count",
            "label": "标签数量",
            "status": rule["level"],
            "detail": f"当前 {count} 个标签，超出{rules['name']}{suggest}，建议精简。",
        }
    return {
        "id": "tags_count",
        "label": "标签数量",
        "status": STATUS_PASS,
        "detail": f"当前 {count} 个标签，符合{rules['name']}要求（{suggest}）。",
    }


def _check_images(rules: Dict, image_count: int) -> Dict:
    """图片数量检查。"""
    rule = rules["images"]
    if image_count <= 0:
        return {
            "id": "image_count",
            "label": "图片完整性",
            "status": STATUS_FAIL,
            "detail": "还没有生成任何图片，无法发布图文内容。",
        }
    if image_count > rule["max"]:
        hard_limit = rule["level"] == STATUS_FAIL
        return {
            "id": "image_count",
            "label": "图片完整性",
            "status": rule["level"],
            "detail": (
                f"共 {image_count} 张图片，超出{rules['name']}"
                f"{'上限' if hard_limit else '建议值'} {rule['max']} 张，"
                f"{'需删减后才能发布' if hard_limit else '建议删减'}。"
            ),
        }
    return {
        "id": "image_count",
        "label": "图片完整性",
        "status": STATUS_PASS,
        "detail": f"共 {image_count} 张图片，符合{rules['name']}要求（≤{rule['max']} 张）。",
    }


def _check_banned_words(banned_words: List[str], title: str, body: str, tags: List[str]) -> Dict:
    """禁用词命中检查（命中即 fail，detail 列出命中词与位置）。"""
    hits = []
    for word in banned_words:
        locations = _find_word_locations(word, title, body, tags)
        if locations:
            hits.append({"word": word, "locations": locations})

    if hits:
        return {
            "id": "banned_words",
            "label": "禁用词",
            "status": STATUS_FAIL,
            "detail": f"命中 {len(hits)} 个禁用词：{_format_word_hits(hits)}，请修改后再发布。",
        }
    detail = (
        "未命中任何禁用词。" if banned_words
        else "未配置禁用词（可在品牌档案中维护），本项跳过。"
    )
    return {
        "id": "banned_words",
        "label": "禁用词",
        "status": STATUS_PASS,
        "detail": detail,
    }


def _check_sensitive_words(title: str, body: str, tags: List[str]) -> Dict:
    """通用敏感营销词软提示（广告法高风险词，warn 级）。"""
    hits = []
    for word in SENSITIVE_MARKETING_WORDS:
        locations = _find_word_locations(word, title, body, tags)
        if locations:
            hits.append({"word": word, "locations": locations})

    if hits:
        return {
            "id": "sensitive_words",
            "label": "敏感营销词",
            "status": STATUS_WARN,
            "detail": (
                f"包含 {len(hits)} 个广告法高风险词：{_format_word_hits(hits)}，"
                "存在限流或违规风险，建议替换表述。"
            ),
        }
    return {
        "id": "sensitive_words",
        "label": "敏感营销词",
        "status": STATUS_PASS,
        "detail": "未发现常见广告法高风险用语。",
    }


def run_checklist(payload: Dict) -> Dict:
    """
    执行发布前体检清单（纯规则计算，不调用 LLM）

    Args:
        payload: 请求参数字典，字段：
            - platform: 平台标识（xiaohongshu/douyin/weixin/bilibili/weibo，必填）
            - title: 标题（可选）
            - body: 正文文案（可选）
            - tags: 标签列表（可选）
            - image_count: 已生成图片数（可选，默认 0）
            - banned_words: 禁用词列表（可选）

    Returns:
        Dict: {
            success: True,
            platform: 平台标识,
            items: [{id, label, status: 'pass'|'warn'|'fail', detail}],
            summary: {pass: n, warn: n, fail: n}
        }

    Raises:
        ValueError: platform 为空或不在支持列表中
    """
    platform = _normalize_str(payload.get("platform"))
    if platform not in PLATFORM_RULES:
        supported = "、".join(PLATFORM_RULES.keys())
        raise ValueError(f"不支持的平台「{platform or '(空)'}」，支持的平台：{supported}")

    rules = PLATFORM_RULES[platform]
    title = _normalize_str(payload.get("title"))
    body = _normalize_str(payload.get("body"))
    tags = _normalize_str_list(payload.get("tags"))
    banned_words = _normalize_str_list(payload.get("banned_words"))

    try:
        image_count = int(payload.get("image_count") or 0)
    except (TypeError, ValueError):
        image_count = 0
    image_count = max(image_count, 0)

    items = [
        _check_title(rules, title),
        _check_body(rules, body),
        _check_tags(rules, tags),
        _check_images(rules, image_count),
        _check_banned_words(banned_words, title, body, tags),
        _check_sensitive_words(title, body, tags),
    ]

    summary = {STATUS_PASS: 0, STATUS_WARN: 0, STATUS_FAIL: 0}
    for item in items:
        summary[item["status"]] += 1

    return {
        "success": True,
        "platform": platform,
        "items": items,
        "summary": summary,
    }
