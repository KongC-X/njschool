# -*- coding: utf-8 -*-
"""
从 index.json 生成《南京中小学档案.md》全量目录。

数据源：index.json（由 build_index.py 从 学段/行政区/学校.md 扫描生成）
说明：本脚本取代早期由 data_*.py 驱动的 build_md.py，改为「档案为唯一数据源」。
"""
import json
import os
from collections import OrderedDict

# 从脚本自身位置推导项目根：写死绝对路径的话，换机器或在 CI 上跑会写到错的地方
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.json")
OUT = os.path.join(ROOT, "南京中小学档案.md")

LEVELS = ["小学", "初中", "高中"]
LEVEL_DESC = {
    "小学": "小学阶段无官方升学率指标，各档案以「对口初中 + 对口初中中考表现」间接体现出口。",
    "初中": "初中中考成绩多数无官方公示，高分段与四星率多来自家长圈口径，均标 `[C]`。",
    "高中": "高中以 2026 年投档线为核心参照，投档线已对照市招考院公布值。",
}


def load():
    with open(INDEX, encoding="utf-8") as f:
        return json.load(f)


def group(schools):
    """按 学段 -> 区 分组，保留 index 原顺序（该顺序已按梯队优先）"""
    out = OrderedDict()
    for lv in LEVELS:
        out[lv] = OrderedDict()
        for s in schools:
            if s["level"] == lv:
                out[lv].setdefault(s["district"], []).append(s)
    return out


