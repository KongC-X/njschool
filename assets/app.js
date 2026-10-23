/* 主题切换 + 首页搜索跳转
 * 说明：主题以 data-theme 属性表达，localStorage 记忆用户选择，
 *       未选择时跟随系统偏好。样式令牌见 tokens.css。
 */
(function () {
  var saved = localStorage.getItem('nj-theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);

  function currentTheme() {
    var cur = document.documentElement.getAttribute('data-theme');
    if (cur) return cur;
    return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function paintIcon(t) {
    var b = document.getElementById('themeBtn');
    if (!b) return;
    b.textContent = t === 'dark' ? '☀️' : '🌙';
    b.setAttribute('aria-label', t === 'dark' ? '切换到浅色模式' : '切换到深色模式');
    b.title = b.getAttribute('aria-label');
  }

  window.toggleTheme = function () {
    var next = currentTheme() === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('nj-theme', next);
    paintIcon(next);
  };

  document.addEventListener('DOMContentLoaded', function () {
    paintIcon(currentTheme());
  });
})();

/* 首页搜索框：回车或点击后跳转学校库并带上关键词 */
function heroSearch() {
  var el = document.getElementById('hq');
  if (!el) return;
  var q = el.value.trim();
  location.href = 'schools.html' + (q ? '?q=' + encodeURIComponent(q) : '');
}

/* 详情页目录联动：滚动时高亮当前章节（渐进增强，无 IntersectionObserver 时静默跳过） */
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

/* 详情页目录联动：滚动时高亮当前章节（渐进增强，无 IntersectionObserver 时静默跳过） */
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

/* 移动端筛选抽屉开合（桌面端过滤器常显，按钮不渲染可见） */
(function () {
  var btn = document.getElementById('filterToggle');
  var box = document.getElementById('filters');
  if (!btn || !box) return;
  btn.addEventListener('click', function () {
    var open = box.dataset.open !== 'true';
    box.dataset.open = open ? 'true' : 'false';
    btn.setAttribute('aria-expanded', String(open));
  });
  btn.setAttribute('aria-expanded', String(box.dataset.open === 'true'));
})();

/* 移动端筛选抽屉开合（桌面端过滤器常显，按钮不渲染可见） */
(function () {
  var btn = document.getElementById('filterToggle');
  var box = document.getElementById('filters');
  if (!btn || !box) return;
  btn.addEventListener('click', function () {
    var open = box.dataset.open !== 'true';
    box.dataset.open = open ? 'true' : 'false';
    btn.setAttribute('aria-expanded', String(open));
  });
  btn.setAttribute('aria-expanded', String(box.dataset.open === 'true'));
})();
