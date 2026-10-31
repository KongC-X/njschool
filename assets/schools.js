/* ============================================================
   学校库页面脚本（DOM 层）
   匹配逻辑在 assets/search-core.js，这里只做状态、渲染与事件。
   ============================================================ */
const S = window.__NJ_SEARCH__;
const COLS = window.__SCHOOLS__.cols;
const ALL_DISTRICTS = window.__SCHOOLS__.districts;
/* 施教区地名索引与列表数据同序同长（构建期 check.py 有守卫核对） */
const STREETS = (window.__STREETS__ && window.__STREETS__.rows) || [];

/* 数组 → 对象；详情页地址按「学段-校名」推导，与构建期规则一致 */
const DATA = window.__SCHOOLS__.rows.map(function (row, i) {
  var o = {};
  COLS.forEach(function (k, idx) { o[k] = row[idx]; });
  o.addr = STREETS[i] || '';
  o.id = o.level + '-' + o.name;
  o.url = 'schools/' + encodeURIComponent(o.id) + '.html';
  return o;
});

/* 跨学段同名（小学部与初中部共用校名，共 10 组）：标题后补学段。
   否则搜「仙外」出来两条一模一样的「南京仙林外国语学校」，家长只能靠徽章分辨。
   详情页的 title 已在构建期补过学段（见 pipeline/main.py 的 dup_names），
   列表页此前漏了这一层，两处口径不一致。 */
const DUP_NAME = {};
DATA.forEach(function (s) { DUP_NAME[s.name] = (DUP_NAME[s.name] || 0) + 1; });

const state = { q: '', lv: '', dist: '', type: '', has: '', sort: '' };
const grid = document.getElementById('grid');
const cnt = document.getElementById('count');
const input = document.getElementById('q');
const sortSel = document.getElementById('sort');

/* 数据项：只放家长真会拿来筛的四项，与构建期 facts.HAS_ORDER 一致。
   措辞统一为「有…」——它筛的是「这份档案里有没有这一项数据」，
   不是「这所学校收不收学费」。 */
const HAS_ITEMS = ['有学费', '有投档线', '有招生计划', '有对口初中'];

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

