# -*- coding: utf-8 -*-
"""
build_website.py — 生成「南京中小学档案」静态网站

数据源：
  - index.json            （由 build_index.py 生成，学校元数据）
  - 小学/初中/高中/**/*.md （档案正文，构建期渲染为 HTML）

输出目录：site/
  index.html              首页（导航 + 概览统计 + 学段/行政区入口 + 2026 政策变化）
  schools.html            学校库（搜索 + 学段/区/性质筛选）
  schools/<学段>-<校名>.html  204 个学校详情页（档案全文渲染）
  about.html              数据说明（信度体系 / 数据缺口 / 官方渠道判定 / 免责声明）
  assets/{tokens.css,site.css,app.js}   从仓库 assets/ 原样拷贝
  sitemap.xml             仅当设置 NJ_BASE_URL 时生成（绝对地址是 sitemap 的必要条件）
  robots.txt

设计决策：
  - 纯静态、零框架、零构建工具链；构建期完成 md → HTML，客户端不做 markdown 解析
  - 数据直接内嵌进页面（不 fetch），保证 file:// 协议双击也能用
  - 中文 UTF-8 文件名，GitHub Pages 等静态托管可直接部署
  - 样式与脚本外置于 assets/，脚本不再内嵌 CSS/JS（避免多份样式并行维护）

环境变量：
  NJ_BASE_URL   站点绝对地址（如 https://nj.example.com）。用于生成 sitemap 与 canonical；
                未设置时跳过 sitemap —— 宁可不产出，也不产出带占位符的无效文件。
"""
import json
import os
import re
import shutil
from datetime import date
from urllib.parse import quote

import markdown

ROOT = "/Users/kongc/WorkBuddy/南京学校"
INDEX = os.path.join(ROOT, "index.json")
WEBFILE = os.path.join(ROOT, "data", "school_websites.json")  # 官网/公众号核查结果
ASSETS = os.path.join(ROOT, "assets")
SITE = os.path.join(ROOT, "site")
TODAY = date.today().isoformat()
BASE_URL = (os.environ.get("NJ_BASE_URL") or "").rstrip("/")

LEVELS = ["小学", "初中", "高中"]

# ============================================================ 样式
# 说明：CSS 变量驱动双主题；默认浅色（家长群体可读性优先），
# prefers-color-scheme 跟随系统，手动切换写入 localStorage 覆盖。
# 样式与脚本已外置：assets/tokens.css（令牌）、assets/site.css（组件）、assets/app.js


# ============================================================ 脚本
# 学校库页面脚本（数据在构建期内嵌）
SCHOOLS_JS = """
const DATA = __DATA__;
const state = { q: new URLSearchParams(location.search).get('q') || '', lv:'', dist:'', type:'' };
const grid = document.getElementById('grid'), cnt = document.getElementById('count');

function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

/* 生成筛选 chip 组 */
function chips(elId, key, values, allLabel){
  const box = document.getElementById(elId);
  [[ '', allLabel ]].concat(values.map(v=>[v,v])).forEach(([v,label])=>{
    const b = document.createElement('button');
    b.className = 'chip' + (v===state[key] ? ' on' : '');
    b.textContent = label; b.dataset.v = v;
    b.onclick = ()=>{ state[key]=v;
      [...box.children].forEach(c=>c.classList.toggle('on', c.dataset.v===v));
      render(); };
    box.appendChild(b);
  });
}

function render(){
  const q = state.q.trim().toLowerCase();
  const rows = DATA.filter(s=>{
    if(state.lv && s.level!==state.lv) return false;
    if(state.dist && s.district!==state.dist) return false;
    if(state.type && s.type!==state.type) return false;
    if(q){
      const hay = (s.name+' '+(s.short||'')+' '+(s.tier||'')+' '+(s.tagline||'')+' '+s.district).toLowerCase();
      if(!hay.includes(q)) return false;
    }
    return true;
  });
  cnt.textContent = `匹配 ${rows.length} 所 / 共 ${DATA.length} 所`;
  grid.innerHTML = rows.length ? rows.map(s=>`
    <div class="card">
      <h3><a href="${s.url}">${esc(s.name)}</a></h3>
      <div class="badges">
        <span class="b b-lv">${esc(s.level)}</span>
        <span class="b ${s.type==='民办'?'b-pri':'b-pub'}">${esc(s.type)}</span>
        <span class="b b-d">${esc(s.district)}</span>
        ${s.short?`<span class="b b-d">${esc(s.short)}</span>`:''}
      </div>
      <div class="tier">${esc(s.tier||'')}</div>
      <div class="tag">${esc(s.tagline||'')}</div>
      <a class="more" href="${s.url}">查看完整档案 →</a>
    </div>`).join('')
    : '<div class="empty">没有匹配的学校，试试换个关键词或清空筛选。</div>';
}

document.getElementById('q').value = state.q;
document.getElementById('q').addEventListener('input', e=>{ state.q=e.target.value; render(); });
chips('f-lv','lv',['小学','初中','高中'],'全部学段');
chips('f-dist','dist',__DISTRICTS__,'全部区');
chips('f-type','type',['公办','民办'],'不限性质');
render();
"""


