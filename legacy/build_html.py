# -*- coding: utf-8 -*-
"""生成南京学校综合报告 HTML"""
import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_high import (
    CONTROL_LINES, PLAN_2026, TOP_SCHOOLS_LINE, OTHER_SCHOOLS_LINE_2026,
    FOUR_STAR, HIGH_SCHOOLS,
)
from data_mid import (
    XSC_POLICY, XSC_TIMELINE_2026, PRIVATE_MIDDLE, PUBLIC_PAIWEI,
    MIDDLE_SCHOOLS, MIDDLE_TIERS,
)
from data_pri import PRIMARY_TIERS, PRIMARY_SCHOOLS
from data_policy import ZHONGKAO_POLICY, INDICATOR_STUDENT, SOURCES, CRED_NOTE, TRENDS

OUT = "/Users/kongc/WorkBuddy/南京学校/南京中小学全景档案.html"


def e(x):
    return html.escape(str(x)) if x is not None else ""


def cred_badge(level):
    lv = (level or "")[:1]
    cls = {"A": "cred-a", "B": "cred-b", "C": "cred-c"}.get(lv, "cred-c")
    return f'<span class="badge {cls}" title="{e(level)}">{e(lv)}</span>'


def type_badge(t):
    cls = "t-private" if "民办" in str(t) else "t-public"
    return f'<span class="badge {cls}">{e(t)}</span>'


# ------------------------------------------------------------------ 排名表
def table_high_lines():
    rows = []
    for i, (sch, camp, y26, y25, y24, y23, cred) in enumerate(TOP_SCHOOLS_LINE, 1):
        cells = "".join(
            f"<td>{e(v)}</td>" if v else '<td class="na">—</td>'
            for v in (y26, y25, y24, y23)
        )
        rows.append(
            f'<tr><td class="rn">{i}</td><td class="sname">{e(sch)}</td><td>{e(camp)}</td>'
            f'{cells}<td>{cred_badge(cred)}</td></tr>'
        )
    return f"""
    <div class="tw"><table class="tbl">
      <thead><tr><th>#</th><th>学校</th><th>校区</th><th>2026</th><th>2025</th><th>2024</th><th>2023</th><th>信度</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table></div>"""


def table_other_lines():
    rows = []
    for i, (sch, camp, sc, cred) in enumerate(OTHER_SCHOOLS_LINE_2026, 13):
        rows.append(
            f'<tr><td class="rn">{i}</td><td class="sname">{e(sch)}</td><td>{e(camp)}</td>'
            f'<td class="hl">{sc}</td><td>{cred_badge(cred)}</td></tr>'
        )
    return f"""
    <div class="tw"><table class="tbl">
      <thead><tr><th>#</th><th>学校</th><th>校区/类别</th><th>2026投档线</th><th>信度</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table></div>"""


def table_plan():
    rows = []
    for i, (n, p, d) in enumerate(PLAN_2026["各校计划"], 1):
        rows.append(f'<tr><td class="rn">{i}</td><td class="sname">{e(n)}</td><td class="hl">{p}</td><td>{e(d)}</td></tr>')
    return f"""
    <div class="tw"><table class="tbl">
      <thead><tr><th>#</th><th>学校</th><th>2026计划(人)</th><th>较去年</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table></div>"""


def table_cr():
    rows = []
    for y in ("2026", "2025"):
        d = CONTROL_LINES[y]
        items = [(k, v) for k, v in d.items() if k not in ("来源", "可信度")]
        rows.append(
            f'<tr><td class="hl">{e(y)}</td><td class="sname">中考总分</td><td>{e(d.get("中考总分",""))}</td></tr>'
        )
        for k, v in items:
            if k == "中考总分":
                continue
            rows.append(f'<tr><td></td><td>{e(k)}</td><td class="hl">{e(v)}</td></tr>')
    return f"""
    <div class="tw"><table class="tbl">
      <thead><tr><th>年份</th><th>类别</th><th>分值/说明</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table></div>"""