/* 命中高亮：先转义再包 <mark>，避免用户输入被当成 HTML 执行 */
function highlight(text, ts) {
  var safe = esc(text || '');
  if (!ts.length) return safe;
  var pattern = ts
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

/* 只 replace 不 push：筛选项变化不该把历史栈塞满，后退仍应能离开本页 */
function syncUrl() {
  const p = [];
  if (state.q.trim()) p.push('q=' + encodeURIComponent(state.q.trim()));
  if (state.lv) p.push('lv=' + encodeURIComponent(state.lv));
  if (state.dist) p.push('dist=' + encodeURIComponent(state.dist));
  if (state.type) p.push('type=' + encodeURIComponent(state.type));
  if (state.has) p.push('has=' + encodeURIComponent(state.has));
  if (state.sort) p.push('sort=' + encodeURIComponent(state.sort));
  try {
    history.replaceState(null, '', location.pathname + (p.length ? '?' + p.join('&') : ''));
  } catch (e) { /* file:// 下可能抛错，忽略 */ }
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

/* 梯队名里带「第一梯队 / 第二梯队」，取出数字用于排序；
   没有梯队标注的排最后，不能因为它们没写就排到第一。 */
const TIER_RANK = { '一': 1, '二': 2, '三': 3, '四': 4, '五': 5 };
function tierRank(s) {
  var m = /第([一二三四五])梯队/.exec(s.tier || '');
  return m ? (TIER_RANK[m[1]] || 9) : 9;
}

function sortRows(rows) {
  if (state.sort === 'name') {
    /* localeCompare('zh') 在浏览器里按拼音排，不需要引入拼音库 */
    return rows.slice().sort(function (a, b) {
      return a.name.localeCompare(b.name, 'zh-Hans-CN');
    });
  }
  if (state.sort === 'tier') {
    return rows.slice().sort(function (a, b) {
      return (tierRank(a) - tierRank(b)) || a.name.localeCompare(b.name, 'zh-Hans-CN');
    });
  }
  return rows;
}

/* 关键词像不像「地址」：家长搜「宁海路」「龙江小区」时，
   原来的空态建议是「减少关键词」——他明明只输入了一个词。 */
function looksLikeAddress(q) {
  return /[路街巷弄村镇苑园号里桥]|小区|新村|花园|公寓|山庄/.test(q || '');
}

/* ---------- 结果渲染 ----------
   原来每次输入都把 545 张卡重拼成字符串再整体 innerHTML：
   单次 339,913 字符 / 5,989 个元素，本机 59ms/键，移动端要 250–350ms。
   现在改成「首屏 24 张 + 滚动追加，最多 60 张」，一次只碰 24 个节点；
   超过 60 条不再追加，改为提示加筛选——545 条一次性铺开对谁都没用。
*/
var PAGE = 24;
var CAP = 60;
var rowsNow = [];
var addrNow = false;
var shown = 0;
var io = null;

function cardHtml(s, ts) {
  const t = s.type === '民办' ? 'b-pri' : 'b-pub';
  /* 「官方还没说死」的标记：只在正文里写，用户会把暂定校名当确定信息用 */
  const warn = (s.marks || '').split(' ').filter(Boolean)
    .map(function (m) { return '<span class="b b-warn">' + esc(m) + '</span>'; }).join('');
  /* 地址命中的学校：必须写出「施教区含：宁海路」。
     否则家长会以为这所学校只是碰巧被搜到，不敢点。 */
  let addrLine = '';
  if (addrNow) {
    const labels = S.addrLabels(s, ts);
    if (labels.length) {
      addrLine = '<div class="addr-hit">施教区含：'
        + labels.slice(0, 3).map(function (x) { return highlight(x, ts); }).join('、')
        + '</div>';
    }
  }
  /* 整张卡就是一个链接：原来「标题」和「查看完整档案」各指同一个地址，
     545 张卡 = 1,090 个 Tab 停留点，键盘用户到第一张卡要按 1,090 次。 */
  const lvSfx = DUP_NAME[s.name] > 1
    ? ' <span class="lv-sfx">（' + esc(s.level) + '）</span>'
    : '';
  return '<a class="card" role="listitem" href="' + s.url + '">'
    + '<h3>' + highlight(s.name, ts) + lvSfx + '</h3>'
    + '<div class="badges">'
    +   '<span class="b b-lv">' + esc(s.level) + '</span>'
    +   '<span class="b ' + t + '">' + esc(s.type) + '</span>'
    +   '<span class="b b-d">' + esc(s.district) + '</span>'
    +   (s.short ? '<span class="b b-d">' + esc(s.short) + '</span>' : '')
    +   warn
    + '</div>'
    + (s.tier ? '<div class="tier">' + esc(s.tier) + '</div>' : '')
    + addrLine
    + '<div class="tag">' + highlight(s.tagline || '', ts) + '</div>'
    + '<span class="more">查看完整档案 →</span>'
    + '</a>';
}

/* 剩余条数与「继续加载」提示。滚动到底部时由 IntersectionObserver 触发追加。 */
function moreHtml() {
  const total = rowsNow.length;
  if (shown >= total) return '';
  if (shown >= CAP) {
    return '<p class="more-hint">还有 ' + (total - shown) + ' 所没有列出，'
      + '加一个筛选条件（学段 / 行政区）会更快。</p>';
  }
  return '<p class="more-hint">还有 ' + (total - shown) + ' 所，继续向下滚动查看。</p>';
}

function paintMore() {
  const box = document.getElementById('gridMore');
  if (!box) return;
  box.innerHTML = moreHtml();
  const canLoad = shown < rowsNow.length && shown < CAP;
  if (canLoad && !io && 'IntersectionObserver' in window) {
    io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) appendChunk(); });
    }, { rootMargin: '400px' });
  }
  if (io) { io.disconnect(); if (canLoad) io.observe(box); }
}

function appendChunk() {
  const stop = Math.min(shown + PAGE, rowsNow.length, CAP);
  if (stop <= shown) { paintMore(); return; }
  let html = '';
  const ts = S.terms(state.q);
  for (let i = shown; i < stop; i++) html += cardHtml(rowsNow[i], ts);
  grid.insertAdjacentHTML('beforeend', html);
  shown = stop;
  paintMore();
}

/* 空态：把「当前生效的条件」列成可单独移除的 chip。
   原来只有一句「清除全部筛选」，家长不知道是哪一条把结果卡没了，
   清空后要重新点四次。 */
function activeChips() {
  const items = [];
  if (state.q.trim()) items.push({ k: 'q', label: '搜索「' + state.q.trim() + '」' });
  if (state.lv) items.push({ k: 'lv', label: '学段 ' + state.lv });
  if (state.dist) items.push({ k: 'dist', label: state.dist });
  if (state.type) items.push({ k: 'type', label: state.type });
  if (state.has) items.push({ k: 'has', label: state.has });
  return items;
}

function emptyHtml() {
  const raw = state.q.trim();
  const hasFilters = !!(state.lv || state.dist || state.type || state.has);
  let msg = '没有匹配的学校';
  let tip = '';

  if (looksLikeAddress(raw) && S.terms(raw).length === 1) {
    msg = '按地址暂时查不到「' + esc(raw) + '」';
    tip = '本站的地址检索依赖各校档案里写明的路名/小区名。'
        + '如果这里没有命中，可能是该校施教区按「××路以南」的四至方式描述、未逐条列路名，'
        + '或者该路名不在任何一所学校的范围内。'
        + '<br>也可以先按行政区浏览，再进学校档案看第五节「招生与施教区」。';
  } else if (S.terms(raw).length > 1) {
    msg = '没有同时命中这几个关键词的学校';
    tip = '试试减少关键词，或改用「行政区 + 学段」筛选。';
  } else if (hasFilters) {
    msg = '当前筛选条件下没有学校';
    tip = '可能是筛选条件叠加过窄，点下面的条件单独移除试试。';
  } else {
    tip = '试试换一个校名简称，或用「行政区 + 学段」筛选。';
  }

  const chips = activeChips().map(function (c) {
    return '<button type="button" class="chip chip--sm filter-chip" data-k="' + c.k + '"'
      + ' aria-label="移除条件：' + esc(c.label) + '">'
      + esc(c.label) + ' <span aria-hidden="true">×</span></button>';
  }).join('');

  return '<div class="empty"><strong>' + msg + '</strong>'
    + (chips ? '<div class="empty-chips">' + chips + '</div>' : '')
    + '<p class="empty-tip">' + tip + '</p>'
    + '<button type="button" class="btn-reset" id="resetFilters">清除全部筛选</button></div>';
}

