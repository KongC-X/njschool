# -*- coding: utf-8 -*-
"""
merge_websites.py — 合并各检索代理产出的官网核查结果，校验后写入 data/school_websites.json

输入：src/websites/[A-I].json
输出：data/school_websites.json

校验规则：
  1. 键必须是 index.json 中存在的学校 id
  2. site 必须为 http(s) 链接或 null
  3. level 必须为 A/B/C；C 级（无法证实）一律降级为 null，避免给出错误链接
  4. 同一「主机名+首段路径」被超过 8 所学校共用 → 视为可疑，全部降级

⚠ 去重铁律（不可用校名/域名相似度自动归并）：
  南师系三个域名只差一个字母，编辑距离极小但分属三所不同学校：
      nsfzsr.cn = 南师附中树人学校（初中）
      nsdfx.net = 南京师范大学附属小学（小学）
      nsfz.net  = 南师附中本部（高中）
  同理 sszsjfx.xwjy.cn（十三中锁金分校·初中）与 sjex.xwjy.cn（锁金新村第二小学·小学）
  同以「锁金」开头、标题仅差后缀，实为两校。
  故：一律按 id（学段-区-校名）精确匹配；域名只用于「同 URL 出现多次」告警，绝不据此合并条目。
  同 URL 多校只打印告警，由人工判断（可能是一个集团共用站，也可能是误配）。
"""
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date

ROOT = "/Users/kongc/WorkBuddy/南京学校"
WEBDIR = os.path.join(ROOT, "src", "websites")
OUT = os.path.join(ROOT, "data", "school_websites.json")

SHARED_DOMAIN_LIMIT = 8  # 同一「主机名 + 首段路径」共用校数上限

# site=null 的成因分类。维护动作与统计口径都不同，必须分开：
#   域名彻底退役     → 不可复活，永久无官网
#   源站下线         → 域名仍在、服务恢复后可用，需定期重试
#   平台槽位空置     → 区教育平台分配了页面但未填充/未开站，可复活
#   被抢注           → 域名已归他人（影视/博彩/配资站），永久弃用
#   内容停更         → 能打开但多年未更新，不宜推荐给家长
#   从未建站         → 该校从未有独立站
#   集团代管         → 无独立站，由集团/总校统一对外发布（无需再找、也无需建议建站）
# ⚠ 统计口径：以上均按「学校」计数，不同成因的分母不可混用、不可相加，
#   尤其「历史域名被抢注数」≠「site=null 数」——抢注域名所属学校可能另有正常站点。
STATE_OF_REASON = {
    "域名彻底退役": "none",
    "被抢注": "none",
    "从未建站": "none",
    "集团代管": "none",
    "未检索到": "none",
    "源站下线": "exists_unreachable",
    "平台槽位空置": "exists_unreachable",
    "内容停更": "stale",
}

# 判断「有官方渠道但未取得 ID」的措辞特征
CHANNEL_HINTS = ("公众号", "官微", "微信", "视频号", "企业号")


def classify_null(basis):
    """按依据措辞判定 site=null 的成因。

    实现要点（踩过的坑）：
      1. 代理若在依据里显式写了「【无站成因：<成因>｜<可修复性>】」，以成因段为准。
      2. 必须先剔除否定表述：「未被抢注」「非被抢注」若按关键词匹配会误判为「被抢注」。
      3. 顺序不能按关键词表遍历：原实现把「抢注」排在首位，导致
         「原域名被劫持 + 现槽位停更」的火瓦巷小学被错判为「被抢注」（实为内容停更）；
         「未被抢注、源站 502」的玄外附小同样被误判。
      4. 源站故障（502/upstream）是「有站但挂了」的强证据，须排在「无本校槽位」之前。
    """
    b = basis or ""
    # 1) 显式标注优先：取「成因段」（｜之前的部分）
    m = re.search(r"【无站成因[:：]\s*([^｜】]+)", b)
    if m:
        t = m.group(1)
        for kw, label in [("停更", "内容停更"), ("退役", "域名彻底退役"),
                          ("抢注", "被抢注"), ("劫持", "被抢注"),
                          ("未填充", "平台槽位空置"), ("未启用", "平台槽位空置"),
                          ("未发布", "平台槽位空置"), ("空站", "平台槽位空置"),
                          ("不可读", "平台槽位空置"), ("槽位", "平台槽位空置"),
                          ("代管", "集团代管"), ("从未", "从未建站"),
                          ("下线", "源站下线"), ("不可达", "源站下线")]:
            if kw in t:
                return label
    # 2) 剔除否定表述，避免「未被抢注」被当成抢注
    clean = b.replace("未被抢注", "").replace("非被抢注", "").replace("并非抢注", "")
    hijack = any(k in clean for k in ("被劫持", "抢注", "被占用", "影视站", "赌博站", "配资"))
    no_slot = any(k in clean for k in ("无本校槽位", "无平台槽位", "均无本校", "无可替代"))
    has_empty_slot = any(k in clean for k in ("空站", "空壳", "空模板", "未填充", "占位"))

    # 3) 按「最能解释为何不展示」的成因优先判定
    if any(k in clean for k in ("停更", "停留在", "多年未更新", "未更新")):
        return "内容停更"
    if any(k in clean for k in ("502", "超时", "timeout", "无法访问", "暂停服务",
                               "停机", "upstream", "源站已下线", "不可达")):
        return "源站下线"
    if no_slot:
        return "被抢注" if hijack else "从未建站"
    if has_empty_slot:
        return "平台槽位空置"
    if hijack:
        return "被抢注"
    if any(k in clean for k in ("退役", "已过期", "不再解析", "域名已", "下线")):
        return "域名彻底退役"
    if any(k in clean for k in ("集团代管", "总校代管", "代管")):
        return "集团代管"
    if any(k in clean for k in ("从未建", "未建站", "没有独立站", "无独立站", "未见独立官网")):
        return "从未建站"
    return "未检索到"


