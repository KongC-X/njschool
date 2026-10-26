# -*- coding: utf-8 -*-
"""六合区（主城）与高淳区（淳溪/古柏）小学建档（2026-10-25）。

来源：
  六合《六合区 2026 年主城义务教育阶段学校施教区方案》（njlh.gov.cn）
  高淳《南京市高淳区 2026 年义务教育阶段学校招生入学工作实施方案》（njgc.gov.cn）
      含附件 2「高淳区 2026 年义务教育阶段学校招生咨询电话」

用法：python src/gen_luhe_gaochun.py
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = "2026年10月25日"

TPL = """# {name}

> **一句话定位**：{tagline}
>
> **档案编写日期**：{today}　|　**数据截止**：2026年10月
> **信度标注**：`[A]` 官方发布　`[B]` 权威媒体转述　`[C]` 家长圈/自媒体口径（需交叉验证）

---

## 一、学校速览

| 项目 | 内容 | 信度 |
|---|---|---|
| 学校全称 | {name}{suffix} | A |
| 所在区 | {district}（{addr}） | A |
| 办学性质 | 公办（区属） | A |
| 学校类别 | 小学（六年制） | A |
| 咨询电话 | **{tel}** | {tel_level} |
| 2026 施教区 | {ns_short} | A |
| 对口初中 | {jr_short} | {jr_level} |

---

## 二、施教区（2026 年原文）`[A]`

依据{src_name}{entry}：

> {ns}

{boundary}
{note}

---

## 三、招生方式与时间节点`[A]`

| 方式 | 说明 |
|---|---|
| **施教区免试就近入学**（主渠道） | 户籍、实际常住地、房屋所有权证三者一致 |
| **热点公办小学电脑派位** | 本区 2026 年派位名单**未获取**，本校是否参与待核 |
| **民办小学电脑派位** | 可在民办小学中最多选 2 所报名（6 月 4—5 日） |
| **长幼随学** | 自 2026 年秋季学期起试行 |

**市级统一时间**`[A]`：户籍儿童网报 **5 月 17—19 日 17:00**；5 月 28 日查看审核进度；民办派位报名 6 月 4—5 日；派位 6 月 13 日；非南京市户籍网报 **7 月 2—6 日 17:00**；8 月 10 日前发放入学通知书。

{extra_time}

---

## 四、对口初中

{jr_body}

---

## 五、升学表现与师资

> **数据缺口**：本档案**未检索到学校公开的中考对口表现、专任教师总数、特级教师、正高级教师、市区骨干数量、创办年份、校训与办学理念**。`[C]`
>
> 若需了解，建议直接联系学校或区教育局招生咨询电话。

---

## 六、择校视角小结

**适合的家庭画像**

| 维度 | 判断 |
|---|---|
| 户籍房产在本校施教区范围内 | ★★★★★（就近入学，公办零学费） |
| 看重施教区边界可核对 | {fit_boundary} |
| 追求可验证的办学特色 | ★☆☆☆☆（公开信息极少） |

**关键决策变量**

{keys}

---

## 七、数据来源与可信度

| 来源 | 采集内容 | 信度 |
|---|---|---|
{src_rows}

### 数据缺口（明确未获取）

- **对口初中**（本区小学文件不写对应关系）
- 学校**具体门牌地址**（部分仅有街道/片区）
- 学校**中考对口表现**
- 学校**专任教师总数、特级教师、正高级教师、市区骨干数量**
- 学校**创办年份与办学沿革**
- 学校**校训、办学理念、三风表述**
- 学校**占地面积、建筑面积、班级与学生总数**
- 学校**特色项目、社团清单、荣誉资质**
- 学校**现任校长与领导班子名单**

### 编写说明

- 本档案基于公开渠道整理，**不代表学校官方立场**，不作为入学承诺依据。
- **施教区**来自区政府网站发布的 2026 年官方方案原文，**信度最高**。
- **对口初中、师资、校史均未获取**，未做推测性填写。
- 施教区与招生政策每年更新，**请以当年{district}教育局发布为准**。
"""

SRC = {
    "六合区": ("《六合区 2026 年主城义务教育阶段学校施教区方案》", "njlh.gov.cn，2026-05-08"),
    "高淳区": ("《南京市高淳区 2026 年义务教育阶段学校招生入学工作实施方案》", "njgc.gov.cn，2026-05-09"),
}


JR_DEFAULT = dict(
    short="**数据缺口**（未获取本区小学—初中对应关系）",
    level="—",
    body="""⚠️ **本节为数据缺口说明，不是结论**

本区小学与初中**分别发布施教区方案 / 分别划定**，小学文件内不写「对口初中」。

**本校对应的初中暂无法确认。** 需查本区初中施教区方案原文，与本校小学施教区逐段比对。

> 本档案不做地理推断——找不到原文就不写。""",
)


def build(s):
    from junior_override import OVERRIDE
    jr = OVERRIDE.get(s["name"], JR_DEFAULT)
    boundary = ""
    if s.get("rows"):
        boundary = "| 边界 | 内容 |\n|---|---|\n" + "\n".join(
            f"| {a} | {b} |" for a, b in s["rows"]) + "\n"

    nm, when = SRC[s["district"]]
    src_rows = (f"| **{nm}**（{when}）{s.get('entry', '')} | **施教区范围原文** | **A** |\n"
                f"| 同文件附表 / 区教育局公开渠道 | **学校名称、咨询电话** | **A** |")

    return TPL.format(
        name=s["name"], tagline=s["tagline"], today=TODAY,
        suffix=s.get("suffix", ""), district=s["district"], addr=s["addr"],
        tel=s["tel"], tel_level=s.get("tel_level", "A"),
        ns_short=s.get("ns_short", "见第二节"), ns=s["ns"],
        src_name=nm + "（" + when + "）", entry=s.get("entry", "原文"),
        boundary=boundary, note=s["note"].strip(),
        fit_boundary=s.get("fit_boundary", "★★★★☆"),
        keys="\n".join(s["keys"]),
        extra_time=s.get("extra_time", ""),
        src_rows=src_rows,
        jr_short=jr["short"], jr_level=jr["level"], jr_body=jr["body"].strip(),
    )


def main():
    from gen_luhe_gaochun_data import SCHOOLS
    bad = 0
    for s in SCHOOLS:
        out = os.path.join(ROOT, "小学", s["district"])
        os.makedirs(out, exist_ok=True)
        text = build(s)
        open(os.path.join(out, s["name"] + ".md"), "w", encoding="utf-8").write(text)
        n = len(text)
        if n < 1500:
            bad += 1
        print(f"{s['name']:<32}{n:>6} 字符{'' if n >= 1500 else '  ⚠ 偏短'}")
    print(f"\n共 {len(SCHOOLS)} 所，偏短 {bad} 处")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
