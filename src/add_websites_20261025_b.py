# -*- coding: utf-8 -*-
"""江宁区 10 所九年一贯制学校（小学部）官网记录（2026-10-25）。"""
import json

PATH = "data/school_websites.json"
TODAY = "2026-10-25"

HAS_SITE = {
    "小学-江宁区-南京市江宁区梅龙湖学校（小学部）": (
        "http://mlhxx.jnjy.net.cn/", "含 2026 年小学部入学公告"),
    "小学-江宁区-南京市江宁区岔路学校（小学部）": (
        "http://clxx.jnjy.net.cn/", "含 2026 年入学公告"),
    "小学-江宁区-南京市江宁区宏运学校（小学部）": (
        "http://hyxx.jnjy.net.cn/", "含区级咨询电话附件等公开材料"),
}

NO_SITE = {
    "小学-江宁区-南京市江宁区滨河实验学校（小学部）":
        "未检索到独立官网或站群分站；施教区见区教育局实施细则的施教区一览",
    "小学-江宁区-南京市江宁区江宁滨江新城学校（小学部）":
        "未检索到独立官网或站群分站；施教区见区教育局实施细则的施教区一览",
    "小学-江宁区-南京市江宁区麒麟科创园学校（小学部）":
        "未检索到独立官网或站群分站；施教区见区教育局实施细则的施教区一览",
    "小学-江宁区-南京市江宁区清水亭学校（小学部）":
        "未检索到独立官网或站群分站；施教区见区教育局实施细则的施教区一览",
    "小学-江宁区-南京市江宁区紫东江宁学校（小学部）":
        "未检索到独立官网或站群分站；施教区见区教育局实施细则的施教区一览",
    "小学-江宁区-南京市江宁区丹阳学校（小学部）":
        "未检索到独立官网或站群分站；施教区未在区级一览公示",
    "小学-江宁区-南京市江宁区周岗学校（小学部）":
        "未检索到独立官网或站群分站；施教区未在区级一览公示",
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
            "basis": f"江宁教育服务平台（jnjy.net.cn）站群内学校分站，2026-10-25 实测可达（200）；{note}",
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
