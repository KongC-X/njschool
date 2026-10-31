# -*- coding: utf-8 -*-
"""分数反查的投档线解析单测。

这里的错误不会让页面崩，只会让家长看到错的分档：
把「第二批次控制线」当成学校线、把 2025 年的分数混进 2026、
或者把两个口径读成一个数。所以每条都钉死。
"""
import os
import sys
import unittest
from collections import namedtuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from pipeline import score  # noqa: E402

Fake = namedtuple("Fake", "id name level district tier url")


def mk(name, level="高中"):
    return Fake(name, name, level, "鼓楼区", "第一梯队", "schools/x.html")


class TestParse(unittest.TestCase):
    def test_多校区取最低作为判断线(self):
        r = score.parse("察哈尔路 652 分（全市最高）；晓庄 645 分")
        self.assertEqual(r["line"], 645, "判断线取最容易进的那个校区")
        self.assertEqual([v["v"] for v in r["values"]], [652, 645])

    def test_两个口径都保留并标记存疑(self):
        r = score.parse("600 分（渠道汇总）；机构口径 594 分")
        self.assertEqual(r["line"], 594)
        self.assertTrue(r["conflict"])
        self.assertEqual(len(r["values"]), 2)

    def test_位次与分数混写时仍能取到分数(self):
        r = score.parse("618 分 / 12,087 名（语数英 304、语数 203）")
        self.assertEqual(r["line"], 618)
        self.assertEqual(len(r["values"]), 1, "位次那一段不应产出第二个分数")

    def test_往年分数不混进今年(self):
        r = score.parse("623 分（渠道汇总）/ 2025 年 618 分（位次 9,396）")
        self.assertEqual([v["v"] for v in r["values"]], [623])

    def test_投档控制线不是学校线(self):
        r = score.parse("527 分（三 A 三合格）；第二批次投档控制线 440 分")
        self.assertEqual([v["v"] for v in r["values"]], [527])

    def test_分批次的数值都保留(self):
        r = score.parse("第一批次 509 分；第二批次 484 分")
        self.assertEqual(r["line"], 484)
        self.assertEqual(len(r["values"]), 2)

    def test_认不出就返回空_不猜(self):
        for s in ("—", "", "未获取", "待公布"):
            self.assertIsNone(score.parse(s)["line"], s)

    def test_区间外的数字不当分数(self):
        # 「招生 1200 人」这类数字不能被当成投档线
        r = score.parse("1200 人")
        self.assertIsNone(r["line"])


class TestBuild(unittest.TestCase):
    def test_只收高中(self):
        schools = [mk("甲高中"), mk("乙初中", "初中"), mk("丙小学", "小学")]
        rows, _ = score.build(schools, {"甲高中": {"score": "600 分"},
                                        "乙初中": {"score": "580 分"},
                                        "丙小学": {}})
        self.assertEqual([r["name"] for r in rows], ["甲高中"])

    def test_缺数据的学校进名单而不是补零(self):
        rows, missing = score.build([mk("甲高中"), mk("乙高中")],
                                    {"甲高中": {"score": "600 分"}, "乙高中": {}})
        self.assertEqual(len(rows), 1)
        self.assertEqual(missing, ["乙高中"])

    def test_按分数线从高到低排(self):
        schools = [mk("低"), mk("高"), mk("中")]
        rows, _ = score.build(schools, {"低": {"score": "520 分"},
                                        "高": {"score": "650 分"},
                                        "中": {"score": "590 分"}})
        self.assertEqual([r["name"] for r in rows], ["高", "中", "低"])
        self.assertEqual(rows[0]["high"], 650)


if __name__ == "__main__":
    unittest.main()
