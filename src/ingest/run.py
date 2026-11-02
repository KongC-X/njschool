# -*- coding: utf-8 -*-
"""采集入口：按源清单抓取，报告内容变化的源。

本阶段的边界（P0）：只回答「哪些源的内容变了」，不做字段抽取、不写变更集。
抽取（P1）需要先有稳定的快照与变化判定，否则会拿整页 HTML 当证据。

安全默认：不加 --fetch 就是干跑，只打印计划，一个请求都不发。
这是刻意的——采集脚本最容易被误执行，而对着 189 个站点跑一轮是有外部影响的。

用法：
  python3 src/ingest/run.py                 # 干跑：看计划
  python3 src/ingest/run.py --fetch         # 真抓（默认全部档位）
  python3 src/ingest/run.py --fetch --tier T0 --limit 5   # 先小范围试
  python3 src/ingest/run.py --show-unverified            # 列出待核源

输出约定：抓取结果只进内存与报告，不触碰任何档案文件。
"""
import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest import discover, fetch, sourcelist   # noqa: E402

# 政策窗口期：施教区/派位在 5 月，投档线在 7 月，新校与更名在 10-11 月。
# 其余月份 T0 源降到每周，省额度也省对方带宽。
WINDOW_MONTHS = (4, 5, 6, 7, 10, 11)

# 空壳判定：去掉 script/style 后剩下的可读文本少于此值，说明正文是 JS 渲染的。
# 2084B 的鼓楼平台框架页去标签后只剩 CSS，实测约 0 个正文字符。
SHELL_TEXT_MIN = 200

# 失败率告警阈值：超过两成才判异常（见方案 6.3）。个别学校站改版是常态，
# 不该因为它让整条链路变红——那样人就会习惯性忽略告警。
FAIL_RATE_ALARM = 0.2

# 连接层失败（超时/DNS/SSL，status=0）的占比超过此值，判定为「运行环境连不上」。
# 与 FAIL_RATE_ALARM 分开是因为两者的含义完全不同：一个是站点出事，一个是跑的地方不对。
# 混在一起算的后果很具体——GitHub Actions 是美国 IP，本地 4% 的失败率在那里会顶到 20% 以上，
# 于是每周一准时失败，告警失去意义（2026-11-02 首次定时执行即如此）。
NET_ALARM = 0.5


def plain_text(html):
    """去掉脚本、样式与标签，返回可读文本。用于判断页面是不是空壳。"""
    h = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", h).strip()


def in_window(today=None):
    today = today or time.localtime()
    return today.tm_mon in WINDOW_MONTHS


def select(items, tier="all", kind="all", limit=None, only=None):
    rows = sourcelist.active(items)
    if tier != "all":
        rows = [r for r in rows if r.get("tier") == tier]
    if kind != "all":
        rows = [r for r in rows if r.get("kind") == kind]
    if only:
        rows = [r for r in rows if only in r["id"] or only in r.get("name", "")]
    return rows[:limit] if limit else rows


def report_plan(items, rows, show_unverified):
    stat = sourcelist.summary(items)
    print(f"源清单：{stat['total']} 条（可采集 {stat['active']} / 待核 {stat['unverified']}）")
    print("按类型：" + "　".join(f"{k} {v}" for k, v in sorted(stat["by_kind"].items())))
    print("按档位：" + "　".join(f"{k} {v}" for k, v in sorted(stat["by_tier"].items())))
    print(f"政策窗口期：{'是' if in_window() else '否'}（窗口月份 {WINDOW_MONTHS}）")

    if show_unverified:
        pend = [i for i in items if i.get("status") == "unverified"]
        if pend:
            print(f"\n待核源 {len(pend)} 条（采集器跳过，需人工补地址）：")
            for i in pend:
                print(f"  - {i.get('name')}　{i.get('id')}")

    print(f"\n[干跑] 本次将抓取 {len(rows)} 个源，约 {len(rows)} 次请求")
    by_tier = {}
    for r in rows:
        by_tier[r.get("tier")] = by_tier.get(r.get("tier"), 0) + 1
    for t in sorted(by_tier):
        print(f"  {t}：{by_tier[t]} 个　{sourcelist.TIER_DESC.get(t, '')}")
    print("\n未发起任何请求。加 --fetch 执行。")


def check_source(f, src, rec):
    """检查单个源，返回 (状态, 载荷)。

    状态：
      spa      已知 JS 渲染壳，跳过（不再浪费请求）
      new      有新增公告，载荷为 [(标题, 地址)]
      same     列表页能抽到条目且无新增
      fail     抓取失败，载荷为 Response
      hash     抽不到条目，退化用整页哈希判断（载荷为 Response）
    """
    if rec.get("spa"):
        return "spa", None

    url = rec.get("list_url") or src["entry"]
    res = f.get(url)
    if not res.ok or not res.text:
        return "fail", res

    items = discover.entries(res.text, url)
    if not items:
        return "hash", res

    seen = set(rec.get("titles") or [])
    if not seen:
        return "hash", res          # 首次发现，只建立基线，不算「新增」

    # 只认「列表顶部的连续新增」：从上往下走，遇到一条见过的就停。
    # 两个理由：
    #   1. 公告就是往顶上插的，顶部连续段才是真新增
    #   2. 首页常带轮播，条目顺序会抖动；按集合做差会把 8 条全部报成「新增」，
    #      实测南师附小首页轮播一次就误报 12 条
    fresh = []
    for title, link in items[:discover.KEEP_ITEMS * 2]:
        if title in seen:
            break
        fresh.append((title, link))
        if len(fresh) >= discover.KEEP_ITEMS:
            break
    return ("new" if fresh else "same"), fresh