function render() {
  const res = S.query(DATA, state.q, state);
  const raw = state.q.trim();
  rowsNow = sortRows(res.rows);
  addrNow = !!res.addrMatch;

  const filtered = !!(raw || state.lv || state.dist || state.type || state.has);
  let label = filtered
    ? '匹配 ' + rowsNow.length + ' 所 / 共 ' + DATA.length + ' 所'
    : '共 ' + DATA.length + ' 所';
  if (raw) {
    label += '（关键词：' + raw;
    if (res.addrMatch) label += '，按施教区路名匹配';
    if (res.fellBack) label += '，在简介中匹配';
    label += '）';
  }
  cnt.textContent = label;

  updateFilterBadge();
  syncUrl();

  /* 重建期间告诉读屏「这里在更新」，避免它对整块内容逐条播报 */
  grid.setAttribute('aria-busy', 'true');
  grid.innerHTML = '';
  shown = 0;

  if (!rowsNow.length) {
    grid.innerHTML = emptyHtml();
    grid.setAttribute('aria-busy', 'false');
    const btn = document.getElementById('resetFilters');
    if (btn) btn.addEventListener('click', resetAll);
    grid.querySelectorAll('.filter-chip').forEach(function (c) {
      c.addEventListener('click', function () {
        state[c.dataset.k] = '';
        if (c.dataset.k === 'q' && input) input.value = '';
        syncChips();
        render();
      });
    });
    return;
  }

  appendChunk();
  grid.setAttribute('aria-busy', 'false');
}

/* 把某一组 chips 的选中态刷新回 DOM（单条移除条件后调用） */
function syncChips() {
  [['f-lv', 'lv'], ['f-dist', 'dist'], ['f-type', 'type'], ['f-has', 'has']].forEach(function (pair) {
    const box = document.getElementById(pair[0]);
    if (!box) return;
    Array.prototype.forEach.call(box.children, function (c) {
      const on = c.dataset.v === state[pair[1]];
      c.classList.toggle('on', on);
      c.setAttribute('aria-pressed', String(on));
    });
  });
}

function resetAll() {
  state.q = ''; state.lv = ''; state.dist = ''; state.type = ''; state.has = '';
  if (input) input.value = '';
  ['f-lv', 'f-dist', 'f-type', 'f-has'].forEach(function (id) {
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
            + (state.has ? 1 : 0) + (state.q.trim() ? 1 : 0);
  badge.textContent = String(n);
  badge.hidden = n === 0;
}

/* ---------- 启动 ---------- */
if (matchMedia('(max-width:720px)').matches) {
  const box = document.getElementById('filters');
  if (box) box.dataset.open = 'false';
}

const params = new URLSearchParams(location.search);
state.q = params.get('q') || '';
state.type = params.get('type') || '';
state.sort = params.get('sort') || '';
if (input) {
  input.value = state.q;
  /* 输入防抖 180ms + 输入法组字门控：
     拼音还在候选阶段就重排结果，会让「输入一个词」变成「重建四五次」。 */
  var qTimer = null;
  var composing = false;
  function schedule() {
    clearTimeout(qTimer);
    qTimer = setTimeout(render, 180);
  }
  input.addEventListener('compositionstart', function () { composing = true; });
  input.addEventListener('compositionend', function () {
    composing = false;
    state.q = input.value;
    schedule();
  });
  input.addEventListener('input', function (e) {
    state.q = e.target.value;
    if (!composing) schedule();
  });
}
if (sortSel) {
  sortSel.value = state.sort;
  sortSel.addEventListener('change', function (e) {
    state.sort = e.target.value;
    render();
  });
}

chips('f-lv', 'lv', ['小学', '初中', '高中'], '全部学段');
chips('f-dist', 'dist', ALL_DISTRICTS, '全部区');
chips('f-type', 'type', ['公办', '民办'], '全部性质');
chips('f-has', 'has', HAS_ITEMS, '不限');

/* 深链直达筛选：?lv= / ?dist= / ?type= / ?has=（首页、页脚、分享链接都靠它） */
[['lv', 'f-lv'], ['dist', 'f-dist'], ['type', 'f-type'], ['has', 'f-has']].forEach(function (pair) {
  const v = params.get(pair[0]);
  if (!v) return;
  Array.prototype.forEach.call(document.getElementById(pair[1]).children, function (c) {
    if (c.dataset.v === v) c.click();
  });
});

render();
