{# 学校库筛选脚本：数据来自 assets/schools-data.js（由页面在脚本前引入） #}
const COLS = window.__SCHOOLS__.cols;
const ALL_DISTRICTS = window.__SCHOOLS__.districts;

/* 数组 → 对象；详情页地址按「学段-校名」推导，与构建期规则一致 */
const DATA = window.__SCHOOLS__.rows.map(function (row) {
  var o = {};
  COLS.forEach(function (k, i) { o[k] = row[i]; });
  o.url = 'schools/' + encodeURIComponent(o.level + '-' + o.name) + '.html';
  return o;
});

const state = { q: new URLSearchParams(location.search).get('q') || '', lv: '', dist: '', type: '' };
const grid = document.getElementById('grid');
const cnt = document.getElementById('count');

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

/* 命中高亮：先转义再包 <mark>，避免用户输入被当成 HTML 执行 */
function highlight(text, terms) {
  var safe = esc(text || '');
  if (!terms.length) return safe;
  var pattern = terms
    .map(function (t) { return t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); })
    .filter(Boolean)
    .join('|');
  if (!pattern) return safe;
  try {
    return safe.replace(new RegExp('(' + pattern + ')', 'gi'), '<mark>$1</mark>');
  } catch (e) {
    return safe;
  }
}

/* 阿拉伯数字 → 中文数字：手机上打「29中」比打「第二十九中学」容易得多。
   只在查询侧转换、不写进索引——「9中」是「29中」的子串，若把 29中 塞进索引，
   搜「9中」就会把二十九中也带出来。 */
function cnNum(n) {
  var d = '零一二三四五六七八九';
  if (n < 10) return d.charAt(n);
  var t = Math.floor(n / 10), o = n % 10;
  return (t === 1 ? '十' : d.charAt(t) + '十') + (o ? d.charAt(o) : '');
}
function normTerm(t) {
  return t.replace(/^(\d{1,2})(?=[中初高小])/, function (_, n) {
    return cnNum(parseInt(n, 10));
  });
}

/* 多关键词：空格分隔，需全部命中（AND） */
function terms() {
  return state.q.trim().toLowerCase().split(/\s+/).filter(Boolean).map(normTerm);
}

/* 主索引：校名、简称、性质、梯队、区名。
   tagline 刻意不进主索引——它是叙述性长文本，「施教区」「集团」这类词会把结果撑满，
   而且会把只是「提到」了某校的档案一并带出（搜「二十九中」曾跳出琅小/拉小/力学）。 */
function hayMain(s) {
  return (s.name + ' ' + (s.short || '') + ' ' + s.type + ' '
          + (s.tier || '') + ' ' + s.district).toLowerCase();
}
/* 兜底索引：主索引零结果时才查 tagline，保证「九年一贯」「电脑派位」这类描述词仍搜得到 */
function hayExtra(s) { return (s.tagline || '').toLowerCase(); }

/* 别名按「整词」比对，不做子串。组合词互为子串（「拉力琅」是「拉力琅芳」的前缀），
   子串匹配会让搜「拉力琅」连带出芳草园——那就不是三所名校的意思了。 */
function aliasHit(s, t) {
  var list = (s.aliases || '').split(' ');
  for (var i = 0; i < list.length; i++) {
    if (list[i] === t) return true;
  }
  return false;
}

/* 命中质量评分：校名精确 > 校名前缀 > 校名包含 > 简称/别名 > 梯队与区名 */
function score(s, ts) {
  var name = s.name.toLowerCase();
  var minor = (s.short || '').toLowerCase();
  var rest = ((s.tier || '') + ' ' + s.district).toLowerCase();
  var total = 0;
  ts.forEach(function (t) {
    if (name === t) total += 100;
    else if (name.indexOf(t) === 0) total += 60;
    else if (name.indexOf(t) !== -1) total += 40;
    else if (aliasHit(s, t)) total += 30;
    else if (minor.indexOf(t) !== -1) total += 20;
    else if (rest.indexOf(t) !== -1) total += 6;
  });
  return total;
}

/* 命中判定。
   「九中」不能靠 indexOf 直接判——它是「二十九中」的子串，会把二十九中一并带出来。
   凡「数字汉字 + 中/初」形式的词，要求命中位置的前一个字不是数字汉字。
   不用正则后行断言：老版 Safari 会直接抛错。 */
const RE_NUM_DEGREE = /^[一二三四五六七八九十]+[中初]$/;
const RE_NUM_CHAR = /[一二三四五六七八九十]/;
function hasTerm(hay, t) {
  var i = hay.indexOf(t);
  if (i === -1) return false;
  if (!RE_NUM_DEGREE.test(t)) return true;
  while (i !== -1) {
    var prev = i > 0 ? hay.charAt(i - 1) : '';
    if (!RE_NUM_CHAR.test(prev)) return true;
    i = hay.indexOf(t, i + 1);
  }
  return false;
}

