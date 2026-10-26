# -*- coding: utf-8 -*-
"""把 gen_jiangning_data4 的 32 所学校批量写入 build_index.py 的 SCHOOLS 列表。

做法：读 build_index.py 源码文本，在 `SCHOOLS = [` 对应列表的结尾 `]` 前插入新条目行，
再写回。只追加未被收录的条目，可重复执行。
"""
import importlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "src", "build_index.py")

# 乡镇校（未列入区级一览）归第三梯队，其余城区校第二梯队
TOWN_PREFIX = "南京市江宁区"


def tier_of(s):
    return "江宁第三梯队" if not s.get("entry") else "江宁第二梯队"


def line_of(s):
    name = s["name"]
    short = re.sub(r"^南京市(江宁区)?", "", name).replace("（", "(").replace("）", ")")
    tag = s["tagline"].replace('"', "”")
    if len(tag) > 100:
        tag = tag[:100].rstrip("，；、") + "…"
    tier = tier_of(s)
    return f'    ("{name}", "{short}", "江宁区", "小学", "公办", "{tier}",\n     "{tag}"),'


def main():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    data = importlib.import_module("gen_jiangning_data4").SCHOOLS

    src = open(IDX, encoding="utf-8").read()
    # 找到 SCHOOLS 列表的结束位置（列表中最后一行以 "]"\n 结束）
    start = src.index("SCHOOLS = [")
    end = src.index("\n]\n", start) + 1
    head, body, tail = src[:start], src[start:end], src[end:]

    added, skipped = [], []
    for s in data:
        key = f'("{s["name"]}"'
        if key in body:
            skipped.append(s["name"])
            continue
        added.append(line_of(s))

    if added:
        body = body.rstrip("\n]") + "\n" + "\n".join(added) + "\n]\n"
        open(IDX, "w", encoding="utf-8").write(head + body + tail)

    print(f"新增 {len(added)} 条，跳过已存在 {len(skipped)} 条")
    for n in skipped:
        print("  已存在：", n)


if __name__ == "__main__":
    main()
