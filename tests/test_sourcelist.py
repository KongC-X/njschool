# -*- coding: utf-8 -*-
"""源清单解析与校验的单元测试。

配置文件的错误后果比代码错误更远：语法写错，采集器会静默少抓一半源，
而输出里只显示「共 N 个源」，没人会去数。所以解析器与校验都要有用例，
并且要对真实的 data/sources.yaml 跑一遍，防止手工编辑时改坏格式。
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ingest import sourcelist  # noqa: E402

GOOD = """\
sources:
  - id: bureau:city-edu
    kind: bureau
    name: 南京市教育局
    entry: https://edu.nanjing.gov.cn/
    tier: T0
    parser: gov_attachment
    status: verified
"""


def one(**kw):
    base = {"id": "school:小学-鼓楼区-某小学", "kind": "school", "name": "某小学",
            "entry": "http://a.cn/", "tier": "T1", "parser": "announcement_list",
            "status": "verified"}
    base.update(kw)
    return [base]


class TestParse(unittest.TestCase):
    def test_basic(self):
        items = sourcelist.parse(GOOD)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["id"], "bureau:city-edu")
        self.assertEqual(it["entry"], "https://edu.nanjing.gov.cn/")
        self.assertEqual(it["tier"], "T0")

    def test_id_with_colon_is_not_split(self):
        # id 值本身含冒号（bureau:city-edu），只能按第一个冒号切键值
        self.assertEqual(sourcelist.parse(GOOD)[0]["id"], "bureau:city-edu")

    def test_url_keeps_scheme(self):
        self.assertTrue(sourcelist.parse(GOOD)[0]["entry"].startswith("https://"))

    def test_comments_ignored(self):
        text = "# 头部注释\nsources:\n  # 段注释\n  - id: x\n    kind: school\n"
        self.assertEqual(len(sourcelist.parse(text)), 1)

    def test_quoted_value_with_colon_and_hash(self):
        text = ('sources:\n  - id: x\n'
                '    note: "含：冒号与 # 井号"\n')
        self.assertEqual(sourcelist.parse(text)[0]["note"], "含：冒号与 # 井号")

    def test_empty_entry_becomes_empty_string(self):
        text = 'sources:\n  - id: x\n    entry: ""\n'
        self.assertEqual(sourcelist.parse(text)[0]["entry"], "")

    def test_unquoted_hash_not_stripped(self):
        # 行内 # 不当注释：URL 锚点必须保留
        text = "sources:\n  - id: x\n    entry: http://a.cn/#sec\n"
        self.assertEqual(sourcelist.parse(text)[0]["entry"], "http://a.cn/#sec")

    def test_multiple_items_and_repeated_sources_line(self):
        # 重复的 sources: 行应被忽略，条目数只由「- 」开头决定
        text = ("sources:\n  - id: a\n    kind: school\n"
                "sources:\n  - id: b\n    kind: school\n")
        self.assertEqual([i["id"] for i in sourcelist.parse(text)], ["a", "b"])

    def test_empty_text(self):
        self.assertEqual(sourcelist.parse(""), [])


class TestValidate(unittest.TestCase):
    def test_good_passes(self):
        self.assertEqual(sourcelist.validate(one()), [])

    def test_missing_required(self):
        bad = sourcelist.validate(one(tier=""))
        self.assertTrue(any("tier" in b for b in bad))

    def test_bad_enum(self):
        self.assertTrue(sourcelist.validate(one(tier="T9")))
        self.assertTrue(sourcelist.validate(one(kind="gov")))
        self.assertTrue(sourcelist.validate(one(parser="xpath")))
        self.assertTrue(sourcelist.validate(one(status="done")))

    def test_duplicate_id(self):
        items = one() + one()
        self.assertTrue(any("重复" in b for b in sourcelist.validate(items)))

    def test_id_prefix_must_match_kind(self):
        bad = sourcelist.validate(one(id="bureau:x", kind="school"))
        self.assertTrue(any("前缀" in b for b in bad))

    def test_verified_without_entry(self):
        bad = sourcelist.validate(one(entry="", status="verified"))
        self.assertTrue(any("没有 entry" in b for b in bad))

    def test_unverified_with_entry(self):
        # 有地址就该核实后改 verified，两态并存说明有人填了但没核
        bad = sourcelist.validate(one(status="unverified"))
        self.assertTrue(any("却标为 unverified" in b for b in bad))

    def test_bad_url(self):
        self.assertTrue(sourcelist.validate(one(entry="edu.nanjing.gov.cn")))


class TestHelpers(unittest.TestCase):
    def test_active_excludes_unverified(self):
        items = one() + one(id="bureau:zkb", kind="bureau", entry="", status="unverified")
        act = sourcelist.active(items)
        self.assertEqual(len(act), 1)
        self.assertEqual(act[0]["id"], "school:小学-鼓楼区-某小学")

    def test_summary_counts(self):
        items = one() + one(id="bureau:zkb", kind="bureau", entry="", status="unverified")
        s = sourcelist.summary(items)
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["active"], 1)
        self.assertEqual(s["unverified"], 1)
        self.assertEqual(s["by_kind"]["bureau"], 1)


class TestRealFile(unittest.TestCase):
    """真实配置必须始终可解析且校验通过——手工编辑最容易在这里改坏。"""

    def test_loads(self):
        items = sourcelist.load()
        self.assertGreater(len(items), 0, "data/sources.yaml 缺失或为空")

    def test_validates(self):
        problems = sourcelist.validate(sourcelist.load())
        self.assertEqual(problems, [], f"配置校验不通过：{problems[:5]}")

    def test_school_entries_have_domain(self):
        # 学校源必须有可直接抓的地址；空地址的只能出现在 bureau 待核项里
        bad = [i["id"] for i in sourcelist.load()
               if i["kind"] == "school" and not i.get("entry")]
        self.assertEqual(bad, [], f"学校源缺少地址：{bad[:5]}")


if __name__ == "__main__":
    unittest.main()
