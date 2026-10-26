/* ============================================================
   全站交互脚本
   1) 主题切换（localStorage 记忆，未选择时跟随系统）
   2) 详情页目录滚动联动
   3) 移动端筛选条件折叠
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

/* ---------- 首页搜索跳转 ---------- */
function heroSearch() {
  var el = document.getElementById('hq');
  if (!el) return;
  var q = el.value.trim();
  location.href = 'schools.html' + (q ? '?q=' + encodeURIComponent(q) : '');
}

/* ---------- 详情页目录联动 ---------- */
(function () {
  var toc = document.querySelector('.toc');
  if (!toc || !('IntersectionObserver' in window)) return;

  var links = Array.prototype.slice.call(toc.querySelectorAll('a[href^="#"]'));
  if (!links.length) return;

  var map = {};
  links.forEach(function (a) {
    var id = decodeURIComponent(a.getAttribute('href').slice(1));
    var el = document.getElementById(id);
    if (el) map[id] = a;
  });
  var ids = Object.keys(map);
  if (!ids.length) return;

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      links.forEach(function (a) { a.removeAttribute('aria-current'); });
      if (map[e.target.id]) map[e.target.id].setAttribute('aria-current', 'true');
    });
  }, { rootMargin: '-72px 0px -70% 0px', threshold: 0 });

  ids.forEach(function (id) { io.observe(document.getElementById(id)); });
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