def table_private_middle():
    rows = []
    for n, d, p26, p25, fee, note in PRIVATE_MIDDLE:
        fee_s = e(fee) if fee != "—" else '<span class="na">待公布</span>'
        rows.append(
            f'<tr><td class="sname">{e(n)}</td><td>{e(d)}</td>'
            f'<td class="hl">{e(p26) if p26 else "—"}</td>'
            f'<td>{e(p25) if p25 else "—"}</td>'
            f'<td>{fee_s}</td><td class="note">{e(note)}</td></tr>'
        )
    return f"""
    <div class="tw"><table class="tbl">
      <thead><tr><th>学校</th><th>区</th><th>2026摇号计划</th><th>2025摇号计划</th><th>学费(元/学期)</th><th>备注</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table></div>"""


def table_public_paiwei():
    rows = []
    for d, n, p in PUBLIC_PAIWEI:
        rows.append(f'<tr><td>{e(d)}</td><td class="sname">{e(n)}</td><td class="hl">{e(p) if p else "有"}</td></tr>')
    return f"""
    <div class="tw"><table class="tbl">
      <thead><tr><th>区</th><th>学校</th><th>2026派位计划(人)</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table></div>"""


# ------------------------------------------------------------------ 档案卡
def card_high(s):
    return f"""
    <article class="card" data-search="{e(s['name'])} {e(s.get('short',''))} {e(s['district'])} {e(s['type'])}">
      <header class="card-hd">
        <h3>{e(s['name'])} <small>{e(s.get('short',''))}</small></h3>
        <div class="tags">{type_badge(s['type'])}<span class="badge d">{e(s['district'])}</span>{cred_badge(s['cred'])}</div>
      </header>
      <dl class="fields">
        <div><dt>建校</dt><dd>{e(s.get('founded','—'))}</dd></div>
        <div><dt>校区</dt><dd>{e(s.get('campuses','—'))}</dd></div>
        <div class="full"><dt>层次/资质</dt><dd>{e(s.get('level','—'))}</dd></div>
        <div class="full"><dt>办学特色</dt><dd>{e(s.get('feature','—'))}</dd></div>
        <div class="full"><dt>师资力量</dt><dd>{e(s.get('faculty','—'))}</dd></div>
        <div class="full"><dt>招生计划</dt><dd>{e(s.get('enroll','—'))}</dd></div>
        <div class="full"><dt>中考录取线</dt><dd class="hl">{e(s.get('line','—'))}</dd></div>
        <div class="full"><dt>高考表现</dt><dd>{e(s.get('gaokao','—'))}</dd></div>
        <div class="full"><dt>信息来源</dt><dd class="src">{e(s.get('source','—'))}</dd></div>
      </dl>
    </article>"""


def card_mid(s):
    return f"""
    <article class="card" data-search="{e(s['name'])} {e(s.get('short',''))} {e(s['district'])} {e(s['type'])} {e(s.get('tier',''))}">
      <header class="card-hd">
        <h3>{e(s['name'])}</h3>
        <div class="tags">{type_badge(s['type'])}<span class="badge d">{e(s['district'])}</span><span class="badge tier">{e(s.get('tier',''))}</span>{cred_badge(s['cred'])}</div>
      </header>
      <dl class="fields">
        <div class="full"><dt>办学特色</dt><dd>{e(s.get('feature','—'))}</dd></div>
        <div class="full"><dt>施教区/招生</dt><dd>{e(s.get('enroll','—'))}</dd></div>
        <div class="full"><dt>2026中考成绩</dt><dd class="hl">{e(s.get('perf2026','—'))}</dd></div>
        <div class="full"><dt>2025中考成绩</dt><dd>{e(s.get('perf2025','—'))}</dd></div>
        <div class="full"><dt>信息来源</dt><dd class="src">{e(s.get('source','—'))}</dd></div>
      </dl>
    </article>"""


