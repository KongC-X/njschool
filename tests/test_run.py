# -*- coding: utf-8 -*-
"""巡检判定的测试。

核心是「什么才算新增公告」。这里踩过的坑很具体：把新列表与旧集合做差集，
南师附小首页轮播转一次就报出 12 条「新增」，全是误报。改成「只认列表顶部的
连续新增」之后，顺序抖动不再制造噪音，真新增也不会漏。
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ingest import discover, fetch, run  # noqa: E402

BASE = "http://school.example.cn/"


def page(*titles):
    body = "".join(f'<a href="/n/{i}.html">{t}</a>' for i, t in enumerate(titles))
    return f"<html><body>{body}</body></html>"


def resp(html, status=200):
    return fetch.Response(url=BASE, status=status, body=html.encode(),
                          content_hash="h" * 16)


class FakeFetcher:
    def __init__(self, r):
        self.r = r
        self.calls = []

    def get(self, url, force=False):
        self.calls.append(url)
        return self.r


def src():
    return {"id": "school:小学-某区-某小学", "name": "某小学", "entry": BASE}


def rec(titles=None, spa=False, ok=True, list_url=BASE):
    return {"ok": ok, "spa": spa, "list_url": list_url, "titles": titles or [],
            "via": "homepage", "reason": "", "checked_at": "2026-11-01"}


OLD = ["关于2026年秋季学期开学工作的通知", "南京市某某小学招生简章公示",
       "关于组织教师参加市级培训的通知", "第十周工作安排与值班表"]


class TestCheckSource(unittest.TestCase):
    def test_spa_is_skipped_without_request(self):
        f = FakeFetcher(resp(""))
        state, _ = run.check_source(f, src(), rec(spa=True))
        self.assertEqual(state, "spa")
        self.assertEqual(f.calls, [])

    def test_top_insert_detected(self):
        new = ["关于2026年秋季运动会报名的通知"] + OLD
        state, fresh = run.check_source(FakeFetcher(resp(page(*new))), src(), rec(OLD))
        self.assertEqual(state, "new")
        self.assertEqual(len(fresh), 1)
        self.assertIn("运动会", fresh[0][0])

    def test_order_jitter_is_not_new(self):
        # 首页轮播会让条目换位，但顶部第一条仍是见过的 → 不算新增
        shuffled = [OLD[0], OLD[2], OLD[1], OLD[3]]
        state, _ = run.check_source(FakeFetcher(resp(page(*shuffled))), src(), rec(OLD))
        self.assertEqual(state, "same")

    def test_no_change(self):
        state, _ = run.check_source(FakeFetcher(resp(page(*OLD))), src(), rec(OLD))
        self.assertEqual(state, "same")

    def test_first_time_has_no_baseline(self):
        # 首次发现只建立基线，不能把整页都报成新增
        state, _ = run.check_source(FakeFetcher(resp(page(*OLD))), src(), rec([]))
        self.assertEqual(state, "hash")

    def test_fresh_capped(self):
        many = [f"第{i}条全新公告标题内容" for i in range(20)]
        state, fresh = run.check_source(FakeFetcher(resp(page(*many))), src(), rec(OLD))
        self.assertEqual(state, "new")
        self.assertLessEqual(len(fresh), discover.KEEP_ITEMS)

    def test_uses_list_url_when_present(self):
        f = FakeFetcher(resp(page(*OLD)))
        run.check_source(f, src(), rec(OLD, list_url="http://school.example.cn/list/"))
        self.assertEqual(f.calls[0], "http://school.example.cn/list/")

    def test_falls_back_to_entry_without_list(self):
        f = FakeFetcher(resp(page(*OLD)))
        run.check_source(f, src(), {"ok": False, "spa": False, "list_url": ""})
        self.assertEqual(f.calls[0], BASE)

    def test_failure_reported(self):
        f = FakeFetcher(fetch.Response(url=BASE, status=404, error="404 Not Found"))
        state, res = run.check_source(f, src(), rec(OLD))
        self.assertEqual(state, "fail")
        self.assertEqual(res.status, 404)

    def test_empty_page_falls_back_to_hash(self):
        f = FakeFetcher(resp("<html><body><p>无链接页面</p></body></html>"))
        state, _ = run.check_source(f, src(), rec(OLD))
        self.assertEqual(state, "hash")


class TestSelect(unittest.TestCase):
    ITEMS = [
        {"id": "school:小学-A区-甲小学", "name": "甲小学", "kind": "school",
         "tier": "T1", "status": "verified", "entry": "http://a.cn/"},
        {"id": "school:初中-B区-乙中学", "name": "乙中学", "kind": "school",
         "tier": "T1", "status": "verified", "entry": "http://b.cn/"},
        {"id": "bureau:city-edu", "name": "南京市教育局", "kind": "bureau",
         "tier": "T0", "status": "verified", "entry": "https://e.cn/"},
        {"id": "bureau:zkb", "name": "招考院", "kind": "bureau",
         "tier": "T0", "status": "unverified", "entry": ""},
    ]

    def test_excludes_unverified(self):
        self.assertEqual(len(run.select(self.ITEMS)), 3)

    def test_by_kind(self):
        self.assertEqual([r["name"] for r in run.select(self.ITEMS, kind="bureau")],
                         ["南京市教育局"])

    def test_by_tier(self):
        self.assertEqual(len(run.select(self.ITEMS, tier="T1")), 2)

    def test_only_matches_name(self):
        self.assertEqual(len(run.select(self.ITEMS, only="乙中学")), 1)

    def test_limit(self):
        self.assertEqual(len(run.select(self.ITEMS, limit=2)), 2)


class TestWindow(unittest.TestCase):
    def test_window_months(self):
        for mon in (5, 7, 10, 11):
            self.assertTrue(run.in_window(type("T", (), {"tm_mon": mon})()), mon)
        for mon in (1, 3, 8, 9, 12):
            self.assertFalse(run.in_window(type("T", (), {"tm_mon": mon})()), mon)


class TestPlainText(unittest.TestCase):
    def test_strips_script_and_style(self):
        html = ("<html><head><style>body{margin:0}</style></head>"
                "<body><script>var a=1;</script><p>正文内容</p></body></html>")
        self.assertEqual(run.plain_text(html), "正文内容")


class TestFailureVerdict(unittest.TestCase):
    """失败率判定：连接层失败与站点异常必须分开算。

    这一组规则是踩着线上故障定出来的——2026-11-02 首次定时巡检失败，
    本地同样的代码跑出 4% 失败率，CI 上却判成「异常」。原因是 runner 在
    美国机房，189 所国内学校站大量连不通（status=0），与「站点返回 404」
    被混在一起算，直接顶破 20% 阈值。
    """

    class Res:
        def __init__(self, status): self.status = status

    def _fails(self, net=0, http=0):
        rows = [("s", self.Res(0)) for _ in range(net)]
        rows += [("s", self.Res(502)) for _ in range(http)]
        return rows

    def test_split_by_status(self):
        net, http = run.classify_failures(self._fails(net=3, http=2))
        self.assertEqual(len(net), 3)
        self.assertEqual(len(http), 2)

    def test_all_connection_failures_not_an_error(self):
        """连不上 ≠ 站点挂了：不能因为 runner 网络差就判失败。"""
        net, http = run.classify_failures(self._fails(net=120, http=0))
        rc, msg = run.verdict(net, http, 200)
        self.assertEqual(rc, 0)
        self.assertIn("运行环境的网络", msg)

    def test_moderate_connection_failures_silent(self):
        """四成连不上只是网络抖动，还不到「环境不可用」的程度，不该刷提示。"""
        net, http = run.classify_failures(self._fails(net=80, http=0))
        rc, msg = run.verdict(net, http, 200)
        self.assertEqual((rc, msg), (0, ""))

    def test_http_failures_still_alarm(self):
        """站点应答了但不对，这条不能放过——否则真出事了也看不出来。"""
        net, http = run.classify_failures(self._fails(net=60, http=50))
        rc, msg = run.verdict(net, http, 200)
        self.assertEqual(rc, 2)
        self.assertIn("站点异常率", msg)

    def test_healthy_round_silent(self):
        net, http = run.classify_failures(self._fails(net=4, http=4))
        rc, msg = run.verdict(net, http, 200)
        self.assertEqual((rc, msg), (0, ""))

    def test_zero_total_does_not_divide_by_zero(self):
        rc, msg = run.verdict([], [], 0)
        self.assertEqual((rc, msg), (0, ""))


if __name__ == "__main__":
    unittest.main()
