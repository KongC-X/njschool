/* ============================================================
   全站交互脚本
   1) 主题切换（localStorage 记忆，未选择时跟随系统）
   2) 详情页目录滚动联动
   3) 移动端筛选条件折叠
   4) 详情页「加入对比」
   5) 详情页「施教区自查」
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

  /* 两个图标共用同一套 SVG 外壳，只有内部路径不同 */
  function icon(inner) {
    return '<svg viewBox="0 0 24 24" width="18" height="18" fill="none"'
      + ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
      + ' stroke-linejoin="round" aria-hidden="true" focusable="false">' + inner + '</svg>';
  }
  var ICONS = {
    moon: icon('<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>'),
    sun: icon('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4'
      + 'M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>')
  };

  function paint(t) {
    var b = document.getElementById('themeBtn');
    if (!b) return;
    b.innerHTML = t === 'dark' ? ICONS.sun : ICONS.moon;
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

/* ---------- 详情页「施教区自查」 ----------
   家长的问题不是「这所学校怎么样」，而是「我家在不在这片里」。
   原来的做法是让他自己在一整段公文里找路名、比号段、判单双号。

   这里只做**定位**，不做判定：
     · 命中 → 指出「在哪条范围里、原文怎么写的」，号段对不对由家长核对；
     · 未命中 → 说明三种常见原因，不暗示「你不能上」。

   为什么不自动判断号段：各校写法有「[19-69号(单)]」「[6号-底]」「单 21 号以上」
   「不分单双」等十余种，机器判错一次，代价可能是一套房的决策。
*/
(function () {
  var box = document.getElementById('skBox');
  var input = document.getElementById('skInput');
  var out = document.getElementById('skOut');
  if (!box || !input || !out) return;

  var anchor = document.getElementById('shijiaoqu');
  var scope = anchor ? anchor.parentNode : null;
  if (!scope) return;
  /* 范围限定在这一节：从锚点起，到下一个 h2/h3 为止 */
  var nodes = [];
  var n = anchor.nextElementSibling;
  while (n && !/^H[23]$/.test(n.tagName)) {
    nodes.push(n);
    n = n.nextElementSibling;
  }

  var HINT = out.textContent;

  /* 每条路名的原始 HTML 先存起来：反复输入时要把上一次的 <mark> 还原 */
  var items = [];
  nodes.forEach(function (node) {
    var lis = node.classList && node.classList.contains('roads')
      ? node.querySelectorAll('li') : [];
    Array.prototype.forEach.call(lis, function (li) {
      if (!li.dataset.raw) li.dataset.raw = li.innerHTML;
      items.push({ el: li, text: li.textContent, campus: campusOf(node) });
    });
    if (node.tagName === 'BLOCKQUOTE') {
      if (!node.dataset.raw) node.dataset.raw = node.innerHTML;
      items.push({ el: node, text: node.textContent, campus: campusOf(node) });
    }
  });
  if (!items.length) return;

  /* 校区名写在列表前面的一段 <p><strong>① 琅琊路校区</strong></p> 里 */
  function campusOf(node) {
    var p = node.previousElementSibling;
    while (p && p.tagName !== 'P') p = p.previousElementSibling;
    if (!p) return '';
    var t = (p.textContent || '').trim();
    return /^[①②③④⑤⑥⑦⑧⑨⑩]/.test(t) ? t : '';
  }

  function clear() {
    items.forEach(function (it) { it.el.innerHTML = it.el.dataset.raw; });
  }

  function esc(s) {
    return String(s).replace(/[&<>]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c];
    });
  }

  function run() {
    var q = (input.value || '').trim();
    clear();
    if (!q) {
      out.className = 'sk-out';
      out.textContent = HINT;
      return;
    }
    var hits = items.filter(function (it) { return it.text.indexOf(q) !== -1; });

    if (!hits.length) {
      out.className = 'sk-out miss';
      out.innerHTML = '没有在这所学校的施教区文本里找到「' + esc(q) + '」。'
        + '常见原因有三个：① 该校施教区按「××路以南」这类四至方式描述，没有逐条列路名；'
        + '② 你输入的是小区名，档案里写的是路段名（可换一个说法再试）；'
        + '③ 这所学校确实不在你所在的片区。';
      return;
    }

    /* 只高亮命中的前若干条，避免整页都是色块 */
    hits.slice(0, 4).forEach(function (it) {
      it.el.innerHTML = it.el.dataset.raw.replace(
        new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'),
        function (m) { return '<mark class="sk-hit">' + m + '</mark>'; });
    });

    var first = hits[0];
    var where = first.campus ? '出自「' + esc(first.campus) + '」的范围' : '出现在施教区原文里';
    var excerpt = first.text.length > 60 ? first.text.slice(0, 60) + '…' : first.text;
    out.className = 'sk-out hit';
    out.innerHTML = '找到「' + esc(q) + '」，' + where + '（共 ' + hits.length + ' 处，已高亮）。'
      + '<br>原文写法：<strong>' + esc(excerpt) + '</strong>'
      + '<br>号段是否符合请对照上面原文核对；不确定时以区教育局公示与学校答复为准。';
  }

  input.addEventListener('input', run);
  /* 回车不提交表单（这里没有 form），但要让用户看到结果已经出来 */
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); run(); }
  });
})();

