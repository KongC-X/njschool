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

  /* 主索引：校名、简称、性质、学段、梯队、区名。
     tagline 刻意不进主索引——它是叙述性长文本，「施教区」「集团」这类词会把结果撑满，
     而且会把只是「提到」了某校的档案一并带出（搜「二十九中」曾跳出琅小/拉小/力学）。

     level 必须在这里：此前只把它交给 passFilters 做筛选，于是「用学段按钮能筛出来、
     在搜索框打『初中』搜不到」——同一份数据两种行为。实测搜「初中」只出 50 条，
     而实际有 164 所；「初中 鼓楼」更是只剩 1 条。校名里带「小学」的占绝大多数，
     所以小学校来像是正常的，初中校名多叫「XX中学」，一漏就是 70%。 */
  function hayMain(s) {
    return (s.name + ' ' + (s.short || '') + ' ' + s.type + ' ' + s.level + ' '
            + (s.tier || '') + ' ' + s.district).toLowerCase();
  }

  /* 地址索引：施教区里的路名/小区名（构建期从档案 5.1 节抽出，见 streets-data.js）。
     家长的真实问题是「我家这条街能上哪所」，而这三个字从不出现在校名里——
     只搜校名的结果是：搜「宁海路」返回 0 所，而琅琊路小学的施教区里就写着宁海路。 */
  function hayAddr(s) { return (s.addr || '').toLowerCase(); }

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

  /* 校名归一：剥掉行政区前缀再比。
     「南京市金陵中学」搜「金陵中学」时 indexOf 是 5，只能拿包含分 40；
     而「金陵中学实验小学」indexOf 是 0，拿前缀分 60——本部反被同族分校压住，
     实测搜「金陵中学」本部排第 5。545 所里 403 所（73.9%）校名以「南京市」开头，
     这不是个例，是系统性偏差。
     只剥这两层：再往下剥「附属/实验/小学」曾把「金陵中学实验小学」和
     「金陵中学附属小学」抹成同一所，造成 4 条错配（见 pipeline/aliases.py 的同类教训）。 */
  var RE_ADMIN = /^(?:江苏省)?(?:南京市)?/;

  function core(x) {
    var c = x.replace(RE_ADMIN, '');
    return c || x;   /* 只输入「南京市」这类纯前缀词时退回原值，空串会命中一切 */
  }

  /* 命中质量评分：校名精确 > 简称精确 > 校名前缀 > 校名包含 > 别名 > 简称包含 > 梯队与区名

     「简称精确」这一档必须有，且要高于校名前缀。
     实测：搜「南师附中」，本部 short 就是「南师附中」，但按原来的规则只拿简称包含分 20，
     而「南师附中高淳学校」因校名以它开头拿 60——本部被系统性地排到分校后面。
     525 所（96.3%）都有 short，这不是个别数据的错，是评分档位缺了一层。 */
  function score(s, ts) {
    var name = s.name.toLowerCase();
    var cname = core(name);
    var minor = (s.short || '').toLowerCase();
    var rest = ((s.tier || '') + ' ' + s.district).toLowerCase();
    var total = 0;
    ts.forEach(function (t) {
      var ct = core(t);
      if (cname === ct) total += 100;
      else if (minor === t) total += 80;
      else if (cname.indexOf(ct) === 0) total += 60;
      else if (cname.indexOf(ct) !== -1) total += 40;
      else if (aliasHit(s, t)) total += 30;
      else if (minor.indexOf(t) !== -1) total += 20;
      else if (rest.indexOf(t) !== -1) total += 6;
    });
    return total;
  }

  /* 地址命中：返回命中的那个地名（用于在结果卡上写「施教区含：宁海路」）。
     不做整词比对：家长可能只记得「宁海」两个字，前缀命中也应算命中。 */
  function addrHit(s, t) {
    var list = (s.addr || '').split(' ');
    for (var i = 0; i < list.length; i++) {
      if (list[i] && list[i].indexOf(t) !== -1) return list[i];
    }
    return '';
  }

  function passFilters(s, filters) {
    if (!filters) return true;
    if (filters.lv && s.level !== filters.lv) return false;
    if (filters.dist && s.district !== filters.dist) return false;
    if (filters.type && s.type !== filters.type) return false;
    /* 数据项筛选：s.has 是空格分隔的标记串（如「学费 投档线」）。
       用两侧补空格做整词比对——否则「学费」会命中「学费说明」这类前缀。 */
    if (filters.has && (' ' + (s.has || '') + ' ').indexOf(' ' + filters.has + ' ') === -1) {
      return false;
    }
    return true;
  }

  function match(s, ts, filters, level) {
    if (!passFilters(s, filters)) return false;
    if (!ts.length) return true;
    var hay = hayMain(s);
    if (level >= 2) hay += ' ' + hayAddr(s);
    if (level >= 3) hay += ' ' + hayExtra(s);
    return ts.every(function (t) { return hasTerm(hay, t) || aliasHit(s, t); });
  }

  /* 返回命中来源：'name'（校名/简称/区/梯队）、'addr'（施教区地名）、'tag'（简介） */
  function hitKind(s, ts) {
    if (!ts.length) return 'name';
    var main = hayMain(s);
    if (ts.every(function (t) { return hasTerm(main, t) || aliasHit(s, t); })) return 'name';
    var addr = hayAddr(s);
    if (ts.every(function (t) { return hasTerm(addr, t) || hasTerm(main, t); })) return 'addr';
    return 'tag';
  }

  function query(data, q, filters, opts) {
    opts = opts || {};
    var ts = terms(q);

    /* 三级检索，逐级放宽：
         1 主索引（校名/简称/区/梯队）
         2 + 施教区地名（「宁海路」「龙江小区」这类地址查询）
         3 + 一句话简介（「九年一贯」「电脑派位」这类描述词）
       只在上一级零结果时才降级，避免「二十九中」把只是提到它的学校也带出来。 */
    var rows = data.filter(function (s) { return match(s, ts, filters, 1); });
    var level = 1;
    if (!rows.length && ts.length) {
      rows = data.filter(function (s) { return match(s, ts, filters, 2); });
      level = 2;
    }
    if (!rows.length && ts.length) {
      rows = data.filter(function (s) { return match(s, ts, filters, 3); });
      level = 3;
    }

    if (ts.length) {
      /* 同分时校名短者优先：「二十九中」应先出本部，再出天润城分校 */
      rows = rows.slice().sort(function (a, b) {
        return (score(b, ts) - score(a, ts)) || (a.name.length - b.name.length);
      });
    }

    /* 命中来源：地址层命中时，结果卡要写出「施教区含：宁海路」，
       否则家长会以为这所学校只是碰巧被搜到。 */
    var hits = {};
    if (ts.length) {
      rows.forEach(function (s) {
        hits[s.id] = level === 1 ? hitKind(s, ts) : (level === 2 ? 'addr' : 'tag');
      });
    }

    return {
      rows: opts.limit ? rows.slice(0, opts.limit) : rows,
      terms: ts,
      level: level,
      /* 兼容旧字段：fellBack 原义是「退到简介层匹配」 */
      fellBack: level === 3,
      addrMatch: level === 2,
      hits: hits
    };
  }

  /* 地址命中的地名，用于结果卡展示 */
  function addrLabels(s, ts) {
    var out = [];
    ts.forEach(function (t) {
      var hit = addrHit(s, t);
      if (hit && out.indexOf(hit) === -1) out.push(hit);
    });
    return out;
  }

  root.__NJ_SEARCH__ = {
    cnNum: cnNum, normTerm: normTerm, terms: terms,
    hayMain: hayMain, hayAddr: hayAddr, hasTerm: hasTerm, aliasHit: aliasHit,
    addrHit: addrHit, addrLabels: addrLabels,
    score: score, query: query
  };
})(typeof window !== 'undefined' ? window : this);
