# -*- coding: utf-8 -*-
"""导出结构化 CSV，供工作簿生成使用"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_high import (
    CONTROL_LINES, PLAN_2026, TOP_SCHOOLS_LINE, OTHER_SCHOOLS_LINE_2026,
    FOUR_STAR, HIGH_SCHOOLS,
)
from data_mid import (
    PRIVATE_MIDDLE, PUBLIC_PAIWEI, MIDDLE_SCHOOLS, MIDDLE_TIERS,
)
from data_pri import PRIMARY_TIERS, PRIMARY_SCHOOLS
from data_policy import INDICATOR_STUDENT, SOURCES, TRENDS

OUTDIR = "/Users/kongc/WorkBuddy/南京学校/data"
os.makedirs(OUTDIR, exist_ok=True)


def write(name, headers, rows):
    p = os.path.join(OUTDIR, name)
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)
    print("OK", p, len(rows), "行")


# 1 高中投档线走势（六大名校）
write("01_高中_投档线走势.csv",
      ["序号", "学校", "校区", "2026年", "2025年", "2024年", "2023年", "数据可信度"],
      [[i, s, c, y26, y25 or "", y24 or "", y23 or "", cr]
       for i, (s, c, y26, y25, y24, y23, cr) in enumerate(TOP_SCHOOLS_LINE, 1)])

# 2 高中投档线（其余学校）
write("02_高中_投档线_其他.csv",
      ["序号", "学校", "校区/类别", "2026年投档线", "数据可信度"],
      [[i, s, c, sc, cr] for i, (s, c, sc, cr) in enumerate(OTHER_SCHOOLS_LINE_2026, 13)])

# 3 高中招生计划
write("03_高中_招生计划2026.csv",
      ["序号", "学校/校区", "2026年计划（人）", "较去年"],
      [[i, n, p, d] for i, (n, p, d) in enumerate(PLAN_2026["各校计划"], 1)])

# 4 高中学校档案
write("04_高中_学校档案.csv",
      ["学校", "简称", "区", "办学性质", "建校", "校区", "层次资质", "办学特色",
       "师资力量", "招生计划", "中考录取线", "高考表现", "信息来源", "可信度"],
      [[s["name"], s.get("short", ""), s["district"], s["type"], s.get("founded", ""),
        s.get("campuses", ""), s.get("level", ""), s.get("feature", ""),
        s.get("faculty", ""), s.get("enroll", ""), s.get("line", ""),
        s.get("gaokao", ""), s.get("source", ""), s.get("cred", "")]
       for s in HIGH_SCHOOLS])

# 5 初中学校档案
write("05_初中_学校档案.csv",
      ["学校", "区", "办学性质", "梯队", "办学特色", "施教区/招生",
       "2026中考成绩", "2025中考成绩", "信息来源", "可信度"],
      [[s["name"], s["district"], s["type"], s.get("tier", ""), s.get("feature", ""),
        s.get("enroll", ""), s.get("perf2026", ""), s.get("perf2025", ""),
        s.get("source", ""), s.get("cred", "")]
       for s in MIDDLE_SCHOOLS])

# 6 初中梯队
rows = []
for lv, names in MIDDLE_TIERS.items():
    for n in names:
        rows.append([lv, n])
write("06_初中_梯队.csv", ["梯队", "学校"], rows)

# 7 民办初中摇号与学费
write("07_初中_民办摇号与学费.csv",
      ["学校", "区", "2026年摇号计划（人）", "2025年摇号计划（人）",
       "学费（元/生·学期）", "备注"],
      [[n, d, p26 or "", p25 or "", fee, note]
       for n, d, p26, p25, fee, note in PRIVATE_MIDDLE])

# 8 公办初中派位计划
write("08_初中_公办派位计划.csv",
      ["区", "学校", "2026年派位计划（人）"],
      [[d, n, p or "有"] for d, n, p in PUBLIC_PAIWEI])

# 9 小学梯队
rows = []
for zone, lvls in PRIMARY_TIERS.items():
    for lv, items in lvls.items():
        for x in items:
            rows.append([zone, lv, x["name"], x.get("note", "")])
write("09_小学_梯队.csv", ["区", "梯队", "学校", "说明"], rows)

# 10 小学档案
write("10_小学_学校档案.csv",
      ["学校", "简称", "区", "办学性质", "梯队", "建校", "办学特色",
       "师资力量", "施教区范围", "升学表现", "信息来源", "可信度"],
      [[s["name"], s.get("short", ""), s["district"], s["type"], s.get("tier", ""),
        s.get("founded", ""), s.get("feature", ""), s.get("faculty", ""),
        s.get("enroll", ""), s.get("perf", ""), s.get("source", ""), s.get("cred", "")]
       for s in PRIMARY_SCHOOLS])

# 11 四星级高中
write("11_高中_四星级名单.csv", ["序号", "学校名称"],
      [[i, n] for i, n in enumerate(FOUR_STAR, 1)])

# 12 指标生政策
write("12_政策_指标生.csv", ["项目", "内容"], [[a, b] for a, b in INDICATOR_STUDENT])

# 13 趋势
write("13_结论_趋势判断.csv", ["趋势", "说明"], [[a, b] for a, b in TRENDS])

# 14 来源
write("14_来源清单.csv", ["来源", "主要采集内容", "可信度"], [[a, b, c] for a, b, c in SOURCES])

# 15 控制线
rows = []
for y in ("2026", "2025"):
    d = CONTROL_LINES[y]
    for k, v in d.items():
        if k in ("来源", "可信度"):
            continue
        rows.append([y, k, v])
write("15_中考_投档控制线.csv", ["年份", "类别", "分值/说明"], rows)

print("\n全部导出完成 ->", OUTDIR)