# ============================================================ 模板
def wrap_tables(html):
    """为所有表格套上 .table-wrap 滚动容器。

    表格元素自身必须保持原生 display:table，否则列宽算法失效、th 背景只覆盖文字；
    横向滚动交给外层容器承担，窄屏时滚动而不是压扁列宽。
    """
    return re.sub(r"<table>(.*?)</table>",
                  r'<div class="table-wrap"><table>\1</table></div>',
                  html, flags=re.S)


def page(title, body, active="", desc="", base=""):
    """整页模板：导航 + 内容 + 页脚。

    active 用于导航高亮；base 为资源相对路径前缀——
    详情页位于 schools/ 子目录，须传 base="../"，否则 CSS/JS 与导航链接全部 404。
    """
    body = wrap_tables(body)
    nav = [("index.html", "首页", "home"), ("schools.html", "学校库", "schools"),
           ("about.html", "数据说明", "about")]
    links = "".join(
        f'<a href="{base}{u}" class="{"on" if k==active else ""}">{t}</a>' for u, t, k in nav)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · 南京中小学档案</title>
<meta name="description" content="{desc or '南京市中小学公开信息汇编：204 所学校档案，含施教区、招生计划、投档线与信度标注。'}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🏫</text></svg>">
<link rel="stylesheet" href="{base}assets/tokens.css">
<link rel="stylesheet" href="{base}assets/site.css">
</head>
<body>
<nav class="nav"><div class="nav-in">
  <a class="brand" href="{base}index.html">🏫 南京<em>中小学</em>档案</a>
  <div class="nav-links">{links}
    <button id="themeBtn" onclick="toggleTheme()" title="切换主题">🌙</button>
  </div>
</div></nav>
{body}
<footer><div class="wrap">
  <div class="cols">
    <div><h4>南京中小学档案</h4>
      公开信息汇编 · 数据版本 v2026-10 · 更新 {TODAY}</div>
    <div><h4>导航</h4>
      <a href="{base}schools.html">学校库</a><br><a href="{base}about.html">数据说明</a></div>
    <div><h4>信度标注</h4>
      [A] 官方发布　[B] 权威媒体　[C] 家长圈口径</div>
  </div>
  <div class="disclaim">
    <strong>免责声明</strong>：本站为公开信息汇编，数据来自政府/教育局官网、学校官网与官方公众号、党报及权威媒体，
    <strong>不构成任何择校建议</strong>；政策与数据每年变动，请以官方最新发布为准。
    家长圈统计的升学数据均已标注 [C]，不可作为唯一依据。各档案末节列有「数据缺口清单」——未获取即未获取，不作推测。
  </div>
