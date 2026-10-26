# -*- coding: utf-8 -*-
"""回填 data/expected_jiangning_primary.csv 的「库内状态」。

判定方式：用 index.json 中江宁区小学的正式全称，与清单里的「名录简称」做包含匹配。
（附件用的是简称，如「将军山小学」，档案用全称「南京市将军山小学」）
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "data", "expected_jiangning_primary.csv")

# 名录简称与档案全称不一致的少数情况（substring 匹配不到）
ALIAS = {
    "禄口小学": "南京市江宁区禄口中心小学",
    "晓庄实验小学": "南京晓庄学院实验小学",
}


def main():
    idx = json.load(open(os.path.join(ROOT, "index.json"), encoding="utf-8"))
    names = [x["name"] for x in idx["schools"]
             if x["district"] == "江宁区" and x["level"] == "小学"]

    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    fields = list(rows[0].keys())

    hit = 0
    for r in rows:
        short = r["名录名称"]
        matched = [n for n in names if short in n]
        if not matched and short in ALIAS:
            matched = [ALIAS[short]] if ALIAS[short] in names else []
        if matched:
            r["库内状态"] = "已建档"
            r["档案全称"] = matched[0]
            hit += 1
        elif r["库内状态"] != "待补":
            r["库内状态"] = "待补"

    with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    todo = [r for r in rows if r["库内状态"] == "待补"]
    print(f"应收 {len(rows)} 个办学单位 | 已建档 {hit} | 待补 {len(todo)}")
    if todo:
        print("待补前 12 条：")
        for r in todo[:12]:
            print(f"  {r['序号']:>2}. [{r['类别']}] {r['名录名称']}")


if __name__ == "__main__":
    main()
