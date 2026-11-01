# -*- coding: utf-8 -*-
"""公告列表页发现与条目抽取。

为什么必须有这一步：实测 188 个学校源里，首页能直接读出公告的只是一部分。
北京东路小学首页 0 条可用链接（整页图片导航），而它「通知公告」指向的列表页
有 9 条带日期的公告；鼓楼 *.njgljy.com 那批更是所有学校共用一个 2084B 框架页。
只抓首页，等于对自己说「本周没有更新」。

两级策略，原则是「能用首页就不多打一次请求」：
  1. 首页就能抽到 ≥ MIN_ENTRIES 条 → 首页即列表页（很多区级平台就是这样）
  2. 否则从首页导航里找关键词链接（通知/公告/新闻…），逐个验证条目数，选最多的

抽条目的判据刻意简单：标题长度 8–80 字、同域、排除导航词。
不引入正文分页特征、不做 DOM 结构学习——学校站模板几十种，学不完，
而「标题够长 + 是站内链接」已经足以把公告和导航分开（实测两个样板站准确）。

发现结果写 data/source_lists.json，与 data/sources.yaml 分开：
  sources.yaml 是「抓哪些源」（人工配置）
  source_lists.json 是「该源的列表页在哪、上次看到什么」（机器产出，可重建）
混在一起会让自动发现去改人工配置，两者互相踩。
"""
import html as htmllib
import json
import os
import re
import sys
import time
from urllib.parse import urljoin, urlsplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest import fetch, sourcelist            # noqa: E402
from pipeline import config                     # noqa: E402

LISTS_FILE = os.path.join(config.ROOT, "data", "source_lists.json")

# 导航关键词，按「越像公告越靠前」排序，用于给候选排序
KEYWORDS = ("通知", "公告", "公示", "新闻", "动态", "要闻", "招生", "信息")
# 这些不是公告条目，是翻页与入口
NAV_WORDS = {"更多", "查看更多", "首页", "上一页", "下一页", "返回", "尾页",
             "末页", "more", "登录", "注册", "English"}
# 面包屑分隔符：北京东路的列表页顶部有一条「首页>> 通知公告」，
# 9 个字刚好越过 8 字门槛，会被当成公告标题写进基线。
BREADCRUMB = (">>", "»", "›", "|", "｜")
# 关键词命中的链接标题不该太长：超过这个长度基本是公告正文标题，不是栏目名。
# 实测栏目名集中在 2–6 字（通知公告 / 校园新闻 / 公示公告 / 招生信息），
# 放到 24 会把 19 字的公告标题也当成栏目入口，白抓一次还选错。
NAV_TITLE_MAX = 12

MIN_ENTRIES = 3          # 首页达到这个数就不再去翻列表页
LIST_MIN_ENTRIES = 3     # 候选页至少要有这么多条才算合格
GOOD_ENOUGH = 8          # 找到这么多条就停止验证后续候选，省请求
KEEP_ITEMS = 8           # 每个源保留最近几条标题，用于比对「新增了什么」

RE_A = re.compile(r'<a\b[^>]*href=["\']([^"\'#][^"\']*)["\'][^>]*>(.*?)</a>', re.S | re.I)


def _clean(raw):
    # 先解 HTML 实体再收空格：面包屑常写成 `首页&gt;&gt; 通知公告`，
    # 不解码就认不出 ">>"，那条会被当成公告标题存进基线。
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", text).strip()


def links(html, base):
    """抽同域链接 [(标题, 绝对地址)]。跨域链接一律丢弃——那多半是友链或统计代码。"""
    host = urlsplit(base).netloc
    out = []
    for m in RE_A.finditer(html):
        href = m.group(1).strip()
        if href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        url = urljoin(base, href)
        if urlsplit(url).netloc != host:
            continue
        out.append((_clean(m.group(2)), url))
    return out


def entries(html, base, min_title=8, max_title=80):
    """抽公告条目 [(标题, 地址)]，去重保序。

    标题门槛 8 字是有依据的：「通知公告」「校园新闻」这类导航 4 个字，
    而公告标题极少短于 8 字（「中标公示」算短的了，通常还带项目名）。
    """
    seen = set()
    out = []
    for title, url in links(html, base):
        if not (min_title <= len(title) <= max_title):
            continue
        if title in NAV_WORDS:
            continue
        # 面包屑「首页>> 通知公告」字数够长但语义是导航，留着会污染基线
        if any(sep in title for sep in BREADCRUMB):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append((title, url))
    return out


def list_candidates(html, base, limit=3):
    """从首页链接里挑疑似公告栏目的地址，按关键词优先级排序。"""
    scored = []
    seen = set()
    for title, url in links(html, base):
        if url.rstrip("/") == base.rstrip("/") or url in seen:
            continue
        if len(title) > NAV_TITLE_MAX:
            continue
        for i, kw in enumerate(KEYWORDS):
            if kw in title:
                seen.add(url)
                # 关键词越靠前、标题越短，越可能是栏目入口
                scored.append((i, len(title), title, url))
                break
    scored.sort()
    return [(t, u) for _, _, t, u in scored[:limit]]


