# -*- coding: utf-8 -*-
"""从既有核验结果引导生成 data/sources.yaml。

为什么不手写：学校源有 188 条，逐条抄既费时又必然抄错。地址的唯一可靠来源是
data/school_websites.json ——那份数据经过 verify_websites.py 的抢注/停更/空模板
判定，是本站最可信的域名清单。

为什么只取 site_state=ok：其它状态（exists_unreachable / stale / none）意味着
地址不可用或内容是别人的，采集器打过去只会得到噪音，还可能把「抢注站」的
内容当成学校公告抓进来。

机构级源（市/区教育局、招考院）不在此自动生成——它们的官网地址没有可机读的
来源，只能人工核实。本脚本只预置条目骨架并标 unverified，地址留空。
**绝不按域名规律猜地址**：README 记的 njgljy.com 那批是学校官网托管平台，
不是区教育局门户，两者混用会把政策抓取指向错误的地方。

用法：
  python3 src/ingest/gen_sources.py            # 预演，只打印统计与样例
  python3 src/ingest/gen_sources.py --apply    # 写入 data/sources.yaml
  python3 src/ingest/gen_sources.py --apply --force   # 覆盖已存在的文件
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import config                     # noqa: E402
from ingest import sourcelist                   # noqa: E402

WEBSITES = os.path.join(config.ROOT, "data", "school_websites.json")
INDEX = os.path.join(config.ROOT, "index.json")

# 机构级源。entry 全部实测可达（2026-11-01），status 一律 verified。
#
# 地址是怎么核实的：以中国教师资格网公布的各区教育局「通知公告发布渠道」
# 与市人社局职称评审文件的「评委会对应网址」两处独立信息为准，两处指向
# 同一批域名才收录，然后逐个实测（含标题确认）。找不到独立教育专网的区，
# 退回区政府门户——招生文件同样在那里发布。
BUREAUS = [
    {
        "id": "bureau:city-edu", "name": "南京市教育局", "entry": "https://edu.nanjing.gov.cn/",
        "note": "施教区、招生政策、电脑派位计划的市级发布口；实测可达",
    },
    {
        "id": "bureau:zkb", "name": "南京教育招生考试院",
        # 无独立官网。2026 年中招投档控制线正是从市教育局「招生考试」栏目抓到的，
        # 所以 entry 指向该栏目，而不是编一个不存在的域名。
        "entry": "https://edu.nanjing.gov.cn/zb/gzzs/",
        "note": "投档控制线、录取进程的发布口；无独立官网，公告经市教育局网站发布",
    },
    {"id": "bureau:01-玄武区", "name": "玄武区教育局", "entry": "http://www.xwzf.gov.cn/",
     "note": "区政府门户（无独立教育专网），招生文件在「教育」栏目"},
    {"id": "bureau:02-秦淮区", "name": "秦淮区教育局", "entry": "http://www.njqhjy.cn/",
     "note": "秦淮教育信息网"},
    {"id": "bureau:03-建邺区", "name": "建邺区教育局", "entry": "https://www.jyjsfz.cn/",
     "note": "南京建邺教育；建邺区官方问答指定的查询网址之一"},
    {"id": "bureau:04-鼓楼区", "name": "鼓楼区教育局", "entry": "http://www.njgl.gov.cn/",
     "note": "区政府门户；招生办法、派位办法、施教区问答均在此发布（已验证）"},
    {"id": "bureau:05-栖霞区", "name": "栖霞区教育局", "entry": "http://www.qxteacher.com/",
     "note": "栖霞教育之家；区政府 www.njqxq.gov.cn 亦有教育栏目，两者实测可达"},
    {"id": "bureau:06-雨花台区", "name": "雨花台区教育局", "entry": "http://www.njyh.gov.cn/",
     "note": "区政府门户（无独立教育专网）"},
    {"id": "bureau:07-江宁区", "name": "江宁区教育局", "entry": "http://www.jnjy.net.cn/",
     "note": "江宁教育服务平台；招生咨询电话附件发布于此"},
    {"id": "bureau:08-江北新区", "name": "江北新区教育局", "entry": "http://www.njnaedu.cn/",
     "note": "南京江北新区教育信息网"},
    {"id": "bureau:09-六合区", "name": "六合区教育局", "entry": "http://www.lhenet.net/",
     "note": "六合教育信息网"},
    {"id": "bureau:10-溧水区", "name": "溧水区教育局", "entry": "http://www.njls.gov.cn/",
     "note": "区政府门户；教育专网 njlsedu.cn 实测 502，改用门户"},
    {"id": "bureau:11-高淳区", "name": "高淳区教育局", "entry": "https://www.gcjy.info/",
     "note": "高淳教育"},
]

HEADER = """\
# 南京学校档案 · 采集源清单
#
# 本文件是采集层（src/ingest）的唯一配置来源，由人工维护。
# 初次由 src/ingest/gen_sources.py 从 data/school_websites.json 引导生成，之后以本文件为准。
#
# 字段：
#   id      唯一标识，前缀 school: / bureau: 必须与 kind 一致
#   kind    school = 学校官网（S2 半结构：公告列表）
#           bureau = 主管部门/招考机构（S1 强结构：PDF 附件与固定表头表格）
#   entry   入口地址。留空表示尚未核实，采集器会跳过
#   tier    抓取档位：T0 政策窗口期每日 / T1 每周 / T2 每日探活 / T3 每学期 / T4 仅手动
#   parser  解析方式：announcement_list / gov_attachment / score_table / manual
#   status  verified = 已核实可用；unverified = 待核，entry 必须留空
#   note    为什么收录、已知的问题
#
# 语法限制（对应 src/ingest/sourcelist.py 的解析器）：
#   只支持「- 开头新条目 + 缩进的 key: value」两层结构；不支持多行值与行内注释。
#   值里含冒号、引号、中文标点时，用双引号包成 JSON 字符串。
#
# 维护纪律：新地址先人工核一遍再填 entry 并改 status；不要按域名规律猜。
# 把「学校官网托管平台」（如 njgljy.com 那批）当成区教育局门户，会抓错地方。

