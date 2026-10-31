# -*- coding: utf-8 -*-
"""从档案正文中提取可用于对比的关键事实。

为什么需要：档案的「学校速览」是键值表，字段名各校不完全统一
（荣誉类会出现「市级」「省级」等），无法直接当结构化字段用。
但对比页只需要少数几个稳定且有决策价值的项，因此按同义词表模糊匹配。

提取失败是常态（例如小学没有投档线），调用方应把缺失显示为「—」，
不要把缺失当成 0 或默认值。
"""
import re

KV_ROW = re.compile(r"^\|\s*([^|]{1,24}?)\s*\|\s*(.+?)\s*\|\s*[ABC]\s*\|\s*$", re.M)

# 字段 → 可能的键名（前缀匹配）
# 同一个语义在档案里有多种写法，只写一种就会静默漏掉一批：
# 「对口初中」182 所 +「主要生源/对口初中」21 所 +「施教区对口初中」12 所。
FACT_KEYS = {
    "founded": ("创办时间", "建校时间", "创办年份"),
    "address": ("校址", "学校地址", "地址"),
    "feeder": ("对口初中", "主要生源/对口初中", "施教区对口初中"),
    "tuition": ("学费", "收费标准"),
    "score": ("2026 投档线", "投档线", "2026投档线"),
    "plan": ("2026 招生计划", "招生计划"),
    "classes": ("核心班型", "班型", "班级规模"),
    # 下面三项是四期新增：覆盖率远高于原有字段，且对择校更实用。
    # 咨询电话 52%——比「有没有官网」（34%）更直接可用。
    "phone": ("咨询电话", "招生咨询电话", "联系电话", "办公电话", "招办电话"),
    "group": ("集团归属", "所属集团"),
    "scale": ("办学规模",),
    # 初中侧的对口关系是反方向写的：不是「我对口哪所初中」，而是「我主要收哪些小学的生源」
    "sources": ("主要生源小学",),
    # 下面四项是「家长真正拿来比的东西」，此前只能去档案正文里翻。
    # 键名按实测出现频次排：专任教师 17 / 教师总数 12 / 骨干教师 12 / 特级 11+10+9。
    "teachers": ("专任教师", "教师总数", "在职教师", "师资"),
    "backbone": ("骨干教师", "区级以上骨干教师", "特级教师", "省特级教师",
                 "江苏省特级教师", "正高级教师"),
    # 「2026 电脑派位计划」比「2026 电脑派位」长，必须排在前面，否则会被前缀先吃掉
    "lottery": ("2026 电脑派位计划", "2026 小学电脑派位", "2026 热点公办小学派位",
                "2026 电脑派位", "2026 摇号计划", "电脑派位计划", "摇号计划"),
}

# 对比页展示顺序与中文标签
FACT_LABELS = {
    "founded": "创办时间",
    "address": "校址",
    "feeder": "对口初中",
    "tuition": "学费",
    "score": "2026 投档线",
    "plan": "2026 招生计划",
    "classes": "班型",
    "phone": "咨询电话",
    "group": "集团归属",
    "scale": "办学规模",
    "sources": "主要生源小学",
    "teachers": "教职工",
    "backbone": "骨干/特级教师",
    "lottery": "2026 派位计划",
    # 摘录类：不是从键值表抽的，是 excerpt() 截的原文。
    # 必须登记在这里，否则 check.py 的「facts 字段必须有中文名」守卫会拦下来。
    "reputation": "升学口碑（原文摘录）",
}

_EMPTY = {"", "—", "-", "–", "未获取", "未公开", "暂无"}

# ---- 学校库「数据项」筛选用 ----
# 只放家长会真的拿来筛的四项：能筛 ≠ 字段多。
# 顺序即界面上的顺序；HAS_LABELS 同时用作筛选按钮的文案与 schools-data 里的标记值。
HAS_ORDER = ("tuition", "score", "plan", "feeder")
HAS_LABELS = {
    "tuition": "有学费",
    "score": "有投档线",
    "plan": "有招生计划",
    "feeder": "有对口初中",
}

