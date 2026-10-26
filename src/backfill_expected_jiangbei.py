# -*- coding: utf-8 -*-
"""回填 data/expected_jiangbei_primary.csv 的「库内状态」列。

改为「按档案文件是否存在」自动判定，避免每批新增都要手写映射。
别名表只处理「CSV 校名」与「档案文件名」不一致的情况。
"""
import csv
import os

PATH = "data/expected_jiangbei_primary.csv"
SCHOOL_DIR = "小学/江北新区"

# CSV 校名 -> 档案文件名（不含 .md）；仅用于两者不一致的少数情况
ALIAS = {
    "南京江北新区浦口实验小学": "南京市浦口实验小学",
}
# 2026 年停招，按特殊状态处理，不算「待补」
SPECIAL = {
    "南京江北新区铁路小学": "2026 年秋停招（由浦口实验小学浦园路分校代招）",
}


def main():
    with open(PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0].keys()) if rows else []

    have = 0
    for r in rows:
        name = r["学校名称"]
        if name in SPECIAL:
            r["库内状态"] = SPECIAL[name]
            continue
        fname = ALIAS.get(name, name)
        if os.path.isfile(os.path.join(SCHOOL_DIR, fname + ".md")):
            r["库内状态"] = "已建档"
            have += 1
        else:
            r["库内状态"] = "待补"

    with open(PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    todo = [r for r in rows if r["库内状态"] == "待补"]
    print(f"应收 {len(rows)} 所 | 已建档 {have} 所 | 待补 {len(todo)} 所 | 特殊 {len(rows)-have-len(todo)} 所")
    from collections import Counter
    c = Counter(r["片区"] for r in todo)
    print("待补按片区：", dict(c))
    print("待补前 10 条：")
    for r in todo[:10]:
        print(f"  {r['序号']:>2}. [{r['片区']}] {r['学校名称']}（{r['招生班数']} 班）")


if __name__ == "__main__":
    main()
