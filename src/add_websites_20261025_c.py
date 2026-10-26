# -*- coding: utf-8 -*-
"""为 gen_jiangning_data4 的 32 所学校批量补官网记录（均未检索到独立站点）。"""
import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "school_websites.json")
TODAY = "2026-10-25"

BASIS = {
    "town": "未检索到独立官网或江宁教育服务平台（jnjy.net.cn）站群分站；"
            "学校施教区亦未在区级一览公示，公开信息极少",
    "city": "未检索到独立官网或江宁教育服务平台（jnjy.net.cn）站群分站；"
            "施教区见区教育局实施细则正文的施教区一览，学校本体信息未公开",
}


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    data = importlib.import_module("gen_jiangning_data4").SCHOOLS

    doc = json.load(open(PATH, encoding="utf-8"))
    table = doc["schools"]
    added = 0

    for s in data:
        key = f"小学-江宁区-{s['name']}"
        if key in table:
            continue
        kind = "city" if s.get("entry") else "town"
        table[key] = {
            "site": None, "site_archived": None, "null_reason": "未检索到",
            "repair": None, "wechat": None, "wechat_status": "unknown",
            "level": "C", "basis": BASIS[kind], "site_state": "none",
        }
        added += 1

    doc["updated"] = TODAY
    json.dump(doc, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"新增官网记录 {added} 条，总计 {len(table)} 条")


if __name__ == "__main__":
    main()
