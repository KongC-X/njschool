# -*- coding: utf-8 -*-
"""产物校验：构建完成后对生成结果做结构性检查。

这一层是「缺陷出不了门」的保障。此前 sitemap 带 207 处占位符能一路到生产，
正是因为缺少这类检查。检查项分两级：error 阻断（构建失败），warning 仅提示。
"""
import glob
import os
import re
import collections
import json
import shutil
import subprocess

from urllib.parse import unquote, urlparse

from . import config, load
from .schema import Report

MIN_H2_FOR_TOC = 3
PAGE_SIZE_WARN_KB = 120
# 索引页天生比档案页大：它的全部价值就是把 545 条一次列全，
# 用同一把尺子量它没有意义，给单独的上限。
PAGE_SIZE_EXEMPT_KB = {"all.html": 200}

# 静态资源体积预算（KB）：超出说明在往同一个文件里堆样式/脚本，应拆分而非继续增长
# pages.css 由 24 → 32：这一轮新增了详情页的四个组件（关键数字芯片、施教区逐条列表、
# 施教区自查框、页尾「接着看」），合计约 5.5KB。下次再要加详情页样式时，
# 应先把 detail-head 及以下整块拆成 assets/detail.css，而不是继续抬这个数字。
ASSET_BUDGET_KB = {"tokens.css": 8, "site.css": 22, "components.css": 14, "pages.css": 20, "detail.css": 10, "compare.css": 14, "all.css": 4, "talent.css": 8,
                   "timeline.css": 10, "score.css": 10,
                   "score.js": 12,
                   "responsive.css": 12, "app.js": 18, "schools-data.js": 200,
                   "schools-compare.js": 140, "streets-data.js": 60,
                   "search-core.js": 16, "schools.js": 20,
                   "compare-core.js": 16, "compare.js": 24}
# 令牌纪律与移动端溢出守卫要扫的样式表。timeline.css 只在时间轴页加载，
# 但它照样是「组件样式」，同样不许写死色值。
STYLE_SHEETS = ("site.css", "pages.css", "detail.css", "compare.css", "responsive.css",
                "timeline.css", "score.css")
# 数据型 JS：内容是一行 JSON，没有「函数块」可言，
# 对它跑重复代码块检测既无意义又慢，故排除。
DATA_ASSETS = ("schools-data.js", "schools-compare.js", "streets-data.js")
RE_HEX = re.compile(r"#[0-9a-fA-F]{3,6}\b")
RE_TABLE_MINW = re.compile(r"\.article table\{[^}]*min-width:\s*(\d{3})px")

RE_H1 = re.compile(r"<h1[\s>]")
RE_H2 = re.compile(r"<h2[\s>]")
RE_STYLE = re.compile(r"<style[\s>]")
RE_LOCAL = re.compile(r'(?:href|src)="([^"]+)"')
RE_PLACEHOLDER = re.compile(r"\{BASE\}")
RE_DOUBLE_ENC = re.compile(r"%25[0-9A-Fa-f]{2}")
RE_SCRIPT = re.compile(r"<script[^>]*>.*?</script>", re.S)

# 404 是错误页，不应被索引，因此不要求 canonical
NO_CANONICAL = {"404.html"}



def media_blocks(css):
    """按括号配对切出所有 @media 块，返回 [(条件, 块内文本)]。

    不能用 `@media ... {(.*?)\n}` 这种非贪婪正则——它会在块内第一条规则的
    闭合处就截断，导致「块里有没有某条规则」判断失准。这个方法此前靠缩进格式
    侥幸通过，一旦块内规则顺序变化就会误报。
    """
    out, i = [], 0
    while True:
        m = re.search(r"@media\s*\(([^)]*)\)\s*\{", css[i:])
        if not m:
            return out
        start = i + m.end()
        depth, k = 1, start
        while k < len(css) and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        out.append((m.group(1).strip(), css[start:k - 1]))
        i = k


