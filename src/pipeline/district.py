# -*- coding: utf-8 -*-
"""施教区处理：地名锚点抽取 + 正文结构化。

解决两个实测问题（见 docs/体验走查报告-2026-10-28.html）：

  P0-1 搜地址搜不到学校——档案里写着「宁海路[1-121号(单)…]」，
       但搜索索引只覆盖校名/简称/区/梯队/一句话，搜「宁海路」返回 0 所。
       → anchors() 抽出地名，供 search-core.js 做地址层检索。

  P0-2 施教区以公文原文堆放，家长无法判断「我在不在里面」。
       → enhance_html() 把「路名、路名、路名」拆成一条一行的列表，
         并在旁边挂一个自查输入框（前端 app.js 负责匹配）。

设计原则：**只搬运、不推断**。
  · 抽不到地名不猜（返回空列表，前端自然搜不到，不会给出错误结果）；
  · 自查框命中后只指出「出现在哪个校区的号段原文里」，
    绝不输出「能上 / 不能上」的结论——号段规则各校写法不一，
    机器判断错一次的代价是一套房的决策。
"""
import re

# 地名后缀。收得比较宽是因为南京施教区原文里「路/街/巷」之外还有
# 「村 / 苑 / 园 / 小区 / 公寓 / 山庄」这类居住区名，家长搜的往往是这些。
_ANCHOR = (r"[\u4e00-\u9fa5A-Za-z0-9]{2,9}?"
           r"(?:路|街|巷|大道|大街|胡同|村|苑|园|小区|花园|新村|里|城|湾|山庄|公寓)")

_RE_WHOLE = re.compile(r"^" + _ANCHOR + r"$")
# 四至句式：「长江路以南」「龙津路—宁六公路以西」，取开头那一段地名
_RE_LEAD = re.compile(r"^(" + _ANCHOR + r")(?:以南|以北|以东|以西|至|到|—|－|-|~|～)")
# 方括号是号段写法 [19-69号(单)]，圆括号是注释 (不分单双)，都要先剥掉再判断
_RE_BRACKET = re.compile(r"\[[^\]]*\]|（[^）]*）|\([^)]*\)")
# 段首的连接词与序号：「① 」「3. 」「另含」「包括」
_RE_LEAD_NOISE = re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫\d\s.、]+")
# 以这些词开头的段落地名不可信（「由应天花园至梦都大街」曾被抽成一个地名）
_NOISE_PREFIX = ("由", "属", "包括", "含", "另含", "以及", "及", "至", "到",
                 "本", "该", "其中", "以上", "以下", "详见", "参见")
# 地名里不该出现的字：出现即判为「号段残片」或「跨段拼接」，如「号开始至菊花台公园」
_NOISE_CHARS = "号至到以及含和与"

# 章节定位：小学有两套模板——「五、招生与施教区」（107 份）
# 与「二、施教区」（233 份），初中另有「四、招生入学」。
_RE_SEC_SHIJIAOQU = re.compile(r"^##\s*.*施教区.*$", re.M)
_RE_SEC_ZHAOSHENG = re.compile(r"^##\s*.*招生.*$", re.M)
_RE_NEXT_H2 = re.compile(r"^##\s", re.M)


def sections(text):
    """返回施教区相关章节的 Markdown 正文（不含标题行本身）。

    优先取标题含「施教区」的章节；一份档案可能有多个（如分校区各一节），
    全部取回。都没有时才退回「招生」章节——那里通常也带范围描述。
    """
    out = []
    for rx in (_RE_SEC_SHIJIAOQU, _RE_SEC_ZHAOSHENG):
        for m in rx.finditer(text):
            rest = text[m.end():]
            n = _RE_NEXT_H2.search(rest)
            out.append(rest[:n.start()] if n else rest)
        if out:
            break
    return out


def anchors(text, limit=60):
    """从施教区章节抽取地名，返回去重后的列表。

    切分顺序即精度来源：先按顿号/逗号切段，再要求**整段就是一个地名**
    （或四至句式的开头地名）。这样「由应天花园至梦都大街」这类整段不会被
    误当成地名，代价是四至型施教区抽不到东西——那类档案本来就没有逐条路名，
    强行抽只会制造搜索结果里的假命中。
    """
    toks = []
    for sec in sections(text):
        # 必须先整节剥括号、再切段。
        # 反过来的话，「宁海路[1-121号(单)(65-底)，2-94号(双)(56-底)]」会先被
        # 中间的逗号切成两半，括号就不成套了，识别不出这条路——
        # 而恰恰是**写了号段的路名**最容易被这样丢掉，等于把最该被搜到的排除了。
        clean = _RE_BRACKET.sub("", sec).replace("**", "")
        for seg in re.split(r"[、，,；;。|\n]", clean):
            token = _token_of(seg)
            if token and token not in toks:
                toks.append(token)
                if len(toks) >= limit:
                    return toks
    return toks


