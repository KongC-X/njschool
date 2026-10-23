# -*- coding: utf-8 -*-
"""从档案正文中提取可用于对比的关键事实。

为什么需要：档案的「学校速览」是键值表，字段名各校不完全统一
（荣誉类会出现「市级」「省级」等），无法直接当结构化字段用。
但对比页只需要少数几个稳定且有决策价值的项，因此按同义词表模糊匹配。

提取失败是常态（例如小学没有投档线），调用方应把缺失显示为「—」，
不要把缺失当成 0 或默认值。
"""
import re

KV_ROW = re.compile(r"^\|\s*([^|]{1,24}?)\s*\|\s*(.+?)\s*\|\s*[ABC]\s*\|\s*$", re.M)

# 字段 → 可能的键名（前缀匹配）
FACT_KEYS = {
    "founded": ("创办时间", "建校时间", "创办年份"),
    "address": ("校址", "学校地址", "地址"),
    "feeder": ("对口初中",),
    "tuition": ("学费", "收费标准"),
    "score": ("2026 投档线", "投档线", "2026投档线"),
    "plan": ("2026 招生计划", "招生计划"),
    "classes": ("核心班型", "班型", "班级规模"),
}

# 对比页展示顺序与中文标签
FACT_LABELS = {
    "founded": "创办时间",
    "address": "校址",
    "feeder": "对口初中",
    "tuition": "学费",
    "score": "2026 投档线",
    "plan": "2026 招生计划",
    "classes": "班型",
}

_EMPTY = {"", "—", "-", "–", "未获取", "未公开", "暂无"}


def extract(text):
    """返回 {field: value}；只保留有实际内容的项。"""
    out = {}
    for m in KV_ROW.finditer(text):
        key = m.group(1).strip().strip("*").strip()
        for field, names in FACT_KEYS.items():
            if field in out:
                continue
            if any(key.startswith(n) for n in names):
                value = _clean(m.group(2))
                if value and value not in _EMPTY:
                    out[field] = value[:60]
    return out


def _clean(v):
    v = re.sub(r"<[^>]+>", "", v)
    v = re.sub(r"\*\*|`|\[[ABC]\]", "", v)
    v = re.sub(r"\s+", " ", v)
    return v.strip(" 　|")
