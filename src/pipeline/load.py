# -*- coding: utf-8 -*-
"""内容读取：把 index.json、档案正文、官网数据、内容页装配成结构化对象。

原则：只读不写。所有写操作在 render / main 完成，便于单独测试本层。
"""
import glob
import json
import os
import re
from urllib.parse import quote

from . import config, mdtext, source
from .schema import School, Website


def read_text(path):
    """读任意 UTF-8 文本文件。统一用 with，避免依赖 GC 回收句柄。"""
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_index():
    with open(config.INDEX, encoding="utf-8") as f:
        return json.load(f)


def _derive_web_counts(records):
    """从逐校记录现算官网统计，不读文件里的 counts 缓存。

    为什么要现算：counts 是半自动维护的——只有联网跑的 merge_websites.py
    会重算它，后续 add_websites_* 补录脚本一个都不更新，于是它冻结在某天。
    实测曾与记录差 35 所：about 页写「153 所（28%）有可用官网」，
    而 545 条记录里 site 非空且 state=ok 的是 188 所（34.5%）。
    这个站的立身之本是数据诚实，公开页面上一个 json.load 就能推翻的数字
    比漏一百个字段更伤——而且它把自家覆盖率低报了 35 所。
    """
    state = {}
    for r in records.values():
        st = r.get("site_state") or ("ok" if r.get("site") else "none")
        state[st] = state.get(st, 0) + 1
    with_site = sum(1 for r in records.values()
                    if r.get("site") and (r.get("site_state") or "ok") == "ok")
    return {"total": len(records), "with_site": with_site, "site_state": state}


def load_websites():
    """官网核查结果。缺失时不阻断构建，退化为空记录。

    返回 (逐校记录, 核验日期, 现算统计, 文件里的 counts 缓存)。
    第四项只用于校验缓存是否过期，不参与渲染。
    """
    if not os.path.isfile(config.WEBFILE):
        return {}, "", {}, {}
    with open(config.WEBFILE, encoding="utf-8") as f:
        payload = json.load(f)
    records = payload.get("schools", {})
    return (records,
            payload.get("verified") or payload.get("updated") or "",
            _derive_web_counts(records),
            payload.get("counts", {}))


def count_md_files():
    n = 0
    for lv in config.LEVELS:
        n += len(glob.glob(os.path.join(config.ROOT, lv, "**", "*.md"), recursive=True))
    return n


def _to_website(rec):
    return Website(
        site=rec.get("site"),
        site_archived=rec.get("site_archived"),
        site_state=rec.get("site_state") or ("ok" if rec.get("site") else "none"),
        null_reason=rec.get("null_reason"),
        repair=rec.get("repair"),
        wechat=rec.get("wechat"),
        wechat_status=rec.get("wechat_status") or "unknown",
        verify=rec.get("verify"),
        basis=rec.get("basis") or "",
        level=rec.get("level") or "C",
    )


def load_schools(index, webmap):
    """索引条目 → School 对象，并挂上官网记录与档案正文。"""
    schools = []
    for raw in index["schools"]:
        w = _to_website(webmap.get(raw["id"], {}))
        schools.append(School(
            id=raw["id"],
            name=raw["name"],
            district=raw["district"],
            level=raw["level"],
            type=raw["type"],
            file=raw["file"],
            tier=raw.get("tier") or "",
            tagline=raw.get("tagline") or "",
            short=raw.get("short") or "",
            url=f"schools/{quote(raw['level'] + '-' + raw['name'])}.html",
            website=w,
        ))
    return schools


SOURCES = os.path.join(config.ROOT, "data", "sources.csv")


def load_source_links():
    """来源标题 → URL（仅取已填 URL 的条目）。"""
    if not os.path.isfile(SOURCES):
        return {}
    import csv
    links = {}
    for r in csv.DictReader(open(SOURCES, encoding="utf-8-sig")):
        url = (r.get("URL") or "").strip()
        if url.startswith("http"):
            links[r["标题"].strip()] = url
    return links


def load_body(school, links=None):
    """读取并渲染档案正文，返回 (html, toc)。"""
    html, toc = mdtext.render(mdtext.strip_leading_h1(source.text(school.file)), links=links)
    return _thin_quickfacts(html, school), toc


# 页头已经用 h1 + 徽章展示过的字段
_RE_TR = re.compile(r"<tr>(.*?)</tr>", re.S)
_RE_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_RE_TAG = re.compile(r"<[^>]+>")


def _plain(cell):
    return _RE_TAG.sub("", cell).strip()


def _thin_quickfacts(html, school):
    """去掉「一、学校速览」里与页头完全重复的行。

    页头已经有 h1（校名）+ 学段/性质/行政区/简称 四个徽章，
    速览表里的「学校全称/简称/所在区/办学性质」再看一遍纯属重复——
    用户滚过一屏才发现这几行没有新信息。

    只在**值完全相同**时才删。「所在区」写成「雨花台区（岱山片区东侧）」
    就带着片区增量，必须保留；「办学性质」写成「公办（区属）」同理。
    """
    exact = {
        "学校全称": school.name,
        "简称": school.short,
        "所在区": school.district,
        "办学性质": school.type,
    }

    def repl(m):
        cells = _RE_TD.findall(m.group(1))
        if len(cells) < 2:
            return m.group(0)                      # 表头行等，原样保留
        label, value = _plain(cells[0]), _plain(cells[1])
        if label in exact and exact[label] and value == exact[label]:
            return ""
        return m.group(0)

    return _RE_TR.sub(repl, html)


def load_pages():
    """读取 content/pages/*.md，返回 {key: {title, summary, updated, html}}。

    支持的 front-matter 为极简 key: value 形式，不引入额外依赖。
    """
    pages = {}
    if not os.path.isdir(config.CONTENT_PAGES):
        return pages
    for path in sorted(glob.glob(os.path.join(config.CONTENT_PAGES, "*.md"))):
        key = os.path.splitext(os.path.basename(path))[0]
        text = read_text(path)
        meta, body = _split_front_matter(text)
        html, _ = mdtext.render(body)
        pages[key] = {
            "key": key,
            "title": meta.get("title", ""),
            "summary": meta.get("summary", ""),
            "updated": meta.get("updated", ""),
            "html": html,
        }
    return pages


def _split_front_matter(text):
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, parts[2].lstrip("\n")