def card_pri(s):
    return f"""
    <article class="card" data-search="{e(s['name'])} {e(s.get('short',''))} {e(s['district'])} {e(s['type'])} {e(s.get('tier',''))}">
      <header class="card-hd">
        <h3>{e(s['name'])} <small>{e(s.get('short',''))}</small></h3>
        <div class="tags">{type_badge(s['type'])}<span class="badge d">{e(s['district'])}</span><span class="badge tier">{e(s.get('tier',''))}</span>{cred_badge(s['cred'])}</div>
      </header>
      <dl class="fields">
        <div><dt>建校</dt><dd>{e(s.get('founded','—'))}</dd></div>
        <div class="full"><dt>办学特色</dt><dd>{e(s.get('feature','—'))}</dd></div>
        <div class="full"><dt>师资力量</dt><dd>{e(s.get('faculty','—'))}</dd></div>
        <div class="full"><dt>施教区范围</dt><dd>{e(s.get('enroll','—'))}</dd></div>
        <div class="full"><dt>升学表现</dt><dd class="hl">{e(s.get('perf','—'))}</dd></div>
        <div class="full"><dt>信息来源</dt><dd class="src">{e(s.get('source','—'))}</dd></div>
      </dl>
    </article>"""


# ------------------------------------------------------------------ 梯队渲染
def tiers_block(tiers):
    out = []
    for zone, lvls in tiers.items():
        inner = []
        for lv, items in lvls.items():
            lis = "".join(
                f'<li><b>{e(x["name"])}</b>{("：" + e(x["note"])) if x.get("note") else ""}</li>'
                for x in items
            )
            inner.append(f'<div class="tier"><h4>{e(lv)}</h4><ul>{lis}</ul></div>')
        out.append(f'<section class="zone"><h3 class="zone-h">{e(zone)}</h3>{"".join(inner)}</section>')
    return "".join(out)


def middle_tiers_block():
    out = []
    for lv, names in MIDDLE_TIERS.items():
        lis = "".join(f"<li>{e(n)}</li>" for n in names)
        out.append(f'<section class="zone"><h3 class="zone-h">{e(lv)}</h3><ul class="names">{lis}</ul></section>')
    return "".join(out)


