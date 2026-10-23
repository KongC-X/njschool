# -*- coding: utf-8 -*-
"""
从 index.json 生成《南京中小学全景档案.html》——单文件可筛选网页。

数据源：index.json
特性：零依赖、单文件、支持搜索/多维筛选、浅色与深色自适应、移动端可用。
"""
import json
import os

ROOT = "/Users/kongc/WorkBuddy/南京学校"
INDEX = os.path.join(ROOT, "index.json")
OUT = os.path.join(ROOT, "南京中小学全景档案.html")

LEVELS = ["小学", "初中", "高中"]

CSS = """
:root{
  --bg:#f7f8fa; --panel:#ffffff; --text:#1a1d23; --muted:#6b7280;
  --line:#e5e7eb; --accent:#2563eb; --accent-soft:#eff6ff;
  --b1:#dcfce7; --b2:#fee2e2; --b3:#fef3c7;
  --t1:#15803d; --t2:#b91c1c; --t3:#a16207;
  --shadow:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.1);
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0f1115; --panel:#171a21; --text:#e6e8eb; --muted:#9aa3af;
    --line:#272b34; --accent:#60a5fa; --accent-soft:#1e293b;
    --b1:#14351f; --b2:#3b1d1d; --b3:#3a2f10;
    --t1:#86efac; --t2:#fca5a5; --t3:#fcd34d;
    --shadow:0 1px 2px rgba(0,0,0,.4);
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font:15px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 64px}
header h1{font-size:26px;margin:0 0 6px;letter-spacing:-.02em}
header .sub{color:var(--muted);font-size:13.5px;margin-bottom:18px}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:10px 16px;box-shadow:var(--shadow)}
.stat b{display:block;font-size:20px;line-height:1.2}
.stat span{font-size:12px;color:var(--muted)}
.controls{position:sticky;top:0;z-index:10;background:var(--bg);
  padding:12px 0 14px;border-bottom:1px solid var(--line);margin-bottom:18px}
#q{width:100%;padding:11px 14px;font-size:15px;border:1px solid var(--line);
  border-radius:10px;background:var(--panel);color:var(--text);outline:none}
#q:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.frow{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-top:12px}
.fgroup{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.flabel{font-size:12px;color:var(--muted);margin-right:2px}
.chip{font-size:13px;padding:5px 11px;border-radius:999px;cursor:pointer;
  border:1px solid var(--line);background:var(--panel);color:var(--text);
  user-select:none;transition:.12s}
.chip:hover{border-color:var(--accent)}
.chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
.count{font-size:13px;color:var(--muted);margin-bottom:14px}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(330px,1fr))}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:14px 16px;box-shadow:var(--shadow);transition:.15s}
.card:hover{border-color:var(--accent);transform:translateY(-1px)}
.card h3{margin:0 0 8px;font-size:16px;letter-spacing:-.01em}
.badges{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.b{font-size:11.5px;padding:2px 8px;border-radius:6px;font-weight:600}
.b-lv{background:var(--accent-soft);color:var(--accent)}
.b-t1{background:var(--b1);color:var(--t1)}
.b-t2{background:var(--b2);color:var(--t2)}
.b-t3{background:var(--b3);color:var(--t3)}
.b-d{background:transparent;color:var(--muted);border:1px solid var(--line);font-weight:500}
.tier{font-size:12.5px;color:var(--muted);margin-bottom:6px}
.tag{font-size:13.5px;color:var(--text);opacity:.88}
.card a{display:inline-block;margin-top:10px;font-size:12.5px;color:var(--accent);
  text-decoration:none;border-bottom:1px dotted currentColor}
.empty{text-align:center;color:var(--muted);padding:60px 0;font-size:14px}
footer{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);
  font-size:12.5px;color:var(--muted);line-height:1.9}
@media (max-width:640px){
  .wrap{padding:18px 14px 48px}
  header h1{font-size:21px}
  .grid{grid-template-columns:1fr}
  .stat{padding:8px 13px}
  .stat b{font-size:17px}
}
"""

