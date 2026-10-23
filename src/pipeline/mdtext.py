# -*- coding: utf-8 -*-
"""Markdown 渲染：档案正文与内容页共用。

统一在此配置扩展，避免各页面各自拼装导致标题锚点、表格样式不一致。
目录（TOC）由标题 token 重建为 <ol>，以匹配站点既有样式，而非沿用扩展自带的 div。
"""
import re

import markdown
from markdown.extensions.toc import slugify_unicode


def render(text, toc_depth=2):
    """返回 (正文 HTML, 目录 HTML)。

    toc_depth 控制目录收录到几级标题：档案正文的 11 个章节为 h2，故默认 2。
    """
    text = _protect_bracket_annotations(text)
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


def _wrap_tables(html):
    """为表格套一层滚动容器。

    表格元素本身必须保持 display:table，否则列宽算法失效、表头背景只覆盖文字；
    横向滚动交给外层 .table-wrap 承担。此规则此前散落在模板后处理里，现统一到渲染层。
    """
    return re.sub(r"<table>(.*?)</table>",
                  r'<div class="table-wrap"><table>\1</table></div>',
                  html, flags=re.S)


def _build_toc(tokens):
    if not tokens:
        return ""
    items = []
    for t in tokens:
        if t.get("level") == 2 and t.get("id"):
            items.append(f'<li><a href="#{t["id"]}">{t["name"]}</a></li>')
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