function match(s, ts, withExtra) {
  if (state.lv && s.level !== state.lv) return false;
  if (state.dist && s.district !== state.dist) return false;
  if (state.type && s.type !== state.type) return false;
  if (!ts.length) return true;
  var hay = hayMain(s) + (withExtra ? ' ' + hayExtra(s) : '');
  return ts.every(function (t) { return hasTerm(hay, t) || aliasHit(s, t); });
}

function chips(elId, key, values, allLabel) {
  const box = document.getElementById(elId);
  const pairs = [['', allLabel]].concat(values.map(function (v) { return [v, v]; }));
  pairs.forEach(function (pair) {
    const v = pair[0], label = pair[1];
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip' + (v === state[key] ? ' on' : '');
    b.setAttribute('aria-pressed', String(v === state[key]));
    b.textContent = label;
    b.dataset.v = v;
    b.addEventListener('click', function () {
      state[key] = v;
      Array.prototype.forEach.call(box.children, function (c) {
        const on = c.dataset.v === v;
        c.classList.toggle('on', on);
        c.setAttribute('aria-pressed', String(on));
      });
      render();
    });
    box.appendChild(b);
  });
}

function render() {
  const ts = terms();
  const raw = state.q.trim();

  let rows = DATA.filter(function (s) { return match(s, ts, false); });
  let fellBack = false;
  if (!rows.length && ts.length) {
    rows = DATA.filter(function (s) { return match(s, ts, true); });
    fellBack = rows.length > 0;
  }
  if (ts.length) {
    /* 同分时校名短者优先：「二十九中」应先出本部，再出天润城分校 */
    rows = rows.slice().sort(function (a, b) {
      return (score(b, ts) - score(a, ts)) || (a.name.length - b.name.length);
    });
  }

  cnt.textContent = '匹配 ' + rows.length + ' 所 / 共 ' + DATA.length + ' 所'
    + (raw ? '（关键词：' + raw + (fellBack ? '，在简介中匹配' : '') + '）' : '');
  updateFilterBadge();

  if (!rows.length) {
    grid.innerHTML = '<div class="empty"><strong>没有匹配的学校</strong>'
      + '试试减少关键词，或清除筛选条件。'
      + '<br><button type="button" class="btn-reset" id="resetFilters">清除全部筛选</button></div>';
    const btn = document.getElementById('resetFilters');
    if (btn) btn.addEventListener('click', resetAll);
    return;
  }

  grid.innerHTML = rows.map(function (s) {
    const t = s.type === '民办' ? 'b-pri' : 'b-pub';
    return '<div class="card">'
      + '<h3><a href="' + s.url + '">' + highlight(s.name, ts) + '</a></h3>'
      + '<div class="badges">'
      +   '<span class="b b-lv">' + esc(s.level) + '</span>'
      +   '<span class="b ' + t + '">' + esc(s.type) + '</span>'
      +   '<span class="b b-d">' + esc(s.district) + '</span>'
      +   (s.short ? '<span class="b b-d">' + esc(s.short) + '</span>' : '')
      + '</div>'
      + '<div class="tier">' + esc(s.tier || '') + '</div>'
      + '<div class="tag">' + highlight(s.tagline || '', ts) + '</div>'
      + '<a class="more" href="' + s.url + '">查看完整档案 →</a>'
      + '</div>';
  }).join('');
}

function resetAll() {
  state.q = ''; state.lv = ''; state.dist = ''; state.type = '';
  const input = document.getElementById('q');
  if (input) input.value = '';
  ['f-lv', 'f-dist', 'f-type'].forEach(function (id) {
    Array.prototype.forEach.call(document.getElementById(id).children, function (c) {
      const on = c.dataset.v === '';
      c.classList.toggle('on', on);
      c.setAttribute('aria-pressed', String(on));
    });
  });
  render();
}

function updateFilterBadge() {
  const badge = document.getElementById('filterCount');
  if (!badge) return;
  const n = (state.lv ? 1 : 0) + (state.dist ? 1 : 0) + (state.type ? 1 : 0)
            + (state.q.trim() ? 1 : 0);
  badge.textContent = String(n);
  badge.hidden = n === 0;
}

if (matchMedia('(max-width:720px)').matches) {
  const box = document.getElementById('filters');
  if (box) box.dataset.open = 'false';
}

document.getElementById('q').value = state.q;
document.getElementById('q').addEventListener('input', function (e) {
  state.q = e.target.value;
  render();
});
chips('f-lv', 'lv', ['小学', '初中', '高中'], '全部学段');
chips('f-dist', 'dist', ALL_DISTRICTS, '全部区');
chips('f-type', 'type', ['公办', '民办'], '不限性质');
render();
