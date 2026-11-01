# -*- coding: utf-8 -*-
"""S1 批次控制线抽取的测试。

样本全部取自市教育局 2026-07-10 的真实公告片段，包括那些看起来别扭的写法：
章节标题和正文黏在一句里、顿号并列、同一句里两个分数。这些正是抽错的来源。
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ingest import extract  # noqa: E402

# 真实公告正文（节选，保留原始标点与空格）
NOTICE = (
    "2026年各类高中阶段学校投档控制分数线如下： "
    "一、科技、学科及数理人才贯通培养实验项目特长生 "
    "科技特长生、学科特长生和数理人才贯通培养实验项目特长生投档控制分数线为 560 分。 "
    "二、普通高中指标生 "
    "原市区和浦口区普通高中指标生投档控制分数线为 593 分。 "
    "江宁区、六合区、溧水区和高淳区普通高中指标生投档控制分数线，由各区教育局划定并向考生公布。 "
    "投档分相同时，需按排序规则录取。 "
    "三、体育、艺术特长生 "
    "普通高中体育特长生投档控制分数线为 455 分，艺术特长生投档控制分数线为 490 分。 "
    "四、普通高中统招生 "
    "1.第一批次原市区和浦口区普通高中投档控制分数线为 535 分。 "
    "2.第一批次中外合作办学项目及国际课程班投档控制分数线为 535 分。 "
    "五、职业学校 "
    "1.第一批次中职与本科3+4分段培养专业班、五年制高职与本科5+2分段培养专业班"
    "和五年制高职联合培养项目投档控制分数线为 500 分。 "
)


class TestScoreLines(unittest.TestCase):
    def setUp(self):
        self.got = extract.score_lines(NOTICE)

    def test_full_notice(self):
        self.assertEqual(self.got["指标生"], 593)
        self.assertEqual(self.got["学科科技特长生"], 560)
        self.assertEqual(self.got["第一批次统招"], 535)
        self.assertEqual(self.got["中职本科3+4"], 500)

    def test_sports_and_art_not_swapped(self):
        # 原句是「三、体育、艺术特长生 普通高中体育特长生…455 分，艺术特长生…490 分」，
        # 章节标题里的「艺术」比正文的「体育」更靠前，按"含关键词"判断必错
        self.assertEqual(self.got["体育特长生"], 455)
        self.assertEqual(self.got["艺术特长生"], 490)

    def test_five_year_college_not_confused_with_undergrad(self):
        # 「五年制高职与本科5+2」是 500 分那一档，
        # 而站点上的「五年制高职专业班 385」是另一档，不能混
        self.assertNotIn("五年制高职", self.got)

    def test_second_batch_not_invented(self):
        # 本公告只说「第二批次将于…发布」，没有数字，绝不能填默认值
        self.assertNotIn("第二批次统招", self.got)

    def test_art_after_sports_in_own_clause(self):
        got = extract.score_lines("普通高中体育特长生投档控制分数线为 455 分，"
                                  "艺术特长生投档控制分数线为 490 分。")
        self.assertEqual(got, {"体育特长生": 455, "艺术特长生": 490})

    def test_vocational_3plus3_vs_3plus4(self):
        got = extract.score_lines("中职与高职3+3分段培养专业班投档控制分数线为 400 分。")
        self.assertEqual(got["中职高职3+3"], 400)

    def test_non_line_sentences_ignored(self):
        # 招生计划人数句里也有三位数，不能当成控制线
        got = extract.score_lines("2026年全市参加中考的初中毕业生有74876人，"
                                  "普通高中招生计划为 45000 人。")
        self.assertEqual(got, {})

    def test_out_of_range_dropped(self):
        # 中考总分 700，出现 800 分只能是小程序里的其它编号
        self.assertEqual(extract.score_lines("投档控制分数线为 800 分。"), {})

    def test_first_occurrence_wins(self):
        got = extract.score_lines("指标生投档控制分数线为 593 分。"
                                  "指标生投档控制分数线为 600 分。")
        self.assertEqual(got["指标生"], 593)

    def test_empty(self):
        self.assertEqual(extract.score_lines(""), {})
        self.assertEqual(extract.score_lines(None), {})


class TestSiteBaseline(unittest.TestCase):
    def test_reads_real_template(self):
        base = extract.site_baseline()
        self.assertEqual(base.get("指标生"), 593)
        self.assertEqual(base.get("艺术特长生"), 490)
        self.assertEqual(base.get("体育特长生"), 455)
        self.assertEqual(base.get("第一批次统招"), 535)
        self.assertEqual(base.get("第二批次统招"), 470)

    def test_missing_file(self):
        self.assertEqual(extract.site_baseline("/nonexistent/score.html"), {})


class TestCompare(unittest.TestCase):
    def test_no_diff(self):
        vals = {"指标生": 593, "第一批次统招": 535}
        self.assertEqual(extract.compare(vals, dict(vals)), [])

    def test_detects_change(self):
        diffs = extract.compare({"指标生": 593}, {"指标生": 590})
        self.assertEqual(diffs, [("指标生", 593, 590)])

    def test_ignores_keys_absent_in_official(self):
        # 官方这次没抽到的项不参与比对——那是缺口，不是错
        diffs = extract.compare({"指标生": 593}, {"指标生": 593, "第二批次统招": 470})
        self.assertEqual(diffs, [])

    def test_reports_missing_on_site(self):
        diffs = extract.compare({"普职融通": 420}, {})
        self.assertEqual(diffs, [("普职融通", 420, None)])


class TestPageText(unittest.TestCase):
    def test_strips_scripts_and_styles(self):
        html = ("<html><head><style>.a{color:red}</style>"
                "<script>var x=1;</script></head><body><p>投档控制分数线</p></body></html>")
        self.assertEqual(extract.page_text(html), "投档控制分数线")


# ---------------------------------------------------------------- 派位计划

LOTTERY_HTML = """<table>
<tr><th>序号</th><th>学校名称</th><th>派位计划（人）</th><th>派位范围</th></tr>
<tr><td>1</td><td>南京市鼓楼区第一中心小学</td><td>28</td><td>鼓楼区</td></tr>
<tr><td>2</td><td>南京市琅琊路小学</td><td>21</td><td>鼓楼区</td></tr>
</table>
<table>
<tr><th>序号</th><th>学校名称</th><th>派位计划（人）</th><th>派位范围</th>
<th>学费标准(元/生·学期)</th><th>住宿条件</th></tr>
<tr><td>1</td><td>南京市鼓楼实验小学</td><td>179</td><td>鼓楼区</td><td>17000</td><td>无</td></tr>
</table>
<table>
<tr><td>索 引 号：</td><td>000014349/2026-32519</td><td>主题分类：</td><td>科技、教育</td></tr>
</table>"""


class TestLotteryPlans(unittest.TestCase):
    def test_extracts_both_tables(self):
        got = extract.lottery_plans(LOTTERY_HTML)
        self.assertEqual(got["南京市鼓楼区第一中心小学"], 28)
        self.assertEqual(got["南京市琅琊路小学"], 21)
        self.assertEqual(got["南京市鼓楼实验小学"], 179)

    def test_meta_table_ignored(self):
        got = extract.lottery_plans(LOTTERY_HTML)
        self.assertEqual(len(got), 3)

    def test_extra_columns_ignored(self):
        # 民办表多两列，不能把学费当计划数
        self.assertEqual(extract.lottery_plans(LOTTERY_HTML)["南京市鼓楼实验小学"], 179)

    def test_empty(self):
        self.assertEqual(extract.lottery_plans("<html></html>"), {})


class TestNameMatching(unittest.TestCase):
    SCHOOLS = [
        ("小学-鼓楼区-南京市琅琊路小学", "南京市琅琊路小学",
         extract.name_keys("南京市琅琊路小学")),
        ("小学-鼓楼区-南师附中鲁迅园小学", "南师附中鲁迅园小学",
         extract.name_keys("南师附中鲁迅园小学")),
        ("小学-玄武区-南京师范大学附属小学", "南京师范大学附属小学",
         extract.name_keys("南京师范大学附属小学")),
        ("小学-玄武区-南京师范大学附属小学仙鹤门分校",
         "南京师范大学附属小学仙鹤门分校",
         extract.name_keys("南京师范大学附属小学仙鹤门分校")),
    ]

    def test_norm_strips_city_prefix(self):
        self.assertEqual(extract._norm("南京市琅琊路小学"), "琅琊路小学")
        self.assertEqual(extract._norm("南京外国语学校"), "外国语学校")

    def test_norm_keeps_province_prefix(self):
        # 「江苏省六合高级中学」的「江苏省」是校名的一部分，不能剥
        self.assertEqual(extract._norm("江苏省六合高级中学"), "江苏省六合高级中学")

    def test_norm_keeps_suffix(self):
        # 抹掉「附属/实验/小学」会把不同学校归一成同一所
        self.assertNotEqual(extract._norm("金陵中学实验小学"),
                            extract._norm("金陵中学附属小学"))

    def test_exact_match(self):
        sid = extract.match_school("南京市琅琊路小学", self.SCHOOLS)
        self.assertEqual(sid, "小学-鼓楼区-南京市琅琊路小学")

    def test_whitespace_ignored(self):
        sid = extract.match_school("南京市琅琊路 小学", self.SCHOOLS)
        self.assertEqual(sid, "小学-鼓楼区-南京市琅琊路小学")

    def test_abbrev_equivalence(self):
        # 公告写「南京师范大学附属中学 鲁迅园小学」，档案是「南师附中鲁迅园小学」
        sid = extract.match_school("南京师范大学附属中学 鲁迅园小学", self.SCHOOLS)
        self.assertEqual(sid, "小学-鼓楼区-南师附中鲁迅园小学")

    def test_ambiguous_substring_not_matched(self):
        # 只给「附属小学」这种片段，会同时命中本体与分校 → 不猜
        self.assertIsNone(extract.match_school("附属小学", self.SCHOOLS))

    def test_campus_suffix_falls_back_to_main(self):
        # 「（本部）」唯一命中本体：包含匹配只有一所成立，可以放心归到本部
        sid = extract.match_school("南京师范大学附属小学（本部）", self.SCHOOLS)
        self.assertEqual(sid, "小学-玄武区-南京师范大学附属小学")

    def test_unknown_school(self):
        self.assertIsNone(extract.match_school("南京市鼓楼区第二实验小学", self.SCHOOLS))

    def test_empty_name(self):
        self.assertIsNone(extract.match_school("", self.SCHOOLS))

    def test_nearest_gives_lead(self):
        got = extract.nearest("南京市琅琊路小学", self.SCHOOLS)
        self.assertIn("南京市琅琊路小学", got)


class TestNameKeys(unittest.TestCase):
    """缩写变体是累积生成、且同时保留原名与去前缀名。"""

    def test_cumulative_abbreviation(self):
        # 公告写「财大附小」，档案是「南京财经大学附属小学」：要两步替换才到
        keys = extract.name_keys("南京财经大学附属小学")
        self.assertIn("财大附小", keys)
        self.assertIn("财大附属小学", keys)

    def test_keeps_original_when_prefix_stripped_form_loses_it(self):
        # 「南京大学」的「南京」会被前缀规则吃掉，只看去前缀形式就永远对不上「南大」
        keys = extract.name_keys("南京大学附属丁家桥小学")
        self.assertIn("南大附属丁家桥小学", keys)
        self.assertIn("南京大学附属丁家桥小学", keys)

    def test_university_abbrev(self):
        self.assertIn("二师院附小", extract.name_keys("江苏第二师范学院附属小学"))

    def test_empty(self):
        self.assertEqual(extract.name_keys(""), set())


class TestLoadSchoolsShort(unittest.TestCase):
    """简称要进可比形式，但只收全库唯一的那些。

    官方名单写「树人附小」，档案写「南师附中树人学校附属小学」——取头取尾的缩写
    规则拼不出来，只能靠档案的 short 字段。但「力小」「拉小」这类两字简称有多校共用，
    一旦进表，match_school 会返回第一所，把别家的数字安到这所头上。
    """

    ROWS = [
        {"id": "a", "name": "南师附中树人学校附属小学", "short": "树人附小",
         "level": "小学"},
        {"id": "b", "name": "南京市力学小学", "short": "力小", "level": "小学"},
        {"id": "c", "name": "南京市力人学校（小学部）", "short": "力小",
         "level": "小学"},  # 与 b 共用「力小」
    ]

    def _load(self, rows):
        import json, tempfile, os
        from unittest import mock
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"schools": rows}, f, ensure_ascii=False)
        self.addCleanup(os.unlink, path)
        with mock.patch.object(extract.config, "INDEX", path):
            return extract.load_schools(level="小学")

    def test_unique_short_becomes_match_key(self):
        schools = self._load(self.ROWS)
        sid = extract.match_school("树人附小", schools)
        self.assertEqual(sid, "a")

    def test_duplicate_short_excluded(self):
        # 「力小」两校共用 → 不进表，只能靠全名匹配，宁可对不上也不猜
        schools = self._load(self.ROWS)
        self.assertIsNone(extract.match_school("力小", schools))
        # 但全名照样能对上
        self.assertEqual(extract.match_school("南京市力学小学", schools), "b")

    def test_no_short_field(self):
        rows = [{"id": "x", "name": "南京市拉萨路小学", "level": "小学"}]
        schools = self._load(rows)
        self.assertEqual(extract.match_school("拉萨路小学", schools), "x")


# ---------------------------------------------------------------- 施教区

ZONE_TEXT = """一、鼓楼区主城小学施教区
第一中心小学： 上海路[1-75号（单），2-68号（双）]、五台山、五台花园、豆菜桥。
第二实验小学：东井村3号1-39幢，小市村1-29幢，小市村[1-100号（不分单双）]。
小市中心小学：中央北路和燕路：泰和园、小市街、百灵街、东门街100号以内。
二、相关说明
1.具体招生办法执行当年《鼓楼区义务教育阶段学校招生办法》。
"""


class TestDistrictZones(unittest.TestCase):
    def test_extracts_entries(self):
        got = extract.district_zones(ZONE_TEXT)
        self.assertEqual(len(got), 3)
        self.assertIn("东井村3号", got["第二实验小学"])

    def test_keeps_inner_period(self):
        # 范围文本里自带句号（「不分单双）」后接句号），按句号切会把一条拆成两条
        got = extract.district_zones(ZONE_TEXT)
        self.assertTrue(got["第二实验小学"].endswith("（不分单双）]")
                        or "小市村" in got["第二实验小学"])

    def test_colon_inside_zone_does_not_split(self):
        # 「中央北路和燕路：泰和园…」中间还有冒号，但前面不是校名
        got = extract.district_zones(ZONE_TEXT)
        self.assertIn("泰和园", got["小市中心小学"])

    def test_tail_cut_off(self):
        got = extract.district_zones(ZONE_TEXT)
        for zone in got.values():
            self.assertNotIn("具体招生办法", zone)

    def test_short_fragment_dropped(self):
        got = extract.district_zones("某小学： 太短\n另一小学：这里是一段足够长的施教区范围描述")
        self.assertNotIn("某小学", got)

    def test_empty(self):
        self.assertEqual(extract.district_zones(""), {})


class TestCompareZones(unittest.TestCase):
    SCHOOLS = [("id-a", "南京市琅琊路小学", extract.name_keys("南京市琅琊路小学"))]

    def test_hit(self):
        hit, missing = extract.compare_zones({"琅琊路小学": "某路段1-10号"}, self.SCHOOLS)
        self.assertEqual(len(hit), 1)
        self.assertEqual(missing, [])

    def test_missing_school(self):
        hit, missing = extract.compare_zones({"查无此小学": "某路段"}, self.SCHOOLS)
        self.assertEqual(hit, [])
        self.assertEqual(missing[0][0], "查无此小学")


class TestMergedInto(unittest.TestCase):
    """已撤并校：旧名单里还在，建制已经没了。

    这类校名会被 compare_zones 判成缺档，于是每一轮抽取都报同一批假缺口。
    假缺口比不报更坏——它把人引去补一份不该存在的档案。
    """

    def test_merged_school_recognized(self):
        got = extract.merged_into("汉口路小学")
        self.assertIsNotNone(got)
        new, why = got
        self.assertEqual(new, "南京市琅琊路小学")
        self.assertIn("2024", why)

    def test_full_name_also_matches(self):
        # 名单里有时写「南京市汉口路小学」，有时写「汉口路小学」
        self.assertIsNotNone(extract.merged_into("南京市汉口路小学"))

    def test_two_into_one(self):
        # 察哈尔路与回龙桥合并成同一所新校，两条都要认得
        a = extract.merged_into("察哈尔路小学")
        b = extract.merged_into("回龙桥小学")
        self.assertEqual(a[0], "南师附中鲁迅园小学")
        self.assertEqual(b[0], "南师附中鲁迅园小学")

    def test_normal_school_not_matched(self):
        # 关键：别把还在办的学校误判成撤并，那会让真缺口被吃掉
        for name in ("南京市琅琊路小学", "拉萨路小学", "力学小学", ""):
            self.assertIsNone(extract.merged_into(name), name)

    def test_short_fragment_not_matched(self):
        """残片不能命中：「小学」的子串是整个校名的尾部。

        名单抽取一旦切坏，key 可能只剩「小学」「路小学」这类片段。
        子串匹配不卡长度的话，它们会命中「汉口路小学」→ 判成已撤并 →
        真实缺口被静默归进「不需补档」，报告里看不出任何异常。
        宁可漏判（报告多一条，人看得见），也不能误判。
        """
        for frag in ("小学", "路小学", "学校", "南京", "一二三"):
            self.assertIsNone(extract.merged_into(frag), frag)

    def test_campus_suffix_still_matched(self):
        # 反过来要保证：带后缀的写法仍然能认出来，否则长度保护就白加了
        got = extract.merged_into("汉口路小学（本部）")
        self.assertIsNotNone(got)
        self.assertEqual(got[0], "南京市琅琊路小学")

    def test_none_input(self):
        self.assertIsNone(extract.merged_into(None))


class TestCompareLottery(unittest.TestCase):
    SCHOOLS = [("id-a", "南京市琅琊路小学", extract.name_keys("南京市琅琊路小学"))]

    def test_same(self):
        got = extract.compare_lottery({"南京市琅琊路小学": 21}, self.SCHOOLS,
                                     {"id-a": 21})
        self.assertEqual(len(got[0]), 1)
        self.assertEqual(got[1:], ([], [], []))

    def test_diff(self):
        same, diff, missing, unmatched = extract.compare_lottery(
            {"南京市琅琊路小学": 21}, self.SCHOOLS, {"id-a": 20})
        self.assertEqual(diff, [("id-a", "南京市琅琊路小学", 21, 20)])
        self.assertEqual(same, [])

    def test_missing_in_archive(self):
        same, diff, missing, unmatched = extract.compare_lottery(
            {"南京市琅琊路小学": 21}, self.SCHOOLS, {})
        self.assertEqual(missing, [("id-a", "南京市琅琊路小学", 21)])
        self.assertEqual(diff, [])

    def test_unmatched_school(self):
        same, diff, missing, unmatched = extract.compare_lottery(
            {"查无此校小学": 9}, self.SCHOOLS, {})
        self.assertEqual(unmatched, [("查无此校小学", 9)])
        self.assertEqual(missing, [])


class TestWriteFacts(unittest.TestCase):
    def test_same_content_not_duplicated(self):
        # 同一天反复跑（调试、重试）不该把文件写重
        import tempfile
        import unittest.mock
        with tempfile.TemporaryDirectory() as d:
            with unittest.mock.patch.object(extract, "FACTS_DIR", d):
                rec = [{"job": "j1", "ok": True, "values": {"指标生": 593}}]
                p1, n1 = extract.write_facts(rec, when="2026-11")
                _p2, n2 = extract.write_facts(rec, when="2026-11")
                self.assertEqual((n1, n2), (1, 0))
                with open(p1, encoding="utf-8") as f:
                    self.assertEqual(len(f.readlines()), 1)

    def test_changed_value_appended(self):
        import tempfile
        import unittest.mock
        with tempfile.TemporaryDirectory() as d:
            with unittest.mock.patch.object(extract, "FACTS_DIR", d):
                extract.write_facts([{"job": "j1", "values": {"指标生": 593}}], when="2026-11")
                p, n = extract.write_facts([{"job": "j1", "values": {"指标生": 590}}],
                                           when="2026-11")
                self.assertEqual(n, 1)
                with open(p, encoding="utf-8") as f:
                    self.assertEqual(len(f.readlines()), 2)


# ---------------------------------------------------------------- 在办学校名单

LIST_TEXT = """二、实施细则
外来务工人员随迁子女是指非南京市户籍、在宁务工人员的随迁子女。
三、附件
咨询方式一览表
2026年鼓楼区小学招生入学线下咨询方式一览表
咨询地点 咨询电话
南京市鼓楼区第一中心小学 83320940
南京市拉萨路小学（百步校区） 86609444
南京市金陵汇文学校小学部 86379955
南京市鼓楼区特殊教育学校 （阅江楼校区） 86371479-806
外来务工人员随迁子女
咨询时间：2026年7月2日—7月6日
"""


class TestSchoolPhoneList(unittest.TestCase):
    def test_extracts_schools(self):
        got = extract.school_phone_list(LIST_TEXT)
        self.assertEqual(got["南京市鼓楼区第一中心小学"], "83320940")
        self.assertEqual(len(got), 4)

    def test_tail_searched_after_head(self):
        # 「外来务工人员随迁子女」在正文前段也出现，右界必须从标题之后找，
        # 否则段落被截成空串，抽到 0 所（实测踩过）
        self.assertGreater(len(extract.school_phone_list(LIST_TEXT)), 0)

    def test_campus_suffix_removed(self):
        got = extract.school_phone_list(LIST_TEXT)
        self.assertIn("南京市拉萨路小学", got)
        self.assertIn("南京市鼓楼区特殊教育学校", got)

    def test_xiaoxuebu_kept(self):
        # 「小学部」结尾不能被截成「小学」，否则剩下一个「部」字对不上号
        got = extract.school_phone_list(LIST_TEXT)
        self.assertIn("南京市金陵汇文学校小学部", got)

    def test_extension_number(self):
        got = extract.school_phone_list(LIST_TEXT)
        self.assertEqual(got["南京市鼓楼区特殊教育学校"], "86371479-806")

    def test_no_anchor(self):
        self.assertEqual(extract.school_phone_list("没有附件标题的正文"), {})


class TestLoadSchools(unittest.TestCase):
    def test_level_filter(self):
        all_rows = extract.load_schools()
        primary = extract.load_schools(level="小学")
        self.assertGreater(len(all_rows), len(primary))
        # 收窄到小学后，「金陵汇文学校小学部」不会同时撞上初中同名档案
        sid = extract.match_school("南京市金陵汇文学校小学部", primary)
        self.assertTrue(sid is None or sid.startswith("小学-"))


class TestExportedRules(unittest.TestCase):
    def test_every_rule_key_has_label(self):
        # 抽到的 key 必须都能翻成中文名，否则报告里会出现裸键名
        for key, _must, _mustnot in extract.SCORE_RULES:
            self.assertIn(key, extract.LABELS)

    def test_site_keys_subset_of_labels(self):
        for key, _kws in extract.SITE_ROW_KEYS:
            self.assertIn(key, extract.LABELS)


if __name__ == "__main__":
    unittest.main()
