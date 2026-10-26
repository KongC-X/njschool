# -*- coding: utf-8 -*-
"""原江北新区 8 所小学官网记录（2026-10-24 第五批）。"""
import json

PATH = "data/school_websites.json"
TODAY = "2026-10-24"

HAS_SITE = {
    "小学-江北新区-南京一中江北新区教育集团第一小学": (
        "http://yzyx.njnaedu.cn/",
        "江北新区教育信息网站群内学校站点，2026-10-24 实测可达（200）；含《学校简介》",
    ),
    "小学-江北新区-南京一中江北新区教育集团第二小学": (
        "http://yzex.njnaedu.cn/",
        "江北新区教育信息网站群内学校站点，2026-10-24 实测可达（200）；"
        "含《校园简介》与《向人民汇报》",
    ),
    "小学-江北新区-南京市琅琊路小学柳洲东路分校": (
        "http://wnsscfx.njnaedu.cn/",
        "江北新区教育信息网站群内学校站点，2026-10-24 实测可达（200）；含 2022 年招生简章",
    ),
    "小学-江北新区-南京市琅琊路小学分校天润城小学": (
        "http://lxtrc.njnaedu.cn/",
        "江北新区教育信息网站群内学校站点，2026-10-24 实测可达（200）；含「穿石课程」系列文章",
    ),
    "小学-江北新区-南京市北京东路小学分校红太阳小学": (
        "http://njsbjdlxxfxhtyxx.njnaedu.cn/",
        "江北新区教育信息网站群内学校站点，2026-10-24 实测可达（200）；含《学校简介》",
    ),
}

NO_SITE = {
    "小学-江北新区-南京市第一中学江北新区分校（小学部）":
        "未检索到独立官网或区级站群分站；公开信息披露极少",
    "小学-江北新区-南京江北新区浦口实验小学浦园路分校":
        "无独立官网；信息见总校（浦口实验小学）官网 pksx.njnaedu.cn 与区教育局招生文件",
    "小学-江北新区-南京江北新区浦口实验小学万江分校":
        "无独立官网；信息见总校（浦口实验小学）官网 pksx.njnaedu.cn 与区教育局招生文件",
}


def main():
    data = json.load(open(PATH, encoding="utf-8"))
    table = data["schools"]
    added = 0

    for key, (site, basis) in HAS_SITE.items():
        if key in table:
            print("已存在，跳过：", key)
            continue
        table[key] = {
            "site": site, "site_archived": None, "null_reason": None,
            "repair": None, "wechat": None, "wechat_status": "unknown",
            "level": "A", "basis": basis, "site_state": "ok",
            "verify": f"{TODAY} HTTP 200",
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
