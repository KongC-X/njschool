# -*- coding: utf-8 -*-
"""数据管道单测：python -m unittest discover -s tests -p "test_*.py"

覆盖 facts / aliases / marks 三块纯逻辑。它们此前完全没有测试——
四期调整「对口初中」口径时，只能靠临时脚本手工比对，改错了没人知道。

全部用内联样本，不依赖 index.json 或 site/ 产物。
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pipeline import aliases, facts, marks, source  # noqa: E402


KV = """| 项目 | 内容 | 信度 |
|---|---|---|
| 学校全称 | 示例小学 | A |
| 创办时间 | 1934 年 | A |
| 对口初中 | 示例中学（单校直升） | A |
| 学费 | 未获取 | A |
| 咨询电话 | 025-12345678 | B |
"""


class TestFacts(unittest.TestCase):
    def test_extract_basic(self):
        got = facts.extract(KV)
        self.assertEqual(got["founded"], "1934 年")
        self.assertEqual(got["feeder"], "示例中学（单校直升）")
        self.assertEqual(got["phone"], "025-12345678")

    def test_extract_drops_empty_marker(self):
        # 「未获取」不能当成一个有值的字段写进去，否则界面会显示「学费：未获取」两次
        self.assertNotIn("tuition", facts.extract(KV))

    def test_feeder_accepts_equivalent_key_names(self):
        # 同一个语义在档案里有三种写法，只认一种会静默漏掉一批
        for key in ("对口初中", "主要生源/对口初中", "施教区对口初中"):
            text = "| 项目 | 内容 | 信度 |\n|---|---|---|\n| %s | 某中学 | A |\n" % key
            self.assertIn("feeder", facts.extract(text), f"{key} 没被识别为对口初中")

    def test_missing_only_inside_gap_section(self):
        text = ("## 一、速览\n\n正文里提一句学费，不算缺口声明。\n\n"
                "## 九、数据缺口（明确未获取）\n\n- 学校**学费**标准未公开\n")
        self.assertEqual(facts.extract_missing(text), {"tuition"})

    def test_missing_ignores_score_lines(self):
        # 「对口初中的完整中考数据」缺的是中考数据，不是对口关系——
        # 整节匹配会把 36 所小学误标成「对口初中未获取」
        text = ("## 四、缺口（未获取）\n\n"
                "- 2025 届**对口初中**的完整**中考**数据\n")
        self.assertNotIn("feeder", facts.extract_missing(text))

    def test_missing_classes_not_confused_with_class_size(self):
        # 「班级与学生总数」讲的是办学规模，不是班型
        text = ("## 四、缺口（未获取）\n\n"
                "- 学校占地面积、建筑面积、**班级**与学生总数\n")
        self.assertNotIn("classes", facts.extract_missing(text))

    def test_missing_without_section_is_empty(self):
        self.assertEqual(facts.extract_missing("## 一、速览\n\n没有缺口小节\n"), set())


# 测试专用的小别名表：真实表要求每条别名都命中至少一所学校，小样本跑不通
COMBOS = [("拉力琅", ("琅琊路小学", "拉萨路小学", "力学小学"))]


class _S:
    def __init__(self, name, short="", sid=None):
        self.name = name
        self.short = short
        self.id = sid or name


class TestAliases(unittest.TestCase):
    def test_combo_expands_to_each_school(self):
        schools = [_S("南京市琅琊路小学", "琅小"),
                   _S("南京市拉萨路小学", "拉小"),
                   _S("南京市力学小学", "力小")]
        got = aliases.build(schools, table=COMBOS)
        self.assertEqual(len(got), 3)
        for sid, text in got.items():
            self.assertIn("拉力琅", text)

    def test_exact_match_does_not_leak_to_branch_school(self):
        # 用包含匹配时，「琅琊路小学明发滨江分校」也会被算成拉力琅（曾多出 10 所）
        schools = [_S("南京市琅琊路小学"),
                   _S("南京市拉萨路小学"),
                   _S("南京市力学小学"),
                   _S("南京市琅琊路小学明发滨江分校")]
        got = aliases.build(schools, table=COMBOS)
        self.assertNotIn("南京市琅琊路小学明发滨江分校", got)

    def test_alias_pointing_at_nothing_fails_loudly(self):
        # 别名写错必须让构建失败，不能悄悄不生效
        with self.assertRaises(SystemExit):
            aliases.build([_S("某某不存在的学校")], table=COMBOS)


class TestMarks(unittest.TestCase):
    def test_tentative_from_name_row(self):
        text = "| 项目 | 内容 | 信度 |\n|---|---|---|\n| 学校全称 | 某规划学校（暂定名） | A |\n"
        self.assertIn("T", marks.flags(text, "某规划学校"))

    def test_tentative_not_triggered_by_mentioning_others(self):
        # 正文里说「别校是暂定名」，不代表自己也是
        text = "## 一、说明\n\n> 「潘窑规划学校」是暂定名，正式校名未定。\n"
        self.assertEqual(marks.flags(text, "南京市板桥中心小学"), [])

    def test_transition_only_inside_own_district_section(self):
        text = ("## 二、施教区（2026 年）\n\n- 某小区（过渡学区）\n\n"
                "## 六、升学\n\n- 与某校（过渡学区）重合\n")
        self.assertIn("D", marks.flags(text, "示例小学"))

    def test_transition_not_triggered_outside_district_section(self):
        text = "## 六、升学\n\n- 对比表里提到某校（过渡学区）\n"
        self.assertNotIn("D", marks.flags(text, "示例小学"))

    def test_labels_are_user_facing_chinese(self):
        text = "| 项目 | 内容 | 信度 |\n|---|---|---|\n| 学校全称 | 某规划学校 | A |\n"
        self.assertEqual(marks.labels(text, "某规划学校"), ["校名暂定"])


if __name__ == "__main__":
    unittest.main()

class TestSourceCache(unittest.TestCase):
    """档案正文必须只读一次。

    此前 schema（校验）、load（渲染详情）、render（生成前端数据）各自 open()，
    实测 545 份文件被读 1640 次。统一到 source.text 后应恰好 545 次。
    """

    def setUp(self):
        source.reset_cache()

    def test_same_file_read_once(self):
        rel = "小学/鼓楼区/南京市琅琊路小学.md"
        first = source.text(rel)
        second = source.text(rel)
        self.assertEqual(first, second)
        self.assertEqual(source.cache_size(), 1, "同一份档案被读了两次")

    def test_different_files_cached_separately(self):
        a = "小学/鼓楼区/南京市琅琊路小学.md"
        b = "小学/鼓楼区/南京市拉萨路小学.md"
        self.assertNotEqual(source.text(a), source.text(b))
        self.assertEqual(source.cache_size(), 2)

    def test_returns_full_text(self):
        # 缓存不能截断内容：校验层靠它判断有没有「数据缺口」章节
        rel = "小学/鼓楼区/南京市琅琊路小学.md"
        self.assertIn("数据缺口", source.text(rel))


class TestTalentPlans(unittest.TestCase):
    """特长生招生计划的数值必须可计算。

    此前 plan 是自由文本「125 人」，既不能排序也不能求和，
    还不能校验——模板表格只能原样打印，写错一个数字看不出。
    """

    @classmethod
    def setUpClass(cls):
        import json
        p = ROOT / "data" / "talent_schools.json"
        cls.data = json.loads(p.read_text(encoding="utf-8"))

    def test_all_plans_are_positive_ints(self):
        for group in ("tech", "info", "academic", "arts", "tiyu"):
            for row in self.data[group]:
                self.assertIsInstance(row["plan_n"], int, f"{row['name']} 的 plan_n 不是整数")
                self.assertGreater(row["plan_n"], 0, f"{row['name']} 的 plan_n 非正")

    def test_every_group_has_rows(self):
        for group in ("tech", "info", "academic", "arts", "tiyu"):
            self.assertTrue(self.data[group], f"{group} 分组为空，页面会少一张表")

    def test_no_free_text_plan_left(self):
        for group in ("tech", "info", "academic", "arts", "tiyu"):
            for row in self.data[group]:
                self.assertNotIn("plan", row, f"{row['name']} 仍留有计划文本字段")
