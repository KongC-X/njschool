# -*- coding: utf-8 -*-
"""只校验不写盘：CI 的快速门禁，也便于本地改完档案后先自查。

退出码：0 通过；1 存在阻断级错误。
"""
import sys

from pipeline import load
from pipeline.schema import (Report, validate_counts, validate_pages,
                             validate_schools, validate_websites)


def main():
    index = load.load_index()
    webmap, _, _ = load.load_websites()
    schools = load.load_schools(index, webmap)
    pages = load.load_pages()
    md_total = load.count_md_files()

    rep = Report()
    validate_schools(schools, index.get("districts", []), rep)
    validate_websites(schools, rep)
    validate_counts(schools, md_total, rep)
    validate_pages(pages, rep)

    rep.dump()
    print(f"校验完成：{len(schools)} 所学校 / {md_total} 份档案 / {len(pages)} 个内容页"
          f" → 错误 {len(rep.errors)}，警告 {len(rep.warnings)}")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
