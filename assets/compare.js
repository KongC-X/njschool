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
const CD = window.__COMPARE_DATA__;

/* 两个数据文件按下标对齐：
   schools-data.js 给列表页要的（校名/区/学段/性质/梯队/一句话），
   schools-compare.js 给对比页专属的（facts/官网有无/已声明缺口）。
   这样列表页不用为对比字段买单——它此前已经顶到 197/200KB 预算。 */
const DATA = window.__SCHOOLS__.rows.map(function (row, i) {
  const o = {};
  COLS.forEach(function (k, k2) { o[k] = row[k2]; });
  const extra = (CD && CD.rows[i]) || [null, 0];
  o.facts = extra[0];
  o.hasSite = extra[1];
  o.id = o.level + '-' + o.name;
  o.url = 'schools/' + encodeURIComponent(o.id) + '.html';
  o.missing = (CD && CD.missing && CD.missing[o.id]) || null;
  return o;
});
const BY_ID = {};
DATA.forEach(function (s) { BY_ID[s.id] = s; });

const MAX = 4;
const STORE = 'nj-compare';
/* 分组按「家长选校时的思考顺序」排：先确认这是不是同一类学校，
   再看出口（升学/对口），再看师资与规模，再看要花多少钱，最后看口碑。
   旧的 identity/path/evidence 是内部模型词，且「证据」组里放的是校址与办学规模，
   名实不符。 */
const GROUPS = {
  base:    '一、基本信息',
  outcome: '二、升学与成绩',
  faculty: '三、师资与规模',
  enroll:  '四、招生与费用',
  voice:   '五、口碑与定位'
};

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

/* 「官方还没说死」的标记（校名暂定 / 施教区含过渡）。
   这类信息如果只在档案正文里，用户并排对比时会把它当确定信息用。 */
function warnHtml(s) {
  const list = (s.marks || '').split(' ').filter(Boolean);
  if (!list.length) return '';
  return '<span class="cmp-head-warn">' + list.map(function (m) {
    return '<span class="b b-warn">' + esc(m) + '</span>';
  }).join('') + '</span>';
}

/* ---------- 状态 ---------- */
let ids = [];
let broken = false;
let onlyDiff = false;
let showBlank = false;   // 是否展开「四所都没有数据」的行

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
  /* 四所都没值的行（招生计划 0/4、学费 0/4……）整行只有横线。
     诚实是必要的，但三整行的空白会把有内容的行稀释掉。
     默认折成表末一行摘要，点开再展开——详情一条不少。 */
  const blanks = rows.filter(function (r) { return r.filled === 0; });
  const visible = (showBlank || onlyDiff) ? rows : rows.filter(function (r) { return r.filled > 0; });

  let out = '<div class="cmp-wrap"><table class="cmp-table" data-n="' + n + '">'
    + '<caption class="sr-only">' + n + ' 所学校对比</caption><thead><tr>'
    + '<th scope="col" class="cmp-corner">对比项</th>';

  const cov = CORE.coverage(rows, items);
  items.forEach(function (s, i) {
    const c = cov[i];
    /* 列头写「11/21 项」：家长一眼知道这一列的数据有多稀，
       不用逐格去数横线，也不会误以为「没写=没有」。 */
    out += '<th scope="col" class="cmp-head">'
      + '<a href="' + s.url + '">' + esc(s.name) + '</a>'
      + '<span class="cmp-head-meta">' + esc(s.level) + ' · ' + esc(s.type)
      + ' · ' + esc(s.district) + '</span>'
      + '<span class="cmp-head-cov" title="本站已收录 ' + c.has + ' 项，'
      + c.gap + ' 项为该档案声明的数据缺口">有数据 ' + c.has + '/' + c.total + '</span>'
      + warnHtml(s) + '</th>';
  });
  out += '</tr></thead>';

  let group = '';
  visible.forEach(function (row, i) {
    if (row.group !== group) {
      if (group) out += '</tbody>';
      group = row.group;
      const inGroup = visible.filter(function (r) { return r.group === group; });
      const count = inGroup.length;
      const diffN = inGroup.filter(function (r) { return r.hasDiff; }).length;
      out += '<tbody data-group="' + group + '"><tr class="cmp-ghead"><th colspan="' + (n + 1) + '">'
        + '<button type="button" class="cmp-gtoggle" aria-expanded="true" data-group="' + group + '">'
        + '<span class="cmp-gcaret" aria-hidden="true">▾</span>'
        + esc(GROUPS[group] || group)
        + '<span class="cmp-gcount">' + count + ' 项'
        + (diffN ? ' · <b>' + diffN + ' 项有差异</b>' : '') + '</span>'
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
      + (row.spread
          ? '<span class="cmp-spread" title="最高与最低相差 ' + row.spread.delta
            + row.spread.unit + '">差 ' + fmtNum(row.spread.delta) + row.spread.unit + '</span>'
          : (row.filled < row.total
              ? '<span class="cmp-fill">' + row.filled + '/' + row.total + '</span>' : ''))
      + '</th>'
      + row.cells.map(function (c) { return cellHtml(row, c); }).join('')
      + '</tr>';
    if (i === visible.length - 1) out += '</tbody>';
  });

  if (blanks.length && !showBlank && !onlyDiff) {
    const names = blanks.map(function (r) { return r.label; });
    /* 「这 N 所都没有数据」读起来像「两校在这项上没差别」——
       实际是本站没抽取到，学校之间大概率并不相同。
       对比页的全部立场是「只标不同不标更好」，那就不能让缺失伪装成相同。 */
    out += '<tbody class="cmp-blanksum"><tr class="cmp-blankrow">'
      + '<th scope="row">未收录</th>'
      + '<td colspan="' + n + '">' + esc(names.join(' · '))
      + ' ——本站未获取上述 ' + blanks.length + ' 项，<strong>不代表各校相同</strong>'
      + '<button type="button" class="cmp-blanktoggle" id="showBlank">展开 ' + blanks.length + ' 项</button>'
      + '</td></tr></tbody>';
  }
  out += '</table></div>';
  return out;
}