def discover(src, fetcher):
    """发现一个源的列表页，返回记录 dict（含 ok / list_url / items）。"""
    entry = src["entry"]
    res = fetcher.get(entry)
    if not res.ok:
        return {"ok": False, "reason": f"入口不可达：{res.error}"}
    if not res.text:
        # 304 且快照缺失：没有正文就没法抽条目，如实记录，别装作「没有更新」
        return {"ok": False, "reason": "入口无正文（304 且无快照）"}

    home = entries(res.text, entry)
    if len(home) >= MIN_ENTRIES:
        return {"ok": True, "via": "homepage", "list_url": entry, "items": home}

    best = None
    for title, url in list_candidates(res.text, entry):
        rr = fetcher.get(url)
        if not rr.text:
            continue
        got = entries(rr.text, url)
        if len(got) >= LIST_MIN_ENTRIES and (best is None or len(got) > len(best["items"])):
            best = {"ok": True, "via": f"栏目「{title}」", "list_url": url, "items": got}
        if best and len(best["items"]) >= GOOD_ENOUGH:
            break

    if best:
        return best

    # 判「是不是 JS 渲染壳」：正文很小且一条站内链接都没有。
    # 实测两类：鼓楼 *.njgljy.com 的 2084B 框架页、万网建站产品输出的 630B 壳
    # （内容全在 img.wanwang.xin 的 JS 里）。这类源 HTTP 抓取永远拿不到内容，
    # 标出来让它们从采集队列里消失，比每周重试一次更诚实。
    shell = len(res.body) < 3000 and not links(res.text, entry)
    return {"ok": False, "spa": shell,
            "reason": ("JS 渲染壳，HTTP 抓不到内容" if shell
                       else f"首页仅 {len(home)} 条，未找到可用栏目页")}


def load_lists():
    if not os.path.isfile(LISTS_FILE):
        return {}
    try:
        with open(LISTS_FILE, encoding="utf-8") as f:
            return json.load(f).get("lists", {})
    except (ValueError, OSError):
        return {}


def save_lists(lists):
    payload = {
        "note": "由 src/ingest/discover.py 生成，勿手工编辑。记录每个源的列表页地址"
                "与最近条目，用于判断「有没有新公告」。删除本文件即可全量重新发现。",
        "updated": time.strftime("%Y-%m-%d", time.localtime()),
        "lists": {k: lists[k] for k in sorted(lists)},
    }
    os.makedirs(os.path.dirname(LISTS_FILE), exist_ok=True)
    with open(LISTS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)


def record(src, found):
    """把一次发现压缩成可长期保存的记录。

    只留最近 KEEP_ITEMS 条的标题，不留 URL：188 个源各存 8 条地址会让文件
    涨到几百 KB，而报告里「新增了什么」给标题就够用，地址用户自己点进去找。
    """
    titles = [t for t, _ in found.get("items", [])][:KEEP_ITEMS]
    return {
        "ok": bool(found.get("ok")),
        # spa=True 表示「这个站 HTTP 抓不到内容」，后续轮次直接跳过，
        # 否则每周都要对同一批壳站重试一次，既浪费也是骚扰。
        "spa": bool(found.get("spa")),
        "list_url": found.get("list_url", ""),
        "via": found.get("via", ""),
        "reason": found.get("reason", ""),
        "titles": titles,
        "checked_at": time.strftime("%Y-%m-%d", time.localtime()),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="发现学校站的公告列表页。默认会联网抓取但不写文件，加 --apply 才保存。")
    ap.add_argument("--apply", action="store_true", help="写入 data/source_lists.json")
    ap.add_argument("--refresh", action="store_true", help="重新发现已有记录的源")
    ap.add_argument("--limit", type=int, default=None, help="只处理前 N 个源")
    ap.add_argument("--only", default=None, help="只处理 id 包含该串的源")
    ap.add_argument("--interval", type=float, default=1.0, help="同域最小请求间隔（秒）")
    args = ap.parse_args()

    items = sourcelist.load()
    if not items:
        print("✗ 未找到 data/sources.yaml")
        return 1
    problems = sourcelist.validate(items)
    if problems:
        print(f"✗ 源清单校验不通过 {len(problems)} 处：")
        for p in problems[:10]:
            print(f"   {p}")
        return 1

    lists = load_lists()
    todo = [i for i in sourcelist.active(items) if i["kind"] == "school"]
    if args.only:
        todo = [i for i in todo if args.only in i["id"]]
    if not args.refresh:
        todo = [i for i in todo if i["id"] not in lists]
    if args.limit:
        todo = todo[:args.limit]

    if not todo:
        print(f"没有待发现的源（已有记录 {len(lists)} 条，加 --refresh 可全部重做）")
        return 0

    f = fetch.Fetcher(min_interval=args.interval)
    ok = fail = spa = 0
    print(f"待发现 {len(todo)} 个源\n")
    for i, src in enumerate(todo, 1):
        found = discover(src, f)
        rec = record(src, found)
        lists[src["id"]] = rec
        tag = f"[{i:>3}/{len(todo)}]"
        if rec["ok"]:
            ok += 1
            print(f"{tag} {src['name'][:22]:<24} {len(rec['titles']):>2} 条 "
                  f"via {rec['via'][:16]:<18} {rec['list_url'][:48]}")
        else:
            fail += 1
            spa += 1 if rec["spa"] else 0
            kind = "SPA" if rec["spa"] else "未找到"
            print(f"{tag} {src['name'][:22]:<24} ✗ {kind}　{rec['reason']}")

    f.flush()
    print(f"\n汇总：成功 {ok} / 失败 {fail}（其中 SPA 壳 {spa}）　"
          f"请求 {f.stats['requests']} 次")
    if args.apply:
        save_lists(lists)
        print(f"已写入 {LISTS_FILE}（{len(lists)} 条记录）")
    else:
        print("\n未写入。加 --apply 保存结果。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