def build():
    d = load()
    schools = d["schools"]
    districts = d["districts"]
    cov = d["coverage"]
    g = group(schools)

    L = []
    L.append("# 南京中小学档案总览\n")
    L.append(f"> **数据版本**：{d.get('version', '—')}　|　**更新时间**：{d.get('updated', '—')}")
    L.append(f"> **收录规模**：共 **{len(schools)} 所**（小学 {cov.get('小学', 0)} 所、初中 {cov.get('初中', 0)} 所、高中 {cov.get('高中', 0)} 所），覆盖 {len(districts)} 个区")
    L.append("> ")
    L.append("> **数据来源**：全部来自公开渠道（政府/教育局官网、学校官网与官方公众号、党报与权威媒体），")
    L.append("> 每份档案内均逐条标注信度 `[A]`/`[B]`/`[C]` 并附来源表与「数据缺口清单」。")
    L.append("> ")
    L.append("> **使用说明**：本目录仅为公开信息汇编，**不构成择校建议**；政策与数据每年变动，请以官方最新发布为准。\n")
    L.append("---\n")

    # ---------- 总览 ----------
    L.append("## 一、总览\n")
    L.append("### 1.1 学段 × 行政区 分布\n")
    head = "| 行政区 | " + " | ".join(LEVELS) + " | 合计 |"
    sep = "|---|" + "---:|" * len(LEVELS) + "---:|"
    L.append(head)
    L.append(sep)
    col_tot = {lv: 0 for lv in LEVELS}
    for dist in districts:
        row = [dist]
        tot = 0
        for lv in LEVELS:
            n = len(g[lv].get(dist, []))
            row.append(str(n) if n else "—")
            col_tot[lv] += n
            tot += n
        if tot:
            row.append(f"**{tot}**")
            L.append("| " + " | ".join(row) + " |")
    L.append("| **合计** | " + " | ".join(f"**{col_tot[lv]}**" for lv in LEVELS) + f" | **{len(schools)}** |\n")

    # ---------- 各学段 ----------
    sec = ["二", "三", "四"]
    for i, lv in enumerate(LEVELS):
        n = col_tot[lv]
        L.append(f"## {sec[i]}、{lv}（{n} 所）\n")
        L.append(f"> {LEVEL_DESC[lv]}\n")
        for dist, items in g[lv].items():
            L.append(f"### {dist}（{len(items)} 所）\n")
            L.append("| 学校 | 简称 | 性质 | 梯队定位 | 一句话定位 | 档案 |")
            L.append("|---|---|---|---|---|---|")
            for s in items:
                tag = (s.get("tagline") or "").replace("|", "／").replace("\n", " ")
                L.append(
                    f"| **{s['name']}** | {s.get('short') or '—'} | {s['type']} | {s.get('tier') or '—'} "
                    f"| {tag} | [打开]({s['file']}) |"
                )
            L.append("")

    # ---------- 2026 重要变化 ----------
    L.append("## 五、2026 年重要变化\n")
    L.append("### 5.1 学校更名与归属变动\n")
    L.append("| 现用校名 | 原校名 | 变动时间 | 依据 |")
    L.append("|---|---|---|---|")
    for a, b, c, e in [
        ("南京市金陵中学建邺实验学校（初中部）", "南京市建邺初级中学", "2026 年 5 月", "南京市人民政府官网"),
        ("南京市金陵中学南湖初级中学", "南京市南湖第二中学", "2026 年 5 月", "南京市人民政府官网"),
        ("南京市金陵中学华山路小学", "南京市华山路小学", "2026 年 5 月", "南京市人民政府官网"),
        ("南京市金陵中学南湖小学", "南京晓庄学院第一实验小学（增挂校名）", "2026 年 5 月", "南京市人民政府官网"),
        ("南京江北新区外国语小学", "浦口外国语学校高新小学", "2026 年 4 月 20 日", "南京晨报／学校官微"),
        ("南京市金陵河西学校", "金陵中学河西分校", "2024 年 5 月 17 日", "学校官方公告"),
        ("南京东南实验学校", "南师附中江宁分校（仅义务教育段）", "2024 年 5 月 17 日", "学校官网"),
        ("南京雨花外国语学校", "南外雨花国际学校（义务教育段）", "—", "学校官方"),
    ]:
        L.append(f"| **{a}** | {b} | {c} | {e} |")
    L.append("")

    L.append("### 5.2 校名易错提示\n")
    L.append("| 易混项 | 说明 |")
    L.append("|---|---|")
    for a, b in [
        ("南京市东山小学", "官方注册名；媒体与家长圈习称「东山实验小学」，为同一所学校"),
        ("玄外附小 vs 玄外", "两个独立办学主体，严格意义上非九年一贯制；约 40% 经校内摇号直升，不看成绩"),
        ("明道学校 vs 明道研创园学校", "前者为民办（摇号招生、无施教区），后者为公办九年一贯制（有施教区），两个实体"),
        ("一中明发滨江分校 vs 一中明发滨江南浦路中学", "两所独立学校（24 班 vs 4 班），数据不可混用"),
        ("南京市秦淮中学", "虽含「秦淮」二字，实际位于江宁区（沿用江宁县秦淮中学渊源）"),
        ("南京江北新区外国语小学 vs 南京江北新区外国语学校", "前者为小学，后者为初中，不同学段不同学校"),
    ]:
        L.append(f"| {a} | {b} |")
    L.append("")

    L.append("### 5.3 2026 年招生政策变化\n")
    for a, b in [
        ("公办初中取消提前一年落户", "2025 年起公办小学已取消，2026 年鼓楼、秦淮、建邺三区初中同步取消（南京市人民政府官网）"),
        ("取消学区房年限限制", "不再提「一套住房三年内只能安排一名学生就读」"),
        ("「长幼随学」试点", "2026 年秋季学期起，义务教育起始年级试行"),
        ("普通高中扩招", f"全市普高计划 53,439 人（净增 6,101），普高学位供给率 71.3%，首次突破 70%"),
        ("浦口区与江北新区招生并轨", "2026 年起浦口区考生纳入原市区填报范围，中招范围打通"),
    ]:
        L.append(f"- **{a}**：{b}")
    L.append("")

    # ---------- 说明 ----------
    L.append("## 六、信度体系与使用说明\n")
    L.append("| 标记 | 含义 |")
    L.append("|---|---|")
    L.append("| `[A]` | 官方发布：学校官网、官方公众号、区教育局/区政府官网、市教育局、市招考院 |")
    L.append("| `[B]` | 权威媒体转述：南京日报、扬子晚报/紫牛新闻、现代快报、新华报业、人民网江苏、南京晨报 |")
    L.append("| `[C]` | 家长圈/自媒体口径（今日头条、微信公众号、培训机构站点），需交叉验证 |")
    L.append("")
    L.append("**关于「数据缺口」**：每份档案末节均列「数据缺口清单」，明确标注哪些字段未获取。")
    L.append("这些是**查不到**，而非**写错了**，请勿将缺口项当作零或默认值。\n")
    L.append("**关于家长圈数据**：中考四星率、普高率、六大率等，全市多数学校无官方公示，")
    L.append("档案中的数值多为家长圈统计，已统一标 `[C]`，**不可作为唯一择校依据**。\n")

    L.append("---\n")
    L.append(f"*本目录由 `src/build_catalog.py` 自动生成，共 {len(schools)} 所。修改档案后重跑即可同步。*\n")

    md = "\n".join(L)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"已生成：{OUT}")
    print(f"  收录 {len(schools)} 所，{len(md)} 字符")


if __name__ == "__main__":
    build()
