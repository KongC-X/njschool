# -*- coding: utf-8 -*-
"""流水线编排：校验 → 渲染 → 落盘 → 产物检查。

退出码：0 成功；1 校验或检查未通过（CI 据此中断发布）。
"""
import json
import os
import shutil

from . import check, config, load, render
from .schema import Report, validate_counts, validate_pages, validate_schools, validate_websites


def run():
    print("① 读取内容")
    index = load.load_index()
    webmap, verified_at, web_counts = load.load_websites()
    schools = load.load_schools(index, webmap)
    pages = load.load_pages()
    md_total = load.count_md_files()
    print(f"   学校 {len(schools)} 所 / 档案文件 {md_total} 个 / 内容页 {len(pages)} 个")

    print("② 校验数据")
    rep = Report()
    validate_schools(schools, index.get("districts", []), rep)
    validate_websites(schools, rep)
    validate_counts(schools, md_total, rep)
    validate_pages(pages, rep)
    ok = rep.dump()
    print(f"   错误 {len(rep.errors)} / 警告 {len(rep.warnings)}")
    if not ok:
        print("✗ 数据校验未通过，终止构建（未产生任何文件改动）")
        return 1

    links = load.load_source_links()
    src_stats = {}
    stats_path = os.path.join(config.ROOT, "data", "sources_stats.json")
    if os.path.isfile(stats_path):
        src_stats = json.load(open(stats_path, encoding="utf-8"))
    print(f"   来源链接：{len(links)} 个标题可点击")

    print("③ 渲染页面")
    env = render.make_env()
    outputs = {
        "index.html": render.home(env, schools, index["districts"], pages, web_counts),
        "schools.html": render.schools_page(env, schools, index["districts"]),
        "compare.html": render.compare(env, schools),
        "compare.html": render.compare(env, schools),
        "policy.html": render.policy(env, pages),
        "about.html": render.about(env, schools, pages, web_counts, src_stats),
        "changelog.html": render.doc(env, pages, "changelog", title="更新日志",
                                     desc="数据与站点的重要变更记录。", eyebrow="记录"),
        "404.html": render.not_found(env),
    }
    for s in schools:
        outputs[f"schools/{s.slug}.html"] = render.detail(env, s, verified_at, links)

    print("④ 写入站点")
    if os.path.isdir(config.SITE):
        shutil.rmtree(config.SITE)
    os.makedirs(os.path.join(config.SITE, "assets"))
    os.makedirs(os.path.join(config.SITE, "schools"), exist_ok=True)

    for name in ("tokens.css", "site.css", "pages.css", "responsive.css", "app.js"):
        src = os.path.join(config.ASSETS, name)
        if not os.path.isfile(src):
            print(f"✗ 缺少资源文件：{src}")
            return 1
        shutil.copyfile(src, os.path.join(config.SITE, "assets", name))

    for rel, html in outputs.items():
        path = os.path.join(config.SITE, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    # sitemap 只在有基址时生成：协议要求绝对地址，宁缺勿假
    # 列表 / 对比 / 搜索共用一份数据资产（浏览器只下载一次）
    with open(os.path.join(config.SITE, "assets", "schools-data.js"), "w",
              encoding="utf-8") as f:
        f.write(render.schools_data(schools, index["districts"]))

    urls = ["", "schools.html", "compare.html", "policy.html", "changelog.html",
            "about.html"] + [s.url for s in schools]
    if config.BASE_URL:
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + "\n".join(f"  <url><loc>{config.BASE_URL}/{u}</loc>"
                           f"<lastmod>{config.TODAY}</lastmod></url>" for u in urls)
               + "\n</urlset>\n")
        with open(os.path.join(config.SITE, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write(xml)
        robots = f"User-agent: *\nAllow: /\n\nSitemap: {config.BASE_URL}/sitemap.xml\n"
    else:
        robots = "User-agent: *\nAllow: /\n"
    with open(os.path.join(config.SITE, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots)

    print(f"   输出 {len(outputs)} 个页面 → {config.SITE}")

    # 回归护栏：登记表里有 URL 却没渲染出任何来源链接，说明链接化链路断了
    if links:
        probe = list(links.values())
        hit = sum(1 for h in outputs.values() if any(u in h for u in probe))
        if hit == 0:
            print("✗ 来源登记表非空，但没有任何页面渲染出来源链接")
            return 1
        print(f"   来源链接已渲染到 {hit} 个页面")

    print("⑤ 检查产物")
    rep2 = Report()
    rep2, stats = check.run(rep2, expected_pages=len(outputs))
    ok2 = rep2.dump()
    print(f"   检查 {stats['checked']} 页，错误 {len(rep2.errors)} / 警告 {len(rep2.warnings)}")
    if not ok2:
        print("✗ 产物检查未通过")
        return 1

    print(f"✓ 构建完成：{stats['checked']} 页"
          + (f"，sitemap {len(urls)} 条" if config.BASE_URL else "，未生成 sitemap（无 NJ_BASE_URL）"))
    return 0
