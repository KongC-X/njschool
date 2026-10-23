# -*- coding: utf-8 -*-
"""数据盘点：量化「收录不全 / 字段缺失 / 来源不足」三类问题。

产物：
  data/data_audit.json   每所学校的缺口明细（机器可读，便于跟踪）
  data/missing_candidates.csv  正文提到但库内没有的学校名（候选补录清单）

方法说明：
  收录完整性无法直接与官方名录比对（官方名录不公开结构化版本），
  因此用「档案正文互相引用」做交叉索引：A 校档案里提到的 B 校若不在库中，
  说明 B 校缺失的概率很高。这是启发式，输出的是候选，不是结论。
"""
import csv
import glob
import json
import os
import re
from collections import Counter

ROOT = "/Users/kongc/WorkBuddy/南京学校"
OUT_JSON = os.path.join(ROOT, "data", "data_audit.json")
OUT_CSV = os.path.join(ROOT, "data", "missing_candidates.csv")

# 学校名候选：中文 2–10 字 + 学段后缀
NAME_RE = re.compile(r"[\u4e00-\u9fa5]{2,20}(?:小学|初级中学|高级中学|中学|学校)")

# 过滤：正文里大量「所有小学」「热点公办小学」这类泛称，靠词表与长度剔除
STOP_WORDS = (
    "所有", "各", "民办", "公办", "热点", "平台", "技工", "培训", "大学", "学院",
    "间接", "不代表", "行电脑", "全市", "区内", "本区", "其他", "部分", "该",
    "我校", "本校", "该校", "对口", "直升", "集团", "确认", "填报", "报名",
    "的", "与", "及", "或", "等", "含", "不含", "以下", "以上", "其中",
    "以及", "包括", "参考", "相关", "所属", "指定", "周边", "附近", "片内",
    # 荣誉/称号类，不是校名
    "先进", "示范", "文明", "德育", "阳光体育", "绿色", "平安", "依法治校",
    "素质教育", "特色", "合格", "现代化", "江苏省实验", "南京市实验",
    "中小学", "查看", "按", "数据是", "家长圈", "衡量",
)
SUFFIXES = ("初级中学", "高级中学", "小学", "中学", "学校")
# 校名通常带地名/品牌特征，用这些词提高召回精度
ANCHORS = ("南京市", "南京", "区", "街", "路", "村", "新城", "星城", "花园",
           "附中", "附小", "实验", "外国语", "中心", "一中", "二中", "三中",
           "四中", "五中", "九中", "十二中", "十三中", "二十七", "二十九",
           "金陵", "南师", "南外", "游府西街", "拉萨路", "琅琊", "力学",
           "芳草园", "银城", "赤壁路", "三牌楼", "天妃宫", "摄山", "晓庄")


def is_likely_school(name):
    if any(w in name for w in STOP_WORDS):
        return False
    for suf in SUFFIXES:
        if name.endswith(suf):
            stem = name[: -len(suf)]
            if len(stem) < 3:
                return False
            return any(a in name for a in ANCHORS)
    return False

# 关键词 → 关注的字段
FIELDS = {
    "special": ("特长生", "科技特长", "信息学", "体育特长", "艺术特长"),
    "exam": ("中考", "四星", "达线", "升学率", "普高率"),
    "score": ("投档线",),
    "zhibiao": ("指标生",),
}


def load_schools():
    with open(os.path.join(ROOT, "index.json"), encoding="utf-8") as f:
        return json.load(f)


def audit_one(raw):
    path = os.path.join(ROOT, raw["file"])
    text = open(path, encoding="utf-8").read()

    conf = len(re.findall(r"\[[ABC]\]", text))
    gap_block = text.split("数据缺口", 1)[1] if "数据缺口" in text else ""
    gap_items = len(re.findall(r"(?m)^\s*[-*\d]", gap_block[:2000]))
    src_rows = len(re.findall(r"(?m)^\|.*https?://.*\|", text))

    present = {k: any(w in text for w in words) for k, words in FIELDS.items()}
    return {
        "id": raw["id"],
        "name": raw["name"],
        "level": raw["level"],
        "district": raw["district"],
        "conf_marks": conf,
        "gap_items": gap_items,
        "source_url_rows": src_rows,
        "has_special": present["special"],
        "has_exam": present["exam"],
        "has_score": present["score"],
        "has_zhibiao": present["zhibiao"],
        "chars": len(text),
    }


def main():
    index = load_schools()
    schools = index["schools"]

    rows = [audit_one(s) for s in schools]
    json.dump({"total": len(rows), "schools": rows},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---------- 字段覆盖统计 ----------
    n = len(rows)
    def pct(key, want=True):
        c = sum(1 for r in rows if r[key] == want)
        return c, c * 100 // n

    print(f"共 {n} 所")
    for key, label in (("has_special", "提到特长生"), ("has_exam", "提到中考/升学"),
                       ("has_score", "提到投档线"), ("has_zhibiao", "提到指标生")):
        c, p = pct(key)
        print(f"  {label:14s} {c:3d} 所（{p}%）")

    print("\n分学段：")
    for lv in ("小学", "初中", "高中"):
        sub = [r for r in rows if r["level"] == lv]
        if not sub:
            continue
        sp = sum(1 for r in sub if r["has_special"])
        ex = sum(1 for r in sub if r["has_exam"])
        print(f"  {lv}: {len(sub):3d} 所 | 特长生 {sp:3d} | 升学 {ex:3d} "
              f"| 平均信度标注 {sum(r['conf_marks'] for r in sub)//len(sub)} 处 "
              f"| 平均缺口 {sum(r['gap_items'] for r in sub)/len(sub):.1f} 条")

    # ---------- 收录缺口：正文提到但库中没有 ----------
    known = {s["name"] for s in schools}
    known_all = set()
    for s in schools:
        known_all.add(s["name"])
        known_all.add(s["name"].replace("南京市", "").replace("南京", ""))
        if s.get("short"):
            known_all.add(s["short"])

    mentions = Counter()
    for s in schools:
        text = open(os.path.join(ROOT, s["file"]), encoding="utf-8").read()
        for cand in set(NAME_RE.findall(text)):
            nm = cand
            if any(k in nm for k in ("我校", "该校", "本校", "集团", "教育集团", "附属")):
                continue
            if nm in known_all or not is_likely_school(nm):
                continue
            mentions[nm] += 1

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["候选学校名", "被提及次数", "说明"])
        for nm, c in mentions.most_common(80):
            w.writerow([nm, c, "档案正文提到，但库内无对应档案"])

    print(f"\n正文提到但库内缺失的候选：{len(mentions)} 个（列出被提及最多的 12 个）")
    for nm, c in mentions.most_common(12):
        print(f"  {c:3d} 次  {nm}")

    print(f"\n明细已写入 {OUT_JSON}")
    print(f"候选清单已写入 {OUT_CSV}")


if __name__ == "__main__":
    main()
