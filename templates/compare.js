{# 对比页脚本：数据来自 assets/schools-data.js #}
const COLS = window.__SCHOOLS__.cols;
const LABELS = window.__SCHOOLS__.factLabels;
const DATA = window.__SCHOOLS__.rows.map(function (row) {
  var o = {};
  COLS.forEach(function (k, i) { o[k] = row[i]; });
  o.id = o.level + '-' + o.name;
  o.url = 'schools/' + encodeURIComponent(o.id) + '.html';
  return o;
});
const BY_ID = {};
DATA.forEach(function (s) { BY_ID[s.id] = s; });

const MAX = 4;
const STORE = 'nj-compare';
const pick = document.getElementById('pick');
const list = document.getElementById('pickList');
const pickedBox = document.getElementById('picked');
const cmp = document.getElementById('cmp');
const clearBtn = document.getElementById('clearAll');

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

/* 来源优先级：URL 参数（可分享） > 本地记忆 */
function loadSelected() {
  var fromUrl = new URLSearchParams(location.search).get('ids');
  var ids = fromUrl ? fromUrl.split(',').filter(Boolean) : [];
  if (!ids.length) {
    try { ids = JSON.parse(localStorage.getItem(STORE) || '[]'); } catch (e) { ids = []; }
  }
  return ids.filter(function (id) { return BY_ID[id]; }).slice(0, MAX);
}

var selected = loadSelected();

function save() {
  try { localStorage.setItem(STORE, JSON.stringify(selected)); } catch (e) {}
}

function add(id) {
  if (selected.indexOf(id) !== -1) return;
  if (selected.length >= MAX) {
    list.innerHTML = '<li class="pick-empty">最多对比 4 所，请先移除一所</li>';
    list.hidden = false;
    return;
  }
  selected.push(id);
  save();
  pick.value = '';
  list.hidden = true;
  render();
}

function remove(id) {
  selected = selected.filter(function (x) { return x !== id; });
  save();
  render();
}

function suggest(q) {
  q = q.trim().toLowerCase();
  if (!q) { list.hidden = true; return; }
  var hits = DATA.filter(function (s) {
    if (selected.indexOf(s.id) !== -1) return false;
    return (s.name + ' ' + (s.short || '') + ' ' + s.district + ' ' + (s.tier || ''))
      .toLowerCase().indexOf(q) !== -1;
  }).slice(0, 8);

  if (!hits.length) {
    list.innerHTML = '<li class="pick-empty">没有匹配的学校</li>';
  } else {
    list.innerHTML = hits.map(function (s) {
      return '<li role="option" tabindex="0" data-id="' + esc(s.id) + '">'
        + '<span>' + esc(s.name) + '</span>'
        + '<em>' + esc(s.district) + ' · ' + esc(s.level) + '</em></li>';
    }).join('');
  }
  list.hidden = false;
}

function chip(id) {
  var s = BY_ID[id];
  return '<button type="button" class="chip on" data-id="' + esc(id) + '" aria-label="移除 ' + esc(s.name) + '">'
    + esc(s.name) + ' ×</button>';
}

/* 对比表的行：先固定元数据，再按需追加事实行 */
function rowsFor(items) {
  var rows = [
    { label: '学段', get: function (s) { return s.level; } },
    { label: '性质', get: function (s) { return s.type; } },
    { label: '行政区', get: function (s) { return s.district; } },
    { label: '梯队', get: function (s) { return s.tier; } },
    { label: '官方渠道', get: function (s) { return s.hasSite ? '有官网' : '暂无可用官网'; } }
  ];
  Object.keys(LABELS).forEach(function (k) {
    var any = items.some(function (s) { return s.facts && s.facts[k]; });
    if (any) {
      rows.push({ label: LABELS[k], get: function (s) {
        return (s.facts && s.facts[k]) || '—';
      }});
    }
  });
  rows.push({ label: '一句话定位', get: function (s) { return s.tagline; } });
  return rows;
}

function render() {
  pickedBox.innerHTML = selected.map(chip).join('')
    + (selected.length ? '<button type="button" class="chip" id="clearInline">清空</button>' : '');
  clearBtn.hidden = selected.length === 0;

  if (selected.length < 2) {
    cmp.innerHTML = '<div class="empty"><strong>先选两所学校</strong>'
      + '在上方输入校名，点选候选即可加入对比。最多 4 所。</div>';
    return;
  }

  var items = selected.map(function (id) { return BY_ID[id]; });
  var rows = rowsFor(items);

  cmp.innerHTML = '<div class="cmp" style="--n:' + items.length + '">'
    + items.map(function (s) {
        var t = s.type === '民办' ? 'b-pri' : 'b-pub';
        return '<div class="cmp-col">'
          + '<h2 class="cmp-name"><a href="' + s.url + '">' + esc(s.name) + '</a></h2>'
          + '<div class="badges">'
          + '<span class="b b-lv">' + esc(s.level) + '</span>'
          + '<span class="b ' + t + '">' + esc(s.type) + '</span>'
          + '<span class="b b-d">' + esc(s.district) + '</span>'
          + '</div>'
          + '<dl class="cmp-dl">'
          + rows.map(function (r) {
              var v = r.get(s);
              return '<dt>' + esc(r.label) + '</dt><dd>' + esc(v || '—') + '</dd>';
            }).join('')
          + '</dl>'
          + '<a class="more" href="' + s.url + '">完整档案 →</a>'
          + '</div>';
      }).join('')
    + '</div>';
}

pick.addEventListener('input', function () { suggest(pick.value); });
pick.addEventListener('focus', function () { suggest(pick.value); });

list.addEventListener('click', function (e) {
  var li = e.target.closest('li[data-id]');
  if (li) add(li.dataset.id);
});
list.addEventListener('keydown', function (e) {
  if (e.key === 'Enter') {
    var li = e.target.closest('li[data-id]');
    if (li) add(li.dataset.id);
  }
});

pickedBox.addEventListener('click', function (e) {
  if (e.target.id === 'clearInline') { selected = []; save(); render(); return; }
  var b = e.target.closest('button[data-id]');
  if (b) remove(b.dataset.id);
});

clearBtn.addEventListener('click', function () {
  selected = []; save(); render();
});

document.getElementById('copyLink').addEventListener('click', function () {
  var url = location.origin + location.pathname
    + (selected.length ? '?ids=' + selected.map(encodeURIComponent).join(',') : '');
  var btn = this;
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

render();
