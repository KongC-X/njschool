# -*- coding: utf-8 -*-
"""六合初中 19 所：批量写索引 + 补官网记录。"""
import importlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "src", "build_index.py")
WEB = os.path.join(ROOT, "data", "school_websites.json")
TODAY = "2026-10-25"

T1 = {"科利华中学棠城分校", "南京师范大学附属六合实验初级中学"}
MBA = {"励志学校（初中部）"}
T2 = {"金牛湖初级中学", "横梁初级中学", "马集初级中学",
      "新篁学校（初中部）", "冶山初级中学"}


def tier_of(name):
    if name in MBA:
        return "六合民办第一梯队"
    if name in T1:
        return "六合第一梯队"
    if name in T2:
        return "六合第二梯队"
    return "六合第三梯队"


def plain(t):
    return t.replace("**", "")


def line_of(s):
    name = s["name"]
    short = re.sub(r"^南京市", "", name)
    short = short.replace("（初中部）", "")
    tag = plain(s["tagline"])
    if len(tag) > 100:
        tag = tag[:100].rstrip("，；、") + "…"
    nat = "民办" if "民办" in s["nature"] else "公办"
    return (f'    ("{name}", "{short}", "六合区", "初中", "{nat}", "{tier_of(name)}",\n'
            f'     "{tag}"),')


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    data = importlib.import_module("gen_luhe_junior_data").SCHOOLS

    src = open(IDX, encoding="utf-8").read()
    start = src.index("SCHOOLS = [")
    end = src.index("\n]\n", start)
    body = src[start:end]
    added = [line_of(s) for s in data if f'("{s["name"]}"' not in body]
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
    for s in data:
        key = f"初中-六合区-{s['name']}"
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
