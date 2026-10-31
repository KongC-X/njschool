# -*- coding: utf-8 -*-
"""表格装饰：给没有包裹层的表格补「可横向滚动容器」，并给每个单元格补列名。

为什么在构建期做，而不是改 5 个模板的 16 张表：
  1. 表格是手写在模板里的，逐张加 `data-label` 要改 16 处、约 190 个 `<td>`，
     以后再加表格还会漏；
  2. 窄屏把表格转成「字段名 / 值」卡片，靠的正是 `td[data-label]`，
     没有这个属性，家长在手机上看到的是被裁掉一半的 4 列表格；
  3. 已经有包裹层或 data-label 的表（详情页键值表、政策页）原样跳过，不动。

转义与结构约定：
  · 只处理带 `<th>` 表头的表；没有表头的（极少数布局表）只补包裹层；
  · 第一行含 `<th>` 的行当作表头，列名按顺序对齐 `<td>`；
  · 单元格里已有 `data-label` 的不覆盖。
"""
import re

_RE_TABLE = re.compile(r"<table\b([^>]*)>(.*?)</table>", re.S)
_RE_TR = re.compile(r"<tr\b[^>]*>.*?</tr>", re.S)
_RE_TH = re.compile(r"<th\b[^>]*>(.*?)</th>", re.S)
_RE_TD = re.compile(r"<td\b([^>]*)>", re.S)
_RE_TAG = re.compile(r"<[^>]+>")


def _text(fragment):
    return _RE_TAG.sub("", fragment).strip()


def _decorate_one(match, before):
    attrs, inner = match.group(1), match.group(2)
    # 已处理过（详情页键值表自带 data-label）或已在包裹层内：跳过
    if "data-label" in inner or "data-kv" in attrs:
        return match.group(0)
    if before.rstrip().endswith('<div class="table-wrap">'):
        return match.group(0)

    rows = _RE_TR.findall(inner)
    heads = []
    body_rows = rows
    if rows and "<th" in rows[0]:
        heads = [_text(h) for h in _RE_TH.findall(rows[0])]
        body_rows = rows[1:]

    if not heads:
        return '<div class="table-wrap">' + match.group(0) + "</div>"

    new_inner = inner
    for row in body_rows:
        idx = 0
        rebuilt = row

        def _sub(m):
            nonlocal idx
            label = heads[idx] if idx < len(heads) else ""
            idx += 1
            if "data-label" in m.group(1) or not label:
                return m.group(0)
            return f'<td{m.group(1)} data-label="{label}">'

        rebuilt = _RE_TD.sub(_sub, row)
        new_inner = new_inner.replace(row, rebuilt, 1)

    table = f"<table{attrs}>{new_inner}</table>"
    return '<div class="table-wrap">' + table + "</div>"


def decorate(html):
    """给整页 HTML 里所有未处理的表格补包裹层与 data-label。"""
    out, pos = [], 0
    for m in _RE_TABLE.finditer(html):
        before = html[max(0, m.start() - 60):m.start()]
        out.append(html[pos:m.start()])
        out.append(_decorate_one(m, before))
        pos = m.end()
    out.append(html[pos:])
    return "".join(out)
