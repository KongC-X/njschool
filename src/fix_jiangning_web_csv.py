# -*- coding: utf-8 -*-
"""补 4 所小学官网记录（data3 那批漏补），并修正江宁初中清单的名称匹配。

名称匹配问题：名录用简称（「淳化中学」），档案用全称（「南京市江宁区淳化初级中学」），
substring 匹配失败。改为「归一化后比较」：去掉 南京市/江宁区/初级/（…） 等修饰再比。
"""
import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "data", "school_websites.json")
CSVJ = os.path.join(ROOT, "data", "expected_jiangning_junior.csv")
TODAY = "2026-10-25"

MISSING_WEB = {
    "小学-江宁区-南京市诚信小学": "施教区见区教育局小学一览（第五条）；学校本体信息未公开",
    "小学-江宁区-南京市翠屏山小学": "施教区见区教育局小学一览（第七条）；学校本体信息未公开",
    "小学-江宁区-南京市科学园小学": "施教区见区教育局小学一览（第十九条）；学校本体信息未公开",
    "小学-江宁区-南京市竹山小学": "施教区见区教育局小学一览（第四十二条）；学校本体信息未公开",
}


def norm(s):
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("初中", "中学")          # 名录「秣陵初中」↔ 档案「秣陵初级中学」
    for w in ("南京市", "江宁区", "初级", "高级", "学校", " "):
        s = s.replace(w, "")
    return s


def main():
    # 1) 补官网记录
    doc = json.load(open(WEB, encoding="utf-8"))
    table = doc["schools"]
    n = 0
    for key, note in MISSING_WEB.items():
        if key in table:
            continue
        table[key] = {
            "site": None, "site_archived": None, "null_reason": "未检索到",
            "repair": None, "wechat": None, "wechat_status": "unknown",
            "level": "C", "site_state": "none",
            "basis": f"未检索到独立官网或江宁教育服务平台（jnjy.net.cn）站群分站；{note}",
        }
        n += 1
    doc["updated"] = TODAY
    json.dump(doc, open(WEB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[官网] 补 {n} 条，总计 {len(table)} 条")

    # 2) 修正初中清单匹配
    idx = json.load(open(os.path.join(ROOT, "index.json"), encoding="utf-8"))
    names = [x["name"] for x in idx["schools"]
             if x["district"] == "江宁区" and x["level"] == "初中"]
    normed = {norm(x): x for x in names}

    rows = list(csv.DictReader(open(CSVJ, encoding="utf-8-sig")))
    fields = list(rows[0].keys())
    have = 0
    for r in rows:
        short = r["名录名称"]
        hit = normed.get(norm(short))
        if not hit:
            cand = [x for x in names if norm(short) in norm(x)]
            hit = cand[0] if cand else None
        if hit:
            r["库内状态"], r["档案全称"] = "已建档", hit
            have += 1
        else:
            r["库内状态"] = "待补"
    with open(CSVJ, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"[清单] 应收 {len(rows)} 所，已建档 {have}，待补 {len(rows)-have}")


if __name__ == "__main__":
    main()
