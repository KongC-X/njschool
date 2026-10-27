/* ============================================================
   全站交互脚本
   1) 主题切换（localStorage 记忆，未选择时跟随系统）
   2) 详情页目录滚动联动
   3) 移动端筛选条件折叠
   4) 详情页「加入对比」
   ============================================================ */

/* ---------- 主题 ---------- */
(function () {
  function read() {
    try { return localStorage.getItem('nj-theme'); } catch (e) { return null; }
  }
  function write(v) {
    try { localStorage.setItem('nj-theme', v); } catch (e) { /* 隐私模式忽略 */ }
  }

  var saved = read();
  /* 首帧的主题已由 base.html <head> 里的内联脚本写好（避免翻页白闪），
     这里不再重复设置，只在「浏览器未预置」时兜底一次。 */
  if (saved && !document.documentElement.getAttribute('data-theme')) {
    document.documentElement.setAttribute('data-theme', saved);
  }

  function current() {
    return document.documentElement.getAttribute('data-theme')
      || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }

  function paint(t) {
    var b = document.getElementById('themeBtn');
    if (!b) return;
    b.textContent = t === 'dark' ? '☀️' : '🌙';
    var label = t === 'dark' ? '切换到浅色模式' : '切换到深色模式';
    b.setAttribute('aria-label', label);
    b.title = label;
  }

  window.toggleTheme = function () {
    var next = current() === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    write(next);
    paint(next);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { paint(current()); });
  } else {
    paint(current());
  }
})();

/* ---------- 「/」快速聚焦搜索框 ----------
   首页与学校库都适用。输入框里按 / 不拦截，否则打不出斜杠。 */
(function () {
  document.addEventListener('keydown', function (e) {
    if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
    var t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
    var el = document.getElementById('hq') || document.getElementById('q');
    if (!el) return;
    e.preventDefault();
    el.focus();
    if (el.select) el.select();
  });
})();

/* ---------- 详情页目录联动 ---------- */
(function () {
  var toc = document.querySelector('.toc');
  if (!toc) return;

  var links = Array.prototype.slice.call(toc.querySelectorAll('a[href^="#"]'));
  if (!links.length) return;

  var map = {}, items = [];
  links.forEach(function (a) {
    var id = decodeURIComponent(a.getAttribute('href').slice(1));
    var el = document.getElementById(id);
    if (el) { map[id] = a; items.push(el); }
  });
  if (!items.length) return;

  /* 判定线：吸顶元素的下沿再往下一点。
     桌面端目录在侧边，只让开导航；窄屏目录变成横条压在正文上，还要再让开它。
     算少了会让高亮永远「提前一节」。 */
  function lineY() {
    var nav = document.querySelector('.nav');
    var navH = nav ? nav.offsetHeight : 58;
    var isBar = matchMedia('(max-width:1023px)').matches;
    return navH + (isBar ? toc.offsetHeight : 0) + 16;
  }

  /* 窄屏的目录是横滑条，章节多时活动项会滑出可视区。
     把它滚回中间——否则用户看到的高亮永远停在最左边那几项。 */
  var bar = toc.querySelector('ol');
  function revealInBar(a) {
    if (!bar || bar.scrollWidth <= bar.clientWidth + 1) return;   // 桌面竖排不处理
    var ar = a.getBoundingClientRect(), br = bar.getBoundingClientRect();
    if (ar.left < br.left || ar.right > br.right) {
      bar.scrollLeft += (ar.left - br.left) - (br.width - ar.width) / 2;
    }
  }

  /* 改成按滚动位置判定「当前读到哪一节」。
     原先用 IntersectionObserver + rootMargin 划一条百来像素的窄带，
     章节一长就没有任何标题落在这条带里，于是回调不触发、活动项停在第一节不动
     ——窄屏滑到一半时高亮还挂在「学校速览」上。
     现在的做法是「取最后一个已经越过判定线的标题」，任何滚动位置都有确定答案。 */
  var ticking = false;
  function updateActive() {
    ticking = false;
    var line = lineY(), current = null;
    for (var i = 0; i < items.length; i++) {
      if (items[i].getBoundingClientRect().top <= line) current = items[i].id;
      else break;                                  // 标题按文档顺序排列，可以提前收工
    }
    for (var k = 0; k < links.length; k++) links[k].removeAttribute('aria-current');
    if (!current) return;
    var active = map[current];
    if (!active) return;
    active.setAttribute('aria-current', 'true');
    revealInBar(active);
  }

  function onScroll() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(updateActive);
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', updateActive);
  updateActive();
})();