sources:
"""

def load_schools():
    """按 index.json 的顺序取可用学校源，保证与站点的排序一致。"""
    web = json.load(open(WEBSITES, encoding="utf-8"))["schools"]
    index = json.load(open(INDEX, encoding="utf-8"))["schools"]

    rows, skipped = [], 0
    for s in index:
        rec = web.get(s["id"]) or {}
        state = rec.get("site_state") or ("ok" if rec.get("site") else "none")
        if state != "ok" or not rec.get("site"):
            skipped += 1
            continue
        rows.append({
            "id": f"school:{s['id']}",
            "kind": "school",
            "name": s["name"],
            "entry": rec["site"],
            "tier": "T1",
            "parser": "announcement_list",
            "status": "verified",
        })
    return rows, skipped


def render(rows, bureaus):
    out = [HEADER]
    out.append("  # ── 主管部门与招考机构（S1）──\n")
    for b in bureaus:
        out.append(f"  - id: {b['id']}\n")
        out.append("    kind: bureau\n")
        out.append(f"    name: {b['name']}\n")
        out.append(f"    entry: {b['entry']}\n")
        out.append("    tier: T0\n")
        out.append("    parser: gov_attachment\n")
        out.append("    status: verified\n")
        out.append(f"    note: {json.dumps(b['note'], ensure_ascii=False)}\n")
        out.append("\n")

    out.append("  # ── 学校官网（S2）──\n")
    level = None
    for r in rows:
        lv = r["id"].split("-")[0].replace("school:", "")
        if lv != level:
            level = lv
            out.append(f"\n  # {lv}\n")
        out.append(f"  - id: {r['id']}\n")
        out.append("    kind: school\n")
        out.append(f"    name: {r['name']}\n")
        out.append(f"    entry: {r['entry']}\n")
        out.append("    tier: T1\n")
        out.append("    parser: announcement_list\n")
        out.append("    status: verified\n")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写入 data/sources.yaml")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的文件")
    args = ap.parse_args()

    if not os.path.isfile(INDEX):
        print("✗ 缺少 index.json，先跑 python3 src/build_index.py")
        return 1

    rows, skipped = load_schools()
    text = render(rows, BUREAUS)
    items = sourcelist.parse(text)
    problems = sourcelist.validate(items)
    stat = sourcelist.summary(items)

    print(f"学校源 {len(rows)} 条（跳过 {skipped} 条：地址不可用或内容停更）")
    print(f"机构源 {len(BUREAUS)} 条（市 2 + 区 11，均已实测可达）")
    print(f"合计 {stat['total']} 条，可采集 {stat['active']} 条")
    print(f"按类型 {stat['by_kind']}　按档位 {stat['by_tier']}")
    if problems:
        print(f"\n✗ 自检不通过 {len(problems)} 处：")
        for p in problems[:10]:
            print(f"   {p}")
        return 1
    print("✓ 自检通过（字段、枚举、id 前缀与 entry/status 一致性）")

    print("\n样例：")
    print("-" * 60)
    print("\n".join(text.splitlines()[-14:]))
    print("-" * 60)

    if not args.apply:
        print("\n预演结束，未写入。加 --apply 执行。")
        return 0
    if os.path.exists(sourcelist.SOURCES) and not args.force:
        print(f"\n✗ {sourcelist.SOURCES} 已存在。该文件人工维护，不覆盖。"
              f"确需重建请加 --force。")
        return 1
    with open(sourcelist.SOURCES, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"\n已写入 {sourcelist.SOURCES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
