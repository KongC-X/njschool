# -*- coding: utf-8 -*-
"""HTML 表格解析：把 <table> 抽成二维文本。

为什么手写而不是用 bs4/lxml：合法表格的判断是「表头写了什么」，不是 DOM 结构，
所以最终都要落到「找到含某几个关键词的表头、按列名取值」。既然如此，
解析层只需要把表格变成二维字符串，剩下的判断留在抽取器里，
不必为几十行的事引入一个 CI 也要装的解析库。

实测的结构问题（都处理了）：
  · 政府页第一张表往往是公文元信息（索引号/主题分类/发布机构），
    表头看着也是「键值」，但取「学校名称」列时会取到空——靠表头关键词排除
  · 页脚常被包进 <table>（备案号、联系电话），整表只有 1 行且无表头
  · 单元格用 &nbsp; 占位表示空值，必须先归一成空格再判断
"""
import html as htmllib
import re

RE_TABLE = re.compile(r"<table\b.*?</table>", re.S | re.I)
RE_ROW = re.compile(r"<tr\b.*?</tr>", re.S | re.I)
RE_CELL = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.S | re.I)


def _cell(raw):
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def tables(html):
    """返回 [ [ [单元格,...], ... ], ... ]，跳过完全空的行。"""
    out = []
    for raw in RE_TABLE.findall(html or ""):
        rows = []
        for tr in RE_ROW.findall(raw):
            cells = [_cell(c) for c in RE_CELL.findall(tr)]
            if any(cells):
                rows.append(cells)
        if rows:
            out.append(rows)
    return out


def header_index(rows, must_all):
    """在前两行里找同时含全部关键词的表头，返回 (行号, {列名: 列号}) 或 (None, {})。

    只看前两行：政府页的表格有时把标题行和列名分成两行，
    再往后找就有把数据行当表头的风险。
    """
    for i, row in enumerate(rows[:2]):
        joined = " ".join(row)
        if all(k in joined for k in must_all):
            return i, {name: j for j, name in enumerate(row)}
    return None, {}


def column(cols, *names):
    """按关键词找列号：先精确相等，再退化为包含。"""
    for want in names:
        for name, j in cols.items():
            if name.strip() == want:
                return j
    for want in names:
        for name, j in cols.items():
            if want in name:
                return j
    return None


def pick_tables(html, must_all):
    """抽出所有「表头含全部关键词」的表格，返回 [(表头行号, 列名映射, 数据行)]。"""
    out = []
    for rows in tables(html):
        head = header_index(rows, must_all)
        if head[0] is None:
            continue
        hi, cols = head
        out.append((hi, cols, rows[hi + 1:]))
    return out
