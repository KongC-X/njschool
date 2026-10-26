# -*- coding: utf-8 -*-
"""比对 index.json 与磁盘上的 md 文件，找出差集（只读）。"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
idx = json.load(open(os.path.join(ROOT, "index.json"), encoding="utf-8"))
files = {x["file"] for x in idx["schools"]}

disk = set()
for lv in ("小学", "初中", "高中"):
    base = os.path.join(ROOT, lv)
    for dirpath, _, names in os.walk(base):
        for n in names:
            if n.endswith(".md"):
                disk.add(os.path.relpath(os.path.join(dirpath, n), ROOT))

only_disk = sorted(disk - files)
only_idx = sorted(files - disk)
print(f"index {len(files)} 条 / 磁盘 {len(disk)} 个")
print("\n仅在磁盘（未登记）：")
for f in only_disk:
    print("  ", f)
print("\n仅在索引（文件缺失）：")
for f in only_idx:
    print("  ", f)