def classify_failures(failed):
    """把失败按「连接层 / HTTP 层」分成两堆。

    status == 0 表示请求根本没到达站点（超时 / DNS / SSL / 连接被重置）。
    它与「站点返回 404」是两件事：前者取决于**跑在哪**，后者才是站点出事。
    混算会把环境问题报成数据问题——GitHub Actions 是美国 IP，访问 189 所
    国内学校站大量不通，本地实测 4% 的失败率在那里会顶到 20% 以上。
    """
    net = [(s, r) for s, r in failed if not r.status]
    http = [(s, r) for s, r in failed if r.status]
    return net, http


def verdict(net, http, total):
    """根据两类失败占比给退出码与说明。返回 (退出码, 提示语)；提示语空串表示无需多说。

    2 只留给「站点应答了但内容不对」（HTTP 4xx/5xx 占比过高），因为那才是需要人去看的。
    连接层失败占多数时给 0：报告里说明是运行环境网络受限，但不让流水线变红——
    每周准时红的告警等于没有告警。
    """
    total = max(total, 1)
    rate_http = len(http) / total
    rate_net = len(net) / total
    if rate_http > FAIL_RATE_ALARM:
        return 2, (f"✗ 站点异常率 {rate_http:.0%} 超过 {FAIL_RATE_ALARM:.0%}，判为异常"
                   f"（{len(http)} 个源有 HTTP 应答但内容不对）")
    if rate_net > NET_ALARM:
        return 0, (f"⚠ 连接层失败 {rate_net:.0%}（{len(net)} 个源连不上）"
                   f"超过 {NET_ALARM:.0%}，基本可断定是**运行环境的网络**受限，"
                   f"而非站点下线。本轮结果不代表站点状态，请在能直连国内网络的机器上补跑。")
    return 0, ""


def split_dup_groups(dup):
    """把「返回完全相同内容」的源按成因分成两类。

    同一 URL 上挂了多份学段档案（金陵中学河西分校的小学/高中、浦口外国语学校的
    小学部/初中部）时，抓到的内容必然 100% 相同——这是**预期**，不该提示去改配置。
    只有**不同 URL 返回同样内容**，才说明是平台统一框架页（壳站），那才需要处理。

    混在一起报的后果：每周都提示「建议改指公告列表页」，而其中大部分是正常的多学段
    共用一址，改无可改。告警里混进改无可改的项，人就会开始整段跳过。
    """
    same_url, cross_url = [], []
    for h, rs in dup.items():
        entries = {r.get("entry") for r in rs}
        (same_url if len(entries) == 1 else cross_url).append((h, rs))
    return same_url, cross_url


