/* ============================================================
   搜索核心：纯函数，不碰 DOM，可在 Node 里直接单测。

   为什么单独成文件：学校库、对比页候选框、首页、404 页，
   此前各自实现一套匹配（对比页那套连俗称别名都没有）。
   这里收敛成一份，页面只负责渲染。

   契约：window.__NJ_SEARCH__ = { cnNum, normTerm, terms, query, score, hayMain }

   query(data, q, filters, opts) → { rows, terms, fellBack }
     filters: { lv, dist, type }  空串表示不限
     opts:    { limit }           只取前 N 条
   ============================================================ */
(function (root) {
  'use strict';

  /* 阿拉伯数字 → 中文数字：手机上打「29中」比打「第二十九中学」容易得多。
     只在查询侧转换、不写进索引——「9中」是「29中」的子串，
     若把 29中 塞进索引，搜「9中」就会把二十九中也带出来。 */
  function cnNum(n) {
    var d = '零一二三四五六七八九';
    if (n < 10) return d.charAt(n);
    var t = Math.floor(n / 10), o = n % 10;
    return (t === 1 ? '十' : d.charAt(t) + '十') + (o ? d.charAt(o) : '');
  }

  function normTerm(t) {
    return t.replace(/^(\d{1,2})(?=[中初高小])/, function (_, n) {
      return cnNum(parseInt(n, 10));
    });
  }

  /* 多关键词：空格分隔，需全部命中（AND） */
  function terms(q) {
    return String(q || '').trim().toLowerCase().split(/\s+/).filter(Boolean).map(normTerm);
  }

  /* 主索引：校名、简称、性质、梯队、区名。
     tagline 刻意不进主索引——它是叙述性长文本，「施教区」「集团」这类词会把结果撑满，
     而且会把只是「提到」了某校的档案一并带出（搜「二十九中」曾跳出琅小/拉小/力学）。 */
  function hayMain(s) {
    return (s.name + ' ' + (s.short || '') + ' ' + s.type + ' '
            + (s.tier || '') + ' ' + s.district).toLowerCase();
  }

  /* 兜底索引：主索引零结果时才查 tagline，保证「九年一贯」「电脑派位」这类描述词仍搜得到 */
  function hayExtra(s) { return (s.tagline || '').toLowerCase(); }

  /* 「九中」不能靠 indexOf 直接判——它是「二十九中」的子串，会把二十九中一并带出来。
     凡「数字汉字 + 中/初」形式的词，要求命中位置的前一个字不是数字汉字。
     不用正则后行断言：老版 Safari 会直接抛错。 */
  var RE_NUM_DEGREE = /^[一二三四五六七八九十]+[中初]$/;
  var RE_NUM_CHAR = /[一二三四五六七八九十]/;

  function hasTerm(hay, t) {
    var i = hay.indexOf(t);
    if (i === -1) return false;
    if (!RE_NUM_DEGREE.test(t)) return true;
    while (i !== -1) {
      var prev = i > 0 ? hay.charAt(i - 1) : '';
      if (!RE_NUM_CHAR.test(prev)) return true;
      i = hay.indexOf(t, i + 1);
    }
    return false;
  }

  /* 别名按「整词」比对，不做子串。组合词互为子串（「拉力琅」是「拉力琅芳」的前缀），
     子串匹配会让搜「拉力琅」连带出芳草园——那就不是三所名校的意思了。 */
  function aliasHit(s, t) {
    var list = (s.aliases || '').split(' ');
    for (var i = 0; i < list.length; i++) {
      if (list[i] === t) return true;
    }
    return false;
  }

  /* 命中质量评分：校名精确 > 校名前缀 > 校名包含 > 别名 > 简称 > 梯队与区名 */
  function score(s, ts) {
    var name = s.name.toLowerCase();
    var minor = (s.short || '').toLowerCase();
    var rest = ((s.tier || '') + ' ' + s.district).toLowerCase();
    var total = 0;
    ts.forEach(function (t) {
      if (name === t) total += 100;
      else if (name.indexOf(t) === 0) total += 60;
      else if (name.indexOf(t) !== -1) total += 40;
      else if (aliasHit(s, t)) total += 30;
      else if (minor.indexOf(t) !== -1) total += 20;
      else if (rest.indexOf(t) !== -1) total += 6;
    });
    return total;
  }

  function match(s, ts, filters, withExtra) {
    if (filters) {
      if (filters.lv && s.level !== filters.lv) return false;
      if (filters.dist && s.district !== filters.dist) return false;
      if (filters.type && s.type !== filters.type) return false;
    }
    if (!ts.length) return true;
    var hay = hayMain(s) + (withExtra ? ' ' + hayExtra(s) : '');
    return ts.every(function (t) { return hasTerm(hay, t) || aliasHit(s, t); });
  }

  function query(data, q, filters, opts) {
    opts = opts || {};
    var ts = terms(q);

    var rows = data.filter(function (s) { return match(s, ts, filters, false); });
    var fellBack = false;

    /* 主索引零结果时退一步查 tagline（如「九年一贯」「集团化办学」），
       调用方应在计数里注明「在简介中匹配」，避免用户误以为是校名命中 */
    if (!rows.length && ts.length) {
      rows = data.filter(function (s) { return match(s, ts, filters, true); });
      fellBack = rows.length > 0;
    }

    if (ts.length) {
      /* 同分时校名短者优先：「二十九中」应先出本部，再出天润城分校 */
      rows = rows.slice().sort(function (a, b) {
        return (score(b, ts) - score(a, ts)) || (a.name.length - b.name.length);
      });
    }

    return {
      rows: opts.limit ? rows.slice(0, opts.limit) : rows,
      terms: ts,
      fellBack: fellBack
    };
  }

  root.__NJ_SEARCH__ = {
    cnNum: cnNum, normTerm: normTerm, terms: terms,
    hayMain: hayMain, hasTerm: hasTerm, aliasHit: aliasHit,
    score: score, query: query
  };
})(typeof window !== 'undefined' ? window : this);
