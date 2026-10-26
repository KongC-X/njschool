# -*- coding: utf-8 -*-
"""雨花台区初中 12 所：批量写索引 + 补官网记录。"""
import importlib, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "src", "build_index.py")
WEB = os.path.join(ROOT, "data", "school_websites.json")
TODAY = "2026-10-26"

T1 = {"软件谷中学", "雨花台学校", "中华中学附属雨花初级中学", "数字城学校",
      "金陵中学西善分校", "金陵华兴实验初级中学", "金地自在城初级中学"}
T3 = {"潘窑规划学校"}


def tier_of(name):
    for k in T3:
        if k in name:
            return "雨花台第三梯队"
    for k in T1:
        if k in name:
            return "雨花台第一梯队"
    return "雨花台第二梯队"


def short_of(name):
    s = re.sub(r"^南京市", "", name)
    s = re.sub(r"^南京师范大学附属中学", "南师附中", s)
    return s.replace("（初中部）", "")


def line_of(s):
    tag = s["tagline"].replace("**", "")
    if len(tag) > 100:
        tag = tag[:100].rstrip("，；、") + "…"
    return (f'    ("{s["name"]}", "{short_of(s["name"])}", "雨花台区", "初中", "公办", '
            f'"{tier_of(s["name"])}",\n     "{tag}"),')


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    data = importlib.import_module("gen_yuhuatai_junior_data").SCHOOLS
    src = open(IDX, encoding="utf-8").read()
    start = src.index("SCHOOLS = [")
    end = src.index("\n]\n", start)
    body = src[start:end]
    added = [line_of(s) for s in data if f'("{s["name"]}"' not in body]
    if added:
        tail = body.rstrip()
        while tail.endswith("]"):
            tail = tail[:-1].rstrip()
        new = tail + "\n\n    # --- 雨花台区 初中（2026-10-26 第6批，雨花台义务教育段收官）---\n" + \
              "\n".join(added) + "\n]\n"
        open(IDX, "w", encoding="utf-8").write(src[:start] + new + src[end + 3:])
    print(f"[索引] 新增 {len(added)} 条")

    doc = json.load(open(WEB, encoding="utf-8"))
    table = doc["schools"]
    n = 0
    for s in data:
        key = f"初中-雨花台区-{s['name']}"
        if key in table:
            continue
        table[key] = {"site": None, "site_archived": None, "null_reason": "未检索到",
                      "repair": None, "wechat": None, "wechat_status": "unknown",
                      "level": "C", "site_state": "none",
                      "basis": "未检索到独立官网；施教区见雨花台区 2026 年初中招生办法附表"}
        n += 1
    doc["updated"] = TODAY
    json.dump(doc, open(WEB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[官网] 新增 {n} 条，总计 {len(table)} 条")


if __name__ == "__main__":
    main()