</div></footer>
<script src="{base}assets/app.js"></script>
</body></html>"""


def esc_attr(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ============================================================ 页面生成
def build_home(d, slim):
    cov = d["coverage"]
    districts = d["districts"]
    n = len(slim)
    by_lv_dist = {}
    for s in slim:
        by_lv_dist.setdefault((s["level"], s["district"]), 0)
        by_lv_dist[(s["level"], s["district"])] += 1

    stat_cards = "".join(
        f'<div class="stat"><b>{v}</b><span>{k}</span></div>'
        for k, v in [("收录学校", f"{n} 所"), ("覆盖行政区", f"{len(districts)} 个"),
                     ("小学", f"{cov.get('小学',0)} 所"), ("初中", f"{cov.get('初中',0)} 所"),
                     ("高中", f"{cov.get('高中',0)} 所")])

    lv_cards = ""
    lv_desc = {"小学": "施教区 · 对口初中 · 电脑派位",
               "初中": "中考表现 · 班型 · 摇号与学区",
               "高中": "投档线 · 招生计划 · 班型设置"}
    for lv in LEVELS:
        c = cov.get(lv, 0)
        lv_cards += f"""<a class="lv-card" href="schools.html?lv={quote(lv)}">
          <h3>{lv}</h3><div class="n">{c} 所</div><p>{lv_desc[lv]}</p></a>"""

    dist_cards = ""
    for dist in districts:
        total = sum(by_lv_dist.get((lv, dist), 0) for lv in LEVELS)
        sub = " · ".join(f"{lv} {by_lv_dist.get((lv, dist), 0)}"
                         for lv in LEVELS if by_lv_dist.get((lv, dist), 0))
        dist_cards += f"""<a class="dist" href="schools.html?dist={quote(dist)}">
          <b>{dist}</b><span>{total} 所</span><small>{sub}</small></a>"""

    # 2026 政策变化（取自已核验档案结论）
    policy_rows = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td></tr>" for a, b in [
        ("公办初中取消提前一年落户", "2025 年公办小学已取消；2026 年鼓楼、秦淮、建邺三区初中同步取消"),
        ("取消学区房年限限制", "不再提「一套住房三年内只能安排一名学生就读」"),
        ("「长幼随学」试点", "2026 年秋季学期起，义务教育起始年级试行"),
        ("普通高中扩招", "全市普高计划 53,439 人（净增 6,101），普高学位供给率 71.3%，首次突破 70%"),
        ("浦口区与江北新区招生并轨", "2026 年起浦口区考生纳入原市区填报范围"),
    ])
    rename_rows = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td></tr>" for a, b, c in [
        ("南京市金陵中学建邺实验学校（初中部）", "南京市建邺初级中学", "2026 年 5 月"),
        ("南京市金陵中学南湖初级中学", "南京市南湖第二中学", "2026 年 5 月"),
        ("南京市金陵中学华山路小学", "南京市华山路小学", "2026 年 5 月"),
        ("南京江北新区外国语小学", "浦口外国语学校高新小学", "2026 年 4 月"),
        ("南京市金陵河西学校", "金陵中学河西分校", "2024 年 5 月"),
        ("南京东南实验学校", "南师附中江宁分校（义务教育段）", "2024 年 5 月"),
    ])

    body = f"""
<div class="wrap">
  <section class="hero">
    <h1>南京中小学档案</h1>
    <p>{n} 所学校的公开信息汇编：施教区、招生计划、投档线、摇号计划，
       逐条标注信度，如实列出数据缺口。</p>
    <div class="hero-search">
      <input id="hq" type="search" placeholder="搜索学校，如「琅琊路」「金中」「江北」……"
             onkeydown="if(event.key==='Enter')heroSearch()">
      <button onclick="heroSearch()">搜索</button>
    </div>
  </section>
  <div class="stats">{stat_cards}</div>

  <section class="sec">
    <h2>按学段浏览</h2><div class="hint">点击进入学校库并自动筛选</div>
    <div class="cards3">{lv_cards}</div>
  </section>

  <section class="sec">
    <h2>按行政区浏览</h2><div class="hint">覆盖南京 {len(districts)} 个区</div>
    <div class="dist-grid">{dist_cards}</div>
  </section>

  <section class="sec">
    <h2>2026 年招生政策要点</h2><div class="hint">依据市教育局/区政府官方发布整理</div>
    <table><tr><th style="width:220px">事项</th><th>内容</th></tr>{policy_rows}</table>
  </section>

  <section class="sec">
    <h2>学校更名对照</h2><div class="hint">近两年更名学校，填报与检索时注意新旧校名</div>
    <table><tr><th>现用校名</th><th>原校名</th><th style="width:110px">时间</th></tr>{rename_rows}</table>
  </section>

  <section class="sec">
    <h2>数据怎么来的</h2>
    <div class="hint">全部来自公开渠道，每份档案附来源表与「数据缺口清单」。
      已于 2026-10-17 完成 779 项全量核验并修正。<a href="about.html">查看数据说明 →</a></div>
  </section>
