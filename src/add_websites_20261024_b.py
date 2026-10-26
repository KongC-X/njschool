# -*- coding: utf-8 -*-
"""为 2026-10-24 新增的 10 所大厂/葛塘/扬子片区小学补写官网记录。

官网可达性已于 2026-10-24 用 HTTP 探测确认（全部返回 200）。
"""
import json

PATH = "data/school_websites.json"
TODAY = "2026-10-24"

# key: 索引键（学段-区-校名） -> (site, basis)
NEW = {
    "小学-江北新区-南京市南化实验小学": (
        "http://nhshx.njnaedu.cn/",
        "江北新区教育信息网站群内学校站点，2026-10-24 实测可达（200）；"
        "《学校介绍》页含 1990 年建校、规模、师资、126 项荣誉等完整信息",
    ),
    "小学-江北新区-南京市南化第四小学": (
        "http://www.nhsx.com/",
        "学校自有域名官网，2026-10-24 实测可达（200）；"
        "《怡园简介》页含 1961 年建校、合并沿革、师资、排球传统、怡然文化等",
    ),
    "小学-江北新区-南京信息工程大学附属实验小学": (
        "http://xdjy.njnaedu.cn/",
        "江北新区教育信息网站群内学校站点，2026-10-24 实测可达（200）；"
        "含《学校简介（2023 年版）》",
    ),
    "小学-江北新区-南京市扬子第二小学": (
        "http://yz2x.njnaedu.cn/",
        "江北新区教育信息网站群内学校站点，2026-10-24 实测可达（200）；"
        "含通知公告、教育科研、德育天地等栏目与 2022 年招生简章",
    ),
    "小学-江北新区-南京市扬子第三小学": (
        "http://www.njyzsx.com/",
        "学校自有域名官网，2026-10-24 实测可达（200）；含 2021 年招生简章（校史、理念、师资、施教区）",
    ),
    "小学-江北新区-南京市扬子第四小学": (
        "http://yzdsxx.njnaedu.cn/",
        "江北新区教育信息网站群内学校站点，2026-10-24 实测可达（200）；"
        "《学校简介》页含 1992 年建校、少年君子教育、儒香校园等",
    ),
    "小学-江北新区-南京市葛塘中心小学": (
        "http://gtxx.njnaedu.cn/",
        "江北新区教育信息网站群内学校站点，2026-10-24 实测可达（200）；"
        "含 2023 年招生简章（校史、理念、善园文化、荣誉）",
    ),
    "小学-江北新区-南京市南化第三小学": (
        "http://njnhsx.njnaedu.cn/",
        "江北新区教育信息网站群内学校站点，2026-10-24 实测可达（200）；"
        "但公开栏目以通知公告与校园新闻为主，未见完整「学校简介」页",
    ),
}

# 无独立官网的两所：用 null_reason 记录成因
NO_SITE = {
    "小学-江北新区-南京市九龙小学":
        "未检索到独立官网或区内站群站点；公开信息以区级活动报道为主，"
        "未见学校简介、办学理念与师资数据",
    "小学-江北新区-南京市长城小学":
        "无独立官网；学校简介发表于集团总校（南化实验小学）站点的集团专栏内，"
        "非学校自有域名",
}


def main():
    data = json.load(open(PATH, encoding="utf-8"))
    table = data["schools"]
    added = 0

    for key, (site, basis) in NEW.items():
        if key in table:
            print("已存在，跳过：", key)
            continue
        table[key] = {
            "site": site,
            "site_archived": None,
            "null_reason": None,
            "repair": None,
            "wechat": None,
            "wechat_status": "unknown",
            "level": "A",
            "basis": basis,
            "site_state": "ok",
            "verify": f"{TODAY} HTTP 200",
        }
        added += 1

    for key, basis in NO_SITE.items():
        if key in table:
            print("已存在，跳过：", key)
            continue
        table[key] = {
            "site": None,
            "site_archived": None,
            "null_reason": "未检索到",
            "repair": None,
            "wechat": None,
            "wechat_status": "unknown",
            "level": "C",
            "basis": basis,
            "site_state": "none",
        }
        added += 1

    data["updated"] = TODAY
    json.dump(data, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"新增官网记录 {added} 条，总计 {len(table)} 条")


if __name__ == "__main__":
    main()