def run(rows, min_interval, apply=False):
    f = fetch.Fetcher(min_interval=min_interval)
    lists = discover.load_lists()
    new_items, same, failed, blocked, shells, volatile, spas = [], [], [], [], [], [], []
    hash_rows = []
    by_hash = {}
    print(f"开始巡检 {len(rows)} 个源（同域限速 {min_interval}s，最多重试 3 次）\n")

    for i, src in enumerate(rows, 1):
        rec = lists.get(src["id"]) or {}
        cached = f.cache.get((rec.get("list_url") or src["entry"])) or {}
        before = cached.get("content_hash", "")
        before_len = cached.get("body_len")
        state, payload = check_source(f, src, rec)
        tag = f"[{i:>3}/{len(rows)}]"
        name = src.get("name", "")[:22]

        if state == "spa":
            spas.append(src)
            print(f"{tag} {name:<24} 跳过（JS 渲染壳）")
        elif state == "fail":
            if payload.error == "circuit_open":
                blocked.append(src)
                print(f"{tag} {name:<24} 熔断跳过")
            else:
                failed.append((src, payload))
                print(f"{tag} {name:<24} 失败 {payload.error}")
        elif state == "new":
            new_items.append((src, payload))
            print(f"{tag} {name:<24} 新增 {len(payload)} 条")
        elif state == "same":
            same.append(src)
            print(f"{tag} {name:<24} 无新增")
        else:
            # 抽不到条目：退回整页哈希，至少能发现「页面被改了」
            res = payload
            n = len(plain_text(res.text))
            by_hash.setdefault(res.content_hash, []).append(src)
            if n < SHELL_TEXT_MIN:
                shells.append((src, res, n))
                print(f"{tag} {name:<24} {res.status} 空壳（正文 {n} 字）")
            elif before and before == res.content_hash:
                same.append(src)
                print(f"{tag} {name:<24} {res.status} 内容相同")
            elif before and before_len and before_len == len(res.body):
                volatile.append((src, res, before_len))
                print(f"{tag} {name:<24} {res.status} 疑似动态（等长 {before_len}B）")
            else:
                hash_rows.append((src, res, "首次" if not before else "有变化"))
                print(f"{tag} {name:<24} {res.status} {hash_rows[-1][2]} {len(res.body)}B")

    f.flush()
    n_net = sum(1 for _s, r in failed if not r.status)
    n_http = len(failed) - n_net
    print(f"\n汇总：新增公告 {len(new_items)} 源 / 无新增 {len(same)} / "
          f"整页变化 {len(hash_rows)} / 空壳 {len(shells)} / 动态 {len(volatile)} / "
          f"失败 {len(failed)}（连接 {n_net} / HTTP {n_http}）/ "
          f"熔断 {len(blocked)} / SPA 跳过 {len(spas)}")

    dup = {h: rs for h, rs in by_hash.items() if len(rs) > 1}
    if dup:
        same_url, cross_url = split_dup_groups(dup)
        if same_url:
            n = sum(len(v) for _h, v in same_url)
            print(f"\n· {len(same_url)} 组多学段档案共用同一站点（共 {n} 个源），内容必然相同，属预期：")
            for _h, rs in same_url[:5]:
                print(f"  · {rs[0].get('entry')}　" + "、".join(x.get("name", "") for x in rs))
        if cross_url:
            n = sum(len(v) for _h, v in cross_url)
            print(f"\n⚠ {len(cross_url)} 组**不同站点**返回完全相同的内容（共 {n} 个源）：")
            for h, rs in sorted(cross_url, key=lambda kv: -len(kv[1]))[:5]:
                names = "、".join(x.get("name", "") for x in rs[:4])
                print(f"  · {len(rs)} 个源同内容（{h}）：{names}{'…' if len(rs) > 4 else ''}")
            print("  通常意味着这些站是平台统一框架页，建议改指公告列表页或标 parser: manual。")

    if new_items:
        print("\n新增公告（待人工核实后写入档案）：")
        for src, fresh in new_items:
            print(f"  · {src.get('name')}")
            for title, url in fresh[:3]:
                print(f"      {title[:44]}　{url[:60]}")

    if hash_rows:
        print("\n整页有变化的源（无可用条目列表，仅提示）：")
        for src, res, why in hash_rows:
            print(f"  · {src.get('name')}　{why}　{res.url}")
    if volatile:
        print("\n疑似动态内容的源（整页比对不适用）：")
        for src, res, ln in volatile:
            print(f"  · {src.get('name')}　每轮 {ln}B 不变但内容变")
    if failed:
        print("\n抓取失败：")
        for src, res in failed:
            print(f"  · {src.get('name')}　{res.status or '-'}　{str(res.error)[:70]}")

    if apply and new_items:
        for src, fresh in new_items:
            rec = lists.setdefault(src["id"], {})
            old = list(rec.get("titles") or [])
            rec["titles"] = ([t for t, _ in fresh] + old)[:discover.KEEP_ITEMS]
        discover.save_lists(lists)
        print(f"\n已更新 {discover.LISTS_FILE} 的条目基线")

    # 局部失败不阻塞：个别学校站改版是常态，不该因此让整条链路变红。
    # 分类与判定见 classify_failures / verdict——两者都是纯函数，有单测覆盖。
    net_failed, http_failed = classify_failures(failed)
    rc, msg = verdict(net_failed, http_failed, len(rows))
    if msg:
        print("\n" + msg)
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="真正发起请求（默认只干跑）")
    ap.add_argument("--tier", default="all", choices=("all",) + sourcelist.TIERS)
    ap.add_argument("--kind", default="all", choices=("all",) + sourcelist.KINDS)
    ap.add_argument("--limit", type=int, default=None, help="只处理前 N 个源（试跑）")
    ap.add_argument("--interval", type=float, default=1.0, help="同域最小请求间隔（秒）")
    ap.add_argument("--show-unverified", action="store_true", help="列出待核源")
    ap.add_argument("--only", default=None, help="只处理 id 或校名含该串的源")
    ap.add_argument("--apply", action="store_true",
                    help="把本次新增的条目标题写回 data/source_lists.json 作基线")
    args = ap.parse_args()

    items = sourcelist.load()
    if not items:
        print("✗ 未找到 data/sources.yaml，先跑 src/ingest/gen_sources.py --apply")
        return 1

    problems = sourcelist.validate(items)
    if problems:
        print(f"✗ 源清单校验不通过 {len(problems)} 处：")
        for p in problems[:15]:
            print(f"   {p}")
        return 1

    rows = select(items, args.tier, args.kind, args.limit, args.only)
    if not args.fetch:
        report_plan(items, rows, args.show_unverified)
        return 0
    return run(rows, args.interval, args.apply)


if __name__ == "__main__":
    sys.exit(main())
