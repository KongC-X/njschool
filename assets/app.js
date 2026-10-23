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
