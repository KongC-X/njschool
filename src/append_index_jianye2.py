# -*- coding: utf-8 -*-
"""建邺第 2 批 6 所：批量写索引 + 补官网记录。"""
import importlib, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "src", "build_index.py")
WEB = os.path.join(ROOT, "data", "school_websites.json")
TODAY = "2026-10-25"

T1 = {"高庙路校区", "第二附属小学", "金陵中学附属小学"}
T3 = {"湖西街小学"}


def tier_of(name):
    if "湖西街小学" in name:
        return "建邺第三梯队"
    for k in T1:
        if k in name:
            return "建邺第一梯队（公办）"
    return "建邺第二梯队"


def short_of(name):
    s = re.sub(r"^南京市", "", name)
    s = re.sub(r"^南京外国语学校河西初级中学", "南外河西", s)
    s = re.sub(r"^金陵中学", "金陵中学", s)
    return s


def line_of(s):
    tag = s["tagline"].replace("**", "")
    if len(tag) > 100:
        tag = tag[:100].rstrip("，；、") + "…"
    return (f'    ("{s["name"]}", "{short_of(s["name"])}", "建邺区", "小学", "公办", '
            f'"{tier_of(s["name"])}",\n     "{tag}"),')


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    data = importlib.import_module("gen_jianye_nanwai_data").SCHOOLS
    src = open(IDX, encoding="utf-8").read()
    start = src.index("SCHOOLS = [")
    end = src.index("\n]\n", start)
    body = src[start:end]
    added = [line_of(s) for s in data if f'("{s["name"]}"' not in body]
    if added:
        tail = body.rstrip()
        while tail.endswith("]"):
            tail = tail[:-1].rstrip()
        new = tail + "\n\n    # --- 建邺区 南外系/金陵中学系/湖西街（2026-10-25 第2批）---\n" + \
              "\n".join(added) + "\n]\n"
        open(IDX, "w", encoding="utf-8").write(src[:start] + new + src[end + 3:])
    print(f"[索引] 新增 {len(added)} 条")

    doc = json.load(open(WEB, encoding="utf-8"))
    table = doc["schools"]
    n = 0
    for s in data:
        key = f"小学-建邺区-{s['name']}"
        if key in table:
            continue
        table[key] = {"site": None, "site_archived": None, "null_reason": "未检索到",
                      "repair": None, "wechat": None, "wechat_status": "unknown",
                      "level": "C", "site_state": "none",
                      "basis": "未检索到独立官网；施教区见建邺区 2026 年小学招生办法附件1"}
        n += 1
    doc["updated"] = TODAY
    json.dump(doc, open(WEB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[官网] 新增 {n} 条，总计 {len(table)} 条")


if __name__ == "__main__":
    main()
