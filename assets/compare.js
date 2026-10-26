/* ============================================================
   对比页脚本（DOM 层）
   数据：assets/schools-data.js；缺口：assets/facts-missing.js；
   行定义：模板内联的 window.__CMP_ROWS__（来自 data/compare_rows.json）；
   纯逻辑：assets/compare-core.js。
   ============================================================ */
const CORE = window.__NJ_COMPARE__;
const SCH = window.__NJ_SEARCH__;
const SPECS = window.__CMP_ROWS__;
const COLS = window.__SCHOOLS__.cols;
const MISS = window.__FACTS_MISSING__;

/* 缺口的字段码 → 字段名。__FACTS_MISSING__.rows 与 __SCHOOLS__.rows 同序同长 */
const MISSING = {};
(function () {
  if (!MISS) return;
  const F = MISS.fields;
  window.__SCHOOLS__.rows.forEach(function (row, i) {
    const codes = MISS.rows[i] || '';
    if (!codes) return;
    const list = [];
    for (let k = 0; k < codes.length; k++) list.push(F[Number(codes.charAt(k))]);
    MISSING[row[COLS.indexOf('level')] + '-' + row[COLS.indexOf('name')]] = list;
  });
})();

const DATA = window.__SCHOOLS__.rows.map(function (row) {
  const o = {};
  COLS.forEach(function (k, i) { o[k] = row[i]; });
  o.id = o.level + '-' + o.name;
  o.url = 'schools/' + encodeURIComponent(o.id) + '.html';
  return o;
});
const BY_ID = {};
DATA.forEach(function (s) { BY_ID[s.id] = s; });

const MAX = 4;
const STORE = 'nj-compare';
const GROUPS = { identity: '身份', path: '通路', evidence: '证据' };

const pick = document.getElementById('pick');
const list = document.getElementById('pickList');
const status = document.getElementById('pickStatus');
const pickedBox = document.getElementById('picked');
const cmp = document.getElementById('cmp');
const clearBtn = document.getElementById('clearAll');
const diffBtn = document.getElementById('onlyDiff');

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

/* ---------- 状态 ---------- */
let ids = [];
let broken = false;
let onlyDiff = false;

function hasId(id) { return Object.prototype.hasOwnProperty.call(BY_ID, id); }

function readStore() {
  try {
    const v = JSON.parse(localStorage.getItem(STORE) || '[]');
    return Array.isArray(v) ? v.filter(hasId).slice(0, MAX) : [];
  } catch (e) { return []; }
}

function save() {
  try { localStorage.setItem(STORE, JSON.stringify(ids)); } catch (e) { /* 隐私模式忽略 */ }
  /* 只 replace 不 push：筛选式操作不该把历史栈塞满后退不回去 */
  try {
    history.replaceState(null, '', location.pathname + CORE.toQuery(ids));
  } catch (e) { /* file:// 下可能抛错，忽略 */ }
}

/* ---------- 候选（combobox 语义 + 键盘可达） ---------- */
/* 候选匹配不再自己实现一套：调 assets/search-core.js，与学校库同一口径。
   之前这里是全站第 4 份搜索实现，连俗称别名都不查——
   「学校库能搜到拉力琅，对比页搜不到」就是这么来的。 */
let activeIdx = -1;

function options() {
  return Array.prototype.slice.call(list.querySelectorAll('li[data-id]'));
}

function setActive(i) {
  const items = options();
  if (!items.length) { activeIdx = -1; pick.removeAttribute('aria-activedescendant'); return; }
  activeIdx = Math.max(0, Math.min(i, items.length - 1));
  items.forEach(function (li, k) {
    const on = k === activeIdx;
    li.classList.toggle('is-active', on);
    li.setAttribute('aria-selected', String(on));
    if (on) {
      li.id = 'pickOpt';                       // 单一 id 跟着活动项走，避免每次重建
      pick.setAttribute('aria-activedescendant', 'pickOpt');
      if (li.scrollIntoView) li.scrollIntoView({ block: 'nearest' });
    } else if (li.id === 'pickOpt') {
      li.removeAttribute('id');
    }
  });
}

function closeList() {
  list.hidden = true;
  pick.setAttribute('aria-expanded', 'false');
  pick.removeAttribute('aria-activedescendant');
  activeIdx = -1;
}

