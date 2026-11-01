# -*- coding: utf-8 -*-
"""HTML 表格解析的测试。

样本取自鼓楼区政府派位办法页的真实结构：四张表里只有两张是名单，
另外两张分别是公文元信息与页脚备案信息。排除它们靠的是表头关键词，
所以这里重点测「表头判定」而不是 DOM 结构。
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ingest import htmltab  # noqa: E402

META_TABLE = """<table>
<tr><td>索 引 号：</td><td>000014349/2026-32519</td><td>主题分类：</td><td>科技、教育</td></tr>
<tr><td>发布机构：</td><td>鼓楼区教育局</td><td>生成日期：</td><td>2026-05-30</td></tr>
</table>"""

PLAN_TABLE = """<table>
<tr><th>序号</th><th>学校名称</th><th>派位计划（人）</th><th>派位范围</th></tr>
<tr><td>1</td><td>南京市鼓楼区第一中心小学</td><td>28</td><td>鼓楼区</td></tr>
<tr><td>2</td><td>南京市琅琊路小学</td><td>21</td><td>鼓楼区</td></tr>
</table>"""

PRIVATE_TABLE = """<table>
<tr><th>序号</th><th>学校名称</th><th>派位计划（人）</th><th>派位范围</th>
<th>学费标准(元/生·学期)</th><th>住宿条件</th></tr>
<tr><td>1</td><td>南京市鼓楼实验小学</td><td>179</td><td>鼓楼区</td><td>17000</td><td>无</td></tr>
</table>"""

FOOTER_TABLE = """<table>
<tr><td>隐私声明 联系我们 网站地图 &#169;Copy Right 版权所有 主办单位：南京市鼓楼区人民政府</td><td></td></tr>
</table>"""

PAGE = META_TABLE + PLAN_TABLE + PRIVATE_TABLE + FOOTER_TABLE


class TestTables(unittest.TestCase):
    def test_counts_all_tables(self):
        self.assertEqual(len(htmltab.tables(PAGE)), 4)

    def test_cells_stripped(self):
        rows = htmltab.tables(PLAN_TABLE)
        self.assertEqual(rows[0][0][1], "学校名称")
        self.assertEqual(rows[0][1][1], "南京市鼓楼区第一中心小学")

    def test_nbsp_becomes_empty(self):
        t = "<table><tr><td>&nbsp;</td><td>值</td></tr></table>"
        self.assertEqual(htmltab.tables(t)[0][0], ["", "值"])

    def test_empty_table_skipped(self):
        self.assertEqual(htmltab.tables("<table><tr><td></td></tr></table>"), [])

    def test_no_table(self):
        self.assertEqual(htmltab.tables("<html><body>无</body></html>"), [])


class TestHeader(unittest.TestCase):
    def test_finds_header(self):
        rows = htmltab.tables(PLAN_TABLE)[0]
        hi, cols = htmltab.header_index(rows, ("学校", "计划"))
        self.assertEqual(hi, 0)
        self.assertEqual(cols["学校名称"], 1)

    def test_meta_table_not_matched(self):
        rows = htmltab.tables(META_TABLE)[0]
        hi, _cols = htmltab.header_index(rows, ("学校", "计划"))
        self.assertIsNone(hi)

    def test_only_first_two_rows_scanned(self):
        rows = [["无关"], ["无关2"], ["序号", "学校名称", "派位计划"]]
        hi, _ = htmltab.header_index(rows, ("学校", "计划"))
        self.assertIsNone(hi)


class TestColumn(unittest.TestCase):
    COLS = {"序号": 0, "学校名称": 1, "派位计划（人）": 2}

    def test_exact_first(self):
        self.assertEqual(htmltab.column(self.COLS, "学校名称"), 1)

    def test_falls_back_to_contains(self):
        # 表头常带单位括号：「派位计划（人）」
        self.assertEqual(htmltab.column(self.COLS, "派位计划"), 2)

    def test_missing(self):
        self.assertIsNone(htmltab.column(self.COLS, "学费"))


class TestPick(unittest.TestCase):
    def test_only_plan_tables(self):
        got = htmltab.pick_tables(PAGE, ("学校", "计划"))
        self.assertEqual(len(got), 2)          # 公办 + 民办，元信息与页脚被排除

    def test_rows_exclude_header(self):
        got = htmltab.pick_tables(PAGE, ("学校", "计划"))
        _hi, _cols, rows = got[0]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1], "南京市鼓楼区第一中心小学")

    def test_extra_columns_do_not_break(self):
        # 民办表多两列，列名映射要按表头而不是位置
        got = htmltab.pick_tables(PAGE, ("学校", "计划"))
        _hi, cols, rows = got[1]
        self.assertEqual(cols["学校名称"], 1)
        self.assertEqual(cols["派位计划（人）"], 2)
        self.assertEqual(rows[0][4], "17000")


if __name__ == "__main__":
    unittest.main()
