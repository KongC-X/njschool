# -*- coding: utf-8 -*-
"""为原浦口区 17 所小学补写官网记录（2026-10-24 第四批）。

说明：浦口区多数学校的「学校简介」由**浦口区教师发展中心（pkjx.com）站群**
承载，且按校名拼音路径分站（如 pkqxdxx = 浦口星甸小学）。这类站点不是学校
自有域名，但属区教育局官方发布渠道，标为 level B。
凡未取得可访问地址的，一律 null_reason="未检索到"。
"""
import json

PATH = "data/school_websites.json"
TODAY = "2026-10-24"

# key -> (site, level, basis)
HAS_SITE = {
    "小学-江北新区-南京市浦口区星甸小学": (
        "http://www.pkjx.com/pkqxdxx/", "B",
        "浦口区教师发展中心（pkjx.com）站群内学校分站，2026-10-24 实测可达（200）；"
        "《南京市浦口区星甸小学简介》即发布于该站",
    ),
    "小学-江北新区-南京市浦口区汤泉小学": (
        "http://www.pkjx.com/pkqtqxx/", "B",
        "浦口区教师发展中心站群内学校分站，2026-10-24 实测可达（200）；"
        "《南京市浦口区汤泉小学简介》发布于该站",
    ),
    "小学-江北新区-南京市浦口区高旺小学": (
        "http://www.pkjx.com/pkqgwxx/", "B",
        "浦口区教师发展中心站群内学校分站，2026-10-24 实测可达（200）；"
        "《文化引领 彰显特色——高旺小学简介》发布于该站",
    ),
    "小学-江北新区-南京市浦口区永宁小学": (
        "http://www.pkjx.com/pkqynxx/", "B",
        "浦口区教师发展中心站群内学校分站，2026-10-24 实测可达（200）；"
        "《南京市浦口区永宁小学简介》（2024-10）发布于该站",
    ),
}

NO_SITE = {
    "小学-江北新区-南京市浦口区珠江小学":
        "无学校自有域名官网；曾用域名 zjxx.pkjx.com（浦口区教师发展中心站群）2026-10-24 实测返回 502，"
        "暂不可用；学校信息现有来源为第三方整理的《学校简介》转载",
    "小学-江北新区-南京市中华中学浦口雨山小学":
        "2023 年 9 月新开办，未检索到独立官网或区级站群分站；"
        "开办信息见江苏文明网 2023 年开学季报道",
    "小学-江北新区-南京审计大学实验学校（小学部）":
        "未检索到学校独立官网；公开信息主要来自第三方百科整理",
    "小学-江北新区-南京市江浦实验小学滨江分校":
        "未检索到分校独立官网；分校信息见总校（江浦实验小学）简介，"
        "总校简介发布于浦口区教师发展中心站群（pkjx.com/pkqjpsyxx/）",
    "小学-江北新区-南京市第一中学浦口分校（小学部）":
        "未检索到独立官网或区级站群分站；公开信息披露极少",
    "小学-江北新区-南京市浦口区石桥小学":
        "未检索到独立官网或区级站群分站；学校信息现有来源为第三方教育资讯站点",
    "小学-江北新区-南京市浦口区永宁学校（小学部）":
        "未检索到独立官网或区级站群分站；公开信息披露极少",
    "小学-江北新区-南京市浦口区车站小学":
        "未检索到独立官网或区级站群分站；公开信息披露极少",
    "小学-江北新区-南京市浦口区大桥小学":
        "未检索到独立官网或区级站群分站；公开信息披露极少",
    "小学-江北新区-南京市浦口区乌江学校（小学部）":
        "未检索到独立官网或区级站群分站；公开信息披露极少",
    "小学-江北新区-南京市第一中学浦口区桥林新城小学":
        "未检索到独立官网或区级站群分站；公开信息披露极少",
    "小学-江北新区-南京市浦口区陡岗小学":
        "未检索到独立官网或区级站群分站；公开信息披露极少",
    "小学-江北新区-南京市浦口区新浦实验小学":
        "未检索到学校自有域名官网；公开信息主要来自第三方百科整理",
}


def main():
    data = json.load(open(PATH, encoding="utf-8"))
    table = data["schools"]
    added = 0

    for key, (site, level, basis) in HAS_SITE.items():
        if key in table:
            print("已存在，跳过：", key)
            continue
        table[key] = {
            "site": site, "site_archived": None, "null_reason": None,
            "repair": None, "wechat": None, "wechat_status": "unknown",
            "level": level, "basis": basis, "site_state": "ok",
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
