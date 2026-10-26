# -*- coding: utf-8 -*-
"""溧水区 18 所小学：批量写索引 + 补官网记录 + 生成应收清单。"""
import importlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "src", "build_index.py")
WEB = os.path.join(ROOT, "data", "school_websites.json")
CSV = os.path.join(ROOT, "data", "expected_lishui_primary.csv")
TODAY = "2026-10-25"
SRC = "《南京市溧水区 2026 年小学招生工作实施方案》（njls.gov.cn，2026-05-08）"

TIER1 = {"力学小学溧水学校", "实验小学崇文路", "实验小学通济街", "实验小学中山东路",
         "文昌小学", "状元坊小学", "游府西街小学溧水分校"}
TIER2 = {"第三小学", "经济开发区小学", "南外仙林", "柘塘", "东庐"}


def tier_of(name):
    for k in TIER1:
        if k in name:
            return "溧水区第一梯队"
    for k in TIER2:
        if k in name:
            return "溧水区第二梯队"
    return "溧水区第三梯队"


def line_of(s):
    name = s["name"]
    short = re.sub(r"^南京市", "", name)
    tag = s["tagline"].replace('"', "”")
    if len(tag) > 100:
        tag = tag[:100].rstrip("，；、") + "…"
    return (f'    ("{name}", "{short}", "溧水区", "小学", "公办", "{tier_of(name)}",\n'
            f'     "{tag}"),')


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    data = importlib.import_module("gen_lishui_data").SCHOOLS

    # 1) 索引
    src = open(IDX, encoding="utf-8").read()
    start = src.index("SCHOOLS = [")
    end = src.index("\n]\n", start)
    body = src[start:end]
    added = [line_of(s) for s in data if f'("{s["name"]}"' not in body]
    if added:
        new = body.rstrip() + "\n" + "\n".join(added) + "\n]\n"
        open(IDX, "w", encoding="utf-8").write(src[:start] + new + src[end + 3:])
    print(f"[索引] 新增 {len(added)} 条")

    # 2) 官网
    doc = json.load(open(WEB, encoding="utf-8"))
    table = doc["schools"]
    n = 0
    for s in data:
        key = f"小学-溧水区-{s['name']}"
        if key in table:
            continue
        table[key] = {
            "site": None, "site_archived": None, "null_reason": "未检索到",
            "repair": None, "wechat": None, "wechat_status": "unknown",
            "level": "C", "site_state": "none",
            "basis": "未检索到独立官网；施教区与咨询电话见区教育局 2026 年小学招生工作实施方案",
        }
        n += 1
    doc["updated"] = TODAY
    json.dump(doc, open(WEB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[官网] 新增 {n} 条，总计 {len(table)} 条")

    # 3) 清单
    import csv
    idx = json.load(open(os.path.join(ROOT, "index.json"), encoding="utf-8"))
    names = [x["name"] for x in idx["schools"]
             if x["district"] == "溧水区" and x["level"] == "小学"]
    rows, have = [], 0
    for i, s in enumerate(data, 1):
        full = s["name"]
        hit = full in names
        if hit:
            have += 1
        rows.append([i, "公办小学", s.get("short_name", full), s["addr"], s["tel"],
                     SRC, TODAY, "已建档" if hit else "待补", full if hit else ""])
    with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["序号", "类别", "校名", "所在街道/片区", "咨询电话", "来源",
                    "采集日期", "库内状态", "档案全称"])
        w.writerows(rows)
    print(f"[清单] 应收 {len(rows)} 所，已建档 {have}，待补 {len(rows)-have} → {CSV}")


if __name__ == "__main__":
    main()
