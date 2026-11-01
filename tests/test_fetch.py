# -*- coding: utf-8 -*-
"""采集层抓取逻辑的单元测试。

这一层出错的表现非常隐蔽：重试策略错了，结果是「跑得很慢但看起来正常」；
304 处理错了，结果是「每周重新下载 188 个站点」；熔断错了，结果是
「对着已经停机的区平台循环请求」。所以每条规则都要有用例钉住。

全部用假 opener 与假时钟，不联网、不 sleep。

一个容易混淆的口径：熔断统计的是「失败的 get 次数」，不是内部的 attempt 次数。
一次 get 内部最多重试 3 个 attempt，但仍只算一次失败——否则一次网络抖动
就会把整个域名熔断掉。
"""
import pathlib
import sys
import unittest
import unittest.mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ingest import fetch  # noqa: E402

URL = "https://example.edu.cn/"
DOM = "example.edu.cn"


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, d):
        self.t += d


class Opener:
    """按预设序列返回响应；元素为 (status, headers, body) 或要抛出的异常。"""

    def __init__(self, *seq):
        self.seq = list(seq)
        self.headers_seen = []
        self.calls = 0

    def __call__(self, req, timeout):
        self.calls += 1
        self.headers_seen.append({k.lower(): v for k, v in req.headers.items()})
        if not self.seq:
            raise fetch.FetchError(status=500, reason="序列用尽", retriable=True)
        item = self.seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def fails(n, status=500):
    return [(status, {}, b"") for _ in range(n)]


def make(opener, clock=None, slept=None, **kw):
    slept = slept if slept is not None else []
    clock = clock or Clock()
    f = fetch.Fetcher(persist=False, opener=opener, sleep=slept.append,
                      now=clock, min_interval=0, **kw)
    f.slept = slept
    f.clock = clock
    return f


class TestConditional(unittest.TestCase):
    def test_200_records_etag_and_hash(self):
        op = Opener((200, {"ETag": '"abc"', "Last-Modified": "Wed, 01 Oct 2026 00:00:00 GMT"},
                     "正文".encode()))
        f = make(op)
        r = f.get(URL)
        self.assertTrue(r.ok)
        self.assertEqual(r.status, 200)
        self.assertEqual(r.text, "正文")
        self.assertEqual(len(r.content_hash), 16)
        self.assertEqual(f.cache[URL]["etag"], '"abc"')
        self.assertEqual(f.cache[URL]["last_modified"], "Wed, 01 Oct 2026 00:00:00 GMT")

    def test_second_request_sends_conditional_headers(self):
        op = Opener((200, {"ETag": '"abc"'}, b"v1"), (304, {}, b""))
        f = make(op)
        f.get(URL)
        r = f.get(URL)
        self.assertTrue(r.not_modified)
        self.assertEqual(r.body, b"")
        self.assertEqual(op.headers_seen[1].get("if-none-match"), '"abc"')
        self.assertEqual(f.stats["not_modified"], 1)

    def test_304_keeps_previous_hash(self):
        op = Opener((200, {"ETag": '"abc"'}, b"v1"), (304, {}, b""))
        f = make(op)
        first = f.get(URL).content_hash
        self.assertEqual(f.get(URL).content_hash, first)

    def test_force_ignores_cache_headers(self):
        op = Opener((200, {"ETag": '"abc"'}, b"v1"), (200, {}, b"v2"))
        f = make(op)
        f.get(URL)
        f.get(URL, force=True)
        self.assertNotIn("if-none-match", op.headers_seen[1])


