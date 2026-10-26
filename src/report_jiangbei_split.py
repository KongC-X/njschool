# -*- coding: utf-8 -*-
"""盘点江北新区小学的公办/民办构成，并与应收清单核对（只读）。"""
import csv
import json
from collections import Counter

data = json.load(open("index.json", encoding="utf-8"))
items = [x for x in data["schools"] if x["district"] == "江北新区" and x["level"] == "小学"]

print(f"江北新区小学 {len(items)} 所")
print("按办学性质：", dict(Counter(x["type"] for x in items)))
print()
for t in ("公办", "民办"):
    group = sorted(x["name"] for x in items if x["type"] == t)
    print(f"【{t}】{len(group)} 所")
    for n in group:
        print("  ", n)
    print()

rows = list(csv.DictReader(open("data/expected_jiangbei_primary.csv", encoding="utf-8-sig")))
print(f"应收清单 {len(rows)} 条，状态：", dict(Counter(r["库内状态"] for r in rows)))