</div>"""
    return page("首页", body, active="home",
                desc=f"南京 {n} 所中小学公开信息汇编：施教区、招生、投档线，逐条标注信度。")


def build_schools(d, slim):
    data_js = json.dumps(slim, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    dist_js = json.dumps(d["districts"], ensure_ascii=False)
    js = SCHOOLS_JS.replace("__DATA__", data_js).replace("__DISTRICTS__", dist_js)
    body = f"""
<div class="wrap">
  <div class="controls">
    <input id="q" type="search" placeholder="搜索学校名称、简称、梯队或关键词……">
    <div class="frow">
      <div class="fgroup"><span class="flabel">学段</span><span id="f-lv" style="display:contents"></span></div>
      <div class="fgroup"><span class="flabel">行政区</span><span id="f-dist" style="display:contents"></span></div>
      <div class="fgroup"><span class="flabel">性质</span><span id="f-type" style="display:contents"></span></div>
    </div>
  </div>
  <p class="count" id="count"></p>
  <div class="grid" id="grid"></div>
</div>
<script>{js}</script>
<script>
/* 支持 ?lv= / ?dist= 直达筛选（首页入口用） */
(function(){{
  const p = new URLSearchParams(location.search);
  const map = {{lv:'f-lv', dist:'f-dist'}};
  Object.keys(map).forEach(k=>{{
    const v = p.get(k); if(!v) return;
    const box = document.getElementById(map[k]);
    [...box.children].forEach(c=>{{
      const on = c.dataset.v===v;
      c.classList.toggle('on', on);
      if(on) c.click();
    }});
  }});
}})();
</script>"""
    return page("学校库", body, active="schools",
                desc=f"南京 {len(slim)} 所中小学检索：按学段、行政区、办学性质筛选。")


def build_about(d, wc=None):
    wc = wc or {}
    site_n = wc.get("with_site", 0)
    tot = wc.get("total", 0) or 1
    body = f"""
