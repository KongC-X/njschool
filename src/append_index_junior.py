# -*- coding: utf-8 -*-
"""江宁区公办初中 24 所：批量写入 build_index.py + 补官网记录 + 生成应收清单。

三步一次完成，避免多次往返：
  1) 在 build_index.py 的 SCHOOLS 列表末尾追加条目（幂等）
  2) 在 data/school_websites.json 补官网记录（均未检索到）
  3) 生成 data/expected_jiangning_junior.csv（25 条含竹山中学）
"""
import importlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "src", "build_index.py")
WEB = os.path.join(ROOT, "data", "school_websites.json")
CSVJ = os.path.join(ROOT, "data", "expected_jiangning_junior.csv")
TODAY = "2026-10-25"

# 名录 25 所（附件 6「公办初中」类），含已在库的竹山中学
ROSTER = [
    ("百家湖中学", "025-52101149", "秣陵街道庄排路 18 号"),
    ("淳化中学", "025-52294710", "淳化街道淳关路 456 号"),
    ("东善桥中学", "025-52741658", "秣陵街道秣周中路 15 号"),
    ("谷里中学", "025-86133228", "谷里街道金谷北街 88 号"),
    ("横溪中学", "025-86161865", "横溪街道新宁丹路"),
    ("湖熟中学", "025-52690546", "湖熟街道灵顺北路 51 号"),
    ("江宁高新区中学", "15950512906", "淳化街道玉树路 78 号"),
    ("将军山中学", "025-52797980", "秣陵街道将军大道 4 号"),
    ("龙都中学", "025-52495663", "湖熟街道龙都陵园路 84 号"),
    ("陆郎中学", "025-86140910", "江宁街道古寺街 12 号"),
    ("禄口中学", "025-52772718", "禄口街道永欣大道 58 号"),
    ("觅秀街中学", "025-52716567-8023", "东山街道觅秀街 8 号"),
    ("秣陵初中", "025-52755283", "秣陵街道娘娘巷 302 号"),
    ("麒麟中学", "025-84199028", "麒麟街道文荟路 75 号"),
    ("齐武路中学", "025-86176165", "淳化街道瑞文路 188 号"),
    ("东山初级中学", "025-52830282", "东山街道上坊新城龙昌路"),
    ("上峰中学", "025-84148858", "汤山街道双阜东路 2 号"),
    ("上元中学", "025-52136504", "东山街道天印大道 701 号"),
    ("汤山中学", "025-84105658", "汤山街道汤泉西路 8 号"),
    ("桃红中学", "025-52737944", "横溪街道高洪路 99 号"),
    ("铜井中学", "025-86123068", "江宁街道花园街 90 号"),
    ("铜山中学", "025-86194901", "禄口街道航金大道 9 号"),
    ("土桥中学", "025-84150626", "淳化街道桂园西路 199 号"),
    ("紫金山科技城中学", "025-87175956", "秣陵街道凤仪街 1 号"),
    ("竹山中学", "025-87187771", "东山街道竹新路 58 号"),
]


def tier_of(s):
    if s.get("entry") or s.get("own_src"):
        return "江宁初中第一梯队"
    return "江宁初中第三梯队"


def line_of(s):
    name = s["name"]
    short = re.sub(r"^南京市(江宁区)?", "", name)
    tag = s["tagline"].replace('"', "”")
    if len(tag) > 100:
        tag = tag[:100].rstrip("，；、") + "…"
    return (f'    ("{name}", "{short}", "江宁区", "初中", "公办", "{tier_of(s)}",\n'
            f'     "{tag}"),')


def step_index(data):
    src = open(IDX, encoding="utf-8").read()
    start = src.index("SCHOOLS = [")
    end = src.index("\n]\n", start)
    body = src[start:end]
    added = []
    for s in data:
        if f'("{s["name"]}"' in body:
            continue
        added.append(line_of(s))
    if added:
        new = body.rstrip() + "\n" + "\n".join(added) + "\n]\n"
        open(IDX, "w", encoding="utf-8").write(src[:start] + new + src[end + 3:])
    print(f"[索引] 新增 {len(added)} 条")


def step_web(data):
    doc = json.load(open(WEB, encoding="utf-8"))
    table = doc["schools"]
    n = 0
    for s in data:
        key = f"初中-江宁区-{s['name']}"
        if key in table:
            continue
        table[key] = {
            "site": None, "site_archived": None, "null_reason": "未检索到",
            "repair": None, "wechat": None, "wechat_status": "unknown",
            "level": "C", "site_state": "none",
            "basis": "未检索到独立官网或江宁教育服务平台（jnjy.net.cn）站群分站；"
                     + ("施教区见区教育局初中一览或学校入学公告，中考成绩与师资未公开"
                        if (s.get("entry") or s.get("own_src"))
                        else "未列入区级初中一览，施教区需查学校公告"),
        }
        n += 1
    doc["updated"] = TODAY
    json.dump(doc, open(WEB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[官网] 新增 {n} 条，总计 {len(table)} 条")


def step_csv():
    import csv
    idx = json.load(open(os.path.join(ROOT, "index.json"), encoding="utf-8"))
    names = [x["name"] for x in idx["schools"]
             if x["district"] == "江宁区" and x["level"] == "初中"]
    SRC = "《2026年江宁区义务教育招生咨询电话》附件6（江宁区教育局，2026-05-09）"
    rows, have = [], 0
    for i, (short, tel, addr) in enumerate(ROSTER, 1):
        matched = [n for n in names if short in n]
        status = "已建档" if matched else "待补"
        if matched:
            have += 1
        rows.append([i, "公办初中", short, addr, tel, SRC, TODAY, status,
                     matched[0] if matched else ""])
    with open(CSVJ, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["序号", "类别", "名录名称", "地址", "咨询电话", "来源",
                    "采集日期", "库内状态", "档案全称"])
        w.writerows(rows)
    print(f"[清单] 应收 {len(rows)} 所，已建档 {have}，待补 {len(rows)-have} → {CSVJ}")


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    data = importlib.import_module("gen_jiangning_data5").SCHOOLS
    step_index(data)
    step_web(data)
    step_csv()


if __name__ == "__main__":
    main()
