# -*- coding: utf-8 -*-
"""收录对账：把「官方应收名单」与库内档案做差集。

用法：
    python3 src/reconcile.py                     # 检查 data/expected_*.csv 全部
    python3 src/reconcile.py data/expected_qixia.csv

输入 CSV 需含列：区、学段、学校、施教区原文、来源、采集日期、库内状态
比对规则：按「学段/区/校名.md」判断是否存在；校区名与主校名不一致时以正式校名为准。

输出：
    控制台摘要（应收 / 实收 / 缺 / 多收）
    data/coverage_report.csv（逐校状态，便于分派任务）
"""
import csv
import glob
import os
import sys

# 从脚本自身位置推导项目根：写死绝对路径的话，换机器或在 CI 上跑会写到错的地方
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "coverage_report.csv")

# 17 份应收清单的列名各不相同（有的叫校名、有的叫名录名称、有的连区列都没有），
# 而旧版 check_file 写死读 r["区"]/r["学段"]/r["学校"]，除栖霞那份外全部 KeyError——
# 也就是说这个对账工具一直是坏的，覆盖率从来没人算过。
# 这里改成「先按列名取，取不到再从文件名推断」：文件名规律是 expected_{区}_{学段}.csv。
DISTRICT_BY_SLUG = {
    "jiangning": "江宁区", "gaochun": "高淳区", "luhe": "六合区",
    "jiangbei": "江北新区", "qixia": "栖霞区", "xuanwu": "玄武区",
    "jianye": "建邺区", "lishui": "溧水区", "yuhuatai": "雨花台区",
    "gulou": "鼓楼区",
}
LEVEL_BY_SLUG = {"primary": "小学", "junior": "初中"}

# 应收清单用的是 2017 年区划调整前的旧口径（「原江北新区」「原浦口区」），
# 而档案目录统一按现行区划归到「江北新区」。不归一化的话，
# 65 所学校会被算成「缺档」——实测缺口 69 里有 65 个都是这个原因。
DISTRICT_ALIAS = {
    "原江北新区": "江北新区",
    "原浦口区": "江北新区",
    "浦口区": "江北新区",
    "原下关区": "鼓楼区",
    "下关区": "鼓楼区",
}

# 清单写法与档案全称不一致的，逐条列出。宁可写死也不要放宽成模糊匹配：
# 模糊匹配会把「XX 小学」和「XX 小学某分校」混为一谈，那类错误在覆盖率报表里
# 看不出来，却会让真正缺的学校被算成已收。
NAME_ALIAS = {
    "南京江北新区浦口实验小学": "南京市浦口实验小学",
}

# 这几类不在中小学档案范围内，不该算进覆盖率缺口
SKIP_WORDS = ("特殊教育", "特教", "盲校", "聋校", "工读")
# 出现在「库内状态」里即表示该条目已由别的档案承接，不需要独立建档
RESOLVED_WORDS = ("并入", "停招", "代招", "合并", "更名")

# 校名列的候选名，按可靠性排序：「档案全称」是已人工确认过的映射，最优先
NAME_COLS = ("档案全称", "学校", "校名", "名录名称", "学校名称")


def pick(row, *names):
    for n in names:
        v = (row.get(n) or "").strip()
        if v:
            return v
    return ""


def level_of(text):
    for lv in ("小学", "初中", "高中"):
        if lv in text:
            return lv
    return ""


def from_filename(path):
    """从 expected_{区}_{学段}.csv 推断区与学段。"""
    slug = os.path.basename(path)
    slug = slug[len("expected_"):].rsplit(".", 1)[0] if slug.startswith("expected_") else slug
    district = next((v for k, v in DISTRICT_BY_SLUG.items() if k in slug), "")
    level = next((v for k, v in LEVEL_BY_SLUG.items() if k in slug), "")
    return district, level


def school_path(region, level, name):
    return os.path.join(ROOT, level, region, f"{name}.md")


def check_file(path):
    """批量核对一个应收清单，返回 rows。"""
    fn_district, fn_level = from_filename(path)
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            district = pick(r, "区", "片区") or fn_district
            district = DISTRICT_ALIAS.get(district, district)
            level = pick(r, "学段") or level_of(pick(r, "类别")) or fn_level
            name = pick(r, *NAME_COLS)
            name = NAME_ALIAS.get(name, name)
            if not (district and level and name):
                continue

            note = r.get("库内状态") or ""
            if any(w in name for w in SKIP_WORDS):
                # 特殊教育学校不在中小学档案范围，但要在报告里单列，
                # 否则「覆盖率」这个数字会永远差几个，没人知道差的是什么
                rows.append({"区": district, "学段": level, "学校": name,
                             "状态": "不收录", "档案路径": ""})
                continue

            fp = school_path(district, level, name)
            exists = os.path.isfile(fp)
            # 「并入」表示该条目是同法人校区，已写在母体档案内，不需要独立档案；
            # 「停招/代招」同理——学校已不独立存在，硬建档案反而是错的
            merged = any(w in note for w in RESOLVED_WORDS)
            state = "已有" if exists else ("并入" if merged else "缺")
            rows.append({
                "区": district, "学段": level, "学校": name,
                "状态": state,
                "档案路径": os.path.relpath(fp, ROOT) if exists
                            else (note if merged else ""),
            })
    return rows


def main():
    targets = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, "data", "expected_*.csv")))
    if not targets:
        print("没有找到 data/expected_*.csv")
        return 1

    all_rows = []
    for t in targets:
        rows = check_file(t)
        all_rows.extend(rows)
        total = len(rows)
        have = sum(1 for r in rows if r["状态"] in ("已有", "并入"))
        skip = sum(1 for r in rows if r["状态"] == "不收录")
        miss = total - have - skip
        print(f"\n{t.replace(ROOT + '/', '')}")
        print(f"  应收 {total - skip} 所 | 已有 {have} | 缺 {miss}"
              + (f"　（另 {skip} 所特教类不收录）" if skip else ""))
        for r in rows:
            if r["状态"] == "缺":
                print(f"    ✗ {r['学段']} {r['学校']}")

    # 写出逐校状态，便于分派任务
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["区", "学段", "学校", "状态", "档案路径"])
        w.writeheader()
        w.writerows(all_rows)

    total = len(all_rows)
    have = sum(1 for r in all_rows if r["状态"] in ("已有", "并入"))
    skip = sum(1 for r in all_rows if r["状态"] == "不收录")
    print(f"\n合计：应收 {total - skip} / 已有 {have} / 缺 {total - have - skip}"
          + (f"　（另 {skip} 所特教类不收录）" if skip else ""))
    print(f"逐校状态已写入 {OUT}")
    return 0 if have == total - skip else 1


if __name__ == "__main__":
    sys.exit(main())
