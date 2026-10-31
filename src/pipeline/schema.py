# -*- coding: utf-8 -*-
"""数据模型与构建前校验。

为什么单独立一层：
  此前字段缺失要到渲染阶段才以 KeyError 暴露，且 204 份档案、index.json、
  官网数据三者之间的一致性全靠人工 grep。本模块把这些问题挡在构建第一步，
  失败即中断，避免把错误发布出去。

校验分两级：
  error   —— 阻断构建（数据错了不能上线）
  warning —— 仅提示（可接受的缺失，例如部分学校无官网记录）
"""
import os
import re

from . import source
from dataclasses import dataclass, field

from . import config


class Report:
    """收集校验结果。"""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, where, msg):
        self.errors.append(f"{where}：{msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}：{msg}")

    @property
    def ok(self):
        return not self.errors

    def dump(self, verbose=True):
        if verbose:
            for w in self.warnings:
                print(f"  ! {w}")
            for e in self.errors:
                print(f"  ✗ {e}")
        return self.ok


@dataclass
class Website:
    """官网/公众号记录。"""
    site: str = None
    site_archived: str = None
    site_state: str = "none"
    null_reason: str = None
    repair: str = None
    wechat: str = None
    wechat_status: str = "unknown"
    verify: str = None
    basis: str = ""
    level: str = "C"

    @property
    def is_unreachable_at_build(self):
        return self.verify == "unreachable_at_build"


@dataclass
class School:
    """一所学校的完整视图：索引字段 + 档案正文 + 官方渠道。"""
    id: str
    name: str
    district: str
    level: str
    type: str
    file: str
    tier: str = ""
    tagline: str = ""
    short: str = ""
    url: str = ""
    website: Website = field(default_factory=Website)

    @property
    def slug(self):
        """详情页文件名：学段-校名（学段前缀避免跨学段重名）。"""
        return f"{self.level}-{self.name}"


def validate_schools(schools, districts, rep: Report):
    """逐校校验必填字段与枚举值。"""
    seen_ids = set()
    for s in schools:
        where = f"学校「{s.name}」"

        if not s.name or not s.name.strip():
            rep.error(where, "缺少校名")
        if not s.district:
            rep.error(where, "缺少行政区")
        elif s.district not in districts:
            rep.error(where, f"行政区「{s.district}」不在已知列表内")
        if s.level not in config.LEVELS:
            rep.error(where, f"学段「{s.level}」非法，应为 {config.LEVELS}")
        if s.type not in config.TYPES:
            rep.error(where, f"办学性质「{s.type}」非法，应为 {config.TYPES}")
        if not s.tagline or len(s.tagline.strip()) < 8:
            rep.error(where, "一句话定位缺失或过短（<8 字）")
        if not s.tier:
            rep.warn(where, "缺少梯队定位")
        if s.id in seen_ids:
            rep.error(where, f"id 重复：{s.id}")
        seen_ids.add(s.id)

        # 档案文件必须存在且包含「数据缺口」章节
        path = os.path.join(config.ROOT, s.file)
        if not os.path.isfile(path):
            rep.error(where, f"档案文件不存在：{s.file}")
            continue
        text = source.text(s.file)
        if "数据缺口" not in text:
            rep.error(where, "档案缺少「数据缺口」章节（信度披露要求）")
        if len(text) < 1500:
            rep.warn(where, f"档案篇幅偏短（{len(text)} 字符），可能未写完")


def validate_websites(schools, rep: Report):
    """校验官网记录：URL 格式、枚举值、与学校的一一对应。"""
    for s in schools:
        w = s.website
        where = f"官网记录「{s.name}」"
        if w.site:
            if not re.match(r"^https?://[^\s\"'<>]+$", w.site):
                rep.error(where, f"官网地址格式非法：{w.site}")
            if w.site_state != "ok":
                rep.warn(where, f"有官网地址但状态为 {w.site_state}")
        else:
            if w.site_state == "ok":
                rep.error(where, "状态为 ok 但没有官网地址")
            if w.site_state == "none" and not w.null_reason:
                rep.warn(where, "无官网且未记录成因")
        if w.site_state not in config.SITE_STATES:
            rep.error(where, f"站点状态非法：{w.site_state}")
        if w.null_reason and w.null_reason not in config.NULL_REASONS:
            rep.error(where, f"无站成因非法：{w.null_reason}")
        if w.wechat_status not in config.WECHAT_STATUS:
            rep.error(where, f"公众号状态非法：{w.wechat_status}")
        if w.wechat and w.wechat_status != "id":
            rep.warn(where, "有公众号名称但状态不是 id")


def validate_web_counts(cached, derived, rep: Report):
    """文件里的 counts 缓存必须与逐校记录现算的结果一致。

    这个字段只有联网跑的 merge_websites.py 会重算，补录脚本不更新它，
    于是会冻结在某一天。实测曾差 35 所，导致 about 页把自己的官网覆盖率
    从 34.5% 写成 28%。
    """
    if not cached:
        return
    for key in ("total", "with_site"):
        if key in cached and cached[key] != derived.get(key):
            rep.warn("官网记录",
                     f"counts.{key}={cached[key]} 与逐校记录现算的 {derived.get(key)} 不符，"
                     f"删除该字段即可（构建期已改为现算）")


def validate_counts(schools, md_total, rep: Report):
    """档案文件总数必须与索引条目数一致（防止漏登记或残留孤儿文件）。"""
    if len(schools) != md_total:
        rep.error("索引", f"索引 {len(schools)} 条，但档案目录下有 {md_total} 个 md 文件，"
                          f"请重跑 build_index.py 或检查是否有未登记档案")
    by_level = {}
    for s in schools:
        by_level[s.level] = by_level.get(s.level, 0) + 1
    for lv in config.LEVELS:
        if not by_level.get(lv):
            rep.error("索引", f"学段「{lv}」没有任何学校")


def validate_pages(pages, rep: Report):
    """内容页（政策、更名等）校验：必须有标题与更新日期。"""
    for key, p in pages.items():
        if not p.get("title"):
            rep.error(f"内容页「{key}」", "缺少 title")
        if not p.get("updated"):
            rep.warn(f"内容页「{key}」", "缺少 updated 日期")
        if not p.get("html"):
            rep.error(f"内容页「{key}」", "正文为空")


def validate_policy_sync(pages, rep: Report):
    """首页「今年主要变化」的条数必须与政策页表格一致。

    首页那份是手写的短文案，政策页那张表是完整清单——两者曾经对不上：
    首页 4 条、政策页 5 条，而首页缺的恰是「取消学区房年限限制」和
    「长幼随学」。数字（首页统计条的「N 项」）已改为从政策页现算，
    这里再加一道守卫，防止文案本身再次漂移。
    """
    policy = pages.get("policy-2026") or {}
    home = pages.get("home-highlights") or {}
    if not policy or not home:
        return
    m = re.search(r"<tbody>(.*?)</tbody>", policy.get("html", ""), re.S)
    n_policy = len(re.findall(r"<tr>", m.group(1))) if m else 0
    n_home = home.get("html", "").count("<li>")
    if n_policy and n_home and n_policy != n_home:
        rep.warn("内容页「home-highlights」",
                 f"首页列了 {n_home} 条变化，政策页有 {n_policy} 条；"
                 f"两处口径不一致，家长会发现首页漏项")
