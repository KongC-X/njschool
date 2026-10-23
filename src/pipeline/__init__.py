# -*- coding: utf-8 -*-
"""站点构建流水线。

分层：
  config   路径与常量
  schema   数据模型与校验（失败即中断）
  load     读取内容并装配对象
  mdtext   Markdown 渲染与目录
  render   模板装配
  check    产物结构性检查
  main     编排

入口：`python src/build_website.py`（或 make site）
"""
