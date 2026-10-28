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
import os

from . import config

_CACHE = {}


def text(rel_path):
    """按相对路径（如「小学/鼓楼区/南京市琅琊路小学.md」）读档案正文，只读一次。"""
    cached = _CACHE.get(rel_path)
    if cached is None:
        with open(os.path.join(config.ROOT, rel_path), encoding="utf-8") as f:
            cached = f.read()
        _CACHE[rel_path] = cached
    return cached


def cache_size():
    """已缓存的档案数。供测试断言「每份只读一次」。"""
    return len(_CACHE)


def reset_cache():
    """清空缓存。供测试使用，正常构建不需要调用。"""
    _CACHE.clear()
