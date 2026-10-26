# -*- coding: utf-8 -*-
"""生成原浦口区 17 所公办小学档案（2026-10-24 第四批）。

骨架统一，内容逐校手写。所有「施教区 / 招生计划 / 对口初中」均来自
《南京江北新区（浦口区）2026 年小学招生入学工作实施方案》（宁新区管教发〔2026〕24 号）
附件 1 与《…2026 年初中招生入学工作实施方案》附件 1。

用法：python src/gen_pukou_primary.py [--check]
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 输出目录：默认 小学/江北新区；可用第二个参数指定区名，如 gen_jiangning_data 江宁区
DEF_DISTRICT = "江北新区"
OUT_DIR = os.path.join(ROOT, "小学", DEF_DISTRICT)
TODAY = "2026年10月24日"
CUTOFF = "2026年10月"

HEAD = """# {name}

> **一句话定位**：{tagline}
>
> **档案编写日期**：{today}　|　**数据截止**：{cutoff}
> **信度标注**：`[A]` 官方发布　`[B]` 权威媒体转述　`[C]` 家长圈/自媒体口径（需交叉验证）

---

## 一、学校速览

| 项目 | 内容 | 信度 |
|---|---|---|
{quick}

---

"""

TAIL = """
---

## 三、招生与施教区

### 3.1 2026 年施教区范围原文`[A]`

依据《南京江北新区（浦口区）2026 年小学招生入学工作实施方案》（宁新区管教发〔2026〕24 号）附件 1：

> {ns}

**招生计划：{classes}**。

{ns_note}

### 3.2 招生方式`[A]`

| 方式 | 说明 |
|---|---|
| **施教区免试就近入学**（主渠道） | 户籍、房屋所有权证（不动产权证）、实际常住地「三者一致」 |
| **热点公办小学电脑派位** | {paidui} |
| **民办小学电脑派位** | 可另行选报（与热点公办合计最多 2 所） |
| **长幼随学** | 2026 年秋季学期起可申请 |

### 3.3 2026 年报名时间节点（区级统一）`[A]`

| 时间 | 事项 |
|---|---|
| 5 月 8 日起 | 公布实施方案及施教区范围 |
| 5 月 15 日起 | 张贴一年级招生通告 |
| 5 月 17 日—19 日 | 平台报名登记（截止 5 月 19 日 17:00） |
| 5 月 28 日 | 查看审核进度 |
| 5 月 30 日 | 公布派位名单与计划 |
| 6 月 4 日—5 日 | 填报派位志愿（截止 6 月 5 日 17:00） |
| 6 月 13 日 | 电脑派位 |
| 6 月 26 日—7 月 2 日 | 确认录取学校 |
| 8 月 10 日前 | 发放入学通知 |

### 3.4 入学条件要点`[A]`

- **年龄**：年满六周岁（2026 年入学对应 2019-09-01 至 2020-08-31 出生）
- **房产与户籍**：三者一致，持证人须仅为法定监护人
- **随迁子女**：由区教育局统筹安排，不参加派位

---

## 四、对口初中与升学

> **核心提示**：小学阶段**不存在官方「升学率」指标**。出口质量由**对口初中的中考表现**间接体现。

### 4.1 对口初中：{zhong_name}`[{zhong_level}]`

{zhong_body}

### 4.2 小升初三类通道`[A]`

1. **施教区对口直升**（主渠道）：升入**{zhong_short}**
2. **热点公办初中/民办初中电脑派位**：最多选报 2 所
3. **南外语言能力测评**：全市所有小学均可报名

> **关于南外录取数据**：**未检索到可靠、可核实的本校南外录取人数。** 本档案不提供未经证实的数字。

### 4.3 对口初中的定位

{zhong_pos}

> ⚠️ **数据缺口**：**未检索到{zhong_short}公开的、可核实的中考成绩数据**（四星达线率、普高率、均分、高分段）。本档案不臆造。

---

## 五、师资力量

{shizi}

---

## 六、办学特色与荣誉

{features}

---

## 七、家长口碑与评价（`[C]`，需自行甄别）

**优势共识**

{pros}

**争议与关注点**

{cons}

---

## 八、择校视角小结

**适合的家庭画像**

| 维度 | 判断 |
|---|---|
{fit}

**关键决策变量**

{keys}

---

## 九、数据来源与可信度

| 来源 | 采集内容 | 信度 |
|---|---|---|
| **《南京江北新区（浦口区）2026 年小学招生入学工作实施方案》（宁新区管教发〔2026〕24 号）附件 1** | **施教区范围原文、招生计划 {classes}** | **A** |
| **《南京江北新区（浦口区）2026 年初中招生入学工作实施方案》附件 1** | **{zhong_name}施教区原文（用于对口比对）、招生班数** | **A** |
| **《南京江北新区（浦口区）2026 年热点公办学校、民办学校电脑随机派位实施方案》** | **确认本校是否列入热点公办小学派位名单** | **A** |
{src}

### 数据缺口（明确未获取）

以下内容**未能从公开渠道获得可靠数据，故未填写**：

{gaps}

### 编写说明

{notes}
"""


def build(s):
    quick = "\n".join(f"| {k} | {v} | {c} |" for k, v, c in s["quick"])
    heads = HEAD.format(
        name=s["name"], tagline=s["tagline"], today=TODAY, cutoff=CUTOFF, quick=quick
    )
    body = s["body"].strip() + "\n"
    tail = TAIL.format(
        ns=s["ns"], classes=s["classes"], ns_note=s["ns_note"],
        paidui=s["paidui"],
        zhong_name=s["zhong_name"], zhong_level=s["zhong_level"],
        zhong_body=s["zhong_body"].strip(), zhong_short=s["zhong_short"],
        zhong_pos=s["zhong_pos"].strip(), shizi=s["shizi"].strip(),
        features=s["features"].strip(), pros=s["pros"].strip(),
        cons=s["cons"].strip(), fit="\n".join(f"| {a} | {b} |" for a, b in s["fit"]),
        keys="\n".join(s["keys"]).strip(),
        src="\n".join(f"| {a} | {b} | {c} |" for a, b, c in s["src"]),
        gaps="\n".join(s["gaps"]).strip(),
        notes="\n".join(s["notes"]).strip(),
    )
    return heads + body + tail


def main():
    import importlib
    mod_name = sys.argv[1] if len(sys.argv) > 1 else "gen_pukou_data"
    district = sys.argv[2] if len(sys.argv) > 2 else DEF_DISTRICT
    SCHOOLS = importlib.import_module(mod_name).SCHOOLS
    out_dir = os.path.join(ROOT, "小学", district)
    os.makedirs(out_dir, exist_ok=True)
    bad = 0
    for s in SCHOOLS:
        text = build(s)
        path = os.path.join(out_dir, s["name"] + ".md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        n = len(text)
        flag = ""
        if n < 1500:
            flag = "  ⚠ 少于 1500 字符"
            bad += 1
        if "数据缺口" not in text:
            flag += "  ⚠ 缺「数据缺口」"
            bad += 1
        print(f"{s['name']:<24} {n:>6} 字符{flag}")
    print(f"\n共 {len(SCHOOLS)} 所，异常 {bad} 处")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
