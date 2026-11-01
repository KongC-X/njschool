# -*- coding: utf-8 -*-
"""抽取全库「数据来源」章节的来源标题，生成来源登记表。

为什么要做：229 份档案共 2,000+ 行来源，但全部只有名称没有链接，
无法核验。逐个改档案不现实，因此改为维护一份登记表（标题 → URL），
构建期按标题匹配、渲染成可点链接。

产物：
    data/sources.csv        标题, 类型, URL, 采集日期, 备注（人工/代理补 URL）
    data/sources_report.csv 标题, 出现次数（用于排优先级，自动生成）

用法：
    python3 src/build_sources.py            # 首次生成，保留已填的 URL
    python3 src/build_sources.py --rebuild  # 全量重建（会清空已填 URL，慎用）
"""
import csv
import glob
import os
import re
import sys
from collections import Counter

# 从脚本自身位置推导项目根：写死绝对路径的话，换机器或在 CI 上跑会写到错的地方
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "sources.csv")
REPORT = os.path.join(ROOT, "data", "sources_report.csv")
STATS = os.path.join(ROOT, "data", "sources_stats.json")

# 自动分类规则：按顺序匹配，先命中者生效
TYPE_RULES = [
    ("政府文件", ("人民政府", "教育局", "招考院", "教育厅", "区政府", "市教育局",
                  "招生委员会", "人社局", "市委")),
    ("媒体", ("扬子晚报", "南京日报", "现代快报", "南京晨报", "新华日报", "新华报业",
              "人民网", "荔枝", "交汇点", "紫牛", "中国江苏网", "江苏教育报",
              "江苏教育新闻网", "央视", "光明日报", "中新网", "澎湃")),
    ("学校官方", ("学校官网", "官网", "公众号", "学校官微", "校方", "招生简章",
                  "招生公告", "喜报", "校史", "学校简介", "校刊")),
    ("第三方站", ("本地宝", "入学网", "ruxue", "百度百科", "九考网", "学校大全",
                  "京督学府", "教育黄页", "知乎", "搜狐", "腾讯", "网易", "新浪",
                  "今日头条", "小红书", "bilibili", "抖音")),
    ("家长圈", ("家长圈", "家长分享", "家长会", "群内", "论坛", "整理")),
]


# 泛指出处：本身没有可点开的单一原文，不是「没找到」，而是「不存在单一出处」
GENERIC_TITLES = ("学校官网", "官网", "公众号", "学校官微", "校方", "家长圈公开讨论",
                  "家长圈", "群内讨论", "培训机构汇总", "渠道汇总", "第三方教育平台",
                  "学校大全", "教育黄页")
GENERIC_HINTS = ("家长圈", "群内", "汇总", "整理", "培训机构", "泛指", "等渠道", "多方")


def status_of(title, url, type_name):
    """三种状态：已核实 / 泛指来源 / 未存档。

    「未存档」不等于「没有出处」，而是「有出处但未取到可点开的链接」
    （公众号文章、已下架页面、纸质材料等）。站点据此说明，避免读者误解。
    """
    if url:
        return "已核实"
    if type_name == "家长圈":
        return "泛指来源"
    if title in GENERIC_TITLES or any(h in title for h in GENERIC_HINTS):
        return "泛指来源"
    if type_name == "学校官方" and len(title) <= 6:
        return "泛指来源"
    return "未存档"


def classify(title):
    for name, keys in TYPE_RULES:
        if any(k in title for k in keys):
            return name
    return "待定"


def normalize(t):
    t = re.sub(r"[*`]", "", t)
    t = t.replace("　", " ").strip()
    return t


def collect():
    """从每份档案的「数据来源」章节抽取来源标题。"""
    counter = Counter()
    files = (glob.glob(os.path.join(ROOT, "小学", "**", "*.md"), recursive=True)
             + glob.glob(os.path.join(ROOT, "初中", "**", "*.md"), recursive=True)
             + glob.glob(os.path.join(ROOT, "高中", "**", "*.md"), recursive=True))
    for f in files:
        text = open(f, encoding="utf-8").read()
        m = re.search(r"##[^\n]*数据来源[^\n]*", text)
        if not m:
            continue
        for line in text[m.start():].split("\n"):
            s = line.strip()
            if not s.startswith("|") or re.search(r"\|[-:\s|]+\|\s*$", s):
                continue
            if not re.search(r"\|\s*[ABC]\s*\|\s*$", s):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) < 2:
                continue
            title = normalize(cells[0])
            if title and not set(title) <= set("-: "):
                counter[title] += 1
    return counter


def main():
    rebuild = "--rebuild" in sys.argv
    counter = collect()

    existing = {}
    if os.path.isfile(OUT) and not rebuild:
        for r in csv.DictReader(open(OUT, encoding="utf-8-sig")):
            existing[r["标题"]] = r

    rows = []
    for title, n in counter.most_common():
        old = existing.get(title, {})
        rows.append({
            "标题": title,
            "类型": old.get("类型") or classify(title),
            "URL": old.get("URL", ""),
            "采集日期": old.get("采集日期", ""),
            "备注": old.get("备注", ""),
            "状态": "",
        })
        rows[-1]["状态"] = status_of(title, rows[-1]["URL"], rows[-1]["类型"])

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["标题", "类型", "URL", "采集日期", "状态", "备注"])
        w.writeheader()
        w.writerows(rows)

    with open(REPORT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["标题", "出现次数", "类型", "已有URL"])
        for title, n in counter.most_common():
            w.writerow([title, n, classify(title),
                        "是" if existing.get(title, {}).get("URL") else "否"])

    total = sum(counter.values())
    filled = sum(1 for r in rows if r["URL"])
    covered = sum(counter[r["标题"]] for r in rows if r["URL"])
    print(f"来源标题 {len(rows)} 个，覆盖 {total} 行")
    print(f"  已填 URL：{filled} 个标题，覆盖 {covered} 行（{covered*100//max(total,1)}%）")
    by_type = Counter(r["类型"] for r in rows)
    print("  类型分布：", dict(by_type))
    # 供站点展示的统计
    import json
    from collections import Counter as _C
    by_status = _C(r["状态"] for r in rows)
    stats = {
        "by_status": dict(by_status),
        "rows_by_status": {
            k: sum(counter.get(r["标题"], 0) for r in rows if r["状态"] == k)
            for k in set(r["状态"] for r in rows)
        },
        "titles": len(rows),
        "rows_total": total,
        "rows_with_url": covered,
        "titles_with_url": filled,
        "by_type": dict(by_type),
    }
    # sort_keys：rows_by_status 的键来自 set()，而字符串哈希每进程随机化，
    # 不排序则每次构建都会产生一次纯键序变化的无意义 diff。
    json.dump(stats, open(STATS, "w", encoding="utf-8"), ensure_ascii=False, indent=1,
              sort_keys=True)

    print(f"\n登记表：{OUT}\n优先级报告：{REPORT}\n统计：{STATS}")
    print("\n出现最多的 10 个来源：")
    for title, n in counter.most_common(10):
        print(f"  {n:4d}  [{classify(title)}] {title[:56]}")


if __name__ == "__main__":
    main()
