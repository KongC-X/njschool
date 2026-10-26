# -*- coding: utf-8 -*-
"""高淳小学 7 所 + 初中 11 所：批量写索引 + 补官网记录。"""
import importlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "src", "build_index.py")
WEB = os.path.join(ROOT, "data", "school_websites.json")
TODAY = "2026-10-25"

# 小学梯队：按 Street 中心校的公开资质划分（非官方排名）
P1 = {"漆桥中心小学", "阳江中心小学"}
P2 = {"东坝中心小学", "固城中心小学", "桠溪中心小学"}
P3 = {"砖墙中心小学"}
PMBA = {"武家嘴实验学校（小学部）"}

# 初中梯队
J1 = {"南京市高淳区第一中学", "南师附中高淳学校（初中部）", "金陵汇淳学校（初中部）"}
JMBA = {"南京武家嘴实验学校（初中部）"}
J2 = {"南京市高淳区永丰中学", "南京市高淳区漆桥中学", "南京市高淳区固城中学"}


def tier_of(name, level):
    if level == "小学":
        if name in PMBA:
            return "高淳民办第一梯队"
        if name in P1:
            return "高淳第一梯队"
        if name in P2:
            return "高淳第二梯队"
        return "高淳第三梯队"
    if name in JMBA:
        return "高淳民办第一梯队"
    if name in J1:
        return "高淳第一梯队"
    if name in J2:
        return "高淳第二梯队"
    return "高淳第三梯队"


def line_of(name, level, tagline, nature):
    short = re.sub(r"^南京(市)?", "", name)
    short = short.replace("（小学部）", "").replace("（初中部）", "")
    tag = tagline.replace("**", "")
    if len(tag) > 100:
        tag = tag[:100].rstrip("，；、") + "…"
    return (f'    ("{name}", "{short}", "高淳区", "{level}", "{nature}", "{tier_of(name, level)}",\n'
            f'     "{tag}"),')


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    prim = importlib.import_module("gen_gaochun_town_data").SCHOOLS
    juni = importlib.import_module("gen_gaochun_junior_data").SCHOOLS

    items = []
    for s in prim:
        items.append((s["name"], "小学", s["tagline"], "民办" if "民办" in s["nature"] else "公办"))
    for s in juni:
        items.append((s["name"], "初中", s["tagline"], "民办" if "民办" in s["nature"] else "公办"))

    src = open(IDX, encoding="utf-8").read()
    start = src.index("SCHOOLS = [")
    end = src.index("\n]\n", start)
    body = src[start:end]
    added = [line_of(*it) for it in items if f'("{it[0]}"' not in body]
    if added:
        tail = body.rstrip()
        while tail.endswith("]"):
            tail = tail[:-1].rstrip()
        new = tail + "\n" + "\n".join(added) + "\n]\n"
        open(IDX, "w", encoding="utf-8").write(src[:start] + new + src[end + 3:])
    print(f"[索引] 新增 {len(added)} 条")

    doc = json.load(open(WEB, encoding="utf-8"))
    table = doc["schools"]
    n = 0
    for name, level, _tag, _nat in items:
        key = f"{level}-高淳区-{name}"
        if key in table:
            continue
        table[key] = {
            "site": None, "site_archived": None, "null_reason": "未检索到",
            "repair": None, "wechat": None, "wechat_status": "unknown",
            "level": "C", "site_state": "none",
            "basis": "未检索到独立官网；校名与咨询电话见高淳区 2026 年招生方案附件 2",
        }
        n += 1
    doc["updated"] = TODAY
    json.dump(doc, open(WEB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[官网] 新增 {n} 条，总计 {len(table)} 条")


if __name__ == "__main__":
    main()