/* ---------- 导航下拉 ----------
   JS 控制开合 + 200ms 关闭宽限。不用 CSS :hover：指针跨过标签与菜单之间
   几像素空隙时悬停会断，菜单瞬间收起（实测空隙 6px 即复现）。
   鼠标：移入开、移出延后关；触屏：点 ▾ 切换，不挂悬停事件。
*/
(function () {
  var GRACE = 200;
  var canHover = window.matchMedia && window.matchMedia('(hover:hover)').matches;
  var drops = document.querySelectorAll('.nav-drop');
  if (!drops.length) return;

  Array.prototype.forEach.call(drops, function (drop) {
    var btn = drop.querySelector('.nav-drop-btn');
    if (!btn) return;
    var timer = null;

    function set(open) {
      if (timer) { clearTimeout(timer); timer = null; }
      drop.dataset.open = open ? 'true' : 'false';
      btn.setAttribute('aria-expanded', String(open));
    }

    if (canHover) {
      drop.addEventListener('mouseenter', function () { set(true); });
      drop.addEventListener('mouseleave', function () {
        if (timer) clearTimeout(timer);
        timer = setTimeout(function () { set(false); }, GRACE);
      });
    }

    /* 焦点离开就收起。刻意不在 focusin 时自动展开：
       触屏上 tap 会先触发 focus 再触发 click，若 focus 就展开，
       紧接着的 click 会把它切换成关闭，表现为「点了没反应」。
       键盘用户按 Enter/Space 激活按钮即可展开（原生 button 行为）。 */
    drop.addEventListener('focusout', function (e) {
      if (!drop.contains(e.relatedTarget)) set(false);
    });

    btn.addEventListener('click', function (e) {
      e.stopPropagation();          // 否则会被下面的「点外部关闭」当场关掉
      /* 鼠标设备上点击只负责「开」：悬停已经开着了，再切换成关反而别扭 */
      set(canHover ? true : drop.dataset.open !== 'true');
    });

    /* Esc 挂在 document 上而不是 drop 上：
       挂在 drop 上时，只有焦点在下拉内部才收得到——鼠标用户把菜单悬停出来、
       焦点还在别处，按 Esc 就毫无反应。 */
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape' || drop.dataset.open !== 'true') return;
      var inside = drop.contains(document.activeElement);
      set(false);
      if (inside) btn.focus();
    });

    document.addEventListener('click', function (e) {
      if (!drop.contains(e.target)) set(false);
    });
  });
})();

/* ---------- 回到顶部 ----------
   全站统一一个按钮，由脚本创建——没有 JS 时页面里不该出现一个点不动的圆钮。

   显示门槛取「一屏的 3/4，且不少于 400px」：太早出现会挡住刚进入页面的视线，
   太晚则等于没有。回到顶部后自动隐藏，滚动用 requestAnimationFrame 节流，
   避免每帧都读一次 scrollY 触发重排。
*/
(function () {
  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'to-top';
  btn.setAttribute('aria-label', '回到页面顶部');
  btn.setAttribute('aria-hidden', 'true');
  btn.tabIndex = -1;
  btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"'
    + ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg>';
  document.body.appendChild(btn);
  /* 给 body 打个标记：滚到底时按钮会压住页脚最后一行文字，
     样式层据此多留一点底部空白。用类而不是直接改内联样式，
     无脚本时这段留白不会存在。 */
  document.body.classList.add('has-totop');

  var on = false;
  var ticking = false;

  function threshold() {
    return Math.max(400, window.innerHeight * 0.75);
  }

  function paint(show) {
    if (show === on) return;
    on = show;
    btn.classList.toggle('is-on', show);
    /* 隐藏时同时摘出 tab 序与无障碍树：否则读屏仍会念到一个看不见的按钮 */
    btn.setAttribute('aria-hidden', String(!show));
    btn.tabIndex = show ? 0 : -1;
  }

  function update() {
    ticking = false;
    var y = window.pageYOffset || document.documentElement.scrollTop || 0;
    paint(y > threshold());
  }

  function request() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(update);
  }

  btn.addEventListener('click', function () {
    var reduce = window.matchMedia
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* 先把焦点交给主内容，再滚动：否则按钮滚动到位后被隐藏，
       键盘用户的焦点会掉到 body 上，等于丢失位置。 */
    var main = document.getElementById('main');
    if (main) {
      if (!main.hasAttribute('tabindex')) main.setAttribute('tabindex', '-1');
      try { main.focus({ preventScroll: true }); } catch (e) { main.focus(); }
    }
    window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    /* 不支持 scrollTo 选项的浏览器会忽略 behavior，退化为瞬时跳转，可接受 */
  });

  window.addEventListener('scroll', request, { passive: true });
  window.addEventListener('resize', request);
  update();
})();