def check_payload_shape(payload, cpayload, rep: Report):
    """前端数据产物的顶层键完整性 + facts 标签一致性。

    单独成函数是为了能直接喂变异过的 dict 做测试——这些键缺失时页面
    不会"显示得难看"，而是**在模块顶层抛 TypeError，之后所有渲染代码
    都不执行**，整页停在骨架屏。这类故障必须由构建挡住。

    实测三处曾全部放行：
      · 删掉 districts → 0 错误，但 schools.js 取它、chips() 里 values.map 抛错
      · 删掉 factLabels → 0 错误，因为原判断是 `if clabels and ...`，
        标签表为空时整段校验被跳过（最该拦的场景自动失效）
      · 两者都不校验「存在且非空」
    """
    shape = (
        ("assets/schools-data.js", payload, ("cols", "rows", "districts")),
        ("assets/schools-compare.js", cpayload, ("cols", "rows", "factLabels")),
    )
    for where, data, keys in shape:
        if data is None:            # 文件缺失/非法 JSON，前面已单独报过
            continue
        for k in keys:
            if not data.get(k):
                rep.error(where, f"顶层键「{k}」缺失或为空，前端会在顶层抛错、整页渲染中断")

    # facts 里出现的每个字段都必须在 factLabels 里有中文名，否则界面显示 undefined。
    # 注意不能写成 `if clabels and ...`：clabels 为空恰恰是要报的缺陷。
    if cpayload:
        ccols = cpayload.get("cols") or []
        clabels = set((cpayload.get("factLabels") or {}).keys())
        if "facts" in ccols:
            fi = ccols.index("facts")
            unknown = set()
            for r in cpayload.get("rows") or []:
                if isinstance(r[fi], dict):
                    unknown |= set(r[fi]) - clabels
            if unknown:
                rep.error("assets/schools-compare.js",
                          f"facts 出现未定义字段 {sorted(unknown)[:3]}，界面会显示 undefined")


