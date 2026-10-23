# -*- coding: utf-8 -*-
"""产物校验：构建完成后对生成结果做结构性检查。

这一层是「缺陷出不了门」的保障。此前 sitemap 带 207 处占位符能一路到生产，
正是因为缺少这类检查。检查项分两级：error 阻断（构建失败），warning 仅提示。
"""
import os
import re

from . import config
from .schema import Report

MIN_H2_FOR_TOC = 3
PAGE_SIZE_WARN_KB = 120

RE_H1 = re.compile(r"<h1[\s>]")
RE_H2 = re.compile(r"<h2[\s>]")
RE_STYLE = re.compile(r"<style[\s>]")
RE_LOCAL = re.compile(r'(?:href|src)="([^"]+)"')
RE_PLACEHOLDER = re.compile(r"\{BASE\}")
RE_DOUBLE_ENC = re.compile(r"%25[0-9A-Fa-f]{2}")
RE_SCRIPT = re.compile(r"<script[^>]*>.*?</script>", re.S)


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
    for name in ("tokens.css", "site.css", "app.js"):
        p = os.path.join(config.SITE, "assets", name)
        if not os.path.isfile(p):
            rep.error("产物", f"缺少资源文件 assets/{name}")

    for path in html_files:
        rel = os.path.relpath(path, config.SITE)
        html = open(path, encoding="utf-8").read()
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
        if 'class="skip"' not in html:
            rep.error(rel, "缺少跳转主内容的无障碍链接")
        if config.BASE_URL and 'rel="canonical"' not in html:
            rep.error(rel, "已配置 BASE_URL 但缺少 canonical")

        # 样式与脚本必须外链，不允许回退到内联
        for need in ("assets/tokens.css", "assets/site.css", "assets/app.js"):
            if need not in html:
                rep.error(rel, f"未引用 {need}")
        if RE_STYLE.search(html):
            rep.error(rel, "存在内联 <style>，样式应只在 assets/ 维护")

        # 占位符与编码
        if RE_PLACEHOLDER.search(html):
            rep.error(rel, "正文残留 {BASE} 占位符")

        # 体积预算
        kb = os.path.getsize(path) / 1024
        if kb > PAGE_SIZE_WARN_KB:
            rep.warn(rel, f"页面体积 {kb:.0f}KB 超过预算 {PAGE_SIZE_WARN_KB}KB")

        # 详情页的目录：正文章节足够多时应生成 TOC
        if rel.startswith("schools" + os.sep) and rel.count(os.sep) == 1:
            if len(RE_H2.findall(html)) >= MIN_H2_FOR_TOC and 'class="toc"' not in html:
                rep.warn(rel, "章节较多但缺少目录")

        # 内部链接可达性
        # 注意：先剔除 <script> 内容——列表页把数据内嵌在 JS 里，
        # 其中 `href="' + s.url + '"` 这类拼接片段会被正则误判为死链。
        base_dir = os.path.dirname(path)
        markup = RE_SCRIPT.sub("", html)
        for target in set(RE_LOCAL.findall(markup)):
            if target.startswith(("http://", "https://", "mailto:", "data:", "#", "//")):
                continue
            clean = target.split("#")[0].split("?")[0]
            if not clean:
                continue
            resolved = os.path.normpath(os.path.join(base_dir, clean))
            if not os.path.exists(resolved):
                rep.error(rel, f"内部链接指向不存在的文件：{target}")

    # 3) sitemap
    sitemap = os.path.join(config.SITE, "sitemap.xml")
    if config.BASE_URL:
        if not os.path.isfile(sitemap):
            rep.error("sitemap", "已配置 BASE_URL 但未生成 sitemap.xml")
        else:
            xml = open(sitemap, encoding="utf-8").read()
            locs = re.findall(r"<loc>([^<]+)</loc>", xml)
            if len(locs) != expected_pages:
                rep.error("sitemap", f"条目数 {len(locs)} 与页面数 {expected_pages} 不一致")
            if RE_DOUBLE_ENC.search(xml):
                rep.error("sitemap", "存在双重 URL 编码（%25 开头的二次编码）")
            if not all(u.startswith(config.BASE_URL) for u in locs):
                rep.error("sitemap", "存在非绝对地址条目")
    elif os.path.isfile(sitemap):
        rep.warn("sitemap", "未配置 BASE_URL 却生成了 sitemap.xml")

    return rep, stats