function suggest(q) {
  if (!q.trim()) { closeList(); status.textContent = ''; return; }

  const pool = DATA.filter(function (s) { return ids.indexOf(s.id) === -1; });
  const res = SCH.query(pool, q, null, { limit: 8 });
  const hits = res.rows;

  if (!hits.length) {
    list.innerHTML = '<li class="pick-empty">没有匹配的学校</li>';
    status.textContent = '没有匹配的学校';
  } else {
    list.innerHTML = hits.map(function (s) {
      return '<li role="option" aria-selected="false" tabindex="-1" data-id="' + esc(s.id) + '">'
        + '<span>' + esc(s.name) + '</span>'
        + '<em>' + esc(s.district) + ' · ' + esc(s.level) + '</em></li>';
    }).join('');
    status.textContent = '找到 ' + hits.length + ' 所，↑↓ 选择，回车加入';
  }
  list.hidden = false;
  pick.setAttribute('aria-expanded', 'true');
  /* 默认高亮第一条：否则有 2 个以上候选时按回车毫无反应，用户会以为坏了。
     高亮也顺带告诉用户「现在按回车会选中哪个」。 */
  if (hits.length) setActive(0);
  else { activeIdx = -1; pick.removeAttribute('aria-activedescendant'); }
}

function add(id) {
  if (!hasId(id) || ids.indexOf(id) !== -1) return;
  if (ids.length >= MAX) {
    /* 上限提示走独立的 aria-live 区，不再覆盖候选列表——
       之前是 list.innerHTML = '最多对比 4 所'，把用户正看着的候选冲掉了 */
    status.textContent = '最多对比 4 所，请先移除一所';
    return;
  }
  ids.push(id);
  pick.value = '';
  closeList();
  status.textContent = '';
  save();
  render();
}

function remove(id) {
  ids = ids.filter(function (x) { return x !== id; });
  save();
  render();
}

/* ---------- 渲染 ---------- */
function chip(id) {
  const s = BY_ID[id];
  return '<button type="button" class="chip on" data-id="' + esc(id) + '"'
    + ' aria-label="移除 ' + esc(s.name) + '">' + esc(s.name) + ' ×</button>';
}

function cellHtml(row, cell) {
  let cls = 'cmp-cell';
  if (cell.state === 'gap') cls += ' is-gap';
  if (cell.state === 'none') cls += ' is-na';
  if (cell.isDiff) cls += ' is-diff';

  let attrs = ' data-label="' + esc(row.label) + '"';
  if (cell.state === 'gap') {
    attrs += ' title="该校档案已声明此项为数据缺口"';
  } else if (cell.state === 'none') {
    attrs += ' title="本站未收录此项，不代表学校没有"';
  }
  return '<td class="' + cls + '"' + attrs + '>' + esc(cell.text) + '</td>';
}

function tableHtml(items, rows) {
  const n = items.length;
  let out = '<div class="cmp-wrap"><table class="cmp-table" data-n="' + n + '">'
    + '<caption class="sr-only">' + n + ' 所学校对比</caption><thead><tr>'
    + '<th scope="col" class="cmp-corner">对比项</th>';

  items.forEach(function (s) {
    out += '<th scope="col" class="cmp-head">'
      + '<a href="' + s.url + '">' + esc(s.name) + '</a>'
      + '<span class="cmp-head-meta">' + esc(s.level) + ' · ' + esc(s.type)
      + ' · ' + esc(s.district) + '</span></th>';
  });
  out += '</tr></thead>';

  let group = '';
  rows.forEach(function (row, i) {
    if (row.group !== group) {
      if (group) out += '</tbody>';
      group = row.group;
      const count = rows.filter(function (r) { return r.group === group; }).length;
      out += '<tbody data-group="' + group + '"><tr class="cmp-ghead"><th colspan="' + (n + 1) + '">'
        + '<button type="button" class="cmp-gtoggle" aria-expanded="true" data-group="' + group + '">'
        + '<span class="cmp-gcaret" aria-hidden="true">▾</span>'
        + esc(GROUPS[group] || group) + '<span class="cmp-gcount">' + count + ' 项</span>'
        + '</button></th></tr>';
    }
    let rowCls = 'cmp-row';
    if (row.hasDiff) rowCls += ' has-diff';
    /* 「相同」只给「所有列都有值且值一致」的行。
       1/4 有值、0/4 有值都不叫相同，它们是「缺」，不该被「只看差异」折叠掉。
       这两类缺口本身也是要看的信号。 */
    else if (row.diff === 'exact' && row.filled === row.total) rowCls += ' is-same';
    /* 一所都没有值：留着是噪声，但也不能说它「相同」。
       单独给一个类，交给「只看差异」按需收起，并在下面报出收起多少项。 */
    if (row.filled === 0) rowCls += ' is-blank';

    out += '<tr class="' + rowCls + '" data-key="' + row.key + '">'
      + '<th scope="row" class="cmp-rowhead">' + esc(row.label)
      + (row.filled < row.total
          ? '<span class="cmp-fill">' + row.filled + '/' + row.total + '</span>' : '')
      + '</th>'
      + row.cells.map(function (c) { return cellHtml(row, c); }).join('')
      + '</tr>';
    if (i === rows.length - 1) out += '</tbody>';
  });
  out += '</table></div>';
  return out;
}