def run(rep: Report, expected_pages):
    """返回 (rep, stats)。"""
    html_files = []
    for root, _, files in os.walk(config.SITE):
        for f in files:
            if f.endswith(".html"):
                html_files.append(os.path.join(root, f))

    stats = {"pages": len(html_files), "checked": 0}

    # 1) 页面数量
    if len(html_files) != expected_pages:
        rep.error("产物", f"生成 {len(html_files)} 个页面，预期 {expected_pages} 个")

    # 2) 资源文件
    for name in ("tokens.css", "site.css", "pages.css", "detail.css", "compare.css", "responsive.css",
                 "app.js", "schools-data.js", "schools-compare.js", "streets-data.js",
                 "timeline.css", "score.css", "score.js", "search-core.js", "schools.js",
                 "compare-core.js", "compare.js"):
        p = os.path.join(config.SITE, "assets", name)
        if not os.path.isfile(p):
            rep.error("产物", f"缺少资源文件 assets/{name}")
            continue
        kb = os.path.getsize(p) / 1024
        budget = ASSET_BUDGET_KB.get(name)
        if budget and kb > budget:
            rep.warn(f"assets/{name}", f"体积 {kb:.1f}KB 超过预算 {budget}KB，考虑拆分")

    # 2b) 令牌纪律：组件样式不得写死色值（#fff 用于强调色上的文字，允许）
    for sheet in STYLE_SHEETS:
        comp = os.path.join(config.SITE, "assets", sheet)
        if not os.path.isfile(comp):
            continue
        css = load.read_text(comp)
        bad = [c for c in RE_HEX.findall(css) if c.lower() not in ("#fff", "#ffffff")]
        if bad:
            rep.error("assets/site.css",
                      f"出现硬编码色值 {sorted(set(bad))[:5]}，应改用 tokens.css 中的变量")

        # 2c) 移动端溢出回归护栏
    # 曾出现：桌面端给表格设 min-width:520px 以便横向滚动，
    # 但窄屏表格已改为卡片布局，min-width 仍生效会把整页撑宽、右侧内容被裁切。
    # 覆盖规则可能在 responsive.css，故需跨三个样式文件合并后判断。
    all_css = ""
    for sheet in STYLE_SHEETS:
        p = os.path.join(config.SITE, "assets", sheet)
        if os.path.isfile(p):
            all_css += load.read_text(p) + "\n"
    mw = RE_TABLE_MINW.search(all_css)
    if mw and int(mw.group(1)) >= 400:
        mobile_blocks = [body for cond, body in media_blocks(all_css)
                         if "max-width:720px" in cond]
        has_override = any("table{min-width:0" in b.replace(" ", "") for b in mobile_blocks)
        if not has_override:
            rep.error("assets/*.css",
                      f"表格设了 min-width:{mw.group(1)}px 但移动端未覆盖为 0，"
                      f"窄屏会整页横向溢出")

    # 2d) 源文件卫生：重复定义检测
    # 反复踩过的坑：用追加方式改文件时，同一段 CSS 或 JS 被写入两次。
    # CSS 重复只是冗余；JS 重复会绑定两个监听器，同一次点击里互相抵消
    # （筛选按钮点不动就是这么来的）。故 JS 重复按错误处理。
    import collections as _c

    for sheet in STYLE_SHEETS:
        f = os.path.join(config.SITE, "assets", sheet)
        if not os.path.isfile(f):
            continue
        text = load.read_text(f)
        sels = re.findall(r"(?m)^([.#][^{\n]+)\{", text)
        dups = [sel for sel, n in _c.Counter(x.strip() for x in sels).items() if n > 1]
        if dups:
            rep.warn(f"assets/{sheet}", f"同一文件内重复定义 {len(dups)} 个选择器：{dups[:3]}")

    for js_name in sorted(n for n in os.listdir(os.path.join(config.SITE, "assets"))
                          if n.endswith(".js") and n not in DATA_ASSETS):
        js = os.path.join(config.SITE, "assets", js_name)
        lines = [ln.rstrip() for ln in open(js, encoding="utf-8").read().splitlines()]
        blocks = [tuple(lines[i:i + 8]) for i in range(len(lines) - 8)
                  if lines[i].strip() and lines[i].lstrip().startswith(("(function", "/*", "var ", "function "))]
        seen = {}
        for b in blocks:
            if len(set(x for x in b if x.strip())) < 6:
                continue
            if b in seen:
                rep.error(f"assets/{js_name}",
                          f"检测到重复代码块（约第 {lines.index(b[0]) + 1} 行起），"
                          f"重复绑定监听器会导致交互失效")
                break
            seen[b] = True

    # 2e) 前端数据契约（G1/G2/G3/G5b）
    # 这一层是盲区：JSON 结构一旦漂移，前端不会报错，只会拿到 undefined，
    # 表现是「某校永远搜不到 / 对比页少一列」——最难查的一类 bug。
    def load_payload(name):
        p = os.path.join(config.SITE, "assets", name)
        if not os.path.isfile(p):
            return None
        raw = load.read_text(p)
        try:
            return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
        except ValueError as e:
            rep.error(f"assets/{name}", f"不是合法 JSON：{e}")
            return None

    payload = load_payload("schools-data.js")
    cpayload = load_payload("schools-compare.js")
    spayload = load_payload("streets-data.js")

    # 地名索引与列表数据靠下标对齐：错一位 = 「搜宁海路」跳到另一所学校。
    # 这类错位在页面上完全看不出异常（照样有结果、照样能点），必须由构建挡住。
    if payload and spayload:
        n_list = len(payload.get("rows") or [])
        n_street = len(spayload.get("rows") or [])
        if n_street != n_list:
            rep.error("assets/streets-data.js",
                      f"行数 {n_street} 与 schools-data.js 的 {n_list} 不一致，"
                      f"地址搜索会张冠李戴")
        empty = sum(1 for a in (spayload.get("rows") or []) if not str(a or "").strip())
        if empty == n_street:
            rep.error("assets/streets-data.js",
                      "所有学校的施教区地名都为空，地址搜索会永远 0 结果")

    if payload:
        cols = payload.get("cols") or []
        rows = payload.get("rows") or []

        # G1 每行长度必须等于 cols，且关键列非空
        mismatched = [i for i, r in enumerate(rows) if len(r) != len(cols)]
        if mismatched:
            rep.error("assets/schools-data.js",
                      f"{len(mismatched)} 行长度与 cols({len(cols)}) 不一致，"
                      f"前端会拿到 undefined")
        for field in ("name", "level"):
            if field not in cols:
                rep.error("assets/schools-data.js", f"缺少 {field} 列")
                continue
            idx = cols.index(field)
            empty = sum(1 for r in rows if not str(r[idx] or "").strip())
            if empty:
                rep.error("assets/schools-data.js", f"{empty} 行的 {field} 为空")

        # G3 前端派生 id（学段-校名）必须唯一且能落到实际文件。
        # 对比页、详情页的「加入对比」都靠它，改拼法 = 历史分享链接静默失效。
        if "level" in cols and "name" in cols:
            li, ni = cols.index("level"), cols.index("name")
            derived = [f"{r[li]}-{r[ni]}" for r in rows]
            dup = [i for i, n in collections.Counter(derived).items() if n > 1]
            if dup:
                rep.error("assets/schools-data.js", f"派生 id 重复：{dup[:3]}")
            missing = [i for i in derived if not os.path.isfile(
                os.path.join(config.SITE, "schools", i + ".html"))]
            if missing:
                rep.error("assets/schools-data.js",
                          f"{len(missing)} 个派生 id 找不到详情页：{missing[:2]}")

    # G0/G2 顶层键完整性 + facts 标签一致性（纯函数，可单测）
    check_payload_shape(payload, cpayload, rep)

    if cpayload:
        crows = cpayload.get("rows") or []

        # G5b 两个数据文件必须同序同长——对比页靠下标对齐，错一位就是「张冠李戴」
        if payload and len(crows) != len(payload.get("rows") or []):
            rep.error("assets/schools-compare.js",
                      f"行数 {len(crows)} 与 schools-data.js 的 "
                      f"{len(payload.get('rows') or [])} 不一致，对比页会张冠李戴")

        # missing 的 key 必须是真实存在的派生 id
        if payload and "level" in (payload.get("cols") or []) and "name" in (payload.get("cols") or []):
            pc = payload["cols"]
            valid = {f"{r[pc.index('level')]}-{r[pc.index('name')]}" for r in payload["rows"]}
            bad = [k for k in (cpayload.get("missing") or {}) if k not in valid]
            if bad:
                rep.error("assets/schools-compare.js",
                          f"{len(bad)} 个缺口记录的 id 不存在：{bad[:2]}")

    # 2g) 模板里不许手写百分号编码
    # 手写的编码看不出对错：曾把「琅」(%E7%90%85) 写成「狼」(%E7%8B%BC)，
    # 首页常搜词点进去搜出 0 条，而构建、链接校验全是绿的，没人发现。
    # 直接写中文让浏览器编码，或用 | urlencode，都比手写安全。
    for tpl in sorted(glob.glob(os.path.join(config.TEMPLATES, "*.html"))):
        text = load.read_text(tpl)
        for m in re.finditer(r'(?:href|action)="([^"]*%[0-9A-Fa-f]{2}[^"]*)"', text):
            raw = m.group(1)
            if raw.startswith(("data:", "http://", "https://")):
                continue
            rep.error(os.path.basename(tpl),
                      f"链接里手写了百分号编码「{raw}」——直接写中文或用 | urlencode，"
                      f"手写极易把字写错且看不出（曾把「琅」写成「狼」）")

    # 2f) 脚本语法（G6）
    # 内联脚本时代这里是盲区：模板里的 JS 语法错误要到用户浏览器才炸。
    # 现在脚本全部外置到 assets/，构建期就能拦。
    node = shutil.which("node")
    if not node:
        rep.warn("assets/*.js", "未找到 node，跳过脚本语法检查")
    else:
        for js_name in sorted(n for n in os.listdir(os.path.join(config.SITE, "assets"))
                              if n.endswith(".js")):
            # 必须显式指定 encoding：默认按 locale 解码，数据文件里一旦有非法 UTF-8，
            # 门禁自己会抛 UnicodeDecodeError 崩掉——守卫变成故障源。
            r = subprocess.run([node, "--check", os.path.join(config.SITE, "assets", js_name)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode != 0:
                detail = [x for x in (r.stderr or "").splitlines() if x.strip()]
                rep.error(f"assets/{js_name}", "脚本语法错误：" + (detail[0] if detail else "未知"))

    for path in html_files:
        rel = os.path.relpath(path, config.SITE)
        html = load.read_text(path)
        stats["checked"] += 1

        # 结构语义
        h1n = len(RE_H1.findall(html))
        if h1n != 1:
            rep.error(rel, f"<h1> 数量为 {h1n}，应恰好 1 个（读屏与 SEO 要求）")
        if '<html lang="zh-CN">' not in html:
            rep.error(rel, "缺少 lang=\"zh-CN\"")
        if "<title>" not in html:
            rep.error(rel, "缺少 <title>")
        if 'name="description"' not in html:
            rep.warn(rel, "缺少 meta description")
        # 分享卡片：og 缺失时转发只显示裸链接，体验明显变差
        if 'property="og:title"' not in html or 'property="og:description"' not in html:
            rep.error(rel, "缺少 og:title / og:description")
        if config.BASE_URL and 'property="og:image"' not in html:
            rep.error(rel, "已配置 BASE_URL 但缺少 og:image（转发出去会是裸链接）")
        if 'name="theme-color"' not in html:
            rep.warn(rel, "缺少 theme-color")
        if 'class="skip"' not in html:
            rep.error(rel, "缺少跳转主内容的无障碍链接")
        if config.BASE_URL and 'rel="canonical"' not in html and rel not in NO_CANONICAL:
            rep.error(rel, "已配置 BASE_URL 但缺少 canonical")

        # 样式与脚本必须外链，不允许回退到内联
        for need in ("assets/tokens.css", "assets/site.css", "assets/app.js"):
            if need not in html:
                rep.error(rel, f"未引用 {need}")
        if RE_STYLE.search(html):
            rep.error(rel, "存在内联 <style>，样式应只在 assets/ 维护")

        # 同一份样式表只允许引入一次。
        # responsive.css 靠「最后加载」来覆盖基础规则，重复引入会让 pages.css
        # 排到它后面，断点内的覆盖静默失效——这类问题极难定位，故按错误处理。
        hrefs = re.findall(r'<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"', html)
        dup_css = [h for h, n in collections.Counter(hrefs).items() if n > 1]
        if dup_css:
            rep.error(rel, f"同一份样式表被重复引入：{dup_css[:2]}，会打乱层叠顺序")

        # 主题必须在首帧之前落到 <html> 上，否则深色模式用户每次翻页都会白闪
        if "data-theme" not in html.split("</head>")[0]:
            rep.error(rel, "缺少首帧主题预置脚本（深色模式会翻页白闪）")

        # 占位符与编码
        if RE_PLACEHOLDER.search(html):
            rep.error(rel, "正文残留 {BASE} 占位符")

        # Markdown 粗体标记泄漏：meta/og/JSON-LD/列表卡片都不解析 Markdown，
        # tagline 若带 ** 会直接显示星号（曾一次性影响 118 个页面）
        if "**" in html:
            rep.error(rel, "存在未解析的 Markdown 粗体标记「**」，应去掉标记后再输出")

        # 体积预算
        kb = os.path.getsize(path) / 1024
        limit = PAGE_SIZE_EXEMPT_KB.get(rel.replace(os.sep, "/"), PAGE_SIZE_WARN_KB)
        if kb > limit:
            rep.warn(rel, f"页面体积 {kb:.0f}KB 超过预算 {limit}KB")

        # 详情页的目录：正文章节足够多时应生成 TOC
        if rel.startswith("schools" + os.sep) and rel.count(os.sep) == 1:
            if len(RE_H2.findall(html)) >= MIN_H2_FOR_TOC and 'class="toc"' not in html:
                rep.warn(rel, "章节较多但缺少目录")
            if 'application/ld+json' not in html:
                rep.warn(rel, "缺少 JSON-LD 结构化数据")

        # 内容页不允许重复章节标题（曾因重复写入导致同一条日志出现两次）
        if rel in ("changelog.html",):
            heads = re.findall(r"<h2[^>]*>(.*?)</h2>", html)
            dup = [h for h in set(heads) if heads.count(h) > 1]
            if dup:
                rep.error(rel, f"存在重复章节标题：{dup[:2]}")

        # 内部链接可达性
        # 注意：先剔除 <script> 内容——列表页把数据内嵌在 JS 里，
        # 其中 `href="' + s.url + '"` 这类拼接片段会被正则误判为死链。
        base_dir = os.path.dirname(path)
        markup = RE_SCRIPT.sub("", html)
        for target in set(RE_LOCAL.findall(markup)):
            if target.startswith(("http://", "https://", "mailto:", "data:", "#", "//")):
                continue
            clean = target.split("#")[0].split("?")[0]
            # 从站点根算起的绝对链接（404 页使用）：按配置的基址路径裁剪后再校验
            if clean.startswith("/"):
                base_path = urlparse(config.BASE_URL).path.rstrip("/") if config.BASE_URL else ""
                if base_path and clean.startswith(base_path + "/"):
                    clean = clean[len(base_path) + 1:]
                elif base_path == "":
                    clean = clean.lstrip("/")
                else:
                    continue
            if not clean:
                continue
            # 链接里的中文是百分号编码的（schools/%E5%B0%8F%E5%AD%A6-…html），
            # 磁盘上的文件名是原样中文。不先解码就比对，会把每一条中文链接都判成死链。
            # 这个盲区此前一直存在——只是学校库靠 JS 渲染，站内没有静态的中文链接，
            # 直到 all.html 出现才暴露。
            resolved = os.path.normpath(os.path.join(base_dir, unquote(clean)))
            if not os.path.exists(resolved):
                rep.error(rel, f"内部链接指向不存在的文件：{target}")

    # 3) sitemap
    sitemap = os.path.join(config.SITE, "sitemap.xml")
    if config.BASE_URL:
        if not os.path.isfile(sitemap):
            rep.error("sitemap", "已配置 BASE_URL 但未生成 sitemap.xml")
        else:
            xml = load.read_text(sitemap)
            locs = re.findall(r"<loc>([^<]+)</loc>", xml)
            # sitemap 不含 404 页
            if len(locs) != expected_pages - 1:
                rep.error("sitemap", f"条目数 {len(locs)} 与可收录页面数 {expected_pages - 1} 不一致")
            if RE_DOUBLE_ENC.search(xml):
                rep.error("sitemap", "存在双重 URL 编码（%25 开头的二次编码）")
            if not all(u.startswith(config.BASE_URL) for u in locs):
                rep.error("sitemap", "存在非绝对地址条目")
    elif os.path.isfile(sitemap):
        rep.warn("sitemap", "未配置 BASE_URL 却生成了 sitemap.xml")

    return rep, stats