/* ---------- 移动端筛选条件折叠 ----------
   这段只能出现一次：此前被重复追加，两个监听器在同一次点击里互相取反
   （false → true → false），表现为「按钮点了没反应」。
   搜索框始终可见，这里只控制筛选条件区域。
*/
(function () {
  var btn = document.getElementById('filterToggle');
  var box = document.getElementById('filters');
  if (!btn || !box) return;

  function sync() {
    var open = box.dataset.open === 'true';
    btn.setAttribute('aria-expanded', String(open));
    btn.classList.toggle('is-open', open);
  }

  btn.addEventListener('click', function () {
    box.dataset.open = box.dataset.open === 'true' ? 'false' : 'true';
    sync();
  });

  sync();
})();

/* ---------- 详情页「加入对比」 ----------
   与 compare.js 共用 localStorage['nj-compare']，id 规则必须一致：学段-校名。
   按钮是切换式的：已在列表里再点一次就是移除，避免「只能加不能撤」。
   列表满 4 所时按钮置灰，指引用去对比页删——不在详情页再做一套管理界面。
*/
(function () {
  var btn = document.getElementById('cmpAdd');
  if (!btn) return;

  var MAX = 4;
  var STORE = 'nj-compare';
  var id = btn.dataset.id;
  var go = document.getElementById('cmpGo');

  function read() {
    try {
      var v = JSON.parse(localStorage.getItem(STORE) || '[]');
      return Array.isArray(v) ? v : [];
    } catch (e) { return []; }
  }
  /* 返回是否写入成功：隐私模式 / 存储被禁时 localStorage 会抛错 */
  function write(list) {
    try { localStorage.setItem(STORE, JSON.stringify(list)); return true; }
    catch (e) { return false; }
  }

  function paint(list) {
    var has = list.indexOf(id) !== -1;
    var n = list.length;
    btn.setAttribute('aria-pressed', String(has));
    if (has) {
      btn.textContent = '已在对比（' + n + '/' + MAX + '）· 点此移除';
      btn.disabled = false;
    } else if (n >= MAX) {
      btn.textContent = '对比已满（' + MAX + '/' + MAX + '）';
      btn.disabled = true;
    } else {
      btn.textContent = '＋ 加入对比';
      btn.disabled = false;
    }
    if (go) {
      go.hidden = n < 2;                       // 少于 2 所，对比页没有可看的东西
      go.textContent = '去对比（' + n + '）→';
    }
  }

  paint(read());

  btn.addEventListener('click', function () {
    var cur = read();
    var i = cur.indexOf(id);
    if (i !== -1) {
      cur.splice(i, 1);
    } else {
      if (cur.length >= MAX) return;
      cur.push(id);
    }
    if (!write(cur)) {
      btn.textContent = '浏览器禁用了本地存储，无法加入对比';
      btn.disabled = true;
      if (go) go.hidden = true;
      return;
    }
    paint(cur);
  });
})();

/* ---------- 导航下拉 ----------
   桌面端的 hover 展开由 CSS 负责；这里管点击、Esc 与点击外部关闭。
   标签本身是链接（进总览页），只有 ▾ 按钮负责展开。 */
(function () {
  var drops = document.querySelectorAll('.nav-drop');
  if (!drops.length) return;

  Array.prototype.forEach.call(drops, function (drop) {
    var btn = drop.querySelector('.nav-drop-btn');
    if (!btn) return;

    function set(open) {
      drop.dataset.open = open ? 'true' : 'false';
      btn.setAttribute('aria-expanded', String(open));
    }

    btn.addEventListener('click', function (e) {
      e.stopPropagation();               // 别让下面的「点外部关闭」立刻把它关掉
      set(drop.dataset.open !== 'true');
    });

    drop.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { set(false); btn.focus(); }
    });

    document.addEventListener('click', function (e) {
      if (!drop.contains(e.target)) set(false);
    });
  });
})();
