# -*- coding: utf-8 -*-
"""抓取层：条件请求、重试分级、限速、熔断。

为什么值得单独立一层：直接 urlopen 的代码会在四个地方同时出事——
  1. 每次都全量下载：188 个站点每周拉一遍，多数是 304 却仍在传字节
  2. 一律重试：对已经 404 的地址重试三次，等于把对方站点当压力测试
  3. 一律不重试：区教育局站点存在间歇 502，第一次失败就判死会漏掉真更新
  4. 不熔断：雨花台 *.yhjyxx.cn 是整片停机（8 所），每轮都去打，既是浪费也是骚扰

判定规则不是凭空写的，来自 verify_websites.py 里已经踩过的坑：
  · 「Tunnel connection failed」是本地出口代理故障，不是站点故障
  · 401/403 多为防爬，不重试也不判死
  · 404/410 才算地址真的没了

可测试性是刻意保留的：opener / sleep / now 三个依赖都可注入，
tests/test_fetch.py 用假 opener 跑完重试、退避、熔断、304 全部分支，不联网。
"""
import hashlib
import json
import os
import random
import re
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from pipeline import config

CACHE_FILE = os.path.join(config.ROOT, "data", "cache", "http.json")
CIRCUIT_FILE = os.path.join(config.ROOT, "data", "cache", "circuit.json")
SNAP_DIR = os.path.join(config.ROOT, "data", "cache", "body")

UA = ("njschool-archive/1.0 (+https://njschool.top/about) "
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 可重试的状态码：瞬时故障。429 会优先服从服务端给的 Retry-After。
RETRIABLE = {408, 425, 429, 500, 502, 503, 504}
# 永久失败：地址没了，或地址本身配错。重试没有意义，也不该计入熔断
# （3xx 能到这里说明 urllib 已跟随过且判定为循环，属配置问题，不是站点故障）。
PERMANENT = {404, 410, 301, 302, 303, 307, 308}
# 防爬：既不算死也不算活，保留记录、不重试
BLOCKED = {401, 403}

MAX_BYTES = 300_000          # 单页上限，与 verify_websites.py 一致
BACKOFF = (1, 4, 16)         # 指数退避基数（秒）
JITTER = 0.2                 # ±20% 抖动，避免同时重试打同一批站
CIRCUIT_THRESHOLD = 3        # 单域连续失败次数
CIRCUIT_SECONDS = 6 * 3600   # 熔断时长

# 政府站常见的「JS 跳转壳」：整页只有 111 字节，用
#   <SCRIPT>htm = "./gzzs/"; document.location.href = htm;</SCRIPT>
# 把浏览器送去真正的栏目页。不跟随的话，市教育局的「招生考试」「考试信息」
# 两个主栏目会被判成空壳——实测 /zb 与 /kb 都是这种壳。
JS_REDIRECT = re.compile(
    r"""(?:document\.)?location(?:\.href)?\s*=\s*["']([^"']+)["']""", re.I)
JS_SHELL_MAX = 2048          # 超过这个体积就不当跳转壳看，避免误读正文里的脚本
MAX_JS_HOPS = 2


@dataclass
class Response:
    url: str
    status: int = 0
    body: bytes = b""
    headers: dict = field(default_factory=dict)
    not_modified: bool = False       # 304：内容未变，用缓存里的 content_hash
    content_hash: str = ""
    from_snapshot: bool = False      # body 来自本地快照（304 回填），不是本次下载
    hops: int = 0                    # 跟随 JS 跳转的次数
    error: str = ""                  # 空串表示成功
    attempts: int = 0

    @property
    def ok(self):
        return not self.error

    @property
    def text(self):
        return decode(self.body)


@dataclass
class FetchError(Exception):
    status: int = 0
    reason: str = ""
    retriable: bool = False
    retry_after: float = 0

    def __str__(self):
        return f"{self.status or '-'} {self.reason}"


def decode(raw):
    """按 meta charset 解码，失败回退 utf-8 → gb18030。

    南京多个区级平台是 GBK 老站，只试 utf-8 会把整页变成乱码，
    再往后所有抽取都会失败而看不出原因。
    """
    import re
    if not raw:
        return ""
    m = re.search(rb'charset=["\']?([\w-]+)', raw[:3000], re.I)
    enc = m.group(1).decode("ascii", "ignore") if m else "utf-8"
    for e in (enc, "utf-8", "gb18030"):
        try:
            return raw.decode(e)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "ignore")


