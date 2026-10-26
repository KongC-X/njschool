# -*- coding: utf-8 -*-
"""原江北新区剩余 19 所小学官网记录（2026-10-24 第六批）。"""
import json

PATH = "data/school_websites.json"
TODAY = "2026-10-24"

HAS_SITE = {
    "小学-江北新区-南京江北新区浦厂小学": ("http://pcxx.njnaedu.cn/", "含招生指南与学校简介"),
    "小学-江北新区-南京晓庄学院顶山实验小学": ("http://xzdssx.njnaedu.cn/", "含入学公告与学校简介"),
    "小学-江北新区-南京信息工程大学附属高新实验小学": ("http://gxsx.njnaedu.cn/", "含《学校简介》"),
    "小学-江北新区-南京江北新区泰山小学": ("http://pkqtsxx.njnaedu.cn/", "含《学校简介》"),
    "小学-江北新区-南京江北新区浦洲路小学": ("http://pzlxx.njnaedu.cn/", "含《学校简介》"),
    "小学-江北新区-南京江北新区浦口外国语学校（小学部）": ("http://www.npfls.com/", "学校自有域名官网，含 2026 年新闻与校务公开"),
    "小学-江北新区-南京江北新区鼎泰实验小学": ("http://dtsx.njnaedu.cn/", "站群内站点，公开栏目以通知公告与校园新闻为主"),
    "小学-江北新区-南京市力学小学海德北岸分校": ("http://lxhdfx.njnaedu.cn/", "含通知公告与校园新闻"),
    "小学-江北新区-南京市第二十九中学天润城分校（小学部）": ("http://nj29ztrcfx.njnaedu.cn/", "含《简介》与小学部招生简章"),
    "小学-江北新区-南京江北新区高新实验小学": ("http://pkgxxx.njnaedu.cn/", "含《学校简介》"),
}

NO_SITE = {
    "小学-江北新区-南京外国语学校江北新区学校（小学部）":
        "2026 年 9 月首批开学，未检索到独立官网；信息见江南时报开学报道",
    "小学-江北新区-南京市江北芳草园小学":
        "2023 年 9 月开学，未检索到独立官网；信息见金陵新闻网与第三方百科",
    "小学-江北新区-南京（大厂）民办育英第二外国语学校中央商务区学校（小学部）":
        "未检索到独立官网或区级站群分站；师资数据仅有媒体报道口径",
    "小学-江北新区-南京明道学校研创园学校（小学部）":
        "未检索到独立官网或区级站群分站；公开信息以媒体报道为主",
    "小学-江北新区-南京工业大学实验小学": "未检索到独立官网或区级站群分站；公开信息披露极少",
    "小学-江北新区-南京江北新区永丰小学": "未检索到独立官网或区级站群分站；公开信息披露极少",
    "小学-江北新区-南京江北新区六一小学": "未检索到独立官网或区级站群分站；公开信息披露极少",
    "小学-江北新区-南京江北新区沿江小学": "未检索到独立官网或区级站群分站；公开信息披露极少",
    "小学-江北新区-南京江北新区玉带实验学校（小学部）": "未检索到独立官网或区级站群分站；公开信息披露极少",
}


def main():
    data = json.load(open(PATH, encoding="utf-8"))
    table = data["schools"]
    added = 0

    for key, (site, note) in HAS_SITE.items():
        if key in table:
            print("已存在，跳过：", key)
            continue
        table[key] = {
            "site": site, "site_archived": None, "null_reason": None,
            "repair": None, "wechat": None, "wechat_status": "unknown",
            "level": "A",
            "basis": f"江北新区教育信息网站群内或学校自有域名站点，2026-10-24 实测可达（200）；{note}",
            "site_state": "ok", "verify": f"{TODAY} HTTP 200",
        }
        added += 1

    for key, basis in NO_SITE.items():
        if key in table:
            print("已存在，跳过：", key)
            continue
        table[key] = {
            "site": None, "site_archived": None, "null_reason": "未检索到",
            "repair": None, "wechat": None, "wechat_status": "unknown",
            "level": "C", "basis": basis, "site_state": "none",
        }
        added += 1

    data["updated"] = TODAY
    json.dump(data, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"新增官网记录 {added} 条，总计 {len(table)} 条")


if __name__ == "__main__":
    main()
