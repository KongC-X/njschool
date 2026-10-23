# -*- coding: utf-8 -*-
"""生成 Markdown 版学校档案"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_high import (
    CONTROL_LINES, PLAN_2026, TOP_SCHOOLS_LINE, OTHER_SCHOOLS_LINE_2026,
    FOUR_STAR, HIGH_SCHOOLS,
)
from data_mid import (
    XSC_POLICY, XSC_TIMELINE_2026, PRIVATE_MIDDLE, PUBLIC_PAIWEI,
    MIDDLE_SCHOOLS, MIDDLE_TIERS,
)
from data_pri import PRIMARY_TIERS, PRIMARY_SCHOOLS
from data_policy import ZHONGKAO_POLICY, INDICATOR_STUDENT, SOURCES, CRED_NOTE, TRENDS

OUT = "/Users/kongc/WorkBuddy/南京学校/南京中小学档案.md"
L = []
w = L.append


def md_table(headers, rows):
    w("| " + " | ".join(headers) + " |")
    w("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        w("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    w("")


def build():
    w("# 南京市中小学全景档案")
    w("")
    w("> 覆盖南京全市小学、初中、高中的学校信息档案，含办学特色、师资与招生范围、历年小升初与中考表现、综合排名。")
    w("> **数据截止：2026 年 10 月**　|　**来源：公开渠道（官方发布 + 权威媒体 + 自媒体）**　|　**每项数据均标注可信度 A / B / C**")
    w("")
    w("---")
    w("")

    # ============================================ 一、概览
    w("## 一、概览与关键结论")
    w("")
    w("### 1.1 2026 年南京中考基本盘（A 级 · 官方）")
    w("")
    md_table(["指标", "数值"], [
        ["中考总分", "700 分"],
        ["考生人数", "74,876 人"],
        ["普高计划", "53,439 人（较 2025 年 +6,101 人）"],
        ["普高学位供给率", "71.3%（首次突破 70%）"],
        ["全市中招总计划", "81,716 人"],
        ["第一批次控制线（原市区+浦口）", "535 分"],
        ["第二批次控制线（原市区+浦口）", "470 分"],
        ["指标生控制线（原市区+浦口）", "593 分"],
        ["科技/学科特长生控制线", "560 分"],
        ["艺术/体育特长生控制线", "490 / 455 分"],
        ["面向全市招生的普高", "13 所"],
        ["省级四星级普高（南京）", "35 所"],
    ])
    w("### 1.2 七大趋势判断")
    w("")
    for i, (t, d) in enumerate(TRENDS, 1):
        w(f"**{i}. {t}**")
        w("")
        w(d)
        w("")

    w("### 1.3 使用提示")
    w("")
    w("南京从未发布过官方的中小学排名。本报告中的「排名」为综合官方投档线（高中）与家长圈 / 学校宣讲会口径（初中、小学）整理，已逐条标注来源与可信度。择校决策请以官方发布为准。")
    w("")
    w("---")
    w("")

    # ============================================ 二、高中
    w("## 二、高中")
    w("")
    w("### 2.1 六大名校 12 校区近四年投档线走势（A 级 · 市招考院官方公布）")
    w("")
    w("分数每年波动，**位次比分数更稳定**。2026 年因普高大幅扩招，部分学校录取位次出现一定程度下移。")
    w("")
    md_table(["#", "学校", "校区", "2026", "2025", "2024", "2023", "信度"],
             [[i, s, c, y26, y25 or "—", y24 or "—", y23 or "—", cr]
              for i, (s, c, y26, y25, y24, y23, cr) in enumerate(TOP_SCHOOLS_LINE, 1)])
    w("### 2.2 2026 年第一批次其余高中投档线（13 名以后 · B/C 级，存在个别冲突）")
    w("")
    md_table(["#", "学校", "校区/类别", "2026 投档线", "信度"],
             [[i, s, c, sc, cr]
              for i, (s, c, sc, cr) in enumerate(OTHER_SCHOOLS_LINE_2026, 13)])

    w("### 2.3 2026 年面向全市招生的 13 所普高招生计划（A 级 · 中考指南）")
    w("")
    w(f"全市普高计划 {PLAN_2026['全市普高计划']} 人，较去年增加 {PLAN_2026['较去年增加']} 人，普高学位供给率 {PLAN_2026['普高学位供给率']}。")
    w("")
    md_table(["#", "学校/校区", "2026 计划（人）", "较去年"],
             [[i, n, p, d] for i, (n, p, d) in enumerate(PLAN_2026["各校计划"], 1)])

    w("### 2.4 投档控制分数线一览（A 级）")
    w("")
    rows = []
    for y in ("2026", "2025"):
        d = CONTROL_LINES[y]
        for k, v in d.items():
            if k in ("来源", "可信度"):
                continue
            rows.append([y, k, v])
    md_table(["年份", "类别", "分值/说明"], rows)

    w("### 2.5 江苏省四星级普通高中（南京，共 35 所 · A 级 · 省教育厅名单）")
    w("")
    w("、".join(FOUR_STAR))
    w("")

    w("### 2.6 高中学校档案")
    w("")
    for s in HIGH_SCHOOLS:
        w(f"#### {s['name']}（{s.get('short','')}）")
        w("")
        md_table(["项目", "内容"], [
            ["区 / 性质", f"{s['district']} / {s['type']}"],
            ["建校", s.get("founded", "—")],
            ["校区", s.get("campuses", "—")],
            ["层次资质", s.get("level", "—")],
            ["办学特色", s.get("feature", "—")],
            ["师资力量", s.get("faculty", "—")],
            ["招生计划", s.get("enroll", "—")],
            ["中考录取线", s.get("line", "—")],
            ["高考表现", s.get("gaokao", "—")],
            ["信息来源", s.get("source", "—")],
            ["可信度", s.get("cred", "—")],
        ])
    w("---")
    w("")

    # ============================================ 三、初中
    w("## 三、初中")
    w("")
    w("> **关于初中排名**：南京初中没有官方排名。下列梯队为家长圈共识 + 2025/2026 中考网传数据 + 学校宣讲会披露数据综合整理（C 级），仅用于判断格局，具体以各校官方发布为准。")
    w("")
    w("### 3.1 初中综合梯队（民间口径 · C 级）")
    w("")
    for lv, names in MIDDLE_TIERS.items():
        w(f"**{lv}**")
        w("")
        for n in names:
            w(f"- {n}")
        w("")

    w("### 3.2 民办初中摇号计划与学费（2026 · B/C 级）")
    w("")
    w("「—」表示该渠道未获取到具体数值。学费单位为元/生·学期。")
    w("")
    md_table(["学校", "区", "2026 摇号计划", "2025 摇号计划", "学费", "备注"],
             [[n, d, p26 or "—", p25 or "—", fee, note]
              for n, d, p26, p25, fee, note in PRIVATE_MIDDLE])

    w("### 3.3 热点公办初中电脑派位计划（部分 · A 级）")
    w("")
    md_table(["区", "学校", "2026 派位计划（人）"],
             [[d, n, p if p else "有"] for d, n, p in PUBLIC_PAIWEI])

    w("### 3.4 初中学校档案")
    w("")
    for s in MIDDLE_SCHOOLS:
        w(f"#### {s['name']}")
        w("")
        md_table(["项目", "内容"], [
            ["区 / 性质 / 梯队", f"{s['district']} / {s['type']} / {s.get('tier','—')}"],
            ["办学特色", s.get("feature", "—")],
            ["施教区 / 招生", s.get("enroll", "—")],
            ["2026 中考成绩", s.get("perf2026", "—")],
            ["2025 中考成绩", s.get("perf2025", "—")],
            ["信息来源", s.get("source", "—")],
            ["可信度", s.get("cred", "—")],
        ])
    w("---")
    w("")

    # ============================================ 四、小学
    w("## 四、小学")
    w("")
    w("> **关于小学排名**：南京小学同样没有官方排名。梯队划分结合家长口碑、南外录取数据与民间评价整理（C 级）。施教区范围来自各区教育局公示（A 级）。")
    w("")
    w("### 4.1 各区小学梯队分布")
    w("")
    for zone, lvls in PRIMARY_TIERS.items():
        w(f"#### {zone}")
        w("")
        for lv, items in lvls.items():
            w(f"**{lv}**")
            w("")
            for x in items:
                note = f"：{x['note']}" if x.get("note") else ""
                w(f"- **{x['name']}**{note}")
            w("")

    w("### 4.2 重点小学详细档案")
    w("")
    for s in PRIMARY_SCHOOLS:
        w(f"#### {s['name']}（{s.get('short','')}）")
        w("")
        md_table(["项目", "内容"], [
            ["区 / 性质 / 梯队", f"{s['district']} / {s['type']} / {s.get('tier','—')}"],
            ["建校", s.get("founded", "—")],
            ["办学特色", s.get("feature", "—")],
            ["师资力量", s.get("faculty", "—")],
            ["施教区范围", s.get("enroll", "—")],
            ["升学表现", s.get("perf", "—")],
            ["信息来源", s.get("source", "—")],
            ["可信度", s.get("cred", "—")],
        ])
    w("---")
    w("")

    # ============================================ 五、政策
    w("## 五、政策要点")
    w("")
    w("### 5.1 2026 年小升初政策（A 级）")
    w("")
    for a, b in XSC_POLICY:
        w(f"**{a}**")
        w("")
        w(b)
        w("")
    w("### 5.2 2026 年小升初时间轴（A 级）")
    w("")
    md_table(["时间", "事项"], [[a, b] for a, b in XSC_TIMELINE_2026])

    w("### 5.3 2026 年中考招生政策（A 级）")
    w("")
    for a, b in ZHONGKAO_POLICY:
        w(f"**{a}**")
        w("")
        w(b)
        w("")
    w("### 5.4 指标生政策详解（小升初择校的关键变量）")
    w("")
    for a, b in INDICATOR_STUDENT:
        w(f"**{a}**")
        w("")
        w(b)
        w("")
    w("---")
    w("")

    # ============================================ 六、来源
    w("## 六、数据来源与可信度")
    w("")
    w("### 6.1 可信度分级说明")
    w("")
    for line in CRED_NOTE.strip().split("\n"):
        if line.strip():
            w(line.strip())
            w("")
    w("### 6.2 来源清单")
    w("")
    md_table(["来源", "主要采集内容", "信度"],
             [[a, b, c] for a, b, c in SOURCES])
    w("---")
    w("")
    w("_本档案由公开渠道整理，仅供参考。官方信息请以南京市教育局（edu.nanjing.gov.cn）及各区政府、教育局官网发布为准。_")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("Markdown 已生成:", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    build()
