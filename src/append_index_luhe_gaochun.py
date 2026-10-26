# -*- coding: utf-8 -*-
"""六合 8 + 高淳 10：批量写索引 + 补官网记录。"""
import importlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "src", "build_index.py")
WEB = os.path.join(ROOT, "data", "school_websites.json")
TODAY = "2026-10-25"

T1 = {"金陵中学龙湖", "双语小学", "广益小学", "北京东路小学棠城", "方州小学",
      "南京师范大学附属六合实验", "宝塔小学", "淳溪中心小学", "新城小学",
      "南师附中高淳", "滨湖小学"}
T2 = {"雄州分校", "蒋湾小学", "汶溪小学", "金陵汇淳", "古柏中心小学"}
T3 = {"薛城小学", "长乐小学"}


def tier_of(name, district):
    for k in T3:
        if k in name:
            return f"{district}第三梯队"
    for k in T2:
        if k in name:
            return f"{district}第二梯队"
    for k in T1:
        if k in name:
            return f"{district}第一梯队"
    return f"{district}第二梯队"


def line_of(s):
    name, dist = s["name"], s["district"]
    short = re.sub(r"^南京市", "", name).replace("（小学部）", "")
    tag = s["tagline"].replace('"', "”")
    if len(tag) > 100:
        tag = tag[:100].rstrip("，；、") + "…"
    return (f'    ("{name}", "{short}", "{dist}", "小学", "公办", "{tier_of(name, dist)}",\n'
            f'     "{tag}"),')


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    data = importlib.import_module("gen_luhe_gaochun_data").SCHOOLS

    src = open(IDX, encoding="utf-8").read()
    start = src.index("SCHOOLS = [")
    end = src.index("\n]\n", start)
    body = src[start:end]
    added = [line_of(s) for s in data if f'("{s["name"]}"' not in body]
    if added:
        new = body.rstrip() + "\n" + "\n".join(added) + "\n]\n"
        open(IDX, "w", encoding="utf-8").write(src[:start] + new + src[end + 3:])
    print(f"[索引] 新增 {len(added)} 条")

    doc = json.load(open(WEB, encoding="utf-8"))
    table = doc["schools"]
    n = 0
    for s in data:
        key = f"小学-{s['district']}-{s['name']}"
        if key in table:
            continue
        table[key] = {
            "site": None, "site_archived": None, "null_reason": "未检索到",
            "repair": None, "wechat": None, "wechat_status": "unknown",
            "level": "C", "site_state": "none",
            "basis": "未检索到独立官网；施教区见区教育局 2026 年招生方案原文",
        }
        n += 1
    doc["updated"] = TODAY
    json.dump(doc, open(WEB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[官网] 新增 {n} 条，总计 {len(table)} 条")


if __name__ == "__main__":
    main()