# ------------------------------------------------------------------ 组装
def build():
    high_cards = "".join(card_high(s) for s in HIGH_SCHOOLS)
    mid_cards = "".join(card_mid(s) for s in MIDDLE_SCHOOLS)
    pri_cards = "".join(card_pri(s) for s in PRIMARY_SCHOOLS)

    four_star_lis = "".join(f"<li>{e(n)}</li>" for n in FOUR_STAR)

    xsc_pol = "".join(f'<div class="li"><b>{e(a)}</b><p>{e(b)}</p></div>' for a, b in XSC_POLICY)
    zk_pol = "".join(f'<div class="li"><b>{e(a)}</b><p>{e(b)}</p></div>' for a, b in ZHONGKAO_POLICY)
    ind = "".join(f'<div class="li"><b>{e(a)}</b><p>{e(b)}</p></div>' for a, b in INDICATOR_STUDENT)
    tl = "".join(f'<li><span class="tl-d">{e(a)}</span><span class="tl-c">{e(b)}</span></li>' for a, b in XSC_TIMELINE_2026)
    trends = "".join(f'<div class="li"><b>{e(a)}</b><p>{e(b)}</p></div>' for a, b in TRENDS)
    src_rows = "".join(
        f'<tr><td class="sname">{e(a)}</td><td>{e(b)}</td><td>{cred_badge(c)}</td></tr>' for a, b, c in SOURCES
    )
    cred_note = "".join(f"<p>{e(l)}</p>" for l in CRED_NOTE.strip().split("\n") if l.strip())

    css = """
:root{
  --bg:#f6f7f9; --panel:#ffffff; --ink:#1a1d21; --ink2:#4a5058; --ink3:#7c848e;
  --line:#e4e7ec; --line2:#eef1f4;
  --brand:#1f4ed8; --brand-soft:#eef2ff;
  --a:#0f7b4f; --a-bg:#e6f5ee;
  --b:#9a6400; --b-bg:#fdf3e0;
  --c:#b3261e; --c-bg:#fdeceb;
  --hl:#c0392b;
  --radius:10px;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:15px;line-height:1.72;-webkit-font-smoothing:antialiased;
}
a{color:var(--brand);text-decoration:none}
.wrap{max-width:1180px;margin:0 auto;padding:0 22px}

/* header */
.hero{background:linear-gradient(160deg,#182848 0%,#2b4a8b 55%,#1f4ed8 100%);color:#fff;padding:52px 0 44px}
.hero h1{margin:0 0 10px;font-size:32px;letter-spacing:.5px;font-weight:700}
.hero p{margin:0;color:#c8d6ef;font-size:15px;max-width:820px}
.hero .meta{margin-top:20px;display:flex;flex-wrap:wrap;gap:10px}
.hero .meta span{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.22);padding:5px 13px;border-radius:20px;font-size:13px}

/* nav */
nav{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.94);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
nav .wrap{display:flex;gap:4px;overflow-x:auto;align-items:center;height:54px}
nav a{padding:8px 15px;border-radius:8px;color:var(--ink2);font-size:14px;white-space:nowrap;font-weight:500}
nav a:hover{background:var(--brand-soft);color:var(--brand)}
.search{margin-left:auto;position:relative}
.search input{
  width:230px;padding:8px 13px 8px 33px;border:1px solid var(--line);border-radius:20px;
  font-size:13.5px;outline:none;background:#fff;color:var(--ink);font-family:inherit;
}
.search input:focus{border-color:var(--brand);box-shadow:0 0 0 3px var(--brand-soft)}
.search::before{content:"⌕";position:absolute;left:12px;top:6px;color:var(--ink3);font-size:16px}

/* sections */
main{padding:34px 0 70px}
section.blk{margin-bottom:46px;scroll-margin-top:70px}
h2.sect{
  font-size:22px;margin:0 0 6px;padding-left:13px;border-left:4px solid var(--brand);
  font-weight:700;letter-spacing:.3px;
}
.sect-sub{color:var(--ink3);font-size:13.5px;margin:0 0 20px;padding-left:17px}

.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:20px 22px;margin-bottom:18px}
.panel h3{font-size:16px;margin:0 0 14px;font-weight:600}
.panel h3 small{font-weight:400;color:var(--ink3);font-size:13px;margin-left:8px}

/* cards grid */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(430px,1fr));gap:16px}
@media(max-width:920px){.grid{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px;transition:.16s}
.card:hover{border-color:#c9d3e8;box-shadow:0 4px 18px rgba(31,78,216,.07)}
.card-hd{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;border-bottom:1px solid var(--line2);padding-bottom:11px;margin-bottom:13px}
.card-hd h3{margin:0;font-size:16.5px;font-weight:650;line-height:1.4}
.card-hd h3 small{font-weight:400;color:var(--ink3);font-size:13px;margin-left:4px}
.tags{display:flex;gap:5px;flex-wrap:wrap;align-items:center}

.badge{display:inline-block;font-size:11.5px;padding:2px 8px;border-radius:5px;font-weight:600;letter-spacing:.2px;white-space:nowrap}
.t-public{background:#e8f1fd;color:#1a5fb4}
.t-private{background:#fdf0e3;color:#a8560a}
.d{background:#eef1f4;color:var(--ink2)}
.tier{background:#f0ecfd;color:#5b3fa8}
.cred-a{background:var(--a-bg);color:var(--a)}
.cred-b{background:var(--b-bg);color:var(--b)}
.cred-c{background:var(--c-bg);color:var(--c)}

.fields{margin:0;display:grid;grid-template-columns:1fr 1fr;gap:9px 18px}
@media(max-width:560px){.fields{grid-template-columns:1fr}}
.fields .full{grid-column:1/-1}
.fields dt{font-size:12px;color:var(--ink3);font-weight:600;margin-bottom:1px;letter-spacing:.3px}
.fields dd{margin:0;font-size:13.5px;color:var(--ink);line-height:1.68}
.fields dd.hl{color:var(--hl);font-weight:600}
.fields dd.src{color:var(--ink3);font-size:12.5px}

/* tables */
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:var(--radius);background:#fff}
table.tbl{width:100%;border-collapse:collapse;font-size:13.5px;min-width:560px}
table.tbl th{background:#f4f6f9;text-align:left;padding:10px 13px;font-weight:600;font-size:12.5px;color:var(--ink2);border-bottom:1px solid var(--line);white-space:nowrap;letter-spacing:.3px}
table.tbl td{padding:9px 13px;border-bottom:1px solid var(--line2);vertical-align:top}
table.tbl tbody tr:last-child td{border-bottom:none}
table.tbl tbody tr:hover{background:#fafbfd}
td.rn{color:var(--ink3);font-variant-numeric:tabular-nums;width:38px}
td.sname{font-weight:600;white-space:nowrap}
td.hl{color:var(--hl);font-weight:600}
td.na{color:#c3c9d1}
td.note{color:var(--ink2);font-size:12.5px}

/* tiers */
.zone{margin-bottom:22px}
.zone-h{font-size:15px;margin:0 0 11px;color:var(--brand);font-weight:650;padding-bottom:6px;border-bottom:1px dashed var(--line)}
.tier{margin-bottom:14px;padding-left:12px;border-left:2px solid var(--line2)}
.tier h4{margin:0 0 6px;font-size:13.5px;color:var(--ink2);font-weight:600}
.tier ul,.names{margin:0;padding-left:19px;font-size:13.5px;color:var(--ink);line-height:1.78}
.names{columns:2;column-gap:26px}
@media(max-width:700px){.names{columns:1}}
.tier li{margin-bottom:2px}

/* list blocks */
.li{padding:11px 0;border-bottom:1px solid var(--line2)}
.li:last-child{border-bottom:none}
.li b{display:block;font-size:13.5px;color:var(--ink);margin-bottom:3px;font-weight:650}
.li p{margin:0;font-size:13.5px;color:var(--ink2);line-height:1.72}

ol.timeline{list-style:none;margin:0;padding:0;position:relative}
ol.timeline::before{content:"";position:absolute;left:74px;top:6px;bottom:6px;width:2px;background:var(--line)}
ol.timeline li{display:flex;gap:16px;padding:7px 0;position:relative}
ol.timeline li::before{content:"";position:absolute;left:69px;top:14px;width:12px;height:12px;border-radius:50%;background:#fff;border:2px solid var(--brand)}
.tl-d{width:64px;flex:none;font-size:12.5px;color:var(--brand);font-weight:600;text-align:right;line-height:1.6}
.tl-c{font-size:13.5px;color:var(--ink2);line-height:1.7;padding-left:10px}

.callout{background:#fff8e6;border:1px solid #f2dfae;border-left:4px solid #d99b12;border-radius:8px;padding:14px 18px;font-size:13.5px;color:#6b4e08;line-height:1.75}
.callout p{margin:0 0 7px}
.callout p:last-child{margin-bottom:0}

footer{border-top:1px solid var(--line);padding:26px 0 40px;color:var(--ink3);font-size:12.5px;text-align:center;line-height:1.9}
.hide{display:none !important}
.count-note{font-size:12.5px;color:var(--ink3);margin:0 0 14px}
"""

    js = """
document.addEventListener('input',e=>{
  if(e.target.id!=='search') return;
  const q=e.target.value.trim().toLowerCase();
  document.querySelectorAll('.card').forEach(c=>{
    const s=(c.dataset.search||'').toLowerCase();
    c.classList.toggle('hide', q && !s.includes(q));
  });
  document.querySelectorAll('.grid').forEach(g=>{
    const vis=[...g.querySelectorAll('.card')].some(c=>!c.classList.contains('hide'));
    g.closest('section')?.querySelectorAll('.empty')?.forEach(x=>x.classList.toggle('hide',vis));
  });
});
document.querySelectorAll('nav a').forEach(a=>{
  a.addEventListener('click',ev=>{
    ev.preventDefault();
    document.querySelector(a.getAttribute('href'))?.scrollIntoView({behavior:'smooth',block:'start'});
  });
});
"""

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>南京市中小学全景档案 · 小升初与中考择校数据报告</title>
<style>{css}</style>
</head>
<body>

