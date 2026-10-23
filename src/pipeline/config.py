# -*- coding: utf-8 -*-
"""构建流水线公共配置：路径与常量。

所有模块只从这里取路径，避免各自拼字符串导致路径漂移。
"""
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INDEX = os.path.join(ROOT, "index.json")
WEBFILE = os.path.join(ROOT, "data", "school_websites.json")
ASSETS = os.path.join(ROOT, "assets")
TEMPLATES = os.path.join(ROOT, "templates")
CONTENT_PAGES = os.path.join(ROOT, "content", "pages")
SITE = os.path.join(ROOT, "site")

TODAY = date.today().isoformat()
BASE_URL = (os.environ.get("NJ_BASE_URL") or "").rstrip("/")

LEVELS = ["小学", "初中", "高中"]
LEVEL_DESC = {
    "小学": "小学阶段无官方升学率指标，各档案以「对口初中 + 对口初中中考表现」间接体现出口。",
    "初中": "初中中考成绩多数无官方公示，高分段与四星率多来自家长圈口径，均标 `[C]`。",
    "高中": "高中以 2026 年投档线为核心参照，投档线已对照市招考院公布值。",
}
TYPES = ["公办", "民办"]

# 官网记录中的枚举值（与 merge_websites.py 保持一致）
SITE_STATES = ["ok", "exists_unreachable", "stale", "none"]
NULL_REASONS = ["源站下线", "平台槽位空置", "内容停更", "被抢注",
                "域名彻底退役", "从未建站", "集团代管", "未检索到"]
WECHAT_STATUS = ["id", "exists_no_id", "unknown"]
REPAIR = ["可复活", "需重启", "不可修复"]