# ---- 「数据缺口」小节的字段级判定 ----
# 只在这一个小节里找关键词：该小节的语义就是「以下内容未能从公开渠道获得」，
# 所以在这里被点名过的字段，才可以负责任地标成「未获取」；否则只能标「未收录」。
#
# 关键词刻意收窄。最初 classes 用了（"班型", "班级"），
# 结果把「学校占地面积、建筑面积、班级与学生总数」也算成「班型缺口」——
# 那句讲的是办学规模，不是班型，属误标。宁少不滥。
MISSING_HEAD = re.compile(r"^#{2,4}\s*.*数据缺口.*$", re.M)
MISSING_NEXT = re.compile(r"^#{1,4}\s", re.M)
MISSING_KW = {
    "founded": ("创办", "建校"),
    "address": ("校址", "地址"),
    "feeder": ("对口初中",),
    "tuition": ("学费", "收费"),
    "score": ("投档线", "录取线", "分数线"),
    "plan": ("招生计划",),
    "classes": ("班型",),
}
# 讲「成绩 / 升学结果」的行不算这一项的缺口。
# 典型误标：「对口初中（二十九中初中部）的完整中考数据」——
# 缺的是中考数据，不是对口关系本身，整节匹配会把它算成 feeder 缺口（实测多出 36 所）。
MISSING_NEG = ("中考", "成绩", "升学率", "录取", "分数", "排名", "高考")


def extract_missing(text):
    """返回档案**明确声明**为数据缺口的字段集合。

    逐行判定，并跳过讲成绩的行——整节通篇匹配会造成误标。
    找不到「数据缺口」小节时返回空集——不猜。
    """
    m = MISSING_HEAD.search(text)
    if not m:
        return set()
    rest = text[m.end():]
    n = MISSING_NEXT.search(rest)
    sec = rest[:n.start()] if n else rest[:2000]

    out = set()
    for line in sec.splitlines():
        if not line.strip() or any(w in line for w in MISSING_NEG):
            continue
        for field, words in MISSING_KW.items():
            if any(w in line for w in words):
                out.add(field)
    return out


def extract(text):
    """返回 {field: value}；只保留有实际内容的项。"""
    out = {}
    for m in KV_ROW.finditer(text):
        key = m.group(1).strip().strip("*").strip()
        for field, names in FACT_KEYS.items():
            if field in out:
                continue
            if any(key.startswith(n) for n in names):
                value = _clean(m.group(2))
                if value and value not in _EMPTY:
                    out[field] = value[:60]
    return out


def _clean(v):
    v = re.sub(r"<[^>]+>", "", v)
    v = re.sub(r"\*\*|`|\[[ABC]\]", "", v)
    v = re.sub(r"\s+", " ", v)
    return v.strip(" 　|")


# ---------------------------------------------------------------- 摘录类

# 口碑与办学特色无法结构化（每份档案的写法都不同），但家长确实要看。
# 做法是截一段原文放进对比表，并在界面上标明「原文摘录」——
# 不摘要、不改写，避免把叙述变成结论。
_SECTION_HEAD = {
    "reputation": re.compile(r"^#{2,4}\s*.*口碑.*$", re.M),
    "feature": re.compile(r"^#{2,4}\s*.*(?:办学特色|师资).*$", re.M),
}
_NEXT_HEAD = re.compile(r"^#{2,4}\s", re.M)


def excerpt(text, kind, limit=44):
    """从指定小节取第一句可用的话，返回纯文本；取不到返回空串。

    长度压到 44 字：对比表一列只有 200px 左右，再长就折成四五行，
    反而比短句更难扫。想要全文的人点进档案即可。

    先按「优势共识」这类小标题找起，找不到就从小节开头取。
    过滤掉表格行、纯列表符号与信度标记——那些在单元格里没法读。
    """
    head = _SECTION_HEAD.get(kind)
    if not head:
        return ""
    m = head.search(text)
    if not m:
        return ""
    # 不能止于「下一个标题」：这些小节的第一行往往就是 ### 7.1 这样的子标题，
    # 那样截出来的段落是空的（实测「师资」只有 60 份能取到，正是这个原因）。
    # 改为向后多取一段，逐行跳过标题/表格，取第一句能读的话。
    seg = text[m.end():m.end() + 1600]

    # 「优势共识」之后的内容比开头那行小标题更有信息量
    pos = seg.find("优势共识")
    if pos != -1:
        seg = seg[pos + 4:]

    for line in seg.splitlines():
        s = line.strip()
        if not s or s.startswith(("|", ">", "#", "**优势", "**争议")):
            continue
        s = re.sub(r"^[-*+]\s*", "", s)
        s = re.sub(r"\[([ABC])\]", "", s)
        s = re.sub(r"[*`>]", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        # 太短的（「管理严格」四个字）信息量不足，跳过取下一行
        if len(s) < 10:
            continue
        return s[:limit] + ("…" if len(s) > limit else "")
    return ""
