# -*- coding: utf-8 -*-
"""呈现层：模板装配。

只负责「把数据放进模板」，不做数据校验（校验在 schema）也不写文件（写盘在 main）。
这样模板可以单独渲染预览，测试时无需触碰文件系统。
"""
import json
import os
import re
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import aliases, config, facts, load

NAV = [
    ("index.html", "首页", "home"),
    ("schools.html", "学校库", "schools"),
    ("compare.html", "对比", "compare"),
    ("policy.html", "政策", "policy"),
    ("about.html", "数据说明", "about"),
]


def make_env():
    env = Environment(
        loader=FileSystemLoader(config.TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["host"] = host_of
    env.globals["today"] = config.TODAY
    return env


def host_of(url):
    """从 URL 取主机名，用于「原域名 xxx」的展示。"""
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1) if m else ""


def canonical(path=""):
    """绝对地址；未配置 BASE_URL 时返回空（模板据此省略 canonical）。"""
    if not config.BASE_URL:
        return ""
    return f"{config.BASE_URL}/{path}" if path else f"{config.BASE_URL}/"


def nav():
    return [{"href": h, "label": l, "key": k} for h, l, k in NAV]


def home(env, schools, districts, pages, web_counts):
    by_key = {}
    for s in schools:
        by_key[(s.level, s.district)] = by_key.get((s.level, s.district), 0) + 1

    stats = [
        ("收录学校", f"{len(schools)} 所"),
        ("覆盖行政区", f"{len(districts)} 个"),
        ("小学", f"{sum(1 for s in schools if s.level == '小学')} 所"),
        ("初中", f"{sum(1 for s in schools if s.level == '初中')} 所"),
        ("高中", f"{sum(1 for s in schools if s.level == '高中')} 所"),
    ]
    level_cards = [{
        "level": lv,
        "count": sum(1 for s in schools if s.level == lv),
        "desc": config.LEVEL_DESC[lv].split("，")[0],
    } for lv in config.LEVELS]

    district_cards = []
    for d in districts:
        total = sum(by_key.get((lv, d), 0) for lv in config.LEVELS)
        detail = " · ".join(f"{lv} {by_key.get((lv, d), 0)}"
                            for lv in config.LEVELS if by_key.get((lv, d)))
        district_cards.append({"name": d, "total": total, "detail": detail})

    return env.get_template("home.html").render(
        base="", active="home", nav=nav(), title="首页",
        desc=f"南京 {len(schools)} 所中小学公开信息汇编：施教区、招生、投档线，逐条标注信度。",
        canonical=canonical(), total=len(schools), stats=stats,
        level_cards=level_cards, district_cards=district_cards, pages=pages,
        districts=districts,
    )


# 列表页数据列顺序（前端按此顺序解包）。用数组而非对象：545 条记录下可省约 30KB。
LIST_COLS = ("name", "short", "district", "level", "type", "tier", "tagline")


def _md_text(school, _cache={}):
    """读档案原文并缓存。

    对比页要的 facts 与「已声明缺口」都来自同一份 md，两次构建期扫描会各读一遍
    545 个文件；这里按路径缓存，一次构建内只读一次。
    """
    path = os.path.join(config.ROOT, school.file)
    if path not in _cache:
        _cache[path] = open(path, encoding="utf-8").read()
    return _cache[path]


def missing_data(schools):
    """生成 assets/facts-missing.js。

    对比表的「未获取」与「—」必须分得开：
      - 未获取 = 该校档案的「数据缺口」小节**明确点名**过这一项
      - —      = 本站没抽到，不代表学校没有
    把两者混成一个符号，就是在替学校下结论，违反「不臆造」。
    数据量很小（每校最多 7 个字符），但 schools-data.js 只剩 2KB 余量，
    所以单独成一个只有对比页加载的小文件。
    """
    fields = list(facts.FACT_LABELS.keys())
    rows = []
    for s in schools:
        miss = facts.extract_missing(_md_text(s))
        rows.append("".join(str(fields.index(f)) for f in fields if f in miss))
    payload = {"fields": fields, "rows": rows}
    return "window.__FACTS_MISSING__ = " + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")) + ";\n"


def schools_data(schools, districts):
    """生成 assets/schools-data.js。

    外置为 JS 资产而不是内联在 HTML 里：
      - 学校库与对比页共用同一份数据，浏览器只下载一次；
      - HTML 从 50KB 降到几 KB；
      - <script src> 不受 file:// 的 fetch 限制，双击打开仍可用。

    aliases 列单独放最后：搜索命中「拉力琅」「秦淮外校」这类俗称靠它，
    但 tagline 不进搜索索引（叙述性长文本，是误命中的唯一来源）。
    """
    alias = aliases.build(schools)
    rows = []
    for s in schools:
        text = open(os.path.join(config.ROOT, s.file), encoding="utf-8").read()
        f = facts.extract(text)
        rows.append([s.name, s.short, s.district, s.level, s.type, s.tier,
                     s.tagline, f or None, 1 if s.website.site else 0,
                     alias.get(s.id, "")])
    payload = {
        "cols": list(LIST_COLS) + ["facts", "hasSite", "aliases"],
        "rows": rows,
        "districts": districts,
        "factLabels": facts.FACT_LABELS,
    }
    return "window.__SCHOOLS__ = " + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")) + ";\n"


def schools_page(env, schools, districts):
    return env.get_template("schools.html").render(
        base="", active="schools", nav=nav(), title="学校库",
        desc=f"南京 {len(schools)} 所中小学检索：支持多关键词、按学段/行政区/性质筛选。",
        canonical=canonical("schools.html"), total=len(schools),
    )


def root_prefix():
    """站点根路径前缀。

    404 页会在任意深层路径下被返回，相对路径会解析到那个不存在的位置，
    因此 404 必须用「从站点根算起」的绝对路径。未配置基址（本地 file://）时返回空串。
    """
    if not config.BASE_URL:
        return ""
    path = urlparse(config.BASE_URL).path.rstrip("/")
    return f"{path}/" if path else "/"


def doc(env, pages, key, title=None, desc=None, eyebrow=None):
    """通用内容页：更新日志等由 content/pages 驱动的静态页。"""
    if key not in pages:
        raise SystemExit(f"缺少内容页：content/pages/{key}.md")
    page = pages[key]
    return env.get_template("doc.html").render(
        base="", active="", nav=nav(),
        title=title or page["title"],
        desc=desc or page["summary"],
        canonical=canonical(f"{key}.html"),
        html=page["html"], updated=page["updated"], eyebrow=eyebrow,
    )


def not_found(env):
    return env.get_template("404.html").render(
        base=root_prefix(), active="", nav=nav(), title="页面不存在",
        desc="页面不存在：可回到学校库重新查找，或查看政策与更名对照。",
    )


COMPARE_ROWS = os.path.join(config.ROOT, "data", "compare_rows.json")


def compare(env, schools):
    """对比页。

    行定义外置在 data/compare_rows.json：加一行 = 加一条数据，
    前端 compare-core.js 不用改（渲染层只认 group / source / diff 三个字段）。
    """
    with open(COMPARE_ROWS, encoding="utf-8") as f:
        row_specs = json.load(f)
    return env.get_template("compare.html").render(
        base="", active="compare", nav=nav(), title="对比",
        desc="自选 2–4 所学校并排对比：性质、梯队、关键数据与官方渠道。",
        canonical=canonical("compare.html"), total=len(schools),
        row_specs=json.dumps(row_specs, ensure_ascii=False, separators=(",", ":")),
    )


def about(env, schools, pages, web_counts, src_stats=None):
    total = len(schools)
    with_site = web_counts.get("with_site", 0)
    pct = round(with_site * 100 / total) if total else 0
    return env.get_template("about.html").render(
        base="", active="about", nav=nav(), title="数据说明",
        desc="数据来源、信度体系、数据缺口原则与免责声明。",
        canonical=canonical("about.html"), total=total,
        with_site=with_site, site_pct=pct,
        about_html=pages["about"]["html"] if "about" in pages else "",
        src_stats=src_stats or {},
    )


def policy(env, pages):
    """政策与更名对照独立成页：这类内容每年更新，需要可引用的固定地址。"""
    missing = [k for k in ("policy-2026", "renames") if k not in pages]
    if missing:
        raise SystemExit(f"缺少内容页：{missing}（应在 content/pages/ 下）")
    return env.get_template("policy.html").render(
        base="", active="policy", nav=nav(), title="政策与更名",
        desc="2026 年南京招生政策要点与学校更名对照，含来源与更新日期。",
        canonical=canonical("policy.html"), pages=pages,
    )


def detail(env, school, verified_at, links=None, dup_names=()):
    """dup_names：跨学段重名的校名集合。

    南京有 10 所「小学部 / 初中部」共用同一校名的学校（如南京仙林外国语学校），
    若 title 只写校名，会出现 10 组完全相同的 <title>——浏览器多标签页、收藏夹、
    搜索结果里都无法区分。重名时补上学段，如「南京仙林外国语学校（小学）」。
    """
    body, toc = load.load_body(school, links)
    jsonld = build_jsonld(school)
    title = f"{school.name}（{school.level}）" if school.name in dup_names else school.name
    return env.get_template("detail.html").render(
        base="../", active="schools", nav=nav(), title=title,
        desc=f"{school.name}（{school.district}{school.level}，{school.type}）：{school.tagline}",
        canonical=canonical(school.url), s=school, body=body, toc=toc,
        verified_at=verified_at, jsonld=jsonld,
        # 对比页的 id 规则是「学段-校名」，必须与 compare.js 的 o.id 完全一致，
        # 否则详情页加进去的学校在对比页认不出来（index.json 的 id 多了区，不能直接用）
        cmp_id=f"{school.level}-{school.name}",
    )


def build_jsonld(school):
    """生成 EducationalOrganization + BreadcrumbList 结构化数据。

    `</` 需转义，否则字符串里出现闭合标签时可能提前终止 script 元素。
    """
    org = {
        "@context": "https://schema.org",
        "@type": "EducationalOrganization",
        "name": school.name,
        "description": school.tagline,
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "南京市",
            "addressRegion": "江苏省",
            "addressCountry": "CN",
        },
    }
    if school.website.site:
        org["url"] = school.website.site
    crumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [],
    }
    for pos, (name, path) in enumerate(
            [("首页", ""), ("学校库", "schools.html"), (school.name, school.url)], start=1):
        item = {"@type": "ListItem", "position": pos, "name": name}
        url = canonical(path)
        if url:                      # 未配置基址时不写空的 item，避免产出无效地址
            item["item"] = url
        crumb["itemListElement"].append(item)
    raw = json.dumps([org, crumb], ensure_ascii=False, separators=(",", ":"))
    return raw.replace("</", "<\\/")
