# -*- coding: utf-8 -*-
"""招生时间轴 抽取与聚类 的单测。

这块的风险不在崩溃，而在**静默出错**：日期解析错一天、或者把某一所学校的
 idiosyncratic 节点当成全市节点，页面上看起来完全正常，家长照着做就会误事。
"""
import os
import sys
import unittest
from collections import namedtuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from pipeline import timeline  # noqa: E402

Fake = namedtuple("Fake", "id level")


def md(rows, title="### 5.3 报名时间节点（2026 年，市级统一）`[A]`"):
    body = "\n".join(f"| {a} | {b} |" for a, b in rows)
    return (f"## 五、招生与施教区\n\n{title}\n\n| 时间 | 事项 |\n|---|---|\n{body}\n\n"
            "## 六、升学表现\n\n正文。\n")


class TestParseDate(unittest.TestCase):
    def test_同月区间(self):
        d = timeline.parse_date("5 月 17 日—19 日")
        self.assertEqual((d["m"], d["d"], d["em"], d["ed"]), (5, 17, 5, 19))
        self.assertEqual(d["kind"], "range")

    def test_跨月区间(self):
        d = timeline.parse_date("6 月 26 日—7 月 2 日")
        self.assertEqual((d["m"], d["d"], d["em"], d["ed"]), (6, 26, 7, 2))

    def test_起止与截止与单日(self):
        self.assertEqual(timeline.parse_date("5 月 8 日起")["kind"], "from")
        self.assertEqual(timeline.parse_date("8 月 10 日前")["kind"], "before")
        self.assertEqual(timeline.parse_date("5 月 28 日")["kind"], "single")

    def test_旬(self):
        d = timeline.parse_date("6 月上旬")
        self.assertEqual((d["m"], d["d"], d["kind"]), (6, 1, "xun"))

    def test_认不出就返回空_不猜(self):
        for s in ("现场确认", "另行通知", "", "6 月"):
            self.assertIsNone(timeline.parse_date(s), s)

    def test_截止时刻(self):
        dl = timeline.parse_deadline("平台报名登记（截止 5 月 19 日 17:00）")
        self.assertEqual((dl["m"], dl["d"], dl["hh"], dl["mm"]), (5, 19, 17, "00"))
        self.assertIsNone(timeline.parse_deadline("电脑派位"))


class TestRows(unittest.TestCase):
    def test_取出时间表并跳过表头(self):
        text = md([("5 月 8 日起", "公布方案"), ("5 月 17 日—19 日", "平台报名"),
                   ("6 月 13 日", "电脑派位")])
        rows = timeline.rows_of(text)
        self.assertEqual(len(rows), 1)
        self.assertEqual([a for a, _ in rows[0]], ["5 月 8 日起", "5 月 17 日—19 日", "6 月 13 日"])

    def test_少于三行的表不当时间轴(self):
        text = md([("5 月 8 日", "公布方案")])
        self.assertEqual(timeline.rows_of(text), [])


class TestBuild(unittest.TestCase):
    def _run(self, texts):
        schools = [Fake(f"s{i}", "小学") for i in range(len(texts))]
        return timeline.build(schools, {f"s{i}": t for i, t in enumerate(texts)})

    def test_同一天的不同措辞归并_取最常见那条(self):
        a = md([("5 月 8 日起", "公布实施方案及施教区范围"), ("5 月 17 日—19 日", "平台报名"),
                ("6 月 13 日", "电脑派位")])
        b = md([("5 月 8 日起", "区教育局公布实施方案及施教区范围"), ("5 月 17 日—19 日", "平台报名"),
                ("6 月 13 日", "电脑派位")])
        c = md([("5 月 8 日起", "公布实施方案及施教区范围"), ("5 月 17 日—19 日", "平台报名"),
                ("6 月 13 日", "电脑派位")])
        # 阈值是「至少 5% 的档案都写了」，样本太少会让所有节点都落进「其他口径」，
        # 所以这里用 20 份（其中 12 份用短写法、8 份用长写法）
        r = self._run([a] * 12 + [b] * 8)["小学"]
        node = [n for n in r["nodes"] if n["m"] == 5 and n["d"] == 8][0]
        self.assertEqual(node["event"], "公布实施方案及施教区范围", "应取出现更多的短写法")
        self.assertEqual(node["count"], 20)
        self.assertEqual(node["variants"], 2, "两种写法应被识别为同一节点的变体")

    def test_截止括号从事项里剥掉_避免同一行重复(self):
        a = md([("5 月 17 日—19 日", "平台报名登记（截止 5 月 19 日 17:00）"),
                ("6 月 13 日", "电脑派位"), ("7 月 1 日", "确认录取")])
        r = self._run([a] * 20)["小学"]
        node = [n for n in r["nodes"] if n["m"] == 5][0]
        self.assertNotIn("截止", node["event"])
        self.assertIsNotNone(node["deadline"], "截止时刻应单独保留")

    def test_只出现一次的节点进其他口径_不进主表(self):
        common = [("5 月 8 日起", "公布方案"), ("5 月 17 日—19 日", "平台报名"),
                  ("6 月 13 日", "电脑派位")]
        texts = [md(common) for _ in range(20)]
        texts.append(md(common + [("4 月 1 日", "某校自主招生咨询")]))
        r = self._run(texts)["小学"]
        main_dates = [(n["m"], n["d"]) for n in r["nodes"]]
        self.assertNotIn((4, 1), main_dates, "只有 1 份档案提到的节点不能进主时间轴")
        self.assertIn((4, 1), [(n["m"], n["d"]) for n in r["extra"]])

    def test_同一份档案重复同一天只算一次(self):
        rows = [("5 月 8 日起", "公布方案"), ("5 月 8 日起", "公布方案"),
                ("5 月 17 日—19 日", "平台报名"), ("6 月 13 日", "电脑派位")]
        r = self._run([md(rows)] * 20)["小学"]
        self.assertEqual(r["contributors"], 20)
        self.assertEqual([n["count"] for n in r["nodes"] if n["m"] == 5 and n["d"] == 8], [20],
                         "同一份档案里重复写两遍，不能算成两所学校")


if __name__ == "__main__":
    unittest.main()
