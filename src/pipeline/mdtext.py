# -*- coding: utf-8 -*-
"""Markdown 渲染：档案正文与内容页共用。

统一在此配置扩展，避免各页面各自拼装导致标题锚点、表格样式不一致。
目录（TOC）由标题 token 重建为 <ol>，以匹配站点既有样式，而非沿用扩展自带的 div。
"""
import re

import markdown
from markdown.extensions.toc import slugify_unicode


def render(text, toc_depth=2, links=None):
    """返回 (正文 HTML, 目录 HTML)。

    toc_depth 控制目录收录到几级标题：档案正文的 11 个章节为 h2，故默认 2。
    """
    text = _protect_bracket_annotations(text)
    if links:
        text = _linkify_sources(text, links)
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
        extension_configs={"toc": {
            "permalink": False,
            "toc_depth": f"2-{toc_depth}",
            # 默认 slugify 会把中文标题归一化为空串，导致锚点全空、目录失效。
            # slugify_unicode 保留 Unicode 字符，中文标题才能得到可用 id。
            "slugify": slugify_unicode,
        }},
    )
    html = md.convert(text)
    html = _add_table_labels(html)
    html = _mark_confidence(html)
    if links:
        html = _add_source_note(html)
    return _wrap_tables(html), _build_toc(md.toc_tokens)


RE_BRACKET_ANNO = re.compile(r"\[([^\]\n]{1,60})\]\(([^)\n]{0,60})\)")
LINK_PREFIX = re.compile(r"^(https?://|mailto:|#|/|\.\.?/)")


def _protect_bracket_annotations(text):
    """避免把「[门牌](说明)」误解析为链接。

    档案的施教区描述沿用 `[6号-底](不分单双)` 这类注释写法，Markdown 会当成
    「文字 + 目标地址」生成 <a href="不分单双">，使说明变成死链。
    处理方式：转义方括号，让 `[..]` 按纯文本渲染，括号内容原样保留。
    真实链接（http/mailto/锚点/相对路径）不受影响。
    """
    def repl(m):
        label, target = m.group(1), m.group(2).strip()
        if LINK_PREFIX.match(target):
            return m.group(0)
        return r"\[" + label + r"\](" + target + ")"

    return RE_BRACKET_ANNO.sub(repl, text)


RE_CODE = re.compile(r"<code>.*?</code>", re.S)
CONF_META = {
    "A": ("conf-a", "官方发布：学校官网、教育局、招考院"),
    "B": ("conf-b", "权威媒体转述"),
    "C": ("conf-c", "家长圈口径，需交叉验证"),
}


SRC_CELL = re.compile(r"^\|\s*([^|]{2,120}?)\s*\|")

def _linkify_sources(text, links):
    """把「数据来源」表首列的来源标题替换为 Markdown 链接。

    只处理表格行，且要求标题在登记表中且有 URL；未登记的保持纯文本。
    这样维护成本集中在 data/sources.csv，不必改 229 份档案。
    """
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("|") and not re.match(r"\|[-:\s|]+\|?$", s):
            m = SRC_CELL.match(s)
            if m:
                title = m.group(1).strip()
                clean = re.sub(r"[*`]", "", title)
                url = links.get(clean)
                if url:
                    line = line.replace(title, f"[{title}]({url})", 1)
        out.append(line)
    return "\n".join(out)


SRC_H2 = re.compile(r"(<h2[^>]*>[^<]*数据来源[^<]*</h2>)")
SRC_NOTE = (
    '<blockquote class="src-note">'
    '<strong>来源状态</strong>：表中带链接的条目已核实原文，可直接打开；'
    "未带链接的多为学校公众号文章、已下架页面或家长圈讨论，属「未存档」或「泛指来源」——"
    "意为暂未取到可点开的链接，<strong>不代表没有出处</strong>。"
    "</blockquote>"
)


def _add_source_note(html):
    """在「数据来源」章节标题后插入状态说明，解释为什么有些来源点不开。"""
    return SRC_H2.sub(lambda m: m.group(1) + SRC_NOTE, html, count=1)


def _badge(k):
    cls, title = CONF_META[k]
    return f'<span class="conf {cls}" title="{title}">{k}</span>'


def _mark_confidence(html):
    """把信度标记渲染为语义色徽章。

    档案中标记有两种形态，需分别处理：
      1. 行内代码 `` `[A]` ``——作者用反引号包住，渲染为 <code>[A]</code>
      2. 表格「信度」列的裸字母 A / B / C
    直接替换裸字母会造成大量误判（例如选项字母），故只处理已确认的信度列。
    """
    # ① 行内代码形式
    html = re.sub(r"<code>\[([ABC])\]</code>", lambda m: _badge(m.group(1)), html)

    # ② 信度列单元格（data-label 已在 _add_table_labels 中注入）
    html = re.sub(r'(<td data-label="信度"[^>]*>)\s*([ABC])\s*(</td>)',
                  lambda m: m.group(1) + _badge(m.group(2)) + m.group(3), html)

    # ③ 正文中直接书写的 [A]（跳过 <code> 内的其它内容）
    parts = RE_CODE.split(html)
    codes = RE_CODE.findall(html)
    out = []
    for i, part in enumerate(parts):
        out.append(re.sub(r"\[([ABC])\]", lambda m: _badge(m.group(1)), part))
        if i < len(codes):
            out.append(codes[i])
    return "".join(out)


