# -*- coding: utf-8 -*-
"""呈现层：模板装配。

只负责「把数据放进模板」，不做数据校验（校验在 schema）也不写文件（写盘在 main）。
这样模板可以单独渲染预览，测试时无需触碰文件系统。
"""
import json
import os
import re
from urllib.parse import quote, urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import aliases, config, facts, load, marks, mdtext

# (href, label, key, children) —— children 非空则渲染成下拉菜单。
# 「特长生」的父项本身指向总览页，右侧单独的 ▾ 按钮才展开子菜单，
# 这样桌面点标签能进总览、触屏也能展开子项。
NAV = [
    ("index.html", "首页", "home", ()),
    ("schools.html", "学校库", "schools", ()),
    ("compare.html", "对比", "compare", ()),
    ("talent.html", "特长生", "talent", (
        ("talent-xueke.html", "学科特长生", "talent-xueke"),
        ("talent-keji.html", "科技特长生", "talent-keji"),
        ("talent-yishu.html", "艺术特长生", "talent-yishu"),
        ("talent-tiyu.html", "体育特长生", "talent-tiyu"),
    )),
    ("policy.html", "政策", "policy", ()),
    ("about.html", "数据说明", "about", ()),
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
    # 分享卡片图。必须是绝对地址，社交平台不会解析相对路径；
    # 未配置基址（本地 file:// 预览）时返回空串，模板据此整块省略。
    env.globals["og_image"] = canonical("assets/og/site.png")
    # 信度徽章：让模板与 Markdown 正文用同一套 HTML，不各写一份样式。
    # 必须包 Markup —— 否则 autoescape 会把 <span> 转义成字面量显示出来。
    env.globals["conf"] = lambda k: Markup(mdtext.badge(k))
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
    return [{"href": h, "label": l, "key": k,
             "children": [{"href": ch, "label": cl, "key": ck} for ch, cl, ck in kids]}
            for h, l, k, kids in NAV]


def home(env, schools, districts, pages, web_counts):
    by_key = {}
    for s in schools:
        by_key[(s.level, s.district)] = by_key.get((s.level, s.district), 0) + 1

    # 统计条只讲「这个站有多大」，不复述学段构成——
    # 小学/初中/高中 的数字紧接着就出现在学段卡片上，同一屏说两遍是冗余。
    # 第三格换成 2026 政策变化条数，把用户引向下面那个区块。
    hl_html = (pages.get("home-highlights") or {}).get("html", "")
    n_changes = hl_html.count("<li>")
    stats = [
        ("收录学校", f"{len(schools)} 所"),
        ("覆盖行政区", f"{len(districts)} 个"),
    ]
    if n_changes:
        stats.append(("2026 政策变化", f"{n_changes} 项"))

    level_cards = [{
        "level": lv,
        "count": sum(1 for s in schools if s.level == lv),
        # 副标题讲「能查到什么」，不是「为什么没数据」
        "desc": config.LEVEL_CARD_DESC[lv],
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
    """返回 {school.id: [field...]}：档案明确声明为数据缺口的字段。

    对比表的「未获取」与「—」必须分得开：
      - 未获取 = 该校档案的「数据缺口」小节**明确点名**过这一项
      - —      = 本站没抽到，不代表学校没有
    把两者混成一个符号，就是在替学校下结论，违反「不臆造」。
    """
    out = {}
    for s in schools:
        miss = facts.extract_missing(_md_text(s))
        if miss:
            # 必须用前端的派生 id（学段-校名），不能用 index.json 的 s.id
            # ——后者多了「区」这一层（小学-鼓楼区-某某小学），前端认不出来。
            # 这条曾一次性让 414 条缺口记录全部失效，靠 check.py 的守卫才拦住。
            out[f"{s.level}-{s.name}"] = sorted(miss)
    return out


def compare_data(schools):
    """生成 assets/schools-compare.js —— 只有对比页加载的数据。

    拆出来的原因：schools-data.js 已经顶到 197/200 KB 预算，
    再加字段根本加不进去。列表页不需要 facts / 官网有无 / 缺口，
    把这些挪到独立文件后，列表页首屏下载量直接降下来。

    rows 与 schools-data.js 的 rows **同序同长**，靠下标对齐；
    check.py 有一条守卫核对这一点。
    """
    rows = []
    for s in schools:
        f = facts.extract(_md_text(s))
        rows.append([f or None, 1 if s.website.site else 0])
    payload = {
        "cols": ["facts", "hasSite"],
        "rows": rows,
        "factLabels": facts.FACT_LABELS,
        "missing": missing_data(schools),
    }
    return "window.__COMPARE_DATA__ = " + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")) + ";\n"


def schools_data(schools, districts):
    """生成 assets/schools-data.js。

    外置为 JS 资产而不是内联在 HTML 里：
      - 学校库与对比页共用同一份数据，浏览器只下载一次；
      - HTML 从 50KB 降到几 KB；
      - <script src> 不受 file:// 的 fetch 限制，双击打开仍可用。

    aliases 列单独放最后：搜索命中「拉力琅」「秦淮外校」这类俗称靠它，
    但 tagline 不进搜索索引（叙述性长文本，是误命中的唯一来源）。

    facts / hasSite 不在这里：它们只有对比页要用，见 compare_data()。
    """
    alias = aliases.build(schools)
    rows = []
    for s in schools:
        rows.append([s.name, s.short, s.district, s.level, s.type, s.tier,
                     s.tagline, alias.get(s.id, ""),
                     " ".join(marks.labels(_md_text(s), s.name))])
    payload = {
        "cols": list(LIST_COLS) + ["aliases", "marks"],
        "rows": rows,
        "districts": districts,
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


def all_page(env, schools, districts):
    """全部学校索引页（all.html）。

    存在的理由有两个，都不是「多一个页面」：
      1. 学校库靠 JS 渲染 545 张卡片，关掉 JS 就一条学校链接都没有。
         这里给出纯静态、可直接点的完整清单。
      2. 站内此前没有任何静态链接指向 545 个详情页，
         搜索引擎只能靠 sitemap 摸进来，拿不到内链权重。
    """
    groups = []
    for d in districts:
        levels = []
        for lv in config.LEVELS:
            items = sorted((s for s in schools if s.district == d and s.level == lv),
                           key=lambda s: s.name)
            if items:
                levels.append({"level": lv, "schools": items})
        if levels:
            groups.append({"name": d, "levels": levels,
                           "total": sum(len(g["schools"]) for g in levels)})
    return env.get_template("all.html").render(
        base="", active="schools", nav=nav(), title="全部学校索引",
        desc=f"南京 {len(schools)} 所中小学的完整清单，按行政区与学段排列。",
        canonical=canonical("all.html"), total=len(schools), groups=groups,
    )


TALENT_SCHOOLS = os.path.join(config.ROOT, "data", "talent_schools.json")

# 三个分类页：(模板名, 输出文件, 标题, 摘要, 数据键)
TALENT_SUBS = [
    ("talent_xueke.html", "talent-xueke.html", "学科特长生",
     "南京中考学科特长生：覆盖数学、物理、化学、生物四大奥赛学科，含招生科目、报名条件与各校计划。",
     "academic"),
    ("talent_keji.html", "talent-keji.html", "科技特长生",
     "南京中考科技特长生：人工智能、机器人、航模、无线电测向等方向，以及信息学（信奥）方向。",
     "tech"),
    ("talent_yishu.html", "talent-yishu.html", "艺术特长生",
     "南京中考艺术特长生：美术、音乐、舞蹈、书法，控制线 490 分与各校招生计划。",
     "arts"),
    ("talent_tiyu.html", "talent-tiyu.html", "体育特长生",
     "南京中考体育特长生：足球、篮球、排球、田径、击剑、跆拳道等，控制线 455 分与各校计划。",
     "tiyu"),
]


def _talent_data(schools):
    """读招生校清单并挂上详情页地址。

    校名写错会渲染出一个点不进去的链接，比漏列更难发现，所以构建期就报错。
    """
    with open(TALENT_SCHOOLS, encoding="utf-8") as f:
        data = json.load(f)

    known = {s.name for s in schools}
    url_of = {}
    for s in schools:
        url_of.setdefault(s.name, s.url)

    for group in ("tech", "info", "academic", "arts", "tiyu"):
        for row in data.get(group, []):
            if row["name"] not in known:
                raise SystemExit(
                    f"✗ talent_schools.json 里的「{row['name']}」不在 index.json 中，"
                    f"请核对校名（写错会渲染出一个点不进去的链接）")
            row["url"] = url_of[row["name"]]
    return data


def talent(env, schools):
    """特长生总览页。

    跨类别的公共内容（四类对照、共同规则、常见误解、小升初无通道）放这里，
    三个分类页只写各自的特有内容，不重复搬运。
    """
    data = _talent_data(schools)
    # 入口卡上写「几所学校」，按校名去重——同一所学校可能有多个校区各占一行
    counts = {k: len({r["name"] for r in data.get(k, [])})
              for k in ("academic", "tech", "arts", "tiyu", "info")}
    return env.get_template("talent.html").render(
        base="", active="talent", nav=nav(), title="特长生",
        desc="南京中考特长生总览：学科、科技、艺术三类的差别、控制线、"
             "报名规则与时间节点，以及各类别的招生计划入口。",
        canonical=canonical("talent.html"), updated=data.get("updated", ""),
        counts=counts,
    )


def talent_sub(env, schools, spec):
    """三个分类页共用。spec 取自 TALENT_SUBS。"""
    tpl, out, title, desc, key = spec
    data = _talent_data(schools)
    active = out.replace(".html", "")
    return env.get_template(tpl).render(
        base="", active=active, nav=nav(), title=title, desc=desc,
        canonical=canonical(out), updated=data.get("updated", ""),
        rows=data.get(key, []), info=data.get("info", []),
        tech=data.get("tech", []),
    )


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
        # 「官方还没说死」的标记要放在页头，不能只埋在正文里
        warn=marks.badges(_md_text(school), school.name),
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
    # 与页面里 <nav class="crumb"> 的层级保持一致：首页 / 学校库 / 学段 / 区 / 校名。
    # 两边对不上时，搜索结果里显示的路径会和页面上的不一样。
    crumbs = [("首页", canonical("")), ("学校库", canonical("schools.html"))]
    if config.BASE_URL:
        crumbs.append((school.level,
                       f"{config.BASE_URL}/schools.html?lv={quote(school.level)}"))
        crumbs.append((school.district,
                       f"{config.BASE_URL}/schools.html?dist={quote(school.district)}"))
    crumbs.append((school.name, canonical(school.url)))

    for pos, (name, url) in enumerate(crumbs, start=1):
        item = {"@type": "ListItem", "position": pos, "name": name}
        if url:                      # 未配置基址时不写空的 item，避免产出无效地址
            item["item"] = url
        crumb["itemListElement"].append(item)
    raw = json.dumps([org, crumb], ensure_ascii=False, separators=(",", ":"))
    return raw.replace("</", "<\\/")
