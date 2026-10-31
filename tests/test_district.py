# -*- coding: utf-8 -*-
"""施教区抽取 / 结构化 与 正文交叉链接 的单测。

这两块都是给 545 份真实档案用的，规则一旦回退不会报错、只会静默失效：
搜「宁海路」回到 0 条、或者正文里少了一批内链。所以用最小样本把行为钉死。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from pipeline import district, xref  # noqa: E402

MD_51 = """## 五、招生与施教区

### 5.1 2026 年施教区范围（区教育局公示原文）

**① 琅琊路校区**

> 琅琊路、北京西路[19-69号(包括69-1)(单)，34-70号(包括70-1)(双)]、天竺路、普陀路

**② 玉泉路校区**

> 宁海路[1-121号(单)(65-底)，2-94号(双)(56-底)]、苏州路、云南路

## 六、升学表现
"""

MD_SIZHI = """## 二、施教区

> **施教区原文**：长江路以南，龙津路—龙津南路—宁六公路以西，宁连高速以东。

## 三、招生方式
"""


class TestAnchors(unittest.TestCase):
    def test_号段括号内的逗号不能截断路名(self):
        """回归：先切段再剥括号，会把「宁海路[1-121号…，2-94号…]」切坏，
        导致**写了号段的路名**全部抽不到——恰好是最该被搜到的那些。"""
        got = district.anchors(MD_51)
        self.assertIn("宁海路", got)
        self.assertIn("北京西路", got)
        self.assertIn("琅琊路", got)

    def test_四至句式抽出开头地名(self):
        got = district.anchors(MD_SIZHI)
        self.assertIn("长江路", got)
        self.assertIn("龙津路", got)

    def test_跨段碎片不算地名(self):
        """「由应天花园至梦都大街」曾是误抽结果，含「至」的一律丢弃。"""
        got = district.anchors("## 二、施教区\n\n> 由应天花园至梦都大街、雨花西路\n")
        self.assertIn("雨花西路", got)
        self.assertFalse([x for x in got if "至" in x])

    def test_无施教区章节时返回空(self):
        self.assertEqual(district.anchors("## 一、学校速览\n\n什么都没有\n"), [])

    def test_去重(self):
        got = district.anchors("## 二、施教区\n\n> 华侨路、华侨路、上海路\n")
        self.assertEqual(got, ["华侨路", "上海路"])


class TestEnhanceHtml(unittest.TestCase):
    def test_路名清单拆成逐条列表(self):
        html = ('<h3 id="5-1">5.1 2026 年施教区范围</h3>'
                "<blockquote>琅琊路、北京西路[19-69号(单)]、天竺路、普陀路</blockquote>")
        out, changed = district.enhance_html(html)
        self.assertTrue(changed)
        self.assertIn('<ul class="roads">', out)
        self.assertEqual(out.count("<li>"), 4)
        self.assertIn("<li>北京西路[19-69号(单)]</li>", out, "号段必须留在同一条里")

    def test_短引用块不当成路名清单(self):
        html = ('<h3 id="x">2.3 施教区范围</h3>'
                "<blockquote>以教育局公示为准。</blockquote>")
        out, changed = district.enhance_html(html)
        self.assertFalse(changed)
        self.assertIn("<blockquote>", out)

    def test_总是插入自查框与锚点(self):
        html = '<h3 id="x">2.3 施教区范围</h3><blockquote>甲路、乙路、丙路、丁路</blockquote>'
        out, _ = district.enhance_html(html)
        self.assertIn('id="shijiaoqu"', out)
        self.assertIn('id="skInput"', out)

    def test_没有施教区章节则原样返回(self):
        html = '<h3 id="x">4.1 录取分数线</h3><blockquote>甲、乙、丙、丁</blockquote>'
        out, changed = district.enhance_html(html)
        self.assertFalse(changed)
        self.assertEqual(out, html)


class TestXref(unittest.TestCase):
    MAP = {"南京市第二十九中学初中部": "../schools/a.html",
           "南京市第二十九中学": "../schools/b.html",
           "二十九中": "../schools/b.html"}

    def test_长名优先_不切碎校名(self):
        linkify = xref.build(self.MAP)
        out = linkify("<p>对口南京市第二十九中学初中部</p>")
        self.assertIn('href="../schools/a.html"', out)
        self.assertNotIn("初中部</a>", out.replace("初中部</a>", "X"))

    def test_不给自己加链接(self):
        linkify = xref.build(self.MAP)
        out = linkify("<p>南京市第二十九中学</p>", exclude="南京市第二十九中学")
        self.assertNotIn("<a", out)

    def test_已有链接与代码块不被二次包装(self):
        linkify = xref.build(self.MAP)
        out = linkify('<p><a href="x">二十九中</a> 与 <code>二十九中</code></p>')
        self.assertEqual(out.count("<a"), 1, "已在 a 标签里的文字不能再包一层")
        self.assertNotIn("<code><a", out)

    def test_同一校名最多链两次(self):
        linkify = xref.build(self.MAP)
        out = linkify("<p>二十九中 二十九中 二十九中</p>")
        self.assertEqual(out.count("<a"), 2)

    def test_空表不报错(self):
        linkify = xref.build({})
        self.assertEqual(linkify("<p>二十九中</p>"), "<p>二十九中</p>")


if __name__ == "__main__":
    unittest.main()
