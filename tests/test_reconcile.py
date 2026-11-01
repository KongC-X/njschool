# -*- coding: utf-8 -*-
"""收录对账的测试。

这套逻辑唯一的用途是把「官方应收」和「库内实有」做差集，一旦判错，
要么把真缺的学校算成已收（漏建档案），要么把已收的算成缺（白忙一场）。
实测两种误判都发生过：
  · 17 份清单列名各不相同，旧版写死取 r["区"] 直接 KeyError，工具等于没跑
  · 「原江北新区」与档案的「江北新区」不归一，65 所学校被误判成缺档
"""
import csv
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import reconcile  # noqa: E402


def write_csv(rows, name="expected_gulou_primary.csv"):
    """在临时目录造一份清单，返回路径。"""
    d = tempfile.mkdtemp()
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return p


class TestFromFilename(unittest.TestCase):
    def test_district_and_level(self):
        d, lv = reconcile.from_filename("data/expected_jiangning_primary.csv")
        self.assertEqual((d, lv), ("江宁区", "小学"))

    def test_junior(self):
        d, lv = reconcile.from_filename("data/expected_luhe_junior.csv")
        self.assertEqual((d, lv), ("六合区", "初中"))

    def test_unknown_slug(self):
        d, lv = reconcile.from_filename("expected_mystery.csv")
        self.assertEqual((d, lv), ("", ""))


class TestAlias(unittest.TestCase):
    def test_district_alias(self):
        self.assertEqual(reconcile.DISTRICT_ALIAS["原江北新区"], "江北新区")
        self.assertEqual(reconcile.DISTRICT_ALIAS["原浦口区"], "江北新区")

    def test_name_alias(self):
        self.assertEqual(reconcile.NAME_ALIAS["南京江北新区浦口实验小学"],
                         "南京市浦口实验小学")


class TestPick(unittest.TestCase):
    def test_first_non_empty(self):
        row = {"档案全称": "", "校名": "某小学", "学校": "别的"}
        self.assertEqual(reconcile.pick(row, "档案全称", "校名"), "某小学")

    def test_none(self):
        self.assertEqual(reconcile.pick({}, "校名"), "")


class TestLevelOf(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(reconcile.level_of("公办九年一贯制（小学部）"), "小学")
        self.assertEqual(reconcile.level_of("公办初中"), "初中")
        self.assertEqual(reconcile.level_of("普通高中"), "高中")
        self.assertEqual(reconcile.level_of("其它"), "")


class TestCheckFile(unittest.TestCase):
    def test_legacy_columns(self):
        # 栖霞那种「区/学段/学校」的旧格式
        p = write_csv([{"区": "鼓楼区", "学段": "小学",
                        "学校": "南京市琅琊路小学", "库内状态": ""}])
        rows = reconcile.check_file(p)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["状态"], "已有")

    def test_name_column_variants(self):
        # 校名 / 名录名称 / 学校名称 三种写法都要认
        for col in ("校名", "名录名称", "学校名称"):
            p = write_csv([{"片区": "鼓楼区", col: "南京市琅琊路小学",
                            "库内状态": ""}])
            rows = reconcile.check_file(p)
            self.assertEqual(rows[0]["学校"], "南京市琅琊路小学", col)

    def test_missing_school(self):
        p = write_csv([{"区": "鼓楼区", "学段": "小学",
                        "学校": "查无此小学", "库内状态": ""}])
        self.assertEqual(reconcile.check_file(p)[0]["状态"], "缺")

    def test_district_alias_applied(self):
        p = write_csv([{"片区": "原江北新区", "校名": "南京市浦口实验小学",
                        "库内状态": ""}], name="expected_jiangbei_primary.csv")
        rows = reconcile.check_file(p)
        self.assertEqual(rows[0]["区"], "江北新区")
        self.assertEqual(rows[0]["状态"], "已有")

    def test_merged_marked(self):
        p = write_csv([{"区": "鼓楼区", "学段": "小学", "学校": "某校小学部",
                        "库内状态": "并入母体档案"}])
        self.assertEqual(reconcile.check_file(p)[0]["状态"], "并入")

    def test_stopped_school_marked(self):
        # 「2026 年秋停招（由某分校代招）」——学校已不独立存在，不该算缺
        p = write_csv([{"区": "鼓楼区", "学段": "小学", "学校": "某停招小学",
                        "库内状态": "2026 年秋停招（由某校代招）"}])
        self.assertEqual(reconcile.check_file(p)[0]["状态"], "并入")

    def test_special_education_skipped(self):
        p = write_csv([{"区": "鼓楼区", "学段": "小学",
                        "学校": "南京市玄武区特殊教育学校", "库内状态": ""}])
        self.assertEqual(reconcile.check_file(p)[0]["状态"], "不收录")

    def test_archive_full_name_preferred(self):
        # 「档案全称」是人工确认过的映射，优先于公告原名
        p = write_csv([{"校名": "公告简称小学", "档案全称": "南京市琅琊路小学",
                        "库内状态": ""}])
        rows = reconcile.check_file(p)
        self.assertEqual(rows[0]["学校"], "南京市琅琊路小学")
        self.assertEqual(rows[0]["状态"], "已有")

    def test_filename_fallback(self):
        # 清单里没有区列时，靠文件名推断
        p = write_csv([{"校名": "南京市琅琊路小学", "库内状态": ""}],
                      name="expected_gulou_primary.csv")
        self.assertEqual(reconcile.check_file(p)[0]["区"], "鼓楼区")


class TestRealFile(unittest.TestCase):
    """真实的 17 份清单都必须能跑通——旧版就是在这里崩的。"""

    def test_all_expected_files_parse(self):
        targets = sorted((ROOT / "data").glob("expected_*.csv"))
        if not targets:
            self.skipTest("没有 expected_*.csv")
        for t in targets:
            rows = reconcile.check_file(str(t))
            self.assertTrue(rows, f"{t.name} 解析出 0 行")
            for r in rows:
                self.assertIn(r["状态"], ("已有", "并入", "缺", "不收录"), t.name)


if __name__ == "__main__":
    unittest.main()
