# -*- coding: utf-8 -*-
"""生成江宁区小学段应收清单。

来源：《2026年江宁区义务教育招生咨询电话》（附件 6，江宁区教育局发布）
      http://hyxx.jnjy.net.cn/html/202605/NewShow-f19b93e68b.html
口径：江宁区**未发布统一施教区一览表**，各类别学校由教育局统一下发咨询电话名录，
      施教区由各校单独发布入学公告。故本清单以「名录」为应收基准。

输出：data/expected_jiangning_primary.csv
"""
import csv
import json
import os
import re

from parse_jiangning_list import load_lines, parse

OUT = "data/expected_jiangning_primary.csv"
INDEX = "index.json"
TODAY = "2026-10-25"
SRC = "《2026年江宁区义务教育招生咨询电话》附件6（江宁区教育局，2026-05-09）"

# 库内已有江宁小学（正式全称）-> 附件简称，用于标记已建档
ALREADY = {
    "南京市百家湖小学": "百家湖小学",
    "南京市东山小学": "东山小学",
    "南京市江宁实验小学": "江宁实验小学",
}


def main():
    cats = parse(load_lines())
    rows = []
    have_short = set(ALREADY.values())

    for cat_name, items in cats:
        if "公办小学" in cat_name:
            kind = "公办小学"
        elif "九年一贯制" in cat_name:
            kind = "公办九年一贯制（小学部）"
        else:
            continue
        for name, addr, tel in items:
            status = "已建档" if name in have_short else "待补"
            rows.append([kind, name, addr, tel, status])

    # 已建档的补齐正式全称备注
    rev = {v: k for k, v in ALREADY.items()}
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["序号", "类别", "名录名称", "校区/地址", "咨询电话", "来源", "采集日期", "库内状态", "档案全称"])
        for i, (kind, name, addr, tel, status) in enumerate(rows, 1):
            w.writerow([i, kind, name, addr, tel, SRC, TODAY, status, rev.get(name, "")])

    from collections import Counter
    c = Counter(r[4] for r in rows)
    print(f"写入 {OUT}")
    print(f"应收小学段办学单位 {len(rows)} 个：", dict(c))
    print("按类别：", dict(Counter(r[0] for r in rows)))


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
