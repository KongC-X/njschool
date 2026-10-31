# -*- coding: utf-8 -*-
"""呈现层：模板装配。

只负责「把数据放进模板」，不做数据校验（校验在 schema）也不写文件（写盘在 main）。
这样模板可以单独渲染预览，测试时无需触碰文件系统。
"""
import json
import os
import re
from hashlib import md5
from urllib.parse import quote, urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import aliases, config, district, facts, load, marks, mdtext, score, source, timeline

# (href, label, key, children) —— children 非空则渲染成下拉菜单。
#
# 导航位是稀缺资源：7 项在 720px 视口刚好放满（实测需约 673px），
# 再加一项就会在 721–768px 区间溢出被裁掉。所以每加一个，就要想清楚谁让位。
# 当前取舍（按家长使用频次与紧急度）：
#   首页 / 学校库      常驻
#   时间轴            每年 5 月必看，错过就是一年
#   分数查学校        出分后那几天的高频动作
#   对比              选校时用，非刚性
#   特长生            窄通道，但它是独立的招生体系，留在导航便于发现
#   政策              规则有没有变，每年看一次
# 「数据说明」不在导航：它是一次性建立信任用的文档，不在决策路径上。
# 改由每页页脚的信度标注一行链入——那正是读者产生「这数据可信吗」疑问的位置，
# 比放在顶部导航更贴上下文。
NAV = [
    ("index.html", "首页", "home", ()),
    ("schools.html", "学校库", "schools", ()),
    ("timeline.html", "时间轴", "timeline", ()),
    ("score.html", "分数查学校", "score", ()),
    ("compare.html", "对比", "compare", ()),
    ("talent.html", "特长生", "talent", (
        ("talent-xueke.html", "学科特长生", "talent-xueke"),
        ("talent-keji.html", "科技特长生", "talent-keji"),
        ("talent-yishu.html", "艺术特长生", "talent-yishu"),
        ("talent-tiyu.html", "体育特长生", "talent-tiyu"),
    )),
    ("policy.html", "政策", "policy", ()),
]


def asset_ver():
    """静态资源的版本串，用于缓存失效。

    GitHub Pages 的 Cache-Control 是固定值、不能改响应头，文件名也没有内容哈希，
    改一行 CSS 后浏览器仍可能拿旧副本。这里按「文件名 + 体积 + 修改时间」算一个短哈希，
    模板里拼成 site.css?v=abc12345 —— 内容一变串就变，等于换了资源地址。

    只哈希 css/js：图片由 git 管理且极少变，多算一遍不会更快。
    """
    h = md5()
    try:
        names = sorted(os.listdir(config.ASSETS))
    except OSError:
        return "0"
    for name in names:
        if not name.endswith((".css", ".js")):
            continue
        path = os.path.join(config.ASSETS, name)
        h.update(name.encode("utf-8"))
        h.update(str(os.path.getsize(path)).encode("ascii"))
        h.update(str(int(os.path.getmtime(path))).encode("ascii"))
    return h.hexdigest()[:8]


