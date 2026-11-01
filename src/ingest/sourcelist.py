# -*- coding: utf-8 -*-
"""源清单（data/sources.yaml）的解析与校验。

为什么单独一份配置：抓取目标此前散落在三处——153/188 个学校域名在
school_websites.json、区级平台的域名规律写在 README 的散文里、市级入口
靠记忆。采集器要按源配置不同的频率与解析器，这些都必须是数据而不是代码，
否则加一个区就得改程序。

为什么不用 PyYAML：项目只锁了 markdown / Jinja2 / openpyxl，没有 YAML 依赖，
为一份两层配置引入新依赖不划算。这里只支持一个受控子集：

    sources:                      # 这一行可省略
      - id: bureau:city-edu       # 「- 」开头即新条目
        kind: bureau              # 续行按 key: value 归属当前条目
        entry: https://...
        note: "含：冒号的中文值"   # 值用 JSON 字符串，与档案 front-matter 同一规则

规则刻意收窄，好处是行为完全可预期：不做多行值、不做嵌套、不做行内注释。
需要写长说明就写在文件头注释里。`#` 只在整行开头时才是注释——值里出现 #
不会被截断（URL 的锚点、说明里的井号都不会坏）。
"""
import json
import os

from pipeline import config

SOURCES = os.path.join(config.ROOT, "data", "sources.yaml")

# 源类型：school 为学校官网（S2 半结构），bureau 为主管部门（S1 强结构）
KINDS = ("school", "bureau")

# 抓取档位，见方案第四章「按信息半衰期分档」
TIERS = ("T0", "T1", "T2", "T3", "T4")
TIER_DESC = {
    "T0": "政策窗口期每日、平峰每周",
    "T1": "每周一次",
    "T2": "每日探活",
    "T3": "每学期一次",
    "T4": "仅手动触发",
}

# 解析器：决定拿到页面后按什么方式抽字段
PARSERS = ("announcement_list", "gov_attachment", "score_table", "manual")
PARSER_DESC = {
    "announcement_list": "取列表页的公告标题与链接",
    "gov_attachment": "取正文中的 PDF/表格附件",
    "score_table": "按固定表头抽投档线/计划数",
    "manual": "仅登记，不做程序化抓取",
}

STATUSES = ("verified", "unverified")

REQUIRED = ("id", "kind", "name", "tier", "parser", "status")


def _value(raw):
    """解析单个值。带引号的按 JSON 串解（与 front-matter 规则一致）。"""
    raw = raw.strip()
    if raw[:1] == '"':
        try:
            return json.loads(raw)
        except ValueError:
            return raw.strip('"')
    return raw


def parse(text):
    """把配置文本解析为条目列表。解析失败的行走不通就把该行丢掉，交给校验层报。"""
    items = []
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s == "sources:":
            continue
        if s.startswith("- "):
            cur = {}
            items.append(cur)
            s = s[2:].strip()
        if cur is None or ":" not in s:
            continue
        key, val = s.split(":", 1)
        cur[key.strip()] = _value(val)
    return items


def load(path=None):
    """读取并解析源清单。文件不存在时返回空列表，由调用方决定是否报错。"""
    path = path or SOURCES
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return parse(f.read())


def validate(items):
    """校验字段、枚举与唯一性，返回问题描述列表（空表示通过）。

    刻意把「entry 为空」与「status=unverified」绑在一起：
    没有可靠地址的源允许登记，但必须显式标为待核，采集器会跳过它。
    这样既能保住「知道有这么个源」这条信息，又不会让采集器去猜地址。
    """
    bad = []
    seen = {}
    for i, it in enumerate(items, 1):
        where = f"第 {i} 条「{it.get('id') or it.get('name') or '?'}」"

        for key in REQUIRED:
            if not it.get(key):
                bad.append(f"{where}：缺少必填字段 {key}")

        sid = it.get("id", "")
        if sid:
            if sid in seen:
                bad.append(f"{where}：id 与第 {seen[sid]} 条重复：{sid}")
            seen[sid] = i
            if sid.startswith("school:") and it.get("kind") != "school":
                bad.append(f"{where}：id 前缀 school: 与 kind={it.get('kind')} 不符")
            if sid.startswith("bureau:") and it.get("kind") != "bureau":
                bad.append(f"{where}：id 前缀 bureau: 与 kind={it.get('kind')} 不符")

        if it.get("kind") and it["kind"] not in KINDS:
            bad.append(f"{where}：kind 非法（{it['kind']}），应为 {KINDS}")
        if it.get("tier") and it["tier"] not in TIERS:
            bad.append(f"{where}：tier 非法（{it['tier']}），应为 {TIERS}")
        if it.get("parser") and it["parser"] not in PARSERS:
            bad.append(f"{where}：parser 非法（{it['parser']}），应为 {PARSERS}")
        if it.get("status") and it["status"] not in STATUSES:
            bad.append(f"{where}：status 非法（{it['status']}），应为 {STATUSES}")

        entry = it.get("entry") or ""
        if entry and not entry.startswith(("http://", "https://")):
            bad.append(f"{where}：entry 必须是 http(s) 地址：{entry}")
        if not entry and it.get("status") == "verified":
            bad.append(f"{where}：标为 verified 但没有 entry 地址")
        if entry and it.get("status") == "unverified":
            bad.append(f"{where}：有地址却标为 unverified，核实后应改为 verified")
    return bad


def active(items):
    """可参与采集的源：已核实且有地址。界面与采集器都只看这一份。"""
    return [it for it in items if it.get("status") == "verified" and it.get("entry")]


def summary(items):
    """按 kind / tier 汇总，供 dry-run 与文档引用。"""
    out = {"total": len(items), "active": len(active(items)),
           "by_kind": {}, "by_tier": {}, "unverified": 0}
    for it in items:
        out["by_kind"][it.get("kind", "?")] = out["by_kind"].get(it.get("kind", "?"), 0) + 1
        out["by_tier"][it.get("tier", "?")] = out["by_tier"].get(it.get("tier", "?"), 0) + 1
        if it.get("status") == "unverified":
            out["unverified"] += 1
    return out
