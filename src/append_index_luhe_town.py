# -*- coding: utf-8 -*-
"""六合街镇小学 20 所：批量写索引 + 补官网记录。"""
import importlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "src", "build_index.py")
WEB = os.path.join(ROOT, "data", "school_websites.json")
TODAY = "2026-10-25"

# 梯队：按校史、资质、集团地位三项公开依据划分（非官方排名）
T1 = {"程桥中心小学", "马鞍中心小学", "龙袍中心小学"}
T2 = {"冶山中心小学", "东沟小学", "竹程小学", "横梁中心小学",
      "金牛湖中心小学", "灵岩小学", "竹镇中心小学"}
T3 = {"瓜埠小学", "乌石小学", "龙池中心小学", "六合经济开发区小学",
      "长山小学", "实验小学八百桥分校", "新篁学校", "马鞍学校", "城西学校"}
MBA = {"励志学校"}


def tier_of(name):
    for k in MBA:
        if k in name:
            return "六合民办第一梯队"
    for k in T1:
        if k in name:
            return "六合第一梯队"
    for k in T2:
        if k in name:
            return "六合第二梯队"
    for k in T3:
        if k in name:
            return "六合第三梯队"
    return "六合第三梯队"


def nature_of(s):
    # schema 只允许「公办 / 民办」两种；九年一贯制的信息写在 tagline 里
    cat, nat_raw = s["category"], s["nature"]
    if "民办" in nat_raw or "民办" in cat:
        return "民办"
    return "公办"


def line_of(s):
    name = s["name"]
    short = re.sub(r"^南京市", "", name)
    short = short.replace("（小学部）", "").replace("（龙池小学）", "")
    tag = s["tagline"].replace('"', "”")
    if len(tag) > 100:
        tag = tag[:100].rstrip("，；、") + "…"
    nat = nature_of(s)
    return (f'    ("{name}", "{short}", "六合区", "小学", "{nat}", "{tier_of(name)}",\n'
            f'     "{tag}"),')


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    data = importlib.import_module("gen_luhe_town_data").SCHOOLS

    src = open(IDX, encoding="utf-8").read()
    start = src.index("SCHOOLS = [")
    end = src.index("\n]\n", start)
    body = src[start:end]
    added = [line_of(s) for s in data if f'("{s["name"]}"' not in body]
    if added:
        # 去掉 body 末尾可能残留的孤立 ']'，再追加，避免出现两个 ]
        tail = body.rstrip()
        while tail.endswith("]"):
            tail = tail[:-1].rstrip()
        new = tail + "\n" + "\n".join(added) + "\n]\n"
        open(IDX, "w", encoding="utf-8").write(src[:start] + new + src[end + 3:])
    print(f"[索引] 新增 {len(added)} 条")

    doc = json.load(open(WEB, encoding="utf-8"))
    table = doc["schools"]
    n = 0
    for s in data:
        key = f"小学-六合区-{s['name']}"
        if key in table:
            continue
        table[key] = {
            "site": None, "site_archived": None, "null_reason": "未检索到",
            "repair": None, "wechat": None, "wechat_status": "unknown",
            "level": "C", "site_state": "none",
            "basis": "未检索到独立官网；校名与咨询电话见《2026年六合区义务教育招生工作咨询电话》",
        }
        n += 1
    doc["updated"] = TODAY
    json.dump(doc, open(WEB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[官网] 新增 {n} 条，总计 {len(table)} 条")


if __name__ == "__main__":
    main()
