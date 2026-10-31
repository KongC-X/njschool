/* ============================================================
   分数查学校（DOM 层）
   数据由页面内嵌的 <script type="application/json" id="scData"> 提供，
   分档与渲染都在这里，纯前端、无请求。
   ============================================================ */
(function () {
  var node = document.getElementById('scData');
  if (!node) return;
  var ROWS = JSON.parse(node.textContent || '[]');

  var input = document.getElementById('scScore');
  var go = document.getElementById('scGo');
  var out = document.getElementById('scResult');
  var sum = document.getElementById('scSummary');

  /* 分档阈值。偏保守：临界区间给到 −15 ~ +5，
     把「刚够」和「差一点」都归进需要谨慎的一档，而不是算作稳。 */
  var SAFE = 15;
  var OK = 6;
  var EDGE = -15;

  var BANDS = [
    { key: 'safe', title: '保底', hint: '比你低 15 分以上' },
    { key: 'ok', title: '较稳', hint: '比你低 6–14 分' },
    { key: 'edge', title: '临界', hint: '在 −15 至 +5 分之间' },
    { key: 'far', title: '差距较大', hint: '比你高 15 分以上', folded: true }
  ];

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function band(d) {
    if (d >= SAFE) return 'safe';
    if (d >= OK) return 'ok';
    if (d >= EDGE) return 'edge';
    return 'far';
  }

  /* 一个学校的分数展示：「2026 线 652 察哈尔路 / 645 晓庄」。
     多校区与多口径都列出来，判断用的那条（最低）加粗。
     数值之间必须有分隔符——否则「600 594」会被读成一个数。 */
  function scoresHtml(r) {
    var parts = r.values.map(function (v) {
      var isLine = v.v === r.line;
      return '<span class="sc-val' + (isLine ? ' is-line' : '') + '">'
        + v.v + (v.label ? '<i>' + esc(v.label) + '</i>' : '') + '</span>';
    });
    return '<span class="sc-k">2026 线</span>' + parts.join('<span class="sc-sep">/</span>');
  }

  function card(r, my) {
    var d = my == null ? null : my - r.line;
    var cls = my == null ? '' : ' b-' + band(d);
    var delta = d == null ? ''
      : '<span class="sc-delta">' + (d > 0 ? '+' : '') + d + ' 分</span>';
    return '<a class="sc-card' + cls + '" href="' + esc(r.url) + '">'
      + '<span class="sc-name">' + esc(r.name)
      +   (r.conflict ? '<i class="sc-flag" title="该校投档线存在两个口径，本站并列呈现，以市招考院公布为准">口径存疑</i>' : '')
      + '</span>'
      + '<span class="sc-meta">' + esc(r.district) + ' · ' + esc(r.tier || '高中') + '</span>'
      + '<span class="sc-line">' + scoresHtml(r) + '</span>'
      + delta
      + '</a>';
  }

  function render(my) {
    out.innerHTML = '';
    if (my == null) {
      /* 没有分数时不再一次性铺 37 张卡（结果区 1,600px，把「分档规则」推到 3 屏外），
         先给前 6 所当「线表预览」，其余收进折叠区。 */
      sum.textContent = '2026 年 ' + ROWS.length + ' 所普通高中的统招投档线（从高到低）'
        + ' · 输入总分后按「保底 / 较稳 / 临界」分档';
      var head = document.createElement('div');
      head.className = 'sc-grid';
      head.innerHTML = ROWS.slice(0, 6).map(function (r) { return card(r, null); }).join('');
      out.appendChild(head);
      if (ROWS.length > 6) {
        var det = document.createElement('details');
        det.className = 'sc-far sc-all';
        det.innerHTML = '<summary>展开完整线表（其余 ' + (ROWS.length - 6) + ' 所）</summary>'
          + '<div class="sc-grid">'
          + ROWS.slice(6).map(function (r) { return card(r, null); }).join('')
          + '</div>';
        out.appendChild(det);
      }
      return;
    }

    var buckets = { safe: [], ok: [], edge: [], far: [] };
    ROWS.forEach(function (r) { buckets[band(my - r.line)].push(r); });

    var above = ROWS.filter(function (r) { return r.line <= my; }).length;
    sum.innerHTML = '<b>' + my + ' 分</b> · 达到 ' + above + ' 所学校的 2026 年投档线，'
      + '另有 ' + (ROWS.length - above) + ' 所够不着';

    BANDS.forEach(function (b) {
      var list = buckets[b.key];
      if (!list.length) return;
      if (b.folded) {
        var det = document.createElement('details');
        det.className = 'sc-far';
        det.innerHTML = '<summary>' + b.title + '（' + list.length + ' 所）· ' + b.hint + '</summary>'
          + '<div class="sc-grid">' + list.map(function (r) { return card(r, my); }).join('') + '</div>';
        out.appendChild(det);
        return;
      }
      var sec = document.createElement('section');
      sec.className = 'sc-band';
      sec.innerHTML = '<h2>' + b.title + '<span>' + list.length + ' 所 · ' + b.hint + '</span></h2>'
        + '<div class="sc-grid">' + list.map(function (r) { return card(r, my); }).join('') + '</div>';
      out.appendChild(sec);
    });

    if (!buckets.safe.length && !buckets.ok.length) {
      var tip = document.createElement('p');
      tip.className = 'sc-warn';
      tip.textContent = '这个分数段没有「保底」或「较稳」的学校。若目标是普高，'
        + '建议同时了解民办高中、国际班与中职的升学通道，别把所有希望放在一条线上。';
      out.insertBefore(tip, out.firstChild);
    }
  }

  /* 空值与非法值必须分开：
     空 = 还没输入，列出全部线表是合理的默认态；
     非法（750 / abc / 12.5）= 必须报错。
     原来两者都 return null，输 750 会静默回落到「37 所从高到低」，
     家长会以为「750 分只能上这些」——这是会误导决策的错。 */
  function readScore() {
    var raw = (input.value || '').trim();
    if (!raw) return { empty: true };
    if (!/^\d{1,3}$/.test(raw)) return { error: raw };
    var v = parseInt(raw, 10);
    if (v < 0 || v > 700) return { error: raw };
    return { value: v };
  }

  function setError(msg) {
    sum.setAttribute('role', 'alert');
    sum.className = 'sc-summary is-error';
    sum.textContent = msg;
    input.setAttribute('aria-invalid', 'true');
  }

  function clearError() {
    sum.setAttribute('role', 'status');
    sum.className = 'sc-summary';
    input.removeAttribute('aria-invalid');
  }

  /* 每次变化都同步地址栏（用 replaceState，不堆历史栈）：
     家长查完常把链接发到家庭群里，「?s=590」就是那个可复现的参数。 */
  function apply() {
    var r = readScore();
    if (r.error != null) {
      /* 不重绘、不写地址栏：保留上一次的结果，只把错误说清楚 */
      setError('总分应在 0–700 之间，你输入了「' + r.error + '」。');
      return;
    }
    clearError();
    var v = r.empty ? null : r.value;
    render(v);
    try {
      history.replaceState(null, '', v == null ? location.pathname : location.pathname + '?s=' + v);
    } catch (e) { /* file:// 下可能抛错 */ }
  }

  /* 输入防抖 200ms：每敲一位就重排 37 张卡没必要，也会让读屏连读。
     按钮、回车、常用分数仍然是立即生效。 */
  var timer = null;
  function later() {
    clearTimeout(timer);
    timer = setTimeout(apply, 200);
  }

  go.addEventListener('click', function () {
    clearTimeout(timer); apply(); input.focus();
  });
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); clearTimeout(timer); apply(); }
  });
  input.addEventListener('input', later);

  Array.prototype.forEach.call(document.querySelectorAll('.sc-chip'), function (b) {
    b.addEventListener('click', function () {
      clearTimeout(timer);
      input.value = b.dataset.v;
      apply();
    });
  });

  /* 支持 ?s=590 深链，方便从详情页/群里直接带分数过来 */
  var q = new URLSearchParams(location.search).get('s');
  if (q && !isNaN(parseInt(q, 10))) input.value = q;
  apply();
})();
