# -*- coding: utf-8 -*-
"""档案正文的统一读取入口（进程内缓存）。

为什么要单独一层：同一份档案在三个地方被读——

  1. `schema.validate_schools` 读全文，只为检查有没有「数据缺口」章节
  2. `load.load_body` 渲染详情页
  3. `render` 生成 schools-data.js / schools-compare.js 时要解析 facts

此前三处各自 `open()`，实测 545 份文件被读 **1640 次（冗余 1090 次）**。
性能上不算大问题（单次约 0.15ms），真正的毛病是：

  · 校验层在做 I/O——它本该只判断数据结构，失败原因却会混进 I/O 错误
  · 三处各自假设「文本已加载」，改一处容易漏掉另两处
  · `render._md_text` 用可变默认参数 `_cache={}` 当缓存，
    那是跨调用共享的全局状态，同一个进程里多次构建会串味

为什么不做成 `schema` 直接 import `load`：`load` 已经 `from .schema import School`，
反过来 import 会形成循环。这一层只依赖 config，谁都能用。
"""
import json
import os
import re

from . import config

_CACHE = {}

# front-matter 只认「文件第一行就是 ---」这一种形式。
# 不能用全文或 split("---") 去切：档案正文开头第 5 行左右就有一条 `---` 分隔线，
# 545 份全部如此。只要匹配位置不对，就会把「一句话定位」以下的整段正文
# 误当成元数据吞掉——页面上表现为档案只剩标题。
FM_OPEN = re.compile(r"\A---[ \t]*\r?\n")
FM_CLOSE = re.compile(r"^---[ \t]*\r?$", re.M)


def raw(rel_path):
    """原始全文（含 front-matter）。只在需要写回或诊断时用。"""
    cached = _CACHE.get(rel_path)
    if cached is None:
        with open(os.path.join(config.ROOT, rel_path), encoding="utf-8") as f:
            cached = f.read()
        _CACHE[rel_path] = cached
    return cached


def split_front_matter(text):
    """拆成 (元数据 dict, 正文)。没有合法 front-matter 时返回 ({}, 原文)。

    值一律按 JSON 字符串写（构建期用 json.dumps 生成），所以这里用 json.loads 解析。
    这么做是为了不引入 PyYAML 依赖，同时避开 YAML 的引号/冒号转义坑——
    tagline 里有中文引号、括号、冒号和 ** 粗体标记，裸写会解析出错。
    """
    m = FM_OPEN.match(text)
    if not m:
        return {}, text
    end = FM_CLOSE.search(text, m.end())
    if not end:
        # 只有开头没有结尾：视为正文里的一条水平线，不当元数据处理。
        return {}, text

    meta = {}
    for line in text[m.end():end.start()].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        val = val.strip()
        if val[:1] == '"':
            try:
                val = json.loads(val)
            except ValueError:
                val = val.strip('"')      # 单行内非法 JSON：退化为去引号
        meta[key.strip()] = val
    return meta, text[end.end():].lstrip("\r\n")


def text(rel_path):
    """按相对路径读档案**正文**（已剥离 front-matter），只读一次。

    正文收口在这一层是刻意的：渲染、校验、facts 抽取、信度统计、检索索引
    共 10 处都经由本函数读档案。若让各调用方自行剥离，漏掉任何一处，
    YAML 就会直接显示在页面上。
    """
    return split_front_matter(raw(rel_path))[1]


def meta(rel_path):
    """档案的元数据（front-matter）。缺失时返回空 dict，由 schema 层决定是否报警。"""
    return split_front_matter(raw(rel_path))[0]


def cache_size():
    """已缓存的档案数。供测试断言「每份只读一次」。"""
    return len(_CACHE)


def reset_cache():
    """清空缓存。供测试使用，正常构建不需要调用。"""
    _CACHE.clear()
