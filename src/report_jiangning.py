# -*- coding: utf-8 -*-
"""列出库内江宁区各学段学校（只读）。"""
import json

data = json.load(open("index.json", encoding="utf-8"))
items = [x for x in data["schools"] if x["district"] == "江宁区"]
for lv in ("小学", "初中", "高中"):
    group = sorted((x for x in items if x["level"] == lv), key=lambda x: x["name"])
    print(f"【{lv}】{len(group)} 所")
    for x in group:
        print(f"   {x['name']}（{x['type']}）")
    print()