class TestRetry(unittest.TestCase):
    def test_500_retries_three_times(self):
        op = Opener(*fails(3))
        f = make(op)
        r = f.get(URL)
        self.assertFalse(r.ok)
        self.assertEqual(op.calls, 3)
        self.assertEqual(r.attempts, 3)

    def test_backoff_grows(self):
        op = Opener(*fails(3))
        f = make(op)
        f.get(URL)
        self.assertEqual(len(f.slept), 2)          # 最后一次失败后不再等待
        self.assertLess(f.slept[0], f.slept[1])
        self.assertGreaterEqual(f.slept[0], 1 * 0.8)

    def test_404_is_not_retried(self):
        op = Opener((404, {}, b""))
        f = make(op)
        r = f.get(URL)
        self.assertFalse(r.ok)
        self.assertEqual(op.calls, 1)
        self.assertEqual(r.status, 404)

    def test_403_is_blocked_not_dead(self):
        # 防爬不能判死：保留记录、不重试、也不计入熔断
        op = Opener((403, {}, b""))
        f = make(op)
        r = f.get(URL)
        self.assertEqual(op.calls, 1)
        self.assertEqual(r.status, 403)
        self.assertEqual(f.circuit, {})

    def test_429_honors_retry_after(self):
        err = fetch.FetchError(status=429, reason="太多请求", retriable=True, retry_after=7.0)
        op = Opener(err, (200, {}, b"ok"))
        f = make(op)
        r = f.get(URL)
        self.assertTrue(r.ok)
        self.assertEqual(f.slept, [7.0])

    def test_timeout_is_retriable(self):
        op = Opener(TimeoutError("timed out"), (200, {}, b"ok"))
        f = make(op)
        self.assertTrue(f.get(URL).ok)
        self.assertEqual(op.calls, 2)

    def test_user_agent_declares_project(self):
        op = Opener((200, {}, b"ok"))
        make(op).get(URL)
        self.assertIn("njschool-archive", op.headers_seen[0]["user-agent"])


class TestCircuit(unittest.TestCase):
    def test_one_failed_get_counts_once(self):
        # 一次 get 内部重试 3 次，但只累加 1 次失败
        f = make(Opener(*fails(3)))
        f.get(URL)
        self.assertEqual(f.circuit[DOM]["failures"], 1)

    def test_trips_after_three_failed_gets(self):
        clock = Clock()
        f = make(Opener(*fails(9)), clock=clock)
        for _ in range(3):
            f.get(URL)
        self.assertEqual(f.circuit[DOM]["failures"], 3)
        self.assertGreater(f.circuit[DOM]["until"], clock.t)

    def test_skips_while_open(self):
        clock = Clock()
        f = make(Opener(), clock=clock)
        f.circuit[DOM] = {"failures": 3, "until": clock.t + 60}
        r = f.get(URL)
        self.assertEqual(r.error, "circuit_open")
        self.assertEqual(f.stats["skipped_circuit"], 1)
        self.assertEqual(f.stats["requests"], 0)

    def test_success_heals_circuit(self):
        f = make(Opener((200, {}, b"ok")))
        f.circuit[DOM] = {"failures": 5, "until": 0}
        self.assertTrue(f.get(URL).ok)
        self.assertNotIn(DOM, f.circuit)

    def test_circuit_expires(self):
        clock = Clock()
        f = make(Opener((200, {}, b"ok")), clock=clock)
        f.circuit[DOM] = {"failures": 3, "until": clock.t + 60}
        clock.advance(61)
        self.assertTrue(f.get(URL).ok)


class TestThrottle(unittest.TestCase):
    def test_same_domain_waits_between_requests(self):
        slept = []
        op = Opener((200, {}, b"a"), (200, {}, b"b"))
        f = fetch.Fetcher(persist=False, opener=op, sleep=slept.append,
                          now=Clock(), min_interval=1.0)
        f.get("https://a.example.cn/1")
        f.get("https://a.example.cn/2")
        self.assertTrue(any(s > 0.5 for s in slept))

    def test_different_domain_no_wait(self):
        slept = []
        op = Opener((200, {}, b"a"), (200, {}, b"b"))
        f = fetch.Fetcher(persist=False, opener=op, sleep=slept.append,
                          now=Clock(), min_interval=1.0)
        f.get("https://a.example.cn/")
        f.get("https://b.example.cn/")
        self.assertEqual(slept, [])