KV_HEADS = ("项目", "内容", "信度")


def _add_table_labels(html):
    """为每个 td 注入 data-label（取自表头）。

    窄屏下表格转为「标签 + 值」卡片布局，需要每个单元格自带字段名；
    仅靠 CSS 无法取到表头文本，因此在构建期写入。

    档案里的表格有两种形态，窄屏表现不同：
      1. 键值表（表头为 项目 / 内容 / 信度）：第一列本身就是字段名。
         若照搬表头，卡片会显示「项目 | 学校全称」「内容 | 南京市xx」——
         标签重复且无意义。故把第一列的文字提升为第二列的标签，
         并把第一列标记为 kv-key 在窄屏隐藏，卡片直接读作
         「学校全称 | 南京市琅琊路小学」。
      2. 普通多列表：按表头顺序逐个注入即可。
    """
    def fix_table(m):
        table = m.group(0)
        heads = re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)
        labels = [re.sub(r"<[^>]+>|&nbsp;", "", h).strip() for h in heads]
        if not labels:
            return table
        body_m = re.search(r"<tbody>(.*?)</tbody>", table, re.S)
        if not body_m:
            return table

        body = body_m.group(1)
        is_kv = tuple(labels[:3]) == KV_HEADS

        if is_kv:
            def fix_row(rm):
                row = rm.group(0)
                cells = re.findall(r"<td([^>]*)>(.*?)</td>", row, re.S)
                if len(cells) < 2:
                    return row
                key = re.sub(r"<[^>]+>", "", cells[0][1]).strip().replace('"', "&quot;")
                out = [f'<td class="kv-key" data-label="项目"{cells[0][0]}>{cells[0][1]}</td>',
                       f'<td data-label="{key}"{cells[1][0]}>{cells[1][1]}</td>']
                for i, (attrs, content) in enumerate(cells[2:], start=2):
                    label = labels[i] if i < len(labels) else ""
                    out.append(f'<td data-label="{label}"{attrs}>{content}</td>')
                return "<tr>" + "".join(out) + "</tr>"

            new_body = re.sub(r"<tr>.*?</tr>", fix_row, body, flags=re.S)
        else:
            counter = {"i": 0}

            def sub_td(td_m):
                idx = counter["i"] % len(labels)
                counter["i"] += 1
                label = labels[idx].replace('"', "&quot;")
                return f'<td data-label="{label}"{td_m.group(1)}>'

            new_body = re.sub(r"<td([^>]*)>", sub_td, body)

        table = table.replace(body, new_body, 1)
        if is_kv:
            # 供样式层识别：宽屏下把三列「项目/内容/信度」重排为双列卡片
            table = table.replace("<table>", '<table data-kv="1">', 1)
        return table

    return re.sub(r"<table>.*?</table>", fix_table, html, flags=re.S)


def _wrap_tables(html):
    """为表格套一层滚动容器。

    表格元素本身必须保持 display:table，否则列宽算法失效、表头背景只覆盖文字；
    横向滚动交给外层 .table-wrap 承担。此规则此前散落在模板后处理里，现统一到渲染层。
    """
    def wrap(m):
        inner = m.group(0)
        cls = "table-wrap table-wrap--kv" if 'data-kv="1"' in inner else "table-wrap"
        return f'<div class="{cls}">{inner}</div>'

    return re.sub(r"<table[^>]*>.*?</table>", wrap, html, flags=re.S)


# 目录里去掉标题末尾的信度注释。312 份档案都有「八、家长口碑与评价（`[C]`，需自行甄别）」
# 这种标题，放进目录会撑成两行，破坏等距节奏；正文标题本身保留注释不动。
RE_TOC_ANNO = re.compile(r"（[^）]*(?:\[[ABC]\]|需自行甄别)[^）]*）")


def _build_toc(tokens):
    if not tokens:
        return ""
    items = []
    for t in tokens:
        if t.get("level") == 2 and t.get("id"):
            label = RE_TOC_ANNO.sub("", t["name"]).strip() or t["name"]
            items.append(f'<li><a href="#{t["id"]}">{label}</a></li>')
    if not items:
        return ""
    return '<ol>' + "".join(items) + "</ol>"


def strip_leading_h1(text):
    """去掉正文首个 H1。

    详情页的校名由页头单独输出；若保留正文 H1，页面会出现两个 H1，
    既违反语义也让读屏软件重复朗读（此前是用 CSS display:none 掩盖的）。
    """
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):
            return "\n".join(lines[:i] + lines[i + 1:])
        if line.strip() and not line.startswith(">"):
            break
    return text
