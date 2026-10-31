/* ============================================================
   对比核心：纯函数，不碰 DOM，可在 Node 里直接单测。

   这里的三个决定，都是为了让「对比」真的能看出差异：

   1. buildRows 把「每校一列」变成「每行一项」。
      之前四列各自渲染 <dl>，列内换行会让后续行整体错位，
      「第 3 行是投档线」这个对位关系就没了。

   2. 「未获取」和「—」必须分开。
      未获取 = 该校档案的「数据缺口」小节明确点名过这一项；
      —      = 本站没抽到，不代表学校没有。
      混成一个符号，等于替学校下结论。

   3. 只标「不同」，不标「更好」。
      全角转半角、空白归一之后仍不同才算不同——
      再激进的归一（比如去掉「小学/中学」）会把真差异抹平。

   契约：window.__NJ_COMPARE__ = { norm, buildRows, parseIds, toQuery }
   ============================================================ */
(function (root) {
  'use strict';

  var GAP_TEXT = '未获取';
  var NA_TEXT = '—';

  /* 全角 ASCII → 半角；空白归一；忽略大小写 */
  function norm(v) {
    return String(v == null ? '' : v)
      .replace(/[\uFF01-\uFF5E]/g, function (c) {
        return String.fromCharCode(c.charCodeAt(0) - 0xFEE0);
      })
      .replace(/\u3000/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
  }

  /* 从单元格文本里取第一个数：招生计划「两校区共 980 人」取 980，
     学费「22,000 元/生·学期」取 22000。取不到返回 null（不做猜测）。 */
  function numOf(text) {
    var m = String(text == null ? '' : text).replace(/[,，\s]/g, '').match(/-?\d+(?:\.\d+)?/);
    return m ? parseFloat(m[0]) : null;
  }

  function cellOf(spec, item, missing) {
    var text = '', state = 'has', val;

    if (spec.source === 'facts') {
      /* mode:excerpt 的字段也是从 facts 里来的（构建期由 facts.excerpt 截取），
         只是渲染时用「原文摘录」样式，不参与精确比对。 */
      val = item.facts && item.facts[spec.field];
      if (val) {
        text = val;
      } else if (missing && missing.indexOf(spec.field) !== -1) {
        text = GAP_TEXT;
        state = 'gap';
      } else {
        text = NA_TEXT;
        state = 'none';
      }
    } else if (spec.source === 'channel') {
      text = item.hasSite ? '有官网' : '暂无可用官网';
    } else if (spec.source === 'tagline') {
      text = item.tagline || '';
      if (!text) { text = NA_TEXT; state = 'none'; }
    } else {                                  /* index */
      text = item[spec.field] || '';
      if (!text) { text = NA_TEXT; state = 'none'; }
    }

    return { text: text, state: state, isDiff: false };
  }

  function buildRows(specs, items, getMissing) {
    var list = specs.slice().sort(function (a, b) { return a.priority - b.priority; });
    var rows = [];

    list.forEach(function (spec) {
      /* spec.levels：只对某些学段有意义的行。
         「2026 投档线」只存在于高中，四所小学并排时这一行永远是四个横线，
         占位又误导。学段不匹配就整行不出——这是结构性的不适配，不是数据缺口。 */
      if (spec.levels && !items.some(function (it) {
        return spec.levels.indexOf(it.level) !== -1;
      })) {
        return;
      }

      var cells = items.map(function (it) {
        return cellOf(spec, it, getMissing ? getMissing(it.id) : null);
      });
      var filled = 0;
      for (var i = 0; i < cells.length; i++) {
        if (cells[i].state === 'has') filled++;
      }

      var row = {
        key: spec.key, label: spec.label, group: spec.group, diff: spec.diff,
        priority: spec.priority,
        mode: spec.mode || 'text', unit: spec.unit || '',
        cells: cells, filled: filled, total: cells.length, hasDiff: false
      };

      /* 数值行的「差幅」：只在**所有有值的格子都能解析成数字**时才算。
         有一个是「约 90%」这种带修饰的，就不给差值——差值比原文更容易被当成精确结论。 */
      if (spec.num && filled >= 2) {
        var nums = [];
        cells.forEach(function (c) {
          if (c.state === 'has') {
            var n = numOf(c.text);
            if (n !== null) nums.push(n);
          }
        });
        if (nums.length === filled && nums.length >= 2) {
          var lo = Math.min.apply(null, nums), hi = Math.max.apply(null, nums);
          if (hi > lo) row.spread = { min: lo, max: hi, delta: hi - lo, unit: spec.unit || '' };
        }
      }

      /* 至少两所有值才谈得上「不同」；只有一所填了，那是「缺」不是「异」 */
      if (spec.diff === 'exact' && filled >= 2) {
        var vals = cells.map(function (c) { return norm(c.text); });
        var uniq = {};
        vals.forEach(function (v) { uniq[v] = (uniq[v] || 0) + 1; });
        if (Object.keys(uniq).length > 1) {
          row.hasDiff = true;
          /* 只标行内「独一无二」的格子。四格全不同时四格都标，
             语义仍成立：每一所都和别人不一样 */
          cells.forEach(function (c, k) { c.isDiff = uniq[vals[k]] === 1; });
        }
      }
      rows.push(row);
    });

    return rows;
  }

  /* 每所学校在各组里有几项拿到了数据——列头显示「8/18 项」，
     让「这一列本来就是稀的」一眼可见，而不是逐格去数横线。 */
  function coverage(rows, items) {
    return items.map(function (it, i) {
      var has = 0, gap = 0;
      rows.forEach(function (r) {
        var st = r.cells[i].state;
        if (st === 'has') has++;
        else if (st === 'gap') gap++;
      });
      return { has: has, gap: gap, total: rows.length };
    });
  }

  /* ?ids= 解析：去重、跳过无效、区分「没传参」与「传了但全失效」 */
  function parseIds(search, hasId) {
    var raw = new URLSearchParams(search || '').get('ids');
    if (!raw) return { ids: [], hadParam: false, allInvalid: false };

    var seen = {}, ids = [], invalid = 0;
    raw.split(',').forEach(function (piece) {
      var id = piece.trim();
      if (!id) return;
      if (!hasId(id)) { invalid++; return; }
      if (seen[id]) return;
      seen[id] = 1;
      ids.push(id);
    });
    return {
      ids: ids,
      hadParam: true,
      allInvalid: ids.length === 0 && invalid > 0
    };
  }

  function toQuery(ids) {
    return ids.length ? '?ids=' + ids.map(encodeURIComponent).join(',') : '';
  }

  root.__NJ_COMPARE__ = {
    norm: norm, numOf: numOf, buildRows: buildRows, coverage: coverage,
    parseIds: parseIds, toQuery: toQuery
  };
})(typeof window !== 'undefined' ? window : this);