class TestJsRedirect(unittest.TestCase):
    """政府站的 JS 跳转壳（111 字节，只有一句 location 赋值）。

    不跟随的后果很具体：市教育局「招生考试」「考试信息」两个主栏目
    都是这种壳，会被当成「空壳站」直接跳过，等于放弃了最权威的源。
    """

    SHELL = ('<SCRIPT LANGUAGE="JavaScript"> \tvar htm = ""; '
             '\thtm = "./gzzs/";         document.location.href = htm; </SCRIPT>')

    def test_target_extracted_from_variable(self):
        # 变量中转写法：var htm = ""; htm = "./gzzs/"; location.href = htm
        self.assertEqual(fetch._js_target(self.SHELL), "./gzzs/")

    def test_target_extracted_direct(self):
        self.assertEqual(fetch._js_target('<script>location.href="/kb/xwgg/";</script>'),
                         "/kb/xwgg/")

    def test_not_a_shell(self):
        self.assertEqual(fetch._js_target("<html><body><p>正文没有跳转</p></body></html>"), "")

    def test_first_literal_not_mispaired(self):
        # 曾经的 bug：["']([^"']+)["'] 会跨段配对，捕获到 `; htm = `
        self.assertNotIn("htm", fetch._js_target(self.SHELL))

    def test_resolve_treats_extensionless_as_dir(self):
        self.assertEqual(fetch._resolve("https://e.cn/zb", "./gzzs/"),
                         "https://e.cn/zb/gzzs/")

    def test_resolve_keeps_file_semantics(self):
        self.assertEqual(fetch._resolve("https://e.cn/a/b.html", "./c/"),
                         "https://e.cn/a/c/")

    def test_follows_shell(self):
        op = Opener((200, {}, self.SHELL.encode()),
                    (200, {}, "<html><body>真实栏目页</body></html>".encode()))
        f = make(op)
        r = f.get("https://e.cn/zb")
        self.assertEqual(r.hops, 1)
        self.assertEqual(r.url, "https://e.cn/zb/gzzs/")
        self.assertIn("真实栏目页", r.text)

    def test_stops_after_max_hops(self):
        # 互相跳转不能无限跟
        shell = '<script>location.href="./next/";</script>'.encode()
        op = Opener((200, {}, shell), (200, {}, shell), (200, {}, shell))
        r = make(op).get("https://e.cn/a")
        self.assertLessEqual(r.hops, fetch.MAX_JS_HOPS)

    def test_large_body_not_treated_as_shell(self):
        big = ("<script>location.href='./x/';</script>" + "内容" * 2000).encode()
        self.assertGreater(len(big), fetch.JS_SHELL_MAX)
        op = Opener((200, {}, big), (200, {}, b"<html>ok</html>"))
        r = make(op).get("https://e.cn/a")
        self.assertEqual(r.hops, 0)


class TestDecode(unittest.TestCase):
    def test_gbk_fallback(self):
        # 南京多个区级平台是 GBK 老站，只试 utf-8 会整页乱码
        self.assertEqual(fetch.decode("施教区范围".encode("gb18030")), "施教区范围")

    def test_html_charset_wins(self):
        raw = '<meta charset="gb2312">'.encode() + "中文".encode("gb18030")
        self.assertIn("中文", fetch.decode(raw))

    def test_empty(self):
        self.assertEqual(fetch.decode(b""), "")


class TestDefaultOpen(unittest.TestCase):
    """真实 HTTP 语义的胶水层。

    这层曾被真实站点打脸过一次：urllib 把 304 归进 HTTPError，
    而 304 是条件请求的**正常**结果。照搬异常语义后，首轮抓取全部成功、
    第二轮只要有 ETag 就整批判失败——构建期看不出来，只有真跑才会暴露。
    """

    def test_304_is_not_an_error(self):
        import urllib.error
        import urllib.request
        err = urllib.error.HTTPError(URL, 304, "Not Modified", {"ETag": '"x"'}, None)
        with unittest.mock.patch("urllib.request.urlopen", side_effect=err):
            status, headers, body = fetch._default_open(urllib.request.Request(URL), 5)
        self.assertEqual(status, 304)
        self.assertEqual(body, b"")
        self.assertEqual(headers.get("ETag"), '"x"')

    def test_500_becomes_fetcherror(self):
        import urllib.error
        import urllib.request
        err = urllib.error.HTTPError(URL, 500, "Server Error", {}, None)
        with unittest.mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(fetch.FetchError) as cm:
                fetch._default_open(urllib.request.Request(URL), 5)
        self.assertEqual(cm.exception.status, 500)
        self.assertTrue(cm.exception.retriable)

    def test_redirect_loop_is_permanent(self):
        # urllib 只在重定向成环时才把 302 抛出来，属地址配置错误：
        # 不该重试，更不该把整个域名熔断掉
        self.assertIn(302, fetch.PERMANENT)
        r = make(Opener((302, {}, b""))).get(URL)
        self.assertFalse(r.ok)
        self.assertEqual(r.attempts, 1)


if __name__ == "__main__":
    unittest.main()