def _token_of(seg):
    """从一段文字里取出地名；取不到返回 None。"""
    s = seg.strip().strip("*`> ").strip()
    s = _RE_LEAD_NOISE.sub("", s).strip()
    if not s:
        return None

    # 「**施教区原文**：长江路以南…」这类整段带标签的写法，
    # 直接匹配会因为标签在前而失败，取冒号后那一段再试一次。
    cands = [s]
    if "：" in s or ":" in s:
        cands.append(re.split(r"[：:]", s)[-1].strip())

    for cand in cands:
        if not cand or cand.startswith(_NOISE_PREFIX):
            continue
        m = _RE_WHOLE.match(cand) or _RE_LEAD.match(cand)
        if not m:
            continue
        token = (m.group(1) if m.re.groups else m.group(0)).strip()
        if any(c in token for c in _NOISE_CHARS):
            continue
        if 2 < len(token) <= 12:
            return token
    return None


# ---------------------------------------------------------------- 正文结构化

_RE_H3 = re.compile(r"<h3[^>]*>(.*?)</h3>", re.S)
_RE_BQ = re.compile(r"<blockquote>(.*?)</blockquote>", re.S)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_CAMPUS = re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫]\s*(.+)$")


def _split_roads(inner):
    """把引用块内容按**顶层**顿号切成路名条目。

    括号内的顿号不切：[19-69号(包括69-1)，34-70号(包括70-1)] 是一个条目。
    方括号与圆括号都要计深度——号段写法里两种都出现。
    """
    depth, cur, out = 0, [], []
    for ch in inner:
        if ch in "[（(":
            depth += 1
        elif ch in "]）)":
            depth = max(0, depth - 1)
        if ch == "、" and depth == 0:
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    out.append("".join(cur))
    return [x.strip() for x in out if x.strip()]


def enhance_html(html):
    """把施教区章节的引用块改成一条一行的列表，并插入自查入口。

    只在「章节内引用块」上动手，且只在**切分结果可信**时才替换：
    条目数少于 4 说明它本来是一段话（四至描述或解读），原样保留。

    返回 (新 HTML, 是否改动)。
    """
    # 定位第一个含「施教区」的 h3，章节范围到下一个 h2/h3 为止
    m = None
    for h in _RE_H3.finditer(html):
        if "施教区" in _RE_TAG.sub("", h.group(1)):
            m = h
            break
    if not m:
        return html, False

    rest = html[m.end():]
    nxt = re.search(r"<h[23][\s>]", rest)
    end = m.end() + (nxt.start() if nxt else len(rest))
    section = html[m.end():end]

    changed = [False]

    def repl_bq(bq):
        inner = bq.group(1)
        if inner.count("、") < 3:
            return bq.group(0)          # 不是路名清单，原样保留
        parts = _split_roads(_RE_TAG.sub("", inner))
        parts = [p for p in parts if 1 < len(p) <= 40]
        if len(parts) < 4:
            return bq.group(0)
        changed[0] = True
        lis = "".join(f"<li>{p}</li>" for p in parts)
        return f'<ul class="roads">{lis}</ul>'

    new_section = _RE_BQ.sub(repl_bq, section)
    # 无论是否拆成列表，都挂上自查框与锚点：
    # 四至型施教区（「长江路以南…以西」）拆不出逐条路名，但家长同样需要
    # 「我输入的路名在这段话里出现过吗」这个能力，前端直接在原文里找即可。
    new_section = ('<span id="shijiaoqu"></span>' + new_section + _selfcheck_box())
    return html[:m.end()] + new_section + html[end:], changed[0]


def _selfcheck_box():
    """施教区自查框。前端 app.js 做匹配，这里只出结构。

    文案刻意不承诺结论：命中后只说「出现在某条范围内」，
    号段对不对由家长对照原文判断。
    """
    return (
        '<div class="sk-box" id="skBox">'
        '<label class="sk-label" for="skInput">查我在不在范围内</label>'
        '<div class="sk-row">'
        '<input id="skInput" type="search" autocomplete="off" '
        'placeholder="输入路名或小区名，如 宁海路、龙江小区">'
        '</div>'
        '<p class="sk-out" id="skOut" role="status" aria-live="polite">'
        '先在上方找找有没有你家的路名；下方会标出命中位置，号段仍需对照原文核对。</p>'
        '</div>'
    )
