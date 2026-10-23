# -*- coding: utf-8 -*-
"""站点构建入口（薄封装）。

实际逻辑在 pipeline/ 各模块中，本文件只负责把退出码传给 shell，
使 `make site` 与历史的 `python src/build_website.py` 调用方式都能继续工作。

环境变量：
  NJ_BASE_URL  站点绝对地址；设置后生成 sitemap 与 canonical
"""
import sys

from pipeline.main import run

if __name__ == "__main__":
    sys.exit(run())