def parse_repair(basis):
    """解析「可修复性」三档：可复活 / 需重启 / 不可修复。

    三档混为一谈会让整改建议失真：
      可复活   —— 站坏了，修复即用，值得定期复探
      需重启   —— 域名未丢、站还在但长期停更，应恢复运营而非续费维护
      不可修复 —— 需另建站
    """
    b = basis or ""
    if "可复活" in b:
        return "可复活"
    if "需重启" in b:
        return "需重启"
    if "不可修复" in b:
        return "不可修复"
    return None


def wechat_status(wechat, basis):
    """区分「有 ID」「渠道存在但 ID 未取」「情况不明」。

    不可把 wechat=null 读作「无公众号」：核查代理普遍未提取微信号，
    但 basis 中常写明该校区有公众号在发布（如「官微」「公众号二维码」）。
    """
    if wechat:
        return "id"
    return "exists_no_id" if any(k in (basis or "") for k in CHANNEL_HINTS) else "unknown"


def domain_of(url):
    """取「主机名 + 首段路径」作为唯一性判断键。

    南京学校官网存在两种平台化形态，必须分别识别：
      1) 子域模式：njjlhw.njgljy.com（鼓楼）、zhzxfscjzx.yhjyxx.cn（雨花台）
         → 主机名即唯一标识
      2) 路径模式：www.jyjsfz.cn/xccjzx/（建邺）
         → 主机名相同，须靠首段路径区分，否则同区多校会被误判为共用同一页面
    若只按主机名统计，建邺区十余所学校会被全部降级。
    """
    m = re.match(r"https?://([^/]+)(/[^/?#]*)?", url or "")
    if not m:
        return ""
    host = m.group(1).lower().removeprefix("www.")
    seg = (m.group(2) or "").strip("/")
    return f"{host}/{seg}" if seg else host


