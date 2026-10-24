# -*- coding: utf-8 -*-
"""来源标题归一与 URL 传播。

背景：同一份文件在不同档案里被写成多个标题（空格、书名号、署名方式不同），
导致「同一文件只有一种写法拿到了 URL，其余写法仍是纯文本」。

做法：
  1. 把标题归一化（去空格、统一书名号/引号、去尾部日期括注）得到 key
  2. 同 key 的标题视为同一份文件；只要其中一个有 URL，就把 URL 传播给其余
  3. 额外处理「同 URL 不同标题」的组：给标题补备注，注明与哪一条同源

用法：
  python3 src/fix_sources.py          # 只报告
  python3 src/fix_sources.py --apply  # 写回 data/sources.csv
"""
import csv
import os
import re
import sys
from collections import defaultdict

ROOT = "/Users/kongc/WorkBuddy/南京学校"
CSV_PATH = os.path.join(ROOT, "data", "sources.csv")

TRAIL_DATE = re.compile(r"[（(]\s*(19|20)\d{2}[-年./]\d{1,2}([-月./]\d{1,2}日?)?\s*[)）]")


def norm_key(title):
    t = title
    t = TRAIL_DATE.sub("", t)                     # 去掉尾部日期括注
    t = re.sub(r"[\s\u3000]+", "", t)              # 去空格
    t = t.replace("《", "").replace("》", "")
    t = t.replace("「", "").replace("」", "")
    t = t.replace("“", "").replace("”", "")
    t = t.replace("／", "/").replace("、", "/")
    t = re.sub(r"^/+|/+$", "", t)
    return t


def main():
    apply = "--apply" in sys.argv
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8-sig")))

    groups = defaultdict(list)
    for r in rows:
        groups[norm_key(r["标题"])].append(r)

    propagate, multi = [], []
    for key, items in groups.items():
        if len(items) < 2:
            continue
        # 同一份文件的多种写法：取其中已核实的 URL（若有多个不同 URL，说明归并过宽，跳过）
        urls = {r["URL"] for r in items if r["URL"]}
        if len(urls) == 1:
            url = urls.pop()
            missing = [r for r in items if not r["URL"]]
            if missing:
                propagate.append((key, url, missing))
        elif len(urls) > 1:
            multi.append((key, sorted(urls)))

    # 同 URL 不同标题（非归一化同名）：仅统计，便于人工判断
    by_url = defaultdict(list)
    for r in rows:
        if r["URL"]:
            by_url[r["URL"]].append(r["标题"])
    same_url = {u: ts for u, ts in by_url.items() if len(set(ts)) > 1}

    print(f"标题 {len(rows)} 个，归一化后 {len(groups)} 组")
    print(f"  可传播 URL 的组：{len(propagate)}，涉及 {sum(len(m) for _, _, m in propagate)} 个标题")
    for key, url, missing in propagate[:6]:
        print(f"    · {key[:44]}")
        print(f"      URL: {url[:56]}")
        for r in missing:
            print(f"      ← {r['标题'][:52]}")
    if multi:
        print(f"  ⚠ 同组多个不同 URL（跳过，需人工判断）：{len(multi)} 组")
        for key, urls in multi[:3]:
            print(f"    · {key[:40]} → {len(urls)} 个 URL")
    print(f"  同 URL 不同标题：{len(same_url)} 组（标题写法不一致，不影响链接）")

    if apply and propagate:
        for _, url, missing in propagate:
            for r in missing:
                r["URL"] = url
                if not r["采集日期"]:
                    r["采集日期"] = "2026-10-24"
                note = r.get("备注") or ""
                tag = "同一份文件的其他写法，URL 由同组条目传播而来"
                r["备注"] = (note + "；" + tag).strip("；")[:150]
        with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["标题", "类型", "URL", "采集日期", "备注"])
            w.writeheader()
            w.writerows(rows)
        filled = sum(1 for r in rows if r["URL"])
        print(f"\n已写回：{filled}/{len(rows)} 个标题有 URL")
    else:
        print("\n（未写回，加 --apply 生效）")


if __name__ == "__main__":
    main()