def domain_of(url):
    try:
        return urlsplit(url).netloc.lower()
    except ValueError:
        return ""


def digest(body):
    return hashlib.sha256(body).hexdigest()[:16]


def _retry_after(headers):
    """读 Retry-After（秒）。只接受纯数字，HTTP-date 形式忽略，用默认退避。"""
    try:
        v = headers.get("Retry-After") or headers.get("retry-after") or ""
        return max(0.0, float(v))
    except (TypeError, ValueError):
        return 0.0


def _default_open(req, timeout):
    ctx = ssl.create_default_context()
    # 教育系统站点证书配置普遍不规范，证书错误不应阻断公开信息采集。
    # 这里只关闭校验，不改变「只抓公开页面」的边界。
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, dict(r.headers), r.read(MAX_BYTES)
    except urllib.error.HTTPError as e:
        # 304 是条件请求的**正常**结果，不是错误。urllib 把它归进 HTTPError，
        # 若照搬异常语义，「内容未变」会被判成「抓取失败」——
        # 实测表现为：首轮全部成功，第二轮只要有 ETag 就整批失败。
        if e.code == 304:
            return 304, dict(e.headers), b""
        # 其余 4xx/5xx 转成带状态码的 FetchError，让「重试 / 不重试 / 防爬」
        # 的分级统一在 get() 里判断——否则会出现两套判定：异常路径一套、
        # 状态码路径另一套，两条路各错一次。
        raise FetchError(status=e.code, reason=str(e.reason or ""),
                         retriable=e.code in RETRIABLE,
                         retry_after=_retry_after(e.headers)) from None


def _json_load(path, default):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return default


def _json_save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)


def snapshot_path(content_hash):
    """快照路径：内容寻址，同 hash 必然同内容，所以天然去重。"""
    return os.path.join(SNAP_DIR, content_hash[:2], content_hash + ".gz")


def save_snapshot(content_hash, body):
    """把正文快照存盘（gzip）。已存在则跳过——同样的 hash 内容是等价的。"""
    path = snapshot_path(content_hash)
    if os.path.isfile(path):
        return path
    import gzip
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wb") as f:
        f.write(body)
    return path


def load_snapshot(content_hash):
    """按 hash 读回正文；没有快照时返回 b""。

    为什么需要：304 表示「内容没变」，但下次要抽取字段时必须拿到正文。
    只存哈希不存正文，就只能在 304 之后干瞪眼——实测首次全量抓完后，
    第二次跑发现 `discover` 有 7/8 个源因 304 拿不到 HTML 而直接失败。
    """
    path = snapshot_path(content_hash)
    if not content_hash or not os.path.isfile(path):
        return b""
    import gzip
    try:
        with gzip.open(path, "rb") as f:
            return f.read()
    except OSError:
        return b""