<div class="wrap">
  <section class="sec">
    <h2>数据说明</h2>
    <div class="hint">本项目是公开信息汇编，以下规则适用于全部 {sum(d['coverage'].values())} 份档案。</div>

    <h3 style="font-size:16px;margin:22px 0 8px">官方渠道（官网 / 公众号）</h3>
    <div class="table-wrap"><table>
      <tr><th style="width:180px">状态</th><th>含义与展示方式</th></tr>
      <tr><td><b>有官网</b></td><td>页面提供「访问学校官网」按钮。{tot} 所中 {site_n} 所（{site_n*100//tot}%）已核实到可用官网。</td></tr>
      <tr><td><b>保留但提示</b></td><td>构建期探测未响应，链接保留并标注「核验时未响应」——多校源站存在间歇性故障，不代表站点已废弃。</td></tr>
      <tr><td><b>存在但不可访问</b></td><td>确认有官网或区教育平台页面，但当前停机/下线，仅显示原域名不设跳转，避免家长点进错误页面。</td></tr>
      <tr><td><b>内容停更</b></td><td>站点可打开但多年未更新，参考价值有限，不提供跳转。</td></tr>
      <tr><td><b>无独立官网</b></td><td>域名退役、被抢注或从未建站；官方信息以学校公众号或区教育局发布为准。</td></tr>
    </table></div>
    <p class="hint" style="margin-top:10px">
      关于公众号：<code>未取得微信号</code> 不等于「没有公众号」，多为仍在更新但未提取到 ID；
      页面会区分「已核实微信号」与「有渠道但未取到 ID」两种情况，不把已停用的账号列为有效渠道。
    </p>

    <h3 style="font-size:16px;margin:22px 0 8px">信度体系</h3>
    <table>
      <tr><th style="width:90px">标记</th><th>含义</th></tr>
      <tr><td><b>[A]</b></td><td>官方发布：学校官网、官方公众号、区教育局/区政府官网、市教育局、市招考院</td></tr>
      <tr><td><b>[B]</b></td><td>权威媒体转述：南京日报、扬子晚报/紫牛新闻、现代快报、新华报业、人民网江苏、南京晨报</td></tr>
      <tr><td><b>[C]</b></td><td>家长圈/自媒体口径（今日头条、微信公众号、培训机构站点），需交叉验证</td></tr>
    </table>

    <h3 style="font-size:16px;margin:22px 0 8px">关于「数据缺口」</h3>
    <table>
      <tr><th style="width:160px">原则</th><th>说明</th></tr>
      <tr><td>缺口 ≠ 零</td><td>每份档案末节列有「数据缺口清单」。未获取即如实标注，不推测、不填默认值。</td></tr>
      <tr><td>升学数据警示</td><td>中考四星率、普高率等多数学校无官方公示，档案数值多为家长圈统计（[C]），不可作为唯一择校依据。</td></tr>
      <tr><td>对口初中警示</td><td>南京官方不公布小学—初中对应表，相关内容系按施教区门牌比对整理，并逐校标注依据与不确定性。</td></tr>
    </table>

    <h3 style="font-size:16px;margin:22px 0 8px">质量控制</h3>
    <table>
      <tr><th style="width:160px">时间</th><th>事项</th></tr>
      <tr><td>2026-10 上旬</td><td>首批档案建档</td></tr>
      <tr><td>2026-10-16</td><td>扩至 198 所；建立十一节/十段式结构、信度标注与数据缺口规范</td></tr>
      <tr><td>2026-10-17</td><td>779 项全量核验（一致 72.3%）；37 项 P0 + 24 项 P1 + 66 项 P2 全部修正；新增 6 所新办校，达 204 所</td></tr>
    </table>

    <h3 style="font-size:16px;margin:22px 0 8px">免责声明</h3>
    <table>
      <tr><td>本站为公开信息汇编，<b>不构成任何择校建议</b>，不做排名推荐。政策与数据每年变动，请以官方最新发布为准。引用请注明来源并保留信度标注。</td></tr>
    </table>
  </section>
</div>"""
    return page("数据说明", body, active="about")


def md_to_html(text):
    """档案 md → HTML。去掉首行 H1（详情页页头已展示校名）。"""
    text = re.sub(r"^#\s+.*\n", "", text, count=1)
    return markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])


def official_block(s, web, verified_at=""):
    """详情页页头的官方渠道区。

    按「存在性状态」分档展示，不把停更站/停机页当可用链接推给家长：
      ok                  → 官网按钮
      exists_unreachable  → 说明「有官网/平台页面，当前不可访问」，只显示域名不设链接
      stale               → 说明「内容长期未更新」，不设链接
      none                → 未检索到独立官网
    公众号按「有 ID / 渠道存在但未取 ID」两种口径展示。
    """
    w = web.get(s["id"]) or {}
    site, arch = w.get("site"), w.get("site_archived")
    state = w.get("site_state") or ("ok" if site else "none")
    reason = w.get("null_reason") or ""
    wechat, wx_status = w.get("wechat"), w.get("wechat_status") or "unknown"

    parts = []
    if site:
        caution = w.get("verify") == "unreachable_at_build"
        cls = "btn-site warn" if caution else "btn-site"
        arrow = "（核验时未响应）" if caution else ""
        parts.append(f'<a class="{cls}" href="{esc_attr(site)}" target="_blank" '
                     f'rel="noopener noreferrer">访问学校官网{arrow} ↗</a>')
    elif state == "exists_unreachable":
        host = re.sub(r"^https?://", "", arch or "").split("/")[0]
        parts.append(f'<span class="nosite">该校有官网／平台页面，但当前无法访问'
                     f'{"（" + reason + "）" if reason else ""}'
                     f'{"，原域名 " + esc_attr(host) if host else ""}，故暂不提供跳转。</span>')
    elif state == "stale":
        parts.append('<span class="nosite">该校官网内容长期未更新，参考价值有限，暂不提供跳转。</span>')
    else:
        parts.append('<span class="nosite">未检索到独立官网。</span>')

    if wechat:
        parts.append(f'<span class="wx">微信公众号：<b>{esc_attr(wechat)}</b></span>')
    elif wx_status == "exists_no_id":
        parts.append('<span class="wx">该校有官方微信公众号（未能核实微信号），'
                     '可在微信内搜索校名关注。</span>')
    else:
        parts.append('<span class="wx">官方信息请以区教育主管部门发布渠道为准。</span>')

    note = (f'<span class="vnote">链接核验于 {verified_at}</span>'
            if verified_at and (site or state != "none") else "")
    return f'<div class="official">{"".join(parts)}{note}</div>'


def build_detail(s, web, verified_at=""):
    with open(os.path.join(ROOT, s["file"]), encoding="utf-8") as f:
        content_html = md_to_html(f.read())
    pri = "b-pri" if s["type"] == "民办" else "b-pub"
    # 详情页在 schools/ 子目录：面包屑与资源链接均须以 ../ 回到站点根
    body = f"""
<div class="wrap">
  <div class="crumb"><a href="../index.html">首页</a> / <a href="../schools.html">学校库</a> /
    <a href="../schools.html?lv={quote(s['level'])}">{s['level']}</a> /
    <a href="../schools.html?dist={quote(s['district'])}">{s['district']}</a></div>
  <div class="detail-head">
    <h1>{esc_attr(s['name'])}</h1>
    <div class="badges">
      <span class="b b-lv">{s['level']}</span>
      <span class="b {pri}">{s['type']}</span>
      <span class="b b-d">{s['district']}</span>
      {f'<span class="b b-d">{esc_attr(s.get("short"))}</span>' if s.get("short") else ''}
    </div>
    <div class="tier">{esc_attr(s.get('tier'))}</div>
    <div class="tag">{esc_attr(s.get('tagline'))}</div>
    {official_block(s, web, verified_at)}
  </div>
  <article class="article">{content_html}</article>
</div>"""
    return page(s["name"], body, active="schools", base="../",
                desc=f"{s['name']}（{s['district']}{s['level']}，{s['type']}）：{s.get('tagline','')}")


# ============================================================ 主流程
def main():
    with open(INDEX, encoding="utf-8") as f:
        d = json.load(f)

    # 官网/公众号核查结果（缺失时退化为「无记录」，不影响构建）
    web, verified_at, web_counts = {}, "", {}
    if os.path.isfile(WEBFILE):
        payload = json.load(open(WEBFILE, encoding="utf-8"))
        web = payload.get("schools", {})
        web_counts = payload.get("counts", {})
        verified_at = payload.get("verified") or payload.get("updated") or ""
    else:
        print("提示：未找到 data/school_websites.json，详情页将不显示官方渠道")

    # 详情页 URL：学段-校名.html（校名跨学段可能重名，故加学段前缀）
    for s in d["schools"]:
        s["url"] = f"schools/{quote(s['level'] + '-' + s['name'])}.html"

    slim = [{k: s.get(k) for k in
             ("name", "short", "district", "level", "type", "tier", "tagline", "url")}
            for s in d["schools"]]

    # 重建输出目录（先清后建，避免残留旧页面）
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(os.path.join(SITE, "assets"))
    os.makedirs(os.path.join(SITE, "schools"))

    def w(rel, content):
        path = os.path.join(SITE, rel)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    # 资产原样拷贝（单一来源在仓库 assets/，脚本内不再保留副本）
    for name in ("tokens.css", "site.css", "app.js"):
        src = os.path.join(ASSETS, name)
        if not os.path.isfile(src):
            raise SystemExit(f"缺少资源文件：{src}")
        shutil.copyfile(src, os.path.join(SITE, "assets", name))

    w("index.html", build_home(d, slim))
    w("schools.html", build_schools(d, slim))
    w("about.html", build_about(d, web_counts))
    for s in d["schools"]:
        w(f"schools/{s['level']}-{s['name']}.html", build_detail(s, web, verified_at))

    # sitemap 只在提供 NJ_BASE_URL 时生成：sitemap 协议要求绝对地址，
    # 没有基址时宁可不出，也不产出带占位符的无效文件（此前 207 处 {BASE} 即为该缺陷）。
    urls = ["", "schools.html", "about.html"] + [s["url"] for s in d["schools"]]
    if BASE_URL:
        w("sitemap.xml",
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "\n".join(f"  <url><loc>{BASE_URL}/{u}</loc>"
                      f"<lastmod>{TODAY}</lastmod></url>" for u in urls)
          + "\n</urlset>\n")
        robots = "User-agent: *\nAllow: /\n\nSitemap: " + BASE_URL + "/sitemap.xml\n"
    else:
        robots = "User-agent: *\nAllow: /\n"
    w("robots.txt", robots)

    print(f"已生成网站：{SITE}")
    print(f"  页面：index / schools / about + {len(d['schools'])} 个学校详情页")
    if BASE_URL:
        print(f"  sitemap：{len(urls)} 条（基址 {BASE_URL}）")
    else:
        print("  sitemap：未生成（未设置 NJ_BASE_URL；部署时由 CI 注入后生成）")


if __name__ == "__main__":
    main()
