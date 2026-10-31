# -*- coding: utf-8 -*-
"""中考分数反查：从「2026 投档线」字段里取出可比较的数字。

数据形态比预期复杂，实测 37 所里有五种写法：
    「察哈尔路 652 分（全市最高）；晓庄 645 分」        ← 多校区
    「600 分（渠道汇总）；机构口径 594 分」              ← 两个口径
    「618 分 / 12,087 名（语数英 304、语数 203）」       ← 分数与位次混写
    「第一批次 509 分；第二批次 484 分」                 ← 分批
    「第二批次投档控制线 440 分」                        ← 这是控制线，不是学校线

三条判断规则（都偏保守，宁可少推荐也不夸大可能性）：

  1. **判断线取最低值**。反查要回答的是「我这个分能不能进这所学校」，
     用最容易进的校区/批次算，才不会把本来能进的学校判成「够不着」。
     全部数值同时展示，家长能看到本部线。

  2. **同校多口径时保留冲突标记**，不静默取一个。本站数据冲突清单里
     明写了九中 625/619、南航附中 600/594 这类分歧，反查页若只显示一个数，
     等于替学校下了结论。

  3. **认不出就排除，不做兜底猜测**。控制线、往年分数、位次串一律不进计算，
     并在页面上列出「哪几所没有可比数据、为什么」。
"""
import re

# 「625 分」——只要三位数。中考总分 700，投档线实测区间 509–652。
_NUM = re.compile(r"(\d{3})\s*分")
# 整段都不采信：控制线不是学校投档线；往年分数不能与 2026 混用
_BAD_SEG = re.compile(r"控制线|20[0-2]\d\s*年|20[0-2]\d\s*届")
# 口径存疑的标记词
_CONFLICT = re.compile(r"渠道汇总|机构口径|机构站点|预估|网传")
# 校区/批次前缀，展示时去掉噪音词。批次要留着（「第一批次 509 / 第二批次 484」
# 是两条不同的录取通道，抹掉会让家长以为只有一个分数）。
_LABEL_NOISE = re.compile(r"统招|投档线|分数线|\(.*?\)|（.*?）")


def parse(raw):
    """返回 {'values': [{v, label}], 'conflict': bool, 'line': int|None}。

    line = 最低值，即判断用的那条线；values 保留全部口径供页面展示。
    """
    if not raw or raw.strip() in ("—", "-", "未获取"):
        return {"values": [], "conflict": False, "line": None}

    values = []
    for seg in re.split(r"[；;/]", raw):
        seg = seg.strip()
        if not seg or _BAD_SEG.search(seg):
            continue
        m = _NUM.search(seg)
        if not m:
            continue
        v = int(m.group(1))
        if not 400 <= v <= 700:      # 中考总分区间的硬边界，防止把人数当成分数
            continue
        label = _LABEL_NOISE.sub("", seg[:m.start()]).strip(" 　（）()，,、·")
        values.append({"v": v, "label": label})

    if not values:
        return {"values": [], "conflict": False, "line": None}

    # 同一数值重复出现（如「618 分（位次 12,087 名）」）只留一条
    uniq = []
    for item in values:
        if item["v"] not in [x["v"] for x in uniq]:
            uniq.append(item)

    return {
        "values": uniq,
        "conflict": bool(_CONFLICT.search(raw)),
        "line": min(x["v"] for x in uniq),
    }


def build(schools, facts_of):
    """返回 (可反查的条目, 缺数据的学校名单)。

    facts_of: {school_id: facts.extract(...)}，由调用方读好传入。
    只收高中——初中与小学没有投档线这回事。
    """
    rows, missing = [], []
    for s in schools:
        if s.level != "高中":
            continue
        parsed = parse((facts_of.get(s.id) or {}).get("score"))
        if parsed["line"] is None:
            missing.append(s.name)
            continue
        vals = parsed["values"]
        rows.append({
            "name": s.name,
            "district": s.district,
            "tier": s.tier,
            "url": s.url,
            "line": parsed["line"],
            "high": max(v["v"] for v in vals),
            # 展示串：「652 / 645」；带口径时注明，避免把两个口径读成一个分数
            "values": [{"v": v["v"], "label": v["label"]} for v in vals],
            "conflict": parsed["conflict"],
        })
    rows.sort(key=lambda r: (-r["line"], r["name"]))
    return rows, missing
