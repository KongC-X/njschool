# -*- coding: utf-8 -*-
"""招生时间轴：把 545 份档案里分散的「报名时间节点」聚合成一张日历。

为什么要单独做一页（而不是继续留在各校档案第 5.3 节）：
家长在 4–6 月的真实问题是「**我现在该做什么、什么时候截止**」，
而不是「这所学校是什么样」。同一批节点被重复写进两百多份档案，
打开任何一份都只看得到一条时间线，却看不到「哪些是全市场统一、哪些是本区特殊」。

数据来源与口径：
  · 只取档案里标题含「时间 / 节点 / 日程 / 流程」的小节的表格，不猜正文；
  · 同一天出现多次的不同措辞做频次聚类，取最常见的那条作为该节点文案；
  · 出现次数即「有多少所学校写了同一条」——这是覆盖率，也是可信度，
    同时天然区分了「市/区统一节点」与「个别学校的补充节点」。
"""
import re
from collections import Counter, defaultdict

# 小节标题：小学多为「3.3 报名时间节点（区级统一）」「5.3 报名时间节点（市级统一）」，
# 初中多为「4.3 时间节点（2026 年，市级统一）」「4.4 招生时间节点」。
_HEAD = re.compile(r"^#{3,4}\s*.*(?:时间|节点|日程|流程).*$", re.M)
_NEXT = re.compile(r"^#{2,4}\s", re.M)
_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", re.M)
_SKIP_FIRST = {"时间", "日期", "阶段", "时间节点", "事项", "内容"}

_RE_DATE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_RE_RANGE = re.compile(
    r"(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*[—–\-~～至]\s*(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*日")
_RE_XUN = re.compile(r"(\d{1,2})\s*月\s*([上中下])\s*旬")
_RE_DEADLINE = re.compile(
    r"截止\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(\d{1,2})\s*[:：]\s*(\d{2})")
# 事件文本里自带的「（截止 5 月 19 日 17:00）」要剥掉：
# 截止时刻单独做成标签展示，留着会在同一行出现两次。
_RE_DEADLINE_PAREN = re.compile(r"[（(]\s*截止[^）)]*[）)]")

# 归一化时抹掉的写法差异（实测同一节点最多有 6 种写法）
_RE_SPACE = re.compile(r"\s+")
_RE_MD = re.compile(r"[*`]")


def _clean(s):
    s = _RE_MD.sub("", s or "")
    s = s.replace("　", " ")
    return _RE_SPACE.sub(" ", s).strip().strip("|").strip()


def parse_date(raw):
    """把「5 月 17 日—19 日」「8 月 10 日前」「5 月 8 日起」解析成可排序的结构。

    返回 None 表示认不出——认不出就不进时间轴，不做猜测。
    """
    s = _RE_SPACE.sub("", raw or "")
    if not s:
        return None

    m = _RE_RANGE.search(s)
    if m:
        m1, d1, m2, d2 = m.group(1), m.group(2), m.group(3), m.group(4)
        return {"m": int(m1), "d": int(d1),
                "em": int(m2) if m2 else int(m1), "ed": int(d2), "kind": "range"}

    if "旬" in s:
        m = _RE_XUN.search(s)
        if m:
            first = {"上": 1, "中": 11, "下": 21}[m.group(2)]
            return {"m": int(m.group(1)), "d": first, "em": None, "ed": None,
                    "kind": "xun", "xun": m.group(2)}

    m = _RE_DATE.search(s)
    if m:
        mm, dd = int(m.group(1)), int(m.group(2))
        kind = "from" if "起" in s else ("before" if "前" in s else "single")
        return {"m": mm, "d": dd, "em": mm, "ed": dd, "kind": kind}
    return None


def parse_deadline(event):
    """提取「（截止 5 月 19 日 17:00）」里的具体截止时刻。"""
    m = _RE_DEADLINE.search(event or "")
    if not m:
        return None
    return {"m": int(m.group(1)), "d": int(m.group(2)),
            "hh": int(m.group(3)), "mm": m.group(4)}


