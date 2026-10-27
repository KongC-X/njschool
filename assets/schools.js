/* ============================================================
   学校库页面脚本（DOM 层）
   匹配逻辑在 assets/search-core.js，这里只做状态、渲染与事件。
   ============================================================ */
const S = window.__NJ_SEARCH__;
const COLS = window.__SCHOOLS__.cols;
const ALL_DISTRICTS = window.__SCHOOLS__.districts;

/* 数组 → 对象；详情页地址按「学段-校名」推导，与构建期规则一致 */
const DATA = window.__SCHOOLS__.rows.map(function (row) {
  var o = {};
  COLS.forEach(function (k, i) { o[k] = row[i]; });
  o.id = o.level + '-' + o.name;
  o.url = 'schools/' + encodeURIComponent(o.id) + '.html';
  return o;
});

const state = { q: '', lv: '', dist: '', type: '' };
const grid = document.getElementById('grid');
const cnt = document.getElementById('count');
const input = document.getElementById('q');

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

function render() {
  const res = S.query(DATA, state.q, state);
  const ts = res.terms;
  const raw = state.q.trim();
  const rows = res.rows;

  cnt.textContent = '匹配 ' + rows.length + ' 所 / 共 ' + DATA.length + ' 所'
    + (raw ? '（关键词：' + raw + (res.fellBack ? '，在简介中匹配' : '') + '）' : '');
  updateFilterBadge();
  syncUrl();

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
    /* 「官方还没说死」的标记：只在正文里写，用户会把暂定校名当确定信息用 */
    const warn = (s.marks || '').split(' ').filter(Boolean)
      .map(function (m) { return '<span class="b b-warn">' + esc(m) + '</span>'; }).join('');
    return '<div class="card">'
      + '<h3><a href="' + s.url + '">' + highlight(s.name, ts) + '</a></h3>'
      + '<div class="badges">'
      +   '<span class="b b-lv">' + esc(s.level) + '</span>'
      +   '<span class="b ' + t + '">' + esc(s.type) + '</span>'
      +   '<span class="b b-d">' + esc(s.district) + '</span>'
      +   (s.short ? '<span class="b b-d">' + esc(s.short) + '</span>' : '')
      +   warn
      + '</div>'
      + '<div class="tier">' + esc(s.tier || '') + '</div>'
      + '<div class="tag">' + highlight(s.tagline || '', ts) + '</div>'
      + '<a class="more" href="' + s.url + '">查看完整档案 →</a>'
      + '</div>';
  }).join('');
}

function resetAll() {
  state.q = ''; state.lv = ''; state.dist = ''; state.type = '';
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

/* ---------- 启动 ---------- */
if (matchMedia('(max-width:720px)').matches) {
  const box = document.getElementById('filters');
  if (box) box.dataset.open = 'false';
}

const params = new URLSearchParams(location.search);
state.q = params.get('q') || '';
state.type = params.get('type') || '';
if (input) {
  input.value = state.q;
  input.addEventListener('input', function (e) {
    state.q = e.target.value;
    render();
  });
}

chips('f-lv', 'lv', ['小学', '初中', '高中'], '全部学段');
chips('f-dist', 'dist', ALL_DISTRICTS, '全部区');
chips('f-type', 'type', ['公办', '民办'], '不限性质');

/* 深链直达筛选：?lv= / ?dist= / ?type=（首页、页脚、分享链接都靠它） */
[['lv', 'f-lv'], ['dist', 'f-dist'], ['type', 'f-type']].forEach(function (pair) {
  const v = params.get(pair[0]);
  if (!v) return;
  Array.prototype.forEach.call(document.getElementById(pair[1]).children, function (c) {
    if (c.dataset.v === v) c.click();
  });
});

render();
