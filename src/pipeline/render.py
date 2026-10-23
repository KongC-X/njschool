# -*- coding: utf-8 -*-
"""呈现层：模板装配。

只负责「把数据放进模板」，不做数据校验（校验在 schema）也不写文件（写盘在 main）。
这样模板可以单独渲染预览，测试时无需触碰文件系统。
"""
import json
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config, load

NAV = [
    ("index.html", "首页", "home"),
    ("schools.html", "学校库", "schools"),
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
    )


def schools_page(env, schools, districts):
    slim = [{
        "name": s.name, "short": s.short, "district": s.district, "level": s.level,
        "type": s.type, "tier": s.tier, "tagline": s.tagline, "url": s.url,
    } for s in schools]

    data_js = json.dumps(slim, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    dist_js = json.dumps(districts, ensure_ascii=False)
    schools_js = env.get_template("schools.js").render(
        schools_json=data_js, districts_json=dist_js)

    return env.get_template("schools.html").render(
        base="", active="schools", nav=nav(), title="学校库",
        desc=f"南京 {len(schools)} 所中小学检索：按学段、行政区、办学性质筛选。",
        canonical=canonical("schools.html"), schools_js=schools_js,
        total=len(schools),
    )


def about(env, schools, pages, web_counts):
    total = len(schools)
    with_site = web_counts.get("with_site", 0)
    pct = round(with_site * 100 / total) if total else 0
    return env.get_template("about.html").render(
        base="", active="about", nav=nav(), title="数据说明",
        desc="数据来源、信度体系、数据缺口原则与免责声明。",
        canonical=canonical("about.html"), total=total,
        with_site=with_site, site_pct=pct,
        about_html=pages["about"]["html"] if "about" in pages else "",
    )


def detail(env, school, verified_at):
    body, toc = load.load_body(school)
    return env.get_template("detail.html").render(
        base="../", active="schools", nav=nav(), title=school.name,
        desc=f"{school.name}（{school.district}{school.level}，{school.type}）：{school.tagline}",
        canonical=canonical(school.url), s=school, body=body, toc=toc,
        verified_at=verified_at,
    )