/* 数字展示：过万折成「2.2 万」，否则原样。
   对比表一列只有 200px，「22,000」＋单位已经要折行，写「2.2 万」更省一行。 */
function fmtNum(v) {
  if (v >= 10000) return (v / 10000).toFixed(1).replace(/\.0$/, '') + ' 万';
  return String(v);
}

function brief(text, n) {
  const t = String(text == null ? '' : text);
  return t.length > n ? t.slice(0, n) + '…' : t;
}

/* 顶部「先看这几处不同」。
   表格有二十来行，家长第一眼看到的往往是「基本信息」这类无差异项——
   把最有决策价值的差异提到最前面，是这一屏唯一能做的「结论先行」。
   但只陈述「不一样」，不排序、不给推荐：排序还取决于通勤、班型、孩子性格。 */
function summaryHtml(items, rows) {
  const live = rows.filter(function (r) { return r.filled > 0; });
  const diffs = live.filter(function (r) { return r.hasDiff; });
  const blanks = rows.filter(function (r) { return r.filled === 0; });
  if (!diffs.length) return '';

  /* 选哪几条放到速览里，不能按表格顺序取前 4——
     那样会全被「性质 / 行政区 / 梯队」这类基本信息占满，而家长最想先看的是
     升学、师资、费用。这里给分组加权，并限制同一组最多 2 条。 */
  const GW = { outcome: 5, faculty: 4, enroll: 4, voice: 3, base: 2 };
  const cands = diffs.slice().sort(function (a, b) {
    return ((GW[b.group] || 1) - (GW[a.group] || 1)) || (a.priority - b.priority);
  });
  const used = {}, picks = [];
  cands.forEach(function (r) {
    if (picks.length >= 4) return;
    used[r.group] = used[r.group] || 0;
    if (used[r.group] >= 2) return;
    used[r.group] += 1;
    picks.push(r);
  });

  const lis = picks.map(function (r) {
    const vals = items.map(function (s, i) {
      const c = r.cells[i];
      if (c.state !== 'has') {
        /* 用「无数据」而不是「—」：速览里破折号会被读成「值为空」，
            「无数据」才明确指向「本站没收录」，与表格里的两种缺失状态呼应。 */
        return '<em class="is-miss">' + (c.state === 'gap' ? '该校声明缺口' : '无数据') + '</em>';
      }
      /* 两所对比时「每格都独一无二」，全上色等于没重点；
         三所以上时只给「和别人都不一样」的那一格上色才有信息量。 */
      const odd = c.isDiff && items.length >= 3;
      return '<span' + (odd ? ' class="is-diff"' : '')
        + ' title="' + esc(s.name) + '">' + esc(brief(c.text, 18)) + '</span>';
    }).join('<i aria-hidden="true">·</i>');
    return '<li><b>' + esc(r.label) + '</b><span class="cmp-sum-vals">' + vals + '</span></li>';
  }).join('');

  return '<section class="cmp-summary" aria-labelledby="cmpSumH">'
    + '<h2 id="cmpSumH">先看这几处不同'
    + '<span>' + live.length + ' 项有数据 · ' + diffs.length + ' 项有差异'
    + (blanks.length ? ' · ' + blanks.length + ' 项本站未收录' : '') + '</span></h2>'
    + '<ul>' + lis + '</ul>'
    + '<p class="cmp-summary-note">按决策权重取前 4 项有差异的字段（升学、师资、费用优先）。这里只说明「哪里不一样」，'
    + '不判断「哪个更好」——最终怎么选还取决于通勤、班型与孩子的性格。</p>'
    + '</section>';
}

