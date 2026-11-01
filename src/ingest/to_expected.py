# -*- coding: utf-8 -*-
"""把抽取到的施教区名单转成应收清单（data/expected_*.csv）。

为什么要落成 CSV：抽取结果留在 data/facts 里只能看，接进 reconcile.py 才能
逐校核对、才能写进 coverage_report.csv 分派任务。这也是项目里既有的做法——
17 份 expected_*.csv 都是「官方应收名单」，只是过去靠人工整理，这份由抽取产生。

关键点：能对上档案的行写**档案全称**（reconcile 会据此判「已有」），
对不上的写公告原名并由 reconcile 判「缺」。不在这里猜哪个是哪个。

用法：
  python3 src/ingest/to_expected.py            # 预演，只打印统计
  python3 src/ingest/to_expected.py --apply    # 写入 data/expected_gulou_primary.csv
"""
import argparse
import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest import extract                      # noqa: E402
from pipeline import config                     # noqa: E402

FACTS = os.path.join(config.ROOT, "data", "facts")
OUT = os.path.join(config.ROOT, "data", "expected_gulou_primary.csv")

# 与多数 expected_*.csv 保持同一套列，reconcile.py 认「档案全称 / 校名」
COLUMNS = ["序号", "校名", "类别", "施教区要点", "备注", "来源", "采集日期",
           "库内状态", "档案全称"]


def latest_records():
    """取最新一条「在办名单」与「施教区」记录。

    存在性判定必须用当年（2026）的招生名单，不能用 2023 年的施教区问答：
    后者还含汉口路、回龙桥、察哈尔路三所已撤并的学校，拿它当应收会
    凭空多出三个永远补不上的缺口。施教区文本仍取 2023 那份，作为补充信息。
    """
    lists, zones = None, None
    for path in sorted(glob.glob(os.path.join(FACTS, "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not rec.get("ok"):
                    continue
                job = rec.get("job", "")
                if job.startswith("school-list-"):
                    lists = rec
                elif job.startswith("zone-"):
                    zones = rec
    return lists, zones


def find_zone(name, zones):
    """公告里的施教区用简称（「天妃宫小学」），按包含关系对回全称。"""
    for key, zone in (zones or {}).items():
        if key and (key in name or name.endswith(key)):
            return zone
    return ""


def build_rows(school_rec, zone_rec):
    """把 {校名: 电话} 变成 CSV 行，施教区从另一份记录补。"""
    schools = extract.load_schools(level="小学")
    by_id = {sid: name for sid, name, _keys in schools}
    zones = (zone_rec or {}).get("values", {})
    rows = []
    for i, (name, phone) in enumerate(school_rec["values"].items(), 1):
        sid = extract.match_school(name, schools)
        rows.append({
            "序号": i,
            "校名": name,
            "类别": "公办小学",
            "施教区要点": find_zone(name, zones),
            "备注": f"咨询电话 {phone}" if phone else "",
            "来源": f"{school_rec.get('title', '')}（{school_rec.get('url', '')}）",
            "采集日期": (school_rec.get("extracted_at") or "")[:10],
            "库内状态": "已建档" if sid else "待建",
            # reconcile 优先读这一列：对上档案的写全称，对不上的留空，
            # 这样它就会按「缺」报出来，而不是被一个错误的映射蒙过去
            "档案全称": by_id.get(sid, "") if sid else "",
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写入 CSV")
    args = ap.parse_args()

    lists, zones = latest_records()
    if not lists:
        print("✗ data/facts/ 里没有「在办名单」记录，先跑：make extract")
        return 1

    rows = build_rows(lists, zones)
    matched = sum(1 for r in rows if r["档案全称"])
    print(f"来源：{lists.get('title')}")
    print(f"      {lists.get('url')}")
    print(f"共 {len(rows)} 所：能对上档案 {matched} / 待建 {len(rows) - matched}")
    if zones:
        print(f"施教区补充自：{zones.get('title')}")

    print("\n待建的学校（reconcile 会按「缺」列出）：")
    for r in rows:
        if not r["档案全称"]:
            print(f"  · {r['校名']}" + (f"　{r['施教区要点'][:20]}…" if r["施教区要点"] else ""))

    if not args.apply:
        print("\n预演结束，未写入。加 --apply 生成 CSV。")
        return 0

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"\n已写入 {os.path.relpath(OUT, config.ROOT)}")
    print("下一步：python3 src/reconcile.py data/expected_gulou_primary.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