def make_env():
    env = Environment(
        loader=FileSystemLoader(config.TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["host"] = host_of
    env.globals["today"] = config.TODAY
    env.globals["ver"] = asset_ver()
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


# 窄屏用的短标签：375px 上「分数查学校」占 76px，改成「查分」省 37px，
# 正好够把五项塞进一行而不必牺牲任何一个入口。
NAV_SHORT = {"score": "查分"}


def nav():
    return [{"href": h, "label": l, "key": k, "short": NAV_SHORT.get(k, ""),
             "children": [{"href": ch, "label": cl, "key": ck} for ch, cl, ck in kids]}
            for h, l, k, kids in NAV]


def _policy_count(pages):
    """2026 政策条数：从政策页的表格里数，不再手写。

    原来首页写「4 项」、政策页列了 5 条，而且首页漏掉的恰恰是
    「取消学区房年限限制」与「长幼随学」这两条最影响决策的。
    这个站的立身之本是准确，首页与内页对不上是最伤那一点的小瑕疵。
    """
    html = (pages.get("policy-2026") or {}).get("html", "")
    m = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    return len(re.findall(r"<tr>", m.group(1))) if m else 0


def home(env, schools, districts, pages, web_counts):
    by_key = {}
    for s in schools:
        by_key[(s.level, s.district)] = by_key.get((s.level, s.district), 0) + 1

    # 统计条只讲「这个站有多大」，不复述学段构成——
    # 小学/初中/高中 的数字紧接着就出现在学段卡片上，同一屏说两遍是冗余。
    # 第三格是 2026 政策变化条数，把用户引向下面那个区块。
    stats = [
        ("收录学校", f"{len(schools)} 所"),
        ("覆盖行政区", f"{len(districts)} 个"),
    ]
    n_changes = _policy_count(pages)
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


def missing_data(schools):
    """返回 {school.id: [field...]}：档案明确声明为数据缺口的字段。

    对比表的「未获取」与「—」必须分得开：
      - 未获取 = 该校档案的「数据缺口」小节**明确点名**过这一项
      - —      = 本站没抽到，不代表学校没有
    把两者混成一个符号，就是在替学校下结论，违反「不臆造」。
    """
    out = {}
    for s in schools:
        miss = facts.extract_missing(source.text(s.file))
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
        text = source.text(s.file)
        f = facts.extract(text)
        # 口碑无法结构化，但家长要对比它：截一段原文放进 facts，
        # 前端以「原文摘录」样式呈现，不做摘要、不做改写。
        rep = facts.excerpt(text, "reputation")
        if rep:
            f["reputation"] = rep
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
        f = facts.extract(source.text(s.file))
        # has：这所学校档案里「有数据」的项。用于学校库的「数据项」筛选——
        # 家长搜「学费」时被告知只有 12 所，实际 376 份档案都写了学费，
        # 差别只是「有没有一个结构化字段能筛」。这里补上这个字段。
        has = " ".join(facts.HAS_LABELS[k] for k in facts.HAS_ORDER if f.get(k))
        rows.append([s.name, s.short, s.district, s.level, s.type, s.tier,
                     s.tagline, alias.get(s.id, ""),
                     " ".join(marks.labels(source.text(s.file), s.name)),
                     has])
    payload = {
        "cols": list(LIST_COLS) + ["aliases", "marks", "has"],
        "rows": rows,
        "districts": districts,
    }
    return "window.__SCHOOLS__ = " + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")) + ";\n"


def streets_data(schools):
    """生成 assets/streets-data.js —— 学校库做地址检索用的地名索引。

    为什么要单独一个文件而不是并进 schools-data.js：
      · 那个文件已到 155KB / 200KB 预算，再加约 12KB 的地名索引会把余地吃光；
      · 只有学校库（和地址搜索）需要它，对比页不该为它付费。

    rows 与 schools-data.js 的 rows **同序同长**，靠下标对齐；
    check.py 有一条守卫核对这一点，错位会让「搜宁海路」跳到别的学校。
    """
    rows = []
    for s in schools:
        # 高中没有施教区概念，一律留空——否则「招生」章节里的路名会被误当学区
        toks = [] if s.level == "高中" else district.anchors(source.text(s.file))
        rows.append(" ".join(toks))
    payload = {"cols": ["anchors"], "rows": rows}
    return "window.__STREETS__ = " + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")) + ";\n"


def timeline_page(env, schools):
    """招生时间轴：把分散在 545 份档案里的报名节点聚合成一张日历。

    页面上每个节点都带「N 份档案提及」——这既是覆盖率也是可信度，
    同时天然把「多数学校都写的通行节点」和「个别学校的补充节点」分开，
    不需要另造一套「权威/非权威」的判断。
    """
    sources = {s.id: source.text(s.file) for s in schools}
    data = timeline.build(schools, sources)
    levels = [lv for lv in config.LEVELS if data.get(lv, {}).get("nodes")]
    blocks = []
    for lv in levels:
        r = data[lv]
        months = []
        for m in sorted({n["m"] for n in r["nodes"]}):
            months.append({"m": m, "nodes": [n for n in r["nodes"] if n["m"] == m]})
        deadlines = [n for n in r["nodes"] if n.get("deadline")]
        deadlines.sort(key=lambda n: (n["deadline"]["m"], n["deadline"]["d"]))
        blocks.append({
            "level": lv, "months": months, "contributors": r["contributors"],
            "extra": r["extra"], "deadlines": deadlines,
        })

    # 高中档案里写时间节点的只有 8 份、能凑成表的只有 3 份，构不成主时间轴。
    # 与其给一个空标签页，不如说清楚为什么没有、该去看哪儿——把数字也带上，
    # 「少数几份」这种模糊说法对一个以准确立身的站点没有意义。
    skipped = []
    for lv in config.LEVELS:
        if lv in levels:
            continue
        skipped.append({
            "level": lv,
            "total": sum(1 for s in schools if s.level == lv),
            "contributors": data.get(lv, {}).get("contributors", 0),
        })
    return env.get_template("timeline.html").render(
        base="", active="timeline", nav=nav(), title="招生时间轴",
        desc="把 545 份学校档案里的报名时间节点合成一张表：什么时候报名、什么时候摇号、"
             "哪些日子过了就等一年。",
        canonical=canonical("timeline.html"), blocks=blocks, skipped=skipped,
        total=len(schools),
    )


def score_page(env, schools):
    """中考分数反查：输入总分，看 2026 年哪些学校的投档线在附近。

    只做「按分差分档」，不预测录取结果：投档线每年会变，且指标生、特长生、
    国际班都能低于这条线录取。页面把这两件事写在结果上方，而不是埋进脚注。
    """
    facts_of = {s.id: facts.extract(source.text(s.file)) for s in schools}
    rows, missing = score.build(schools, facts_of)
    return env.get_template("score.html").render(
        base="", active="", nav=nav(), title="分数查学校",
        desc="输入中考总分，看 2026 年南京 37 所普通高中的投档线分布："
             "哪些可以冲、哪些比较稳、哪些够不着。",
        canonical=canonical("score.html"), rows=rows, missing=missing,
        total=len(rows),
    )


def schools_page(env, schools, districts):
    return env.get_template("schools.html").render(
        base="", active="schools", nav=nav(), title="学校库",
        desc=f"南京 {len(schools)} 所中小学检索：支持多关键词、按学段/行政区/性质筛选。",
        canonical=canonical("schools.html"), total=len(schools),
        # 关掉 JS 时给一串「按区直达」的静态入口（all.html 的锚点），
        # 否则这一页在无脚本环境下只剩一句「去全部索引」。
        districts=districts,
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
            # 锚点用序号而不是区名：中文出现在 id 里虽然合法，但分享出去的
            # 「#d-江北新区」会被各种客户端二次编码，反倒打不开。
            groups.append({"name": d, "id": f"d-{len(groups)}", "levels": levels,
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
            if not isinstance(row.get("plan_n"), int) or row["plan_n"] <= 0:
                raise SystemExit(
                    f"✗ talent_schools.json 里「{row['name']}」的 plan_n 必须是正整数，"
                    f"实际为 {row.get('plan_n')!r}")
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


# 芯片取值优先级：按学段各排一列，前面的取不到就往后补，最多显示 3 个。
# 顺序的依据是「家长在这一步会拿它做什么决定」：
#   小学 → 对口哪所初中（决定要不要买这套房）
#   初中 → 中考成绩 / 收费（决定摇不摇号）
#   高中 → 投档线（决定能不能报）
# 咨询电话排在末位：它不是决策依据，但在招生季是唯一能打通的动作。
CHIP_KEYS = {
    "小学": ("feeder", "plan", "classes", "tuition", "group", "phone"),
    "初中": ("score", "tuition", "plan", "classes", "sources", "phone"),
    "高中": ("score", "plan", "classes", "tuition", "phone"),
}
_H2_ID = re.compile(r'<h2 id="([^"]+)">')


def _probe(value):
    """取值里最适合用来在正文中定位的一段文字。

    不能直接拿 value 前几个字符去找：
      · Markdown 渲染后「625」外面包着 <strong>，字符序列被打断；
      · 「22,000 元/生·学期」里的斜杠在正文里也在，但截断点常常正好落在符号上。
    做法是取 value 里**最长的一段连续汉字**（2–4 字），它几乎总能在正文里原样出现。
    """
    runs = re.findall(r"[\u4e00-\u9fa5]{2,}", value or "")
    if not runs:
        return ""
    return max(runs, key=len)[:4]


def _anchor_of(body, heads, value):
    probe = _probe(value)
    if not probe:
        return ""
    pos = body.find(probe)
    while pos != -1:
        anchor = ""
        for start, aid in heads:
            if start <= pos:
                anchor = aid
            else:
                break
        if anchor:
            return anchor
        pos = body.find(probe, pos + 1)
    return ""


def _chips(school, body):
    """页头关键数字芯片：家长在咨询会现场要 5 秒内看到的那几个数。

    取不到的项直接不出现——宁缺勿滥，别用「—」占一格。
    """
    f = facts.extract(source.text(school.file))
    heads = [(m.start(), m.group(1)) for m in _H2_ID.finditer(body)]
    out = []
    for key in CHIP_KEYS.get(school.level, ()):
        value = f.get(key)
        if not value:
            continue
        # 芯片是一格小卡，值太长会把整行撑开（「南京市第二十九中学初中部（单校直升口径）」
        # 曾占两行）。截断显示，完整值放 title。
        # 原来截到 13 字，「察哈尔路 652 分（全市…」——左括号没闭合，读起来像排版坏了；
        # 桌面明明有 1100px 余量。现在放宽到 24 字，并且不在括号里下刀。
        LIMIT = 24
        if len(value) <= LIMIT:
            shown = value
        else:
            cut = value[:LIMIT]
            if cut.count("（") > cut.count("）"):
                pos = cut.rfind("（")
                if pos > 8:
                    cut = cut[:pos]
            shown = cut.rstrip("、，, ") + "…"
        out.append({
            "label": facts.FACT_LABELS.get(key, key),
            "value": shown,
            "full": value,
            "href": _anchor_of(body, heads, value),
        })
        if len(out) == 3:
            break
    return out


def _related(school, schools, f):
    """页尾「接着看」：给三条能走的下一步。

    详情页原先没有任何横向出口——读完一所只能回退到列表重搜。
    这里按家长真实决策链排：对口初中 → 同区同梯队 → 同学段同区。
    """
    out = []

    feeder = f.get("feeder") or f.get("sources") or ""
    if feeder:
        hit = None
        for s in schools:
            if s is not school and s.name in feeder:
                if hit is None or len(s.name) > len(hit.name):
                    hit = s
        if hit:
            out.append({"k": "对口初中" if f.get("feeder") else "主要生源小学",
                        "n": hit.name, "d": f"{hit.district} · {hit.level}",
                        "href": "../" + hit.url})
            out.append({"k": "看看它的升学表现", "n": hit.name + " 的档案",
                        "d": "中考成绩 / 四星率 / 指标生", "href": "../" + hit.url})

    peers = [s for s in schools
             if s is not school and s.district == school.district
             and s.level == school.level and s.tier and s.tier == school.tier]
    peers.sort(key=lambda s: s.name)
    for s in peers[:2]:
        out.append({"k": "同区同梯队", "n": s.name,
                    "d": f"{s.district} · {s.level}", "href": "../" + s.url})

    if len(out) < 3:
        near = [s for s in schools
                if s is not school and s.district == school.district
                and s.level == school.level]
        near.sort(key=lambda s: s.name)
        for s in near:
            if len(out) >= 3:
                break
            if any(o["n"] == s.name for o in out):
                continue
            out.append({"k": "同区同学段", "n": s.name,
                        "d": f"{s.district} · {s.level}", "href": "../" + s.url})
    return out[:3]


def detail(env, school, verified_at, links=None, dup_names=(), schools=None, linkify=None):
    """dup_names：跨学段重名的校名集合。

    南京有 10 所「小学部 / 初中部」共用同一校名的学校（如南京仙林外国语学校），
    若 title 只写校名，会出现 10 组完全相同的 <title>——浏览器多标签页、收藏夹、
    搜索结果里都无法区分。重名时补上学段，如「南京仙林外国语学校（小学）」。
    """
    body, toc = load.load_body(school, links)
    if linkify:
        body = linkify(body, exclude=school.name)
    jsonld = build_jsonld(school)
    title = f"{school.name}（{school.level}）" if school.name in dup_names else school.name
    f = facts.extract(source.text(school.file))
    return env.get_template("detail.html").render(
        base="../", active="schools", nav=nav(), title=title,
        desc=f"{school.name}（{school.district}{school.level}，{school.type}）：{school.tagline}",
        canonical=canonical(school.url), s=school, body=body, toc=toc,
        verified_at=verified_at, jsonld=jsonld,
        chips=_chips(school, body),
        related=_related(school, schools or [], f),
        has_shijiaoqu='id="shijiaoqu"' in body,
        # 对比页的 id 规则是「学段-校名」，必须与 compare.js 的 o.id 完全一致，
        # 否则详情页加进去的学校在对比页认不出来（index.json 的 id 多了区，不能直接用）
        cmp_id=f"{school.level}-{school.name}",
        # 「官方还没说死」的标记要放在页头，不能只埋在正文里
        warn=marks.badges(source.text(school.file), school.name),
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