/* 窄屏用：一校一张卡。
   表格在 360px 上要靠横滑才看得全，4 列的校名会被压成两行碎片；
   卡片模式把「行」竖过来，逐校读完再读下一所，比横滑省力。
   两套结构同时输出，用 CSS 媒体查询切换（隐藏的那套不进无障碍树）。 */
function cardsHtml(items, rows) {
  const blanks = rows.filter(function (r) { return r.filled === 0; });
  const visible = (showBlank || onlyDiff) ? rows : rows.filter(function (r) { return r.filled > 0; });
  return '<div class="cmp-cards">' + items.map(function (s) {
    const body = visible.map(function (row) {
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
      + warnHtml(s)
      + '<dl>' + body + '</dl>'
      + (blanks.length && !showBlank && !onlyDiff
          ? '<p class="cmp-card-note">另有 ' + blanks.length + ' 项未收录：'
            + esc(blanks.map(function (r) { return r.label; }).join('、')) + '</p>'
          : '')
      + '</article>';
  }).join('') + '</div>';
}

function render() {
  pickedBox.innerHTML = ids.map(chip).join('')
    /* 清空用文字按钮，不套 chip：原来和已选学校同一个形状，
       夹在蓝色选中项里会被当成「还有一个已选项」 */
    + (ids.length ? '<button type="button" class="chip-clear" id="clearInline">清空</button>' : '');
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
  const rows = CORE.buildRows(SPECS, items, function (id) {
    return BY_ID[id] && BY_ID[id].missing;
  });
  const diffN = rows.filter(function (r) { return r.hasDiff; }).length;

  if (diffBtn) {
    diffBtn.hidden = false;
    diffBtn.setAttribute('aria-pressed', String(onlyDiff));
    /* 按钮上的数字必须是「点下去会剩几行」，不是「有几项存在差异」。
       两者不等：有值但不构成差异的行、以及只有一所填了值的行都会留下
       （缺失本身就是信号）。写成 diffN 会让人点完发现行数对不上。 */
    const keepN = rows.filter(function (r) {
      const same = r.diff === 'exact' && r.filled === r.total && !r.hasDiff;
      return !same && r.filled > 0;
    }).length;
    diffBtn.textContent = onlyDiff
      ? '显示全部 ' + rows.length + ' 项'
      : '只看差异（' + keepN + ' 项）';
  }

  cmp.innerHTML = summaryHtml(items, rows) + tableHtml(items, rows) + cardsHtml(items, rows);
  /* 表格是整体重排的，读屏不会自己发现内容变了。
     往状态区写一句「现在对比的是哪几所、共多少项」，加/删学校才播报得到。 */
  if (items.length) {
    status.textContent = '正在对比 ' + items.length + ' 所，共 '
      + rows.length + ' 项：' + items.map(function (s) { return s.name; }).join('、');
  }

  const blankBtn = document.getElementById('showBlank');
  if (blankBtn) {
    blankBtn.addEventListener('click', function () { showBlank = true; render(); });
  }

  if (onlyDiff) {
    cmp.classList.add('only-diff');
    const sameN = rows.filter(function (r) { return !r.hasDiff && r.diff === 'exact'
                                               && r.filled === r.total; }).length;
    const blankN = rows.filter(function (r) { return r.filled === 0; }).length;
    const notes = [];
    if (sameN) notes.push(sameN + ' 项各处相同');
    if (blankN) notes.push(blankN + ' 项本站未获取（不代表相同）');
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
