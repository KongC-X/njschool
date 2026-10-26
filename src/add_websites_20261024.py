# -*- coding: utf-8 -*-
"""为 2026-10-24 新增的 7 所江北新区小学补写官网记录（均为无独立官网）。"""
import json

PATH = "data/school_websites.json"

NEW = {
    "小学-江北新区-南京市江浦实验小学":
        "未检索到学校独立官网；该校《学校简介》发布于浦口区教师发展中心网站（pkjx.com），"
        "可视为准官方信息源，但非学校自有域名",
    "小学-江北新区-南京市浦口区实验学校（小学部）":
        "未检索到学校独立官网；公开信息主要经浦口区教师发展中心网站与区教育局渠道发布",
    "小学-江北新区-南京市金陵中学浦口分校（小学部）":
        "未检索到学校独立官网；学校「十四五」发展规划、儿童友好学校建设等材料发布于"
        "浦口区教师发展中心网站（pkjx.com），非学校自有域名",
    "小学-江北新区-南京市游府西街小学浦口分校":
        "未检索到学校独立官网；足球特色项目实施总结等材料发布于浦口区教师发展中心网站"
        "（pkjx.com）；2020 年开办信息见「浦口发布」",
    "小学-江北新区-南京市浦口区新世纪小学":
        "未检索到学校独立官网；办学沿革以南京市地方志工作办公室《时光印记》专文为准",
    "小学-江北新区-南京市浦口区行知小学":
        "未检索到学校独立官网；行知教育集团信息经人民网、新华日报、中国教育报等权威媒体发布，"
        "学校层面无独立站点",
    "小学-江北新区-南京市浦口区实验学校桥林新城分校（小学部）":
        "未检索到学校独立官网；2024 年开办信息见新华日报与浦口区教育局渠道",
}


def main():
    data = json.load(open(PATH, encoding="utf-8"))
    table = data["schools"]
    added = 0
    for key, basis in NEW.items():
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
    json.dump(data, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"新增官网记录 {added} 条，总计 {len(table)} 条")


if __name__ == "__main__":
    main()