def rows_of(text):
    """取档案里所有「时间节点」小节的表格行。"""
    out = []
    for m in _HEAD.finditer(text):
        rest = text[m.end():]
        n = _NEXT.search(rest)
        seg = rest[:n.start()] if n else rest
        rows = []
        for a, b in _ROW.findall(seg):
            a, b = _clean(a), _clean(b)
            if not a or a in _SKIP_FIRST:
                continue
            if set(a) <= set("-: "):
                continue
            rows.append((a, b))
        if len(rows) >= 3:          # 少于 3 行的多半是别的表被误取
            out.append(rows)
    return out


def _key(d):
    """同一节点的归并键：起止日相同即视为同一天。"""
    return (d["m"], d["d"], d["em"], d["ed"])


def _label(d):
    """日期展示文案。原文写法差异大，这里统一成一种，避免同一天出现两种格式。"""
    if d["kind"] == "range" and (d["em"], d["ed"]) != (d["m"], d["d"]):
        if d["em"] == d["m"]:
            return f"{d['m']} 月 {d['d']}—{d['ed']} 日"
        return f"{d['m']} 月 {d['d']} 日—{d['em']} 月 {d['ed']} 日"
    if d["kind"] == "xun":
        return f"{d['m']} 月{d.get('xun', '')}旬"
    if d["kind"] == "from":
        return f"{d['m']} 月 {d['d']} 日起"
    if d["kind"] == "before":
        return f"{d['m']} 月 {d['d']} 日前"
    return f"{d['m']} 月 {d['d']} 日"


def build(schools, sources):
    """返回 {level: {nodes, extra, contributors}}。

    sources: {school_id: 档案正文}，由调用方读好传入（避免本模块碰文件系统）。
    """
    by_level = defaultdict(list)
    contributors = Counter()

    for s in schools:
        text = sources.get(s.id, "")
        if not text:
            continue
        seen = set()
        for rows in rows_of(text):
            for raw_date, event in rows:
                d = parse_date(raw_date)
                if not d or not event:
                    continue
                dl = parse_deadline(event)
                # 截止时刻单独成标签，正文里就不再重复一遍
                event = _RE_DEADLINE_PAREN.sub("", event).strip()
                if not event:
                    continue
                k = _key(d)
                if k in seen:          # 同一份档案里重复出现的同一天只算一次
                    continue
                seen.add(k)
                by_level[s.level].append((d, event, dl))
        if seen:
            contributors[s.level] += 1

    out = {}
    for lv, items in by_level.items():
        total = contributors[lv]
        # 同一天的不同措辞按频次聚类，取最常见的一条
        groups = defaultdict(Counter)
        meta = {}
        for d, event, dl in items:
            k = _key(d)
            groups[k][event] += 1
            meta.setdefault(k, (d, dl))
        nodes = []
        for k, counter in groups.items():
            # count 是「有多少份档案在这一天写了节点」，不是「某种措辞被写了多少次」——
            # 页面上的文案是「N 份档案提及」，数错口径就是在虚报覆盖率。
            text, _top = counter.most_common(1)[0]
            n = sum(counter.values())
            d, dl = meta[k]
            nodes.append({
                "key": k, "m": d["m"], "d": d["d"],
                "label": _label(d),
                "event": text,
                "count": n,
                "share": round(n * 100 / total) if total else 0,
                "deadline": dl,
                "variants": len(counter),
            })
        nodes.sort(key=lambda x: (x["m"], x["d"]))
        # 主时间轴 = 至少 8%（且不少于 5 份）的档案都写了；其余归入「个别学校的补充节点」。
        # 阈值不能只看绝对次数：小学有 189 份档案、初中只有 74 份。
        # 5% 时初中会把「某校初一新生分班调研」这种单校安排抬进主表——
        # 那种节点混在「全市报名节点」里，家长会以为所有学校都要去。
        floor = max(5, round(total * 0.08))
        main = [x for x in nodes if x["count"] >= floor]
        extra = [x for x in nodes if x["count"] < floor]
        out[lv] = {"nodes": main, "extra": extra, "contributors": total,
                   "all": len(nodes)}
    return out
