# -*- coding: utf-8 -*-
"""玄武区 24 所：批量写索引 + 补官网记录（全项目最后一批）。"""
import importlib, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "src", "build_index.py")
WEB = os.path.join(ROOT, "data", "school_websites.json")
TODAY = "2026-10-26"

P1 = {"北京东路小学紫金山分校", "北京东路小学红山分校", "仙鹤门分校", "铁北新城分校",
      "长江路小学启迪分校", "南京理工大学实验小学", "南京农业大学实验小学"}
P3 = {"樱花小学", "孝陵卫初级中学小学部"}
J1 = {"科利华", "红山初级中学", "弘光中学"}


def tier_of(name, lv):
    if lv == "小学":
        for k in P3:
            if k in name:
                return "玄武第三梯队"
        for k in P1:
            if k in name:
                return "玄武第一梯队"
        return "玄武第二梯队"
    for k in J1:
        if k in name:
            return "玄武第一梯队"
    return "玄武第二梯队"


def short_of(name):
    s = re.sub(r"^南京市", "", name)
    s = re.sub(r"^南京师范大学附属小学", "南师附小", s)
    return s.replace("（梅园校区）", "梅园校区")


def line_of(s):
    tag = s["tagline"].replace("**", "")
    if len(tag) > 100:
        tag = tag[:100].rstrip("，；、") + "…"
    return (f'    ("{s["name"]}", "{short_of(s["name"])}", "玄武区", "{s["level"]}", "公办", '
            f'"{tier_of(s["name"], s["level"])}",\n     "{tag}"),')


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    data = importlib.import_module("gen_xuanwu_data").SCHOOLS
    src = open(IDX, encoding="utf-8").read()
    start = src.index("SCHOOLS = [")
    end = src.index("\n]\n", start)
    body = src[start:end]
    added = [line_of(s) for s in data if f'("{s["name"]}"' not in body]
    if added:
        tail = body.rstrip()
        while tail.endswith("]"):
            tail = tail[:-1].rstrip()
        new = tail + "\n\n    # --- 玄武区（2026-10-26 第7批，全项目最后一批/16 张清单全部清零）---\n" + \
              "\n".join(added) + "\n]\n"
        open(IDX, "w", encoding="utf-8").write(src[:start] + new + src[end + 3:])
    print(f"[索引] 新增 {len(added)} 条")

    doc = json.load(open(WEB, encoding="utf-8"))
    table = doc["schools"]
    n = 0
    for s in data:
        key = f"{s['level']}-玄武区-{s['name']}"
        if key in table:
            continue
        table[key] = {"site": None, "site_archived": None, "null_reason": "未检索到",
                      "repair": None, "wechat": None, "wechat_status": "unknown",
                      "level": "C", "site_state": "none",
                      "basis": "未检索到独立官网；施教区未公开发布（玄武区未发布一览表），"
                               "校名/地址/电话见《玄武区义务教育学校名录》"}
        n += 1
    doc["updated"] = TODAY
    json.dump(doc, open(WEB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[官网] 新增 {n} 条，总计 {len(table)} 条")


if __name__ == "__main__":
    main()