/* 窄屏用：一校一张卡。
   表格在 360px 上要靠横滑才看得全，4 列的校名会被压成两行碎片；
   卡片模式把「行」竖过来，逐校读完再读下一所，比横滑省力。
   两套结构同时输出，用 CSS 媒体查询切换（隐藏的那套不进无障碍树）。 */
function cardsHtml(items, rows) {
  return '<div class="cmp-cards">' + items.map(function (s) {
    const body = rows.map(function (row) {
      let cls = 'cmp-crow';
      if (row.hasDiff) cls += ' has-diff';
      else if (row.diff === 'exact' && row.filled === row.total) cls += ' is-same';
      if (row.filled === 0) cls += ' is-blank';

      const cell = row.cells[items.indexOf(s)];
      let dcls = 'cmp-cell';
      if (cell.state === 'gap') dcls += ' is-gap';
      if (cell.state === 'none') dcls += ' is-na';
      if (cell.isDiff) dcls += ' is-diff';

      return '<div class="' + cls + '"><dt>' + esc(row.label)
        + (row.filled < row.total
            ? '<span class="cmp-fill">' + row.filled + '/' + row.total + '</span>' : '')
        + '</dt><dd class="' + dcls + '">' + esc(cell.text) + '</dd></div>';
    }).join('');

    return '<article class="cmp-card">'
      + '<h2 class="cmp-head"><a href="' + s.url + '">' + esc(s.name) + '</a></h2>'
      + '<span class="cmp-head-meta">' + esc(s.level) + ' · ' + esc(s.type)
      + ' · ' + esc(s.district) + '</span>'
      + '<dl>' + body + '</dl></article>';
  }).join('') + '</div>';
}

function render() {
  pickedBox.innerHTML = ids.map(chip).join('')
    + (ids.length ? '<button type="button" class="chip" id="clearInline">清空</button>' : '');
  clearBtn.hidden = ids.length === 0;

  if (broken) {
    cmp.innerHTML = '<div class="empty"><strong>这条分享链接已失效</strong>'
      + '可能是学校改名或链接过期。可以到学校库重新挑选。'
      + '<br><a class="cmp-go" href="schools.html">去学校库 →</a></div>';
    if (diffBtn) diffBtn.hidden = true;
    return;
  }

  if (ids.length < 2) {
    cmp.innerHTML = '<div class="empty"><strong>'
      + (ids.length ? '再加 1 所就能对比了' : '先选两所学校') + '</strong>'
      + '在上方输入校名，点选候选即可加入对比。最多 4 所。</div>';
    if (diffBtn) diffBtn.hidden = true;
    return;
  }

  const items = ids.map(function (id) { return BY_ID[id]; });
  const rows = CORE.buildRows(SPECS, items, function (id) { return MISSING[id]; });
  const diffN = rows.filter(function (r) { return r.hasDiff; }).length;

  if (diffBtn) {
    diffBtn.hidden = false;
    diffBtn.setAttribute('aria-pressed', String(onlyDiff));
    diffBtn.textContent = onlyDiff
      ? '显示全部 ' + rows.length + ' 项'
      : '只看差异（' + diffN + ' 项）';
  }

  cmp.innerHTML = tableHtml(items, rows) + cardsHtml(items, rows);

  if (onlyDiff) {
    cmp.classList.add('only-diff');
    const sameN = rows.filter(function (r) { return !r.hasDiff && r.diff === 'exact'
                                               && r.filled === r.total; }).length;
    const blankN = rows.filter(function (r) { return r.filled === 0; }).length;
    const notes = [];
    if (sameN) notes.push(sameN + ' 项各处相同');
    if (blankN) notes.push(blankN + ' 项四所都没有数据');
    if (!diffN) {
      notes.unshift('这 ' + items.length + ' 所在已收录的字段上没有差异');
    }
    if (notes.length) {
      cmp.innerHTML += '<p class="cmp-note">已收起：' + notes.join('，')
        + '。<button type="button" class="cmp-note-btn" id="showAll">显示全部</button></p>';
      const btn = document.getElementById('showAll');
      if (btn) btn.addEventListener('click', function () { onlyDiff = false; render(); });
    }
  } else {
    cmp.classList.remove('only-diff');
  }
}