def prune_snapshots(keep_days=30, now=None):
    """清理过旧快照，返回删除个数。

    快照按内容寻址会随内容变化累积。学校站一年更新几十次，188 个源
    一个月也就几 MB，但不管它迟早会涨。按天清理留出回溯窗口即可。
    """
    if not os.path.isdir(SNAP_DIR):
        return 0
    now = now or time.time()
    cutoff = now - keep_days * 86400
    n = 0
    for root, _dirs, files in os.walk(SNAP_DIR):
        for name in files:
            path = os.path.join(root, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    n += 1
            except OSError:
                continue
    return n


# 成对的字符串字面量：反向引用保证首尾是同一个引号。
# 用 ["']([^"']+)["'] 这种写法会在 `var htm = ""; htm = "./x/"` 上跨段配对，
# 把 `; htm = ` 当成一个路径（实测如此）。
RE_JS_STR = re.compile(r'(["\'])((?:(?!\1).){0,200})\1')


def _js_target(html):
    """从 JS 跳转壳里取出目标路径；不是跳转壳则返回空串。

    政府站的写法是变量中转，不能只匹配 location.href="..."：

        <SCRIPT>var htm = ""; htm = "./gzzs/"; document.location.href = htm;</SCRIPT>

    所以先试直给字符串，再退化为「在小脚本里找一个像路径的字面量」。
    只在 body 很小且含 location 时才会走到这里，不会误读正文脚本。
    """
    if "location" not in (html or "").lower():
        return ""
    m = JS_REDIRECT.search(html)
    if m:
        return m.group(1).strip()
    for lit in RE_JS_STR.finditer(html):
        s = lit.group(2).strip()
        if not s:
            continue
        if s.startswith(("./", "/", "../")) or s.endswith((".html", ".htm")):
            return s
    return ""


def _resolve(base_url, target):
    """把跳转目标解析成绝对地址。

    关键细节：`https://…/zb` 这种「无扩展名但也无尾斜杠」的地址，
    标准 urljoin 会把它当成文件、把最后一段替换掉，得到 `/gzzs/`（实测 404）；
    服务端与浏览器的实际意图是 `/zb/gzzs/`。所以这种情况按「目录」补一个斜杠。
    """
    path = urlsplit(base_url).path
    last = path.rsplit("/", 1)[-1]
    base = base_url if (base_url.endswith("/") or "." in last) else base_url + "/"
    return urljoin(base, target)


class Fetcher:
    """按源抓取，带条件请求、分级重试、单域限速与熔断。

    opener(req, timeout) -> (status, headers, body)，异常抛 FetchError。
    sleep(seconds)、now() 可注入，测试里用假实现跑完所有分支而不等待。
    """

    def __init__(self, cache_path=CACHE_FILE, circuit_path=CIRCUIT_FILE,
                 timeout=15, max_retries=3, min_interval=1.0,
                 opener=None, sleep=None, now=None, persist=True):
        self.cache_path = cache_path
        self.circuit_path = circuit_path
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.min_interval = min_interval
        self._open = opener or _default_open
        self._sleep = sleep or time.sleep
        self._now = now or time.time
        self._persist = persist
        # persist=False 表示纯内存模式：不读也不写磁盘。
        # 只挡写不挡读会留下一个隐蔽的坑——测试会读到上一次真实抓取留下的
        # 熔断与缓存状态，用例之间互相污染，失败原因看上去毫不相干。
        self.cache = _json_load(cache_path, {}) if persist else {}
        self.circuit = _json_load(circuit_path, {}) if persist else {}
        self._last_hit = {}
        self.stats = {"requests": 0, "not_modified": 0, "failed": 0, "skipped_circuit": 0}

    # ---- 熔断 ----
    def circuit_open(self, url):
        rec = self.circuit.get(domain_of(url)) or {}
        return self._now() < rec.get("until", 0)

    def _trip(self, url):
        dom = domain_of(url)
        rec = self.circuit.setdefault(dom, {"failures": 0, "until": 0})
        rec["failures"] = rec.get("failures", 0) + 1
        if rec["failures"] >= CIRCUIT_THRESHOLD:
            rec["until"] = self._now() + CIRCUIT_SECONDS
            rec["tripped_at"] = int(self._now())
        if self._persist:
            _json_save(self.circuit_path, self.circuit)

    def _heal(self, url):
        dom = domain_of(url)
        if self.circuit.pop(dom, None) and self._persist:
            _json_save(self.circuit_path, self.circuit)

    # ---- 限速 ----
    def _throttle(self, url):
        if not self.min_interval:
            return
        dom = domain_of(url)
        last = self._last_hit.get(dom)
        if last is not None:
            wait = self.min_interval - (self._now() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_hit[dom] = self._now()

    # ---- 主流程 ----
    def _follow_js(self, url, body, hops):
        """若是 JS 跳转壳则跟到目标页，返回 Response；不是则返回 None。"""
        if hops >= MAX_JS_HOPS or len(body) >= JS_SHELL_MAX:
            return None
        target = _js_target(decode(body))
        if not target:
            return None
        nxt = _resolve(url, target)
        if nxt.rstrip("/") == url.rstrip("/"):
            return None
        res = self.get(nxt, force=True, _hops=hops + 1)
        res.hops = hops + 1
        return res

    def get(self, url, force=False, _hops=0):
        """抓取单个地址。304 时返回 not_modified=True，body 由快照回填。"""
        if self.circuit_open(url):
            self.stats["skipped_circuit"] += 1
            return Response(url=url, error="circuit_open",
                            content_hash=(self.cache.get(url) or {}).get("content_hash", ""))

        cached = self.cache.get(url) or {}
        headers = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
        if cached.get("etag") and not force:
            headers["If-None-Match"] = cached["etag"]
        if cached.get("last_modified") and not force:
            headers["If-Modified-Since"] = cached["last_modified"]

        last = FetchError(reason="未发起请求")
        tries = 0
        for attempt in range(1, self.max_retries + 1):
            tries = attempt
            self._throttle(url)
            self.stats["requests"] += 1
            req = urllib.request.Request(url, headers=headers)
            try:
                status, rheaders, body = self._open(req, self.timeout)
            except FetchError as exc:
                last = exc
                if (exc.status in PERMANENT or exc.status in BLOCKED
                        or not exc.retriable or attempt == self.max_retries):
                    break
                self._backoff(attempt, exc.retry_after)
                continue
            except Exception as exc:                      # 网络类异常统一按可重试处理
                last = FetchError(reason=f"{type(exc).__name__}: {str(exc)[:80]}",
                                  retriable=True)
                self._backoff(attempt)
                continue

            if status == 304:
                self.stats["not_modified"] += 1
                self._heal(url)
                h = cached.get("content_hash", "")
                # 304 也要能拿到正文：抽取、发现都依赖 HTML。
                # 拿不到就变成「内容没变所以什么都做不了」，整条链路空转。
                body = load_snapshot(h) if self._persist else b""
                if not body and self._persist:
                    # 快照缺失（首次升级到快照机制、或已被清理）时，这次 304
                    # 没有正文可用，等价于「什么都没拿到」。强制重取一次补上：
                    # force 不再带条件头，不会再次 304，因此不会递归。
                    return self.get(url, force=True)
                # 304 拿到的也可能是跳转壳（政府栏目页就是这样），同样要跟随，
                # 否则每轮巡检都只能看到那 111 字节的 location 赋值。
                followed = self._follow_js(url, body, _hops)
                if followed is not None:
                    return followed
                return Response(url=url, status=304, body=body, not_modified=True,
                                content_hash=h, from_snapshot=bool(body),
                                attempts=attempt)

            # 3xx 也要算失败：正常情况下 urllib 会自动跟随重定向，
            # 能走到这里的 302/301 只可能是「跟随成环」——那是地址配错，
            # 不是一篇可用的页面。若按 status>=400 一刀切，它会当成成功落缓存。
            if status >= 400 or status in PERMANENT:
                # 状态码路径也要走分级：注入的 opener 可能直接返回 500，
                # 而真实 urllib 是抛 HTTPError。两条路径必须判得一样。
                last = FetchError(status=status, reason="HTTP %d" % status,
                                  retriable=status in RETRIABLE,
                                  retry_after=_retry_after(rheaders))
                if (status in PERMANENT or status in BLOCKED
                        or status not in RETRIABLE or attempt == self.max_retries):
                    break
                self._backoff(attempt, last.retry_after)
                continue

            self._heal(url)
            h = digest(body)
            if self._persist:
                save_snapshot(h, body)
            self._remember(url, rheaders, h, len(body))

            followed = self._follow_js(url, body, _hops)
            if followed is not None:
                return followed

            return Response(url=url, status=status, body=body,
                            headers={k.lower(): v for k, v in rheaders.items()},
                            content_hash=h, attempts=attempt)

        self.stats["failed"] += 1
        if last.status not in PERMANENT and last.status not in BLOCKED:
            self._trip(url)
        # 报真实尝试次数：写死 max_retries 会让「只试了 1 次就 404」在日志里
        # 显示成「重试 3 次」，排查时方向直接跑偏。
        return Response(url=url, status=last.status, error=str(last), attempts=tries)

    def _backoff(self, attempt, retry_after=0):
        if retry_after:
            self._sleep(retry_after)
            return
        base = BACKOFF[min(attempt - 1, len(BACKOFF) - 1)]
        self._sleep(base * (1 + random.uniform(-JITTER, JITTER)))

    def _remember(self, url, headers, content_hash, body_len=0):
        rec = {
            "etag": (headers.get("ETag") or headers.get("etag") or ""),
            "last_modified": (headers.get("Last-Modified") or headers.get("last-modified") or ""),
            "content_hash": content_hash,
            # 字节数用来识别「动态页面」：内容变了但长度一字节不差，
            # 通常是页面内嵌了时间戳/随机令牌/访问计数，不是真的更新。
            # 实测南师附小、东山小学连续两轮 87935B / 253588B 完全不变而 hash 每次都变。
            "body_len": body_len,
            "fetched_at": int(self._now()),
        }
        self.cache[url] = rec
        if self._persist:
            _json_save(self.cache_path, self.cache)

    def flush(self):
        """把内存里的缓存与熔断状态落盘（persist=False 时由调用方决定时机）。"""
        if self._persist:
            _json_save(self.cache_path, self.cache)
            _json_save(self.circuit_path, self.circuit)
