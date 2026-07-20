"""
热点节点（营销日历图层）服务

为内容日历提供全年营销节点的静态数据与日期区间查询，
帮助创作者提前 3-14 天备稿。纯本地计算，不调用任何外部 API、
不依赖 AI 模型配置（数据类工具在未配置模型时也要可用）。

节点分三类（type）：
- festival: 公历/农历节日（元旦、情人节、春节、中秋等）
- ecommerce: 电商大促节点（年货节、618、双 11、双 12）
- season: 周期性节点（寒暑假、开学季、换季、年终总结季），按月份规则逐年生成

单个节点字段：
- id: 稳定标识（日期 + 名称）
- name: 节点名称
- date: 公历日期（YYYY-MM-DD）
- type: 节点类型（festival/ecommerce/season）
- prep_days: 建议提前备稿天数（3-14）
- platform_hint: 平台侧重提示（如"小红书情人节礼物攻略流量高峰提前 10 天"）
- niche_hint: 适配赛道提示

农历节日不做本地推算（不引第三方农历库），内置 2026-2028 三年的
公历对照表；超出该范围的年份优雅降级：只返回公历/规则节点。
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

# 节点类型枚举
HOTSPOT_TYPES = ("festival", "ecommerce", "season")

# 无参数请求时的默认查询窗口：未来 60 天
DEFAULT_RANGE_DAYS = 60

# ==================== 公历固定节点（每年同一天） ====================
# (month, day, name, type, prep_days, platform_hint, niche_hint)
_YEARLY_FIXED_NODES: List[Tuple[int, int, str, str, int, str, str]] = [
    (1, 1, "元旦", "festival", 7,
     "全平台新年 Flag/年度总结内容高峰，元旦前一周开始预热",
     "个人成长、职场、健身、学习打卡"),
    (1, 10, "年货节", "ecommerce", 14,
     "电商年货节大促，小红书/抖音好物清单类内容提前 2 周布局",
     "美食、家居好物、送礼攻略、母婴"),
    (2, 14, "情人节", "festival", 10,
     "小红书情人节礼物攻略流量高峰提前 10 天，抖音情侣向内容同步升温",
     "礼物攻略、情感、美妆、约会穿搭"),
    (3, 8, "38 妇女节", "festival", 10,
     "电商 38 大促与她经济话题并行，小红书女性成长/好物内容提前布局",
     "美妆个护、女性成长、好物清单"),
    (5, 1, "劳动节", "festival", 7,
     "五一出游攻略搜索量大涨，旅游/探店内容提前一周发布抢占搜索",
     "旅游攻略、探店、露营、亲子出行"),
    (5, 20, "520", "festival", 10,
     "520 表白节礼物种草高峰，小红书攻略类笔记提前 10 天进入流量池",
     "礼物攻略、情感、婚恋、美妆"),
    (6, 18, "618", "ecommerce", 14,
     "618 大促预售期长，好物测评/凑单攻略提前 2 周开始铺量",
     "数码家电、美妆、家居好物、省钱攻略"),
    (9, 10, "教师节", "festival", 7,
     "尊师感恩类话题与礼物攻略并行，公众号/小红书提前一周备稿",
     "教育、送礼攻略、校园、手工"),
    (10, 1, "国庆节", "festival", 14,
     "国庆长假出游攻略提前 2 周搜索量爆发，旅游内容务必提前发布",
     "旅游攻略、探店、拍照打卡、自驾"),
    (11, 11, "双 11", "ecommerce", 14,
     "双 11 预售期好物清单/攻略类内容流量最高，提前 2 周布局",
     "好物测评、省钱攻略、美妆、数码家电"),
    (12, 12, "双 12", "ecommerce", 10,
     "双 12 主打清单收尾与年末囤货，攻略类内容提前 10 天发布",
     "好物清单、年末囤货、家居"),
    (12, 25, "圣诞节", "festival", 10,
     "圣诞氛围感内容（穿搭/拍照/礼物）提前 10 天进入流量高峰",
     "礼物攻略、氛围感穿搭、美食、拍照打卡"),
]

# ==================== 周期性节点（按月份规则逐年生成） ====================
_SEASONAL_NODES: List[Tuple[int, int, str, str, int, str, str]] = [
    (1, 15, "寒假开启", "season", 10,
     "学生党/亲子内容进入寒假流量季，假期规划类选题提前 10 天备稿",
     "学习规划、亲子活动、游戏、宅家好物"),
    (3, 1, "春季开学季", "season", 10,
     "开学好物/学习计划搜索高峰，小红书清单类笔记提前 10 天发布",
     "文具好物、学习方法、宿舍收纳、通勤穿搭"),
    (3, 20, "春夏换季", "season", 14,
     "换季穿搭/护肤内容需求爆发，穿搭博主提前 2 周准备春夏企划",
     "穿搭、护肤、衣橱整理、家居换新"),
    (7, 1, "暑假流量季", "season", 10,
     "暑假全平台活跃度上升，旅行/技能学习/亲子选题提前布局",
     "旅游、技能学习、亲子、副业"),
    (9, 1, "秋季开学季", "season", 10,
     "秋季开学装备与新学期计划类内容高峰，提前 10 天备稿",
     "开学好物、学习规划、校园生活"),
    (9, 20, "秋冬换季", "season", 14,
     "秋冬换季穿搭/护肤/养生内容需求上升，提前 2 周准备企划",
     "穿搭、护肤保湿、养生、家居保暖"),
    (12, 15, "年终总结季", "season", 7,
     "年度总结/明年计划类内容在 12 月中下旬集中爆发，提前一周备稿",
     "个人成长、职场复盘、理财总结、年度书单"),
]

# ==================== 农历节日（内置 2026-2028 公历对照表） ====================
# 数据来源：公开万年历（老黄历网/万年历）2026-2028 年农历-公历对照，
# 覆盖年份范围：2026-2028。超出范围的年份不生成农历节点（优雅降级）。
# 年份 -> {节日名: (month, day)}
_LUNAR_FESTIVAL_TABLE: Dict[int, Dict[str, Tuple[int, int]]] = {
    2026: {
        "春节": (2, 17),
        "元宵节": (3, 3),
        "端午节": (6, 19),
        "七夕节": (8, 19),
        "中秋节": (9, 25),
        "重阳节": (10, 18),
    },
    2027: {
        "春节": (2, 6),
        "元宵节": (2, 20),
        "端午节": (6, 9),
        "七夕节": (8, 8),
        "中秋节": (9, 15),
        "重阳节": (10, 8),
    },
    2028: {
        "春节": (1, 26),
        "元宵节": (2, 9),
        "端午节": (5, 28),
        "七夕节": (8, 26),
        "中秋节": (10, 3),
        "重阳节": (10, 26),
    },
}

# 农历对照表覆盖的年份范围（用于降级判断与对外说明）
LUNAR_YEARS = tuple(sorted(_LUNAR_FESTIVAL_TABLE.keys()))

# 农历节日的类型与提示元信息（与对照表按名称关联）
_LUNAR_NODE_META: Dict[str, Tuple[str, int, str, str]] = {
    "春节": ("festival", 14,
             "春节全平台流量最高峰，年味/团圆/返乡选题提前 2 周排产",
             "美食年菜、家乡文化、亲情情感、新年穿搭"),
    "元宵节": ("festival", 7,
              "元宵节汤圆/灯会氛围内容，春节流量长尾的收尾节点",
              "美食、传统文化、手工 DIY"),
    "端午节": ("festival", 10,
              "端午小长假 + 粽子话题双热点，美食与出游内容提前 10 天",
              "美食教程、传统文化、周边游"),
    "七夕节": ("festival", 10,
              "七夕礼物攻略在小红书提前 10 天进入搜索高峰，情感话题同步升温",
              "礼物攻略、情感、约会妆容穿搭"),
    "中秋节": ("festival", 10,
              "中秋团圆/月饼测评/礼盒攻略流量高峰，提前 10 天布局",
              "美食测评、送礼攻略、家庭情感"),
    "重阳节": ("festival", 7,
              "重阳敬老话题适合情感向与养生向内容，提前一周备稿",
              "养生、亲情情感、传统文化"),
}


def _parse_date(value: str, field: str) -> date:
    """解析 YYYY-MM-DD 日期字符串（严格补零格式），格式非法抛 ValueError。"""
    text = str(value or "").strip()
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
        # strptime 会宽松接受 "2026-1-1" 这类未补零写法，这里要求严格 ISO 格式
        if parsed.isoformat() != text:
            raise ValueError(text)
        return parsed
    except ValueError:
        raise ValueError(f"{field} 日期格式非法：{text or '(空)'}，应为 YYYY-MM-DD")


def resolve_range(
    start: Optional[str] = None,
    end: Optional[str] = None,
    today: Optional[date] = None,
) -> Tuple[str, str]:
    """
    归一化查询区间：
    - start 缺省 -> 今天
    - end 缺省 -> start + DEFAULT_RANGE_DAYS 天（默认未来 60 天）

    Returns:
        (start, end) 的 YYYY-MM-DD 字符串对

    Raises:
        ValueError: 日期格式非法或 start 晚于 end 时抛出
    """
    base = today or date.today()

    start_date = base if not str(start or "").strip() else _parse_date(start, "start")
    end_date = (
        start_date + timedelta(days=DEFAULT_RANGE_DAYS)
        if not str(end or "").strip()
        else _parse_date(end, "end")
    )

    if start_date > end_date:
        raise ValueError(
            f"start 不能晚于 end：{start_date.isoformat()} > {end_date.isoformat()}"
        )
    return start_date.isoformat(), end_date.isoformat()


def _build_node(
    d: date, name: str, node_type: str, prep_days: int,
    platform_hint: str, niche_hint: str,
) -> Dict:
    """构造单个节点字典（id 由日期 + 名称组成，跨年份稳定）。"""
    return {
        "id": f"{d.isoformat()}-{name}",
        "name": name,
        "date": d.isoformat(),
        "type": node_type,
        "prep_days": prep_days,
        "platform_hint": platform_hint,
        "niche_hint": niche_hint,
    }


def _nodes_for_year(year: int) -> List[Dict]:
    """生成某一年的全部节点（公历固定 + 周期性规则 + 农历对照表命中）。"""
    nodes: List[Dict] = []

    for month, day, name, node_type, prep, p_hint, n_hint in (
        list(_YEARLY_FIXED_NODES) + list(_SEASONAL_NODES)
    ):
        nodes.append(_build_node(date(year, month, day), name, node_type, prep, p_hint, n_hint))

    # 农历节日：仅对照表覆盖的年份生成，超出范围优雅降级（跳过）
    lunar_table = _LUNAR_FESTIVAL_TABLE.get(year)
    if lunar_table:
        for name, (month, day) in lunar_table.items():
            node_type, prep, p_hint, n_hint = _LUNAR_NODE_META[name]
            nodes.append(_build_node(date(year, month, day), name, node_type, prep, p_hint, n_hint))

    return nodes


def get_hotspots(start: str, end: str) -> List[Dict]:
    """
    返回区间内（含端点）的节点列表，按日期升序（同日按名称排序保证稳定）。

    Args:
        start: 区间起点（YYYY-MM-DD）
        end: 区间终点（YYYY-MM-DD）

    Raises:
        ValueError: 日期格式非法或 start 晚于 end 时抛出
    """
    start_date = _parse_date(start, "start")
    end_date = _parse_date(end, "end")
    if start_date > end_date:
        raise ValueError(
            f"start 不能晚于 end：{start_date.isoformat()} > {end_date.isoformat()}"
        )

    nodes: List[Dict] = []
    for year in range(start_date.year, end_date.year + 1):
        nodes.extend(_nodes_for_year(year))

    start_str, end_str = start_date.isoformat(), end_date.isoformat()
    hit = [n for n in nodes if start_str <= n["date"] <= end_str]
    return sorted(hit, key=lambda n: (n["date"], n["name"]))