/* ---------- 事件 ---------- */
pick.addEventListener('input', function () { suggest(pick.value); });
pick.addEventListener('focus', function () { suggest(pick.value); });

pick.addEventListener('keydown', function (e) {
  const items = options();

  if (e.key === 'ArrowDown') {
    if (list.hidden) { suggest(pick.value); return; }
    e.preventDefault();                       // 否则整页跟着滚
    setActive(activeIdx < 0 ? 0 : activeIdx + 1);
    return;
  }
  if (e.key === 'ArrowUp') {
    if (list.hidden || !items.length) return;
    e.preventDefault();
    setActive(activeIdx < 0 ? items.length - 1 : activeIdx - 1);
    return;
  }
  if (e.key === 'Enter') {
    if (!list.hidden && activeIdx >= 0 && items[activeIdx]) {
      e.preventDefault();
      add(items[activeIdx].dataset.id);
      return;
    }
    /* 没手动选中但只有一个候选时，回车即选——这是搜索框的普遍预期 */
    if (!list.hidden && items.length === 1) {
      e.preventDefault();
      add(items[0].dataset.id);
    }
    return;
  }
  if (e.key === 'Escape') {
    closeList();
    status.textContent = '';
  }
});

pick.addEventListener('blur', function () {
  /* 延迟：先让候选的 click 落地，否则点选时列表先消失 */
  setTimeout(closeList, 120);
});

list.addEventListener('mousedown', function (e) {
  e.preventDefault();                         // 保住输入框焦点，别让 blur 抢先
});

list.addEventListener('click', function (e) {
  const li = e.target.closest('li[data-id]');
  if (li) add(li.dataset.id);
});
list.addEventListener('mouseover', function (e) {
  const li = e.target.closest('li[data-id]');
  if (li) setActive(options().indexOf(li));
});

pickedBox.addEventListener('click', function (e) {
  if (e.target.id === 'clearInline') { ids = []; save(); render(); return; }
  const b = e.target.closest('button[data-id]');
  if (b) remove(b.dataset.id);
});

clearBtn.addEventListener('click', function () { ids = []; save(); render(); });

if (diffBtn) {
  diffBtn.addEventListener('click', function () {
    onlyDiff = !onlyDiff;
    render();
  });
}

/* 分组折叠 */
cmp.addEventListener('click', function (e) {
  const btn = e.target.closest('.cmp-gtoggle');
  if (!btn) return;
  const body = btn.closest('tbody');
  const open = btn.getAttribute('aria-expanded') === 'true';
  btn.setAttribute('aria-expanded', String(!open));
  body.classList.toggle('is-collapsed', open);
  const caret = btn.querySelector('.cmp-gcaret');
  if (caret) caret.textContent = open ? '▸' : '▾';
});

document.getElementById('copyLink').addEventListener('click', function () {
  const btn = this;
  if (!location.origin || location.origin === 'null') {
    status.textContent = '本地打开无法生成分享链接，请在已部署的站点上复制地址栏';
    return;
  }
  const url = location.origin + location.pathname + CORE.toQuery(ids);
  function done() {
    btn.textContent = '已复制';
    setTimeout(function () { btn.textContent = '复制分享链接'; }, 1500);
  }
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(done, function () { window.prompt('复制此链接', url); });
  } else {
    window.prompt('复制此链接', url);
  }
});

window.addEventListener('popstate', function () {
  const p = CORE.parseIds(location.search, hasId);
  ids = p.ids.length ? p.ids : readStore();
  broken = false;
  render();
});

/* ---------- 启动 ---------- */
(function init() {
  const p = CORE.parseIds(location.search, hasId);
  if (p.hadParam) {
    ids = p.ids;
    broken = p.allInvalid;
    if (ids.length) save();
  } else {
    ids = readStore();
  }
  render();
})();