<div class="hero">
  <div class="wrap">
    <h1>南京市中小学全景档案</h1>
    <p>覆盖南京全市小学、初中、高中的学校信息档案，含办学特色、师资与招生范围、历年小升初与中考表现、综合排名，并标注每项数据的来源与可信度。</p>
    <div class="meta">
      <span>数据截止 2026年10月</span>
      <span>高中档案 {len(HIGH_SCHOOLS)} 所</span>
      <span>初中档案 {len(MIDDLE_SCHOOLS)} 所</span>
      <span>小学档案 {len(PRIMARY_SCHOOLS)} 所</span>
      <span>覆盖 11 区 + 江北新区</span>
      <span>信度分级 A / B / C</span>
    </div>
  </div>
</div>

<nav>
  <div class="wrap">
    <a href="#overview">概览</a>
    <a href="#high">高中</a>
    <a href="#middle">初中</a>
    <a href="#primary">小学</a>
    <a href="#policy">政策</a>
    <a href="#source">来源与可信度</a>
    <div class="search"><input id="search" type="search" placeholder="搜索学校 / 区 / 梯队…"></div>
  </div>
</nav>

<main class="wrap">

<!-- ============ 概览 ============ -->
<section class="blk" id="overview">
  <h2 class="sect">概览与关键结论</h2>
  <p class="sect-sub">2026年南京高中阶段招生格局与择校核心判断</p>

  <div class="panel">
    <h3>2026年南京中考基本盘 <small>来源：市招考院 / 南京市人民政府，A级</small></h3>
    <dl class="fields">
      <div><dt>中考总分</dt><dd>700 分</dd></div>
      <div><dt>考生人数</dt><dd>74,876 人</dd></div>
      <div><dt>普高计划</dt><dd>53,439 人（较去年 +6,101）</dd></div>
      <div><dt>普高学位供给率</dt><dd class="hl">71.3%（首次突破 70%）</dd></div>
      <div><dt>一批次控制线（原市区+浦口）</dt><dd>535 分</dd></div>
      <div><dt>指标生控制线（原市区+浦口）</dt><dd>593 分</dd></div>
      <div><dt>面向全市招生的普高</dt><dd>13 所</dd></div>
      <div><dt>四星级高中（省级认定）</dt><dd>35 所（南京）</dd></div>
    </dl>
  </div>

  <div class="panel">
    <h3>七大趋势判断</h3>
    {trends}
  </div>

  <div class="callout">
    <p><b>使用提示：</b>南京从未发布过官方的中小学排名。本报告中的「排名」为综合官方投档线（高中）与家长圈/学校宣讲会口径（初中、小学）整理，已逐条标注来源与可信度。择校决策请以官方发布为准，并结合孩子实际情况。</p>
  </div>
