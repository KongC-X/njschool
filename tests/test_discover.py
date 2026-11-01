# -*- coding: utf-8 -*-
"""公告列表页发现与条目抽取的测试。

三个样本分别对应实测到的三种站点形态：
  首页就有公告（区级平台的常见形态）
  首页只有图片导航、栏目页才有公告（北京东路小学）
  JS 渲染壳（鼓楼 njgljy 平台、万网建站）

规则本身都是从这三类现场校准出来的，用例就是它们的固化。
不联网，用假 fetcher 按 URL 返回预置页面。
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ingest import discover, fetch  # noqa: E402

BASE = "http://school.example.cn/"

HOME_WITH_NEWS = """<html><body>
<a href="/xwzx">校园新闻</a>
<a href="/tzgg/1.html">关于2026年秋季学期开学工作的通知</a>
<a href="/tzgg/2.html">南京市某某小学招生简章与施教区公示</a>
<a href="/tzgg/3.html">关于组织教师参加市级培训的通知</a>
<a href="/tzgg/4.html">第十周工作安排与值班表</a>
</body></html>"""

HOME_NAV_ONLY = """<html><body>
<img src="/banner.jpg">
<a href="/html/NewList-abc.html">通知公告</a>
<a href="/html/NewList-def.html">校园新闻</a>
<a href="/">首页</a>
</body></html>"""

LIST_PAGE = """<html><body>
<a href="/html/202610/NewShow-1.html">南京市北京东路小学档案室采购中标通知 2026-10-19</a>
<a href="/html/202610/NewShow-2.html">关于国庆节放假安排的通知 2026-09-28</a>
<a href="/html/202610/NewShow-3.html">第十周工作安排与国旗下讲话 2026-11-01</a>
<a href="/html/202610/NewShow-4.html">2026年秋季运动会报名通知 2026-10-08</a>
</body></html>"""

SHELL = ("<html class='smart-design-mode'><head>"
         "<script src='https://img.example.com/x.js'></script>"
         "<title>南京某小学</title></head><body><script src='y.js'></script></body></html>")


class FakeFetcher:
    def __init__(self, pages=None, fail=()):
        self.pages = pages or {}
        self.fail = set(fail)
        self.calls = []

    def get(self, url, force=False):
        self.calls.append(url)
        if url in self.fail:
            return fetch.Response(url=url, status=404, error="404 Not Found")
        html = self.pages.get(url)
        if html is None:
            return fetch.Response(url=url, status=404, error="404 Not Found")
        return fetch.Response(url=url, status=200, body=html.encode(),
                              content_hash="x" * 16)


def src(url=BASE):
    return {"id": "school:小学-某区-某小学", "name": "某小学", "entry": url}


class TestLinks(unittest.TestCase):
    def test_relative_becomes_absolute(self):
        got = discover.links('<a href="/a/b.html">标题足够长的公告一</a>', BASE)
        self.assertEqual(got[0][1], "http://school.example.cn/a/b.html")

    def test_offsite_dropped(self):
        self.assertEqual(discover.links('<a href="https://other.com/x">外站链接</a>', BASE), [])

    def test_javascript_and_mailto_dropped(self):
        html = ('<a href="javascript:void(0)">脚本一</a>'
                '<a href="mailto:a@b.cn">邮件链接</a>')
        self.assertEqual(discover.links(html, BASE), [])

    def test_tags_stripped_from_title(self):
        got = discover.links('<a href="/x"><span>带标签</span>的标题</a>', BASE)
        self.assertEqual(got[0][0], "带标签 的标题")


class TestEntries(unittest.TestCase):
    def test_short_titles_filtered(self):
        # 「更多」「首页」这类是导航，不是公告
        got = discover.entries('<a href="/1">更多</a><a href="/2">首页</a>', BASE)
        self.assertEqual(got, [])

    def test_long_titles_filtered(self):
        long_title = "关" * 90
        got = discover.entries(f'<a href="/1">{long_title}</a>', BASE)
        self.assertEqual(got, [])

    def test_dedup_by_url(self):
        html = ('<a href="/1">同一个公告标题内容</a><a href="/1">同一个公告标题内容</a>')
        self.assertEqual(len(discover.entries(html, BASE)), 1)

    def test_breadcrumb_dropped(self):
        # 北京东路列表页顶部有「首页>> 通知公告」，9 字越过长度门槛但它是导航
        html = ('<a href="http://school.example.cn/">首页&gt;&gt; 通知公告</a>'
                '<a href="/n/1.html">关于2026年秋季学期开学工作的通知</a>')
        got = discover.entries(html, BASE)
        self.assertEqual(len(got), 1)
        self.assertNotIn("首页", got[0][0])

    def test_realistic_page(self):
        got = discover.entries(HOME_WITH_NEWS, BASE)
        self.assertEqual(len(got), 4)
        self.assertTrue(got[0][0].startswith("关于2026年秋季学期"))


class TestCandidates(unittest.TestCase):
    def test_picks_nav_by_keyword(self):
        cands = discover.list_candidates(HOME_NAV_ONLY, BASE)
        self.assertEqual(cands[0][0], "通知公告")
        self.assertTrue(cands[0][1].endswith("NewList-abc.html"))

    def test_excludes_self(self):
        html = '<a href="/">通知公告</a>'
        self.assertEqual(discover.list_candidates(html, BASE), [])

    def test_excludes_long_titles(self):
        # 长标题是公告正文，不是栏目入口
        html = '<a href="/x">关于2026年秋季学期开学工作的通知公告</a>'
        self.assertEqual(discover.list_candidates(html, BASE), [])


class TestDiscover(unittest.TestCase):
    def test_homepage_enough_entries(self):
        f = FakeFetcher({BASE: HOME_WITH_NEWS})
        got = discover.discover(src(), f)
        self.assertTrue(got["ok"])
        self.assertEqual(got["via"], "homepage")
        self.assertEqual(len(got["items"]), 4)
        self.assertEqual(len(f.calls), 1)          # 不多打一次请求

    def test_falls_back_to_nav_list(self):
        list_url = "http://school.example.cn/html/NewList-abc.html"
        f = FakeFetcher({BASE: HOME_NAV_ONLY, list_url: LIST_PAGE})
        got = discover.discover(src(), f)
        self.assertTrue(got["ok"])
        self.assertEqual(got["list_url"], list_url)
        self.assertIn("通知公告", got["via"])
        self.assertEqual(len(got["items"]), 4)

    def test_shell_is_flagged_spa(self):
        f = FakeFetcher({BASE: SHELL})
        got = discover.discover(src(), f)
        self.assertFalse(got["ok"])
        self.assertTrue(got["spa"])

    def test_no_entries_no_candidates_not_spa(self):
        # 页面够大（不是壳）但没有任何站内链接：应判「未找到栏目页」而非 SPA
        empty = "<html><body>" + "<p>占位内容</p>" * 400 + "</body></html>"
        f = FakeFetcher({BASE: empty})
        got = discover.discover(src(), f)
        self.assertFalse(got["ok"])
        self.assertFalse(got["spa"])

    def test_entry_failure(self):
        f = FakeFetcher({}, fail=[BASE])
        got = discover.discover(src(), f)
        self.assertFalse(got["ok"])
        self.assertIn("不可达", got["reason"])

    def test_stops_after_good_list(self):
        # 找到够好的列表就停，不再验证后续候选（省请求）
        cand = ("http://school.example.cn/html/NewList-abc.html")
        f = FakeFetcher({BASE: HOME_NAV_ONLY, cand: LIST_PAGE})
        discover.discover(src(), f)
        self.assertLessEqual(len(f.calls), 3)


class TestRecord(unittest.TestCase):
    def test_truncates_titles(self):
        items = [(f"公告标题第{i}条记录", f"http://x/{i}") for i in range(20)]
        rec = discover.record(src(), {"ok": True, "list_url": BASE, "via": "homepage",
                                      "items": items})
        self.assertEqual(len(rec["titles"]), discover.KEEP_ITEMS)
        self.assertTrue(rec["ok"])

    def test_keeps_spa_flag(self):
        rec = discover.record(src(), {"ok": False, "spa": True, "reason": "壳"})
        self.assertTrue(rec["spa"])
        self.assertFalse(rec["ok"])

    def test_failure_has_reason(self):
        rec = discover.record(src(), {"ok": False, "reason": "未找到"})
        self.assertEqual(rec["reason"], "未找到")
        self.assertEqual(rec["titles"], [])


class TestRealLists(unittest.TestCase):
    """真实发现结果的结构必须始终可被 run.py 消费。"""

    def test_if_present_is_wellformed(self):
        lists = discover.load_lists()
        if not lists:
            self.skipTest("尚未运行 discover，跳过")
        for sid, rec in lists.items():
            self.assertTrue(sid.startswith("school:"), sid)
            for key in ("ok", "spa", "list_url", "titles", "checked_at"):
                self.assertIn(key, rec, f"{sid} 缺字段 {key}")
            self.assertIsInstance(rec["titles"], list)


if __name__ == "__main__":
    unittest.main()