def main():
    index = json.load(open(os.path.join(ROOT, "index.json"), encoding="utf-8"))
    valid_ids = {s["id"] for s in index["schools"]}

    raw = {}
    for fn in sorted(os.listdir(WEBDIR)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(WEBDIR, fn)
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            print(f"  ✗ {fn} 解析失败：{e}")
            continue
        for k, v in data.items():
            if k in raw:
                print(f"  ! {k} 重复出现（{fn}），保留首个")
                continue
            raw[k] = v
        print(f"  ✓ {fn}：{len(data)} 条")

    merged, dropped = {}, defaultdict(list)
    for sid, v in raw.items():
        if sid not in valid_ids:
            dropped["未知学校 id"].append(sid)
            continue
        site = v.get("site")
        wechat = v.get("wechat")
        level = (v.get("level") or "C").upper()
        basis = v.get("basis") or ""

        if site and not re.match(r"^https?://", site):
            dropped["网址格式非法"].append(f"{sid} → {site}")
            site = None
        # C 级不可证实：不展示链接
        if site and level == "C":
            dropped["C 级降级"].append(f"{sid} → {site}")
            site = None
        merged[sid] = {
            "site": site,
            "site_archived": None,           # 曾记录但当前不可用的域名，供维护期复活
            "null_reason": classify_null(basis) if not site else None,
            "repair": parse_repair(basis) if not site else None,
            "wechat": wechat,
            "wechat_status": wechat_status(wechat, basis),
            "level": level,
            "basis": basis,
        }

    # 同域名共用过多 → 可疑，降级
    dom = Counter(domain_of(v["site"]) for v in merged.values() if v["site"])
    suspicious = {d for d, c in dom.items() if c > SHARED_DOMAIN_LIMIT}
    if suspicious:
        for sid, v in merged.items():
            if v["site"] and domain_of(v["site"]) in suspicious:
                dropped["共用域名降级"].append(f"{sid} → {v['site']}")
                v["site_archived"] = v["site"]
                v["site"] = None
                v["null_reason"] = "平台槽位空置"

    # 同一 URL 被多校引用 → 仅告警，绝不自动合并（可能集团共用站，也可能误配）
    by_url = defaultdict(list)
    for sid, v in merged.items():
        if v["site"]:
            by_url[v["site"]].append(sid)
    dup_urls = {u: ids for u, ids in by_url.items() if len(ids) > 1}

    # ⚠ 判空的举证责任应重于判「有站」：
    #   曾出现「按拼音猜 4 个子域均不存在 → 判该校无官网」的错误（实际槽位是 njycxx，
    #   命名规则为「njs/nj 前缀 + 校名缩写 + xx 后缀」，猜不到不等于不存在）。
    #   因此 null 项须能说明已尝试范围；缺证据的条目单列，供二次核查。
    EVIDENCE_HINTS = ("穷举", "候选", "试了", "已试", "均未注册", "均无", "逐个", "排查")
    weak_null = [sid for sid, v in merged.items()
                 if not v["site"] and not any(k in (v["basis"] or "") for k in EVIDENCE_HINTS)]

    # 存在性状态：区分「无官网」与「有官网但当前不可达」
    for v in merged.values():
        if v["site"]:
            v["site_state"] = "ok"
        else:
            v["site_state"] = STATE_OF_REASON.get(v["null_reason"], "none")

    def recount(payload_schools):
        vals = payload_schools.values()
        by_reason, by_state, by_repair = Counter(), Counter(), Counter()
        for v in vals:
            if not v["site"]:
                by_reason[v["null_reason"]] += 1
                if v.get("repair"):
                    by_repair[v["repair"]] += 1
            by_state[v["site_state"]] += 1
        return {
            "total": len(payload_schools),
            "with_site": sum(1 for v in vals if v["site"]),
            "site_state": dict(by_state),
            "wechat_id": sum(1 for v in vals if v["wechat_status"] == "id"),
            "wechat_exists_no_id": sum(1 for v in vals if v["wechat_status"] == "exists_no_id"),
            "wechat_unknown": sum(1 for v in vals if v["wechat_status"] == "unknown"),
            "null_by_reason": dict(by_reason),
            "null_by_repair": dict(by_repair),
        }

    counts = recount(merged)
    payload = {
        "updated": date.today().isoformat(),
        "note": ("官网地址经检索核查并全量体检。统计按「学校」计数，各成因分母不同、不可相加："
                 "「历史域名被抢注」数 ≠ 「无官网」数。wechat=null 一律读作「未取得可确认 ID」，"
                 "不代表该校无官方渠道。"),
        "counts": counts,
        "schools": {k: merged[k] for k in sorted(merged)},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(payload, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\n已写入 {OUT}")
    print(f"  覆盖 {counts['total']} 所")
    print(f"  可用官网 {counts['with_site']}；存在性状态 {counts['site_state']}")
    print(f"  公众号：有 ID {counts['wechat_id']}、渠道存在未取 ID {counts['wechat_exists_no_id']}、"
          f"情况不明 {counts['wechat_unknown']}")
    print(f"  无官网成因：{counts['null_by_reason']}")
    for reason, items in dropped.items():
        print(f"  降级/丢弃 [{reason}] {len(items)} 条")
        for i in items[:5]:
            print(f"      - {i}")
    if suspicious:
        print(f"  可疑共用域名：{sorted(suspicious)}")
    if dup_urls:
        print(f"  ⚠ 同一 URL 被多校引用（未合并，请人工判断）{len(dup_urls)} 组：")
        for u, ids in list(dup_urls.items())[:8]:
            print(f"      {u} ← {len(ids)} 校：{ids[:3]}")
    if weak_null:
        print(f"  ⚠ 判空缺穷举证据 {len(weak_null)} 条（建议二次核查，不代表结论错误）：")
        for sid in weak_null[:10]:
            print(f"      {sid}")


if __name__ == "__main__":
    main()
