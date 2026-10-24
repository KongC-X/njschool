# -*- coding: utf-8 -*-
"""收录对账：把「官方应收名单」与库内档案做差集。

用法：
    python3 src/reconcile.py                     # 检查 data/expected_*.csv 全部
    python3 src/reconcile.py data/expected_qixia.csv

输入 CSV 需含列：区、学段、学校、施教区原文、来源、采集日期、库内状态
比对规则：按「学段/区/校名.md」判断是否存在；校区名与主校名不一致时以正式校名为准。

输出：
    控制台摘要（应收 / 实收 / 缺 / 多收）
    data/coverage_report.csv（逐校状态，便于分派任务）
"""
import csv
import glob
import os
import sys

ROOT = "/Users/kongc/WorkBuddy/南京学校"
OUT = os.path.join(ROOT, "data", "coverage_report.csv")


def school_path(region, level, name):
    return os.path.join(ROOT, level, region, f"{name}.md")


def check_file(path):
    """批量核对一个应收清单，返回 (rows, 统计)。"""
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        region, level, name = r["区"], r["学段"], r["学校"]
        fp = school_path(region, level, name)
        exists = os.path.isfile(fp)
        # 「并入」表示该条目是同法人校区，已写在母体档案内，不需要独立档案
        merged = (r.get("库内状态") or "").startswith("并入")
        state = "已有" if exists else ("并入" if merged else "缺")
        rows.append({
            "区": region, "学段": level, "学校": name,
            "状态": state,
            "档案路径": os.path.relpath(fp, ROOT) if exists else
                        (r.get("库内状态") if merged else ""),
        })
    return rows


def main():
    targets = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, "data", "expected_*.csv")))
    if not targets:
        print("没有找到 data/expected_*.csv")
        return 1

    all_rows = []
    for t in targets:
        rows = check_file(t)
        all_rows.extend(rows)
        total = len(rows)
        have = sum(1 for r in rows if r["状态"] in ("已有", "并入"))
        miss = total - have
        print(f"\n{t.replace(ROOT + '/', '')}")
        print(f"  应收 {total} 所 | 已有 {have} | 缺 {miss}")
        for r in rows:
            if r["状态"] == "缺":
                print(f"    ✗ {r['学段']} {r['学校']}")

    # 写出逐校状态，便于分派任务
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["区", "学段", "学校", "状态", "档案路径"])
        w.writeheader()
        w.writerows(all_rows)

    total = len(all_rows)
    have = sum(1 for r in all_rows if r["状态"] in ("已有", "并入"))
    print(f"\n合计：应收 {total} / 已有 {have} / 缺 {total - have}")
    print(f"逐校状态已写入 {OUT}")
    return 0 if have == total else 1


if __name__ == "__main__":
    sys.exit(main())
