# -*- coding: utf-8 -*-
"""盘点全库学段与区域分布（只读，不修改任何数据）。"""
import json
from collections import Counter, defaultdict

data = json.load(open("index.json", encoding="utf-8"))
items = data["schools"]

level_cnt = Counter(x["level"] for x in items)
table = defaultdict(Counter)
for x in items:
    table[x["district"]][x["level"]] += 1

print(f"总计 {len(items)} 所")
print("学段分布：", dict(level_cnt))
print()
print("按区（总数｜小学｜初中｜高中）：")
for dist, c in sorted(table.items(), key=lambda kv: -sum(kv[1].values())):
    total = sum(c.values())
    print(f"  {dist:<6} {total:>3}  ({c.get('小学',0):>2} | {c.get('初中',0):>2} | {c.get('高中',0):>2})")

print()
print("各区小学数量排序：")
for dist, n in sorted(((d, c.get("小学", 0)) for d, c in table.items()), key=lambda kv: -kv[1]):
    print(f"  {dist:<6} {n:>2}")