</section>

<!-- ============ 高中 ============ -->
<section class="blk" id="high">
  <h2 class="sect">高中</h2>
  <p class="sect-sub">全市普通高中投档线、招生计划、高考表现与办学特色</p>

  <div class="panel">
    <h3>六大名校 12 校区近四年投档线走势 <small>来源：市招考院官方公布，A级</small></h3>
    <p class="count-note">分数每年波动，<b>位次比分数更稳定</b>。2026年因普高大幅扩招，部分学校录取位次出现一定程度下移。</p>
    {table_high_lines()}
  </div>

  <div class="panel">
    <h3>2026年第一批次其余高中投档线（13 名以后） <small>来源：多渠道汇总，B/C级，存在个别冲突</small></h3>
    <p class="count-note">红色为投档线。此表为渠道汇总值，个别学校与机构口径存在分歧，详见文末「已知数据冲突提示」。</p>
    {table_other_lines()}
  </div>

  <div class="panel">
    <h3>2026年面向全市招生的 13 所普高招生计划 <small>来源：《2026年南京市中考指南》，A级</small></h3>
    <p class="count-note">全市普高计划 {PLAN_2026['全市普高计划']} 人，较去年增加 {PLAN_2026['较去年增加']} 人。</p>
    {table_plan()}
  </div>

  <div class="panel">
    <h3>投档控制分数线一览（2026 / 2025） <small>来源：市招考院，A级</small></h3>
    {table_cr()}
  </div>

  <div class="panel">
    <h3>江苏省四星级普通高中（南京，共 35 所） <small>来源：江苏省教育厅名单，A级</small></h3>
    <ul class="names">{four_star_lis}</ul>
  </div>

  <h3 style="font-size:17px;margin:30px 0 14px;padding-left:13px;border-left:4px solid var(--brand)">高中学校档案</h3>
  <div class="grid">{high_cards}</div>
