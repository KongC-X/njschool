# -*- coding: utf-8 -*-
"""采集层（ingest）。

与 pipeline 的分工：
  pipeline  把「已有内容」渲染成站点，只读不写数据
  ingest    从外部抓取「将会成为内容」的东西，产出变更提议，由人合并

本层永远不直接改写档案。它只做四件事：抓取（fetch）、抽取（extract）、
比对（differ）、产出提议（changeset）。写 md 是人的动作。

入口：`python3 src/ingest/run.py --dry-run`（或 make ingest）
"""
