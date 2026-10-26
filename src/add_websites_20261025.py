# -*- coding: utf-8 -*-
"""江宁区 8 所小学官网记录（2026-10-25）。

江宁区学校站点统一挂在江宁教育服务平台（jnjy.net.cn）子域下，均为区教育局站群。
"""
import json

PATH = "data/school_websites.json"
TODAY = "2026-10-25"

HAS_SITE = {
    "小学-江宁区-南京市将军山小学": ("http://jjsxx.jnjy.net.cn/", "含 2026 年入学公告"),
    "小学-江宁区-南京市东郊小镇小学": ("http://djxzxx.jnjy.net.cn/", "含入学公告"),
    "小学-江宁区-南京市江宁上坊新城小学": ("http://sfxcxx.jnjy.net.cn/", "含 2026 年入学公告"),
    "小学-江宁区-南京市江宁开发区学校（小学部）": (
        "http://kfqxx.jnjy.net.cn/", "含小学部与初中部 2026 年入学公告"),
    "小学-江宁区-南京市江宁区禄口第二小学": (
        "http://lkdexx.jnjy.net.cn/", "含《2026 年禄口片区小学一年级入学公告》"),
}

NO_SITE = {
    "小学-江宁区-南京市礼尚路学校（小学部）":
        "未检索到独立官网或站群分站；施教区见禄口片区入学公告（lkdexx.jnjy.net.cn）",
    "小学-江宁区-南京市江宁区禄口中心小学":
        "未检索到独立官网或站群分站；施教区见禄口片区入学公告（lkdexx.jnjy.net.cn）",
    "小学-江宁区-南京市江宁区空港小学":
        "未检索到独立官网或站群分站；施教区见禄口片区入学公告（lkdexx.jnjy.net.cn）",
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