</section>

<!-- ============ 初中 ============ -->
<section class="blk" id="middle">
  <h2 class="sect">初中</h2>
  <p class="sect-sub">中考成绩表现、施教区范围、民办招生计划与学费</p>

  <div class="callout" style="margin-bottom:18px">
    <p><b>关于初中排名：</b>南京初中没有官方排名。下表梯队为家长圈共识 + 2025/2026 中考网传数据 + 学校宣讲会披露数据综合整理（C级可信度），仅用于判断格局，具体以各校官方发布为准。</p>
  </div>

  <div class="panel">
    <h3>初中综合梯队（民间口径）</h3>
    {middle_tiers_block()}
  </div>

  <div class="panel">
    <h3>民办初中摇号计划与学费（2026） <small>来源：各区教育局派位方案 + 培训机构汇总，B/C级</small></h3>
    <p class="count-note">2026年热门民办校摇号计划普遍上涨，「—」表示该渠道未获取到具体数值。</p>
    {table_private_middle()}
  </div>

  <div class="panel">
    <h3>热点公办初中电脑派位计划（部分） <small>来源：各区教育局派位方案，A级</small></h3>
    {table_public_paiwei()}
  </div>

  <h3 style="font-size:17px;margin:30px 0 14px;padding-left:13px;border-left:4px solid var(--brand)">初中学校档案</h3>
  <div class="grid">{mid_cards}</div>
</section>

<!-- ============ 小学 ============ -->
<section class="blk" id="primary">
  <h2 class="sect">小学</h2>
  <p class="sect-sub">各区梯队分布、办学特色、施教区范围与对口初中</p>

  <div class="callout" style="margin-bottom:18px">
    <p><b>关于小学排名：</b>南京小学同样没有官方排名。梯队划分结合家长口碑、南外录取数据与民间评价整理（C级可信度）。施教区范围来自各区教育局公示（A级）。</p>
  </div>

  <div class="panel">
    <h3>各区小学梯队分布</h3>
    {tiers_block(PRIMARY_TIERS)}
  </div>

  <h3 style="font-size:17px;margin:30px 0 14px;padding-left:13px;border-left:4px solid var(--brand)">重点小学详细档案</h3>
  <div class="grid">{pri_cards}</div>
</section>

<!-- ============ 政策 ============ -->
<section class="blk" id="policy">
  <h2 class="sect">政策</h2>
  <p class="sect-sub">2026年小升初与中考核心政策要点</p>

  <div class="panel">
    <h3>2026年小升初政策要点 <small>来源：《2026年全市义务教育招生入学工作实施意见》，A级</small></h3>
    {xsc_pol}
  </div>

  <div class="panel">
    <h3>2026年小升初时间轴 <small>来源：市教育局，A级</small></h3>
    <ol class="timeline">{tl}</ol>
  </div>

  <div class="panel">
    <h3>2026年中考招生政策 <small>来源：南京市2026年中考招生政策问答，A级</small></h3>
    {zk_pol}
  </div>

  <div class="panel">
    <h3>指标生政策详解（小升初择校的关键变量） <small>来源：市教育局、江苏教育黄页等，A/B级</small></h3>
    {ind}
  </div>
</section>

<!-- ============ 来源 ============ -->
<section class="blk" id="source">
  <h2 class="sect">数据来源与可信度</h2>
  <p class="sect-sub">所有数据的出处与分级说明</p>

  <div class="callout" style="margin-bottom:18px">{cred_note}</div>

  <div class="panel">
    <h3>来源清单</h3>
    <div class="tw"><table class="tbl">
      <thead><tr><th>来源</th><th>主要采集内容</th><th>信度</th></tr></thead>
      <tbody>{src_rows}</tbody>
    </table></div>
  </div>
</section>

</main>

<footer>
  <div class="wrap">
    南京市中小学全景档案 · 数据截止 2026年10月 · 由公开渠道整理，仅供参考<br>
    官方信息请以南京市教育局（edu.nanjing.gov.cn）及各区政府、教育局官网发布为准
  </div>
</footer>

<script>{js}</script>
</body>
</html>
"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)
    print("HTML 已生成:", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    build()