JS = """
const DATA = __DATA__;
const state = {q:'', lv:'', dist:'', type:''};
const $ = s => document.querySelector(s);
const grid = $('#grid'), cnt = $('#count');

function chips(el, key, values, allLabel){
  const box = document.getElementById(el);
  const mk = (v,label)=>{
    const b=document.createElement('button');
    b.className='chip'+(v===state[key]?' on':''); b.textContent=label; b.dataset.v=v;
    b.onclick=()=>{ state[key]=v;
      [...box.children].forEach(c=>c.classList.toggle('on', c.dataset.v===v));
      render(); };
    return b;
  };
  box.appendChild(mk('', allLabel));
  values.forEach(v=>box.appendChild(mk(v,v)));
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
  if(!rows.length){ grid.innerHTML='<div class="empty">没有匹配的学校，试试换个关键词或清空筛选。</div>'; return; }
  grid.innerHTML = rows.map(s=>{
    const t = s.type==='民办' ? 'b-t2' : 'b-t1';
    return `<div class="card">
      <h3>${esc(s.name)}</h3>
      <div class="badges">
        <span class="b b-lv">${esc(s.level)}</span>
        <span class="b ${t}">${esc(s.type)}</span>
        <span class="b b-d">${esc(s.district)}</span>
        ${s.short?`<span class="b b-d">${esc(s.short)}</span>`:''}
      </div>
      <div class="tier">${esc(s.tier||'')}</div>
      <div class="tag">${esc(s.tagline||'')}</div>
      <a href="${encodeURI(s.file)}" target="_blank" rel="noopener">查看完整档案 →</a>
    </div>`;
  }).join('');
}
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

$('#q').addEventListener('input', e=>{ state.q=e.target.value; render(); });
chips('f-lv','lv',['小学','初中','高中'],'全部');
chips('f-dist','dist',__DISTRICTS__,'全部');
chips('f-type','type',['公办','民办'],'不限');
render();
"""


def build():
    with open(INDEX, encoding="utf-8") as f:
        d = json.load(f)
    schools = d["schools"]
    cov = d["coverage"]
    districts = d["districts"]

    slim = [
        {
            "name": s["name"], "short": s.get("short"), "district": s["district"],
            "level": s["level"], "type": s["type"], "tier": s.get("tier"),
            "file": s["file"], "tagline": s.get("tagline"),
        }
        for s in schools
    ]
    data_js = json.dumps(slim, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    dist_js = json.dumps(districts, ensure_ascii=False)

    js = JS.replace("__DATA__", data_js).replace("__DISTRICTS__", dist_js)

    stat_cards = "".join(
        f'<div class="stat"><b>{n}</b><span>{k}</span></div>'
        for k, n in [
            ("收录学校总数", len(schools)),
            ("小学", cov.get("小学", 0)),
            ("初中", cov.get("初中", 0)),
            ("高中", cov.get("高中", 0)),
            ("覆盖行政区", len(districts)),
        ]
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>南京中小学全景档案（{len(schools)} 所）</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>南京中小学全景档案</h1>
    <div class="sub">公开信息汇编 · 数据版本 {d.get('version','—')} · 更新 {d.get('updated','—')} · 每所均标注信度与数据缺口</div>
    <div class="stats">{stat_cards}</div>
  </header>

  <div class="controls">
    <input id="q" type="search" placeholder="搜索学校名称、简称、梯队或关键词……">
    <div class="frow">
      <div class="fgroup"><span class="flabel">学段</span><span id="f-lv" style="display:contents"></span></div>
      <div class="fgroup"><span class="flabel">行政区</span><span id="f-dist" style="display:contents"></span></div>
      <div class="fgroup"><span class="flabel">性质</span><span id="f-type" style="display:contents"></span></div>
    </div>
  </div>

  <div class="count" id="count"></div>
  <div class="grid" id="grid"></div>

  <footer>
    <strong>数据说明</strong>：全部来自公开渠道（政府/教育局官网、学校官网与官方公众号、党报与权威媒体）。
    信度标注 <code>[A]</code> 官方发布、<code>[B]</code> 权威媒体、<code>[C]</code> 家长圈口径。<br>
    <strong>免责声明</strong>：本页仅为公开信息汇编，<strong>不构成择校建议</strong>；政策与数据每年变动，请以官方最新发布为准。
    家长圈统计的中考升学率不可作为唯一依据。<br>
    <strong>数据缺口</strong>：各档案末节列明未获取字段——那是「查不到」，不是「零」。
  </footer>
</div>
<script>{js}</script>
</body>
</html>
"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成：{OUT}")
    print(f"  收录 {len(schools)} 所，{len(html)} 字符")


if __name__ == "__main__":
    build()
