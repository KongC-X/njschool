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
}

_EMPTY = {"", "—", "-", "–", "未获取", "未公开", "暂无"}

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
