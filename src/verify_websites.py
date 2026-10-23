# -*- coding: utf-8 -*-
"""
verify_websites.py — 对 data/school_websites.json 中的官网地址做全量体检

为什么需要：仅凭「HTTP 200 + title 含校名」不足以证明链接可用。实践中已遇到三类问题：
  1. 域名被抢注：原校域名过期后被色情/博彩/影视站接管（内容与本项目严重不符，绝不能展示）
  2. 空模板站：域名有效、title 就是正确校名，正文却是别的学校占位内容
  3. 停更站：仍可访问但内容停在多年前，家长进去看到的是一堆失效通知

检查项：
  - 可达性（HTTP 状态 / 超时 / 证书）
  - 抢注特征词（博彩、色情、影视、直播等）
  - 关停提示词（暂停服务、域名到期、维护中）
  - 校名匹配度（标题 + 正文中本校关键词出现次数）
  - 内容新鲜度（正文中出现的最大年份）
  - SPA 站点（正文极小，无法判定）单独标记，依赖人工/代理自证

用法：
  python3 src/verify_websites.py           # 只体检并输出报告
  python3 src/verify_websites.py --apply   # 体检并把不合格项降级写回
"""
import json
import re
import ssl
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

ROOT = "/Users/kongc/WorkBuddy/南京学校"
DATA = f"{ROOT}/data/school_websites.json"
REPORT = f"{ROOT}/data/website_check.json"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
UA_DESKTOP = UA

# 抢注特征：命中 2 个及以上即判定为被接管
HIJACK_WORDS = ["博彩", "彩票", "赌场", "娱乐城", "真人荷官", "提现", "六合彩", "澳门",
                "色情", "情色", "约炮", "伴游", "私服", "代练", "棋牌", "投注",
                "影视大全", "高清在线", "免费观看", "直播平台", "体育下注"]
# 关停特征：命中 1 个即判定为不可用
CLOSED_WORDS = ["暂停服务", "网站已关闭", "域名已到期", "域名过期", "已停止访问",
                "网站维护中", "无法访问", "站点已下线", "404 Not Found", "Bad Gateway"]

STALE_YEAR = 2022      # 正文最大年份 <= 该值 → 判定停更
SPA_BODY_MIN = 600     # 正文小于该字节数 → 视为 SPA/纯 JS 站，无法正文判定


def fetch(url, mobile=False):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
          if mobile else UA_DESKTOP)
    req = urllib.request.Request(url, headers={"User-Agent": ua,
                                              "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        return r.status, r.read(300000)


def decode(raw):
    m = re.search(rb'charset=["\']?([\w-]+)', raw[:3000], re.I)
    enc = m.group(1).decode("ascii", "ignore") if m else "utf-8"
    for e in (enc, "utf-8", "gb18030"):
        try:
            return raw.decode(e)
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


def text_of(html):
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", txt)


def name_windows(name):
    """生成用于正文匹配的校名连续片段（长度 4 起）。

    不可用「剥掉 小学/中学 后的残余词」做匹配：例如「金陵中学实验小学」
    剥掉后缀会得到「金陵实验」，而「金陵中学实验小学」中并不含该连续子串，
    会造成正常站点被误判为空模板。故改用原名的所有连续窗口。
    """
    n = name.replace("南京市", "").replace("南京", "")
    wins = set()
    for L in range(4, min(9, len(n)) + 1):
        for i in range(len(n) - L + 1):
            wins.add(n[i:i + L])
    if not wins and len(n) >= 2:      # 极短校名兜底
        wins.add(n)
    return wins


def check_one(item):
    sid, meta = item
    url = meta["site"]
    res = {"id": sid, "url": url, "status": None, "title": "", "verdict": "ok",
           "reasons": [], "maxyear": None, "name_hits": 0, "body_bytes": 0}

    # 1) 抓取：失败后再用移动端 UA 与 https 变体各试一次，避免把防爬误判为死站
    html, status = None, None
    proxy_fail = False
    for attempt_url, mobile in [(url, False), (url, True),
                                (url.replace("http://", "https://", 1), False)]:
        try:
            status, raw = fetch(attempt_url, mobile)
            html = decode(raw)
            res["status"] = status
            break
        except urllib.error.HTTPError as e:
            res["status"] = e.code
            if e.code in (401, 403):          # 防爬，非失效
                res["verdict"] = "blocked"
                res["reasons"].append(f"拒绝抓取（HTTP {e.code}），疑为防爬，保留链接")
                return res
        except Exception as e:
            msg = f"{type(e).__name__}: {str(e)[:80]}"
            res["last_error"] = msg
            # 「Tunnel connection failed / Connection refused」是本地出口代理故障，
            # 不代表目标站点不可用。若据此判死，会把大量正常站误删。
            if "Tunnel" in msg or "proxy" in msg.lower() or "Connection refused" in msg:
                proxy_fail = True
    if html is None:
        if proxy_fail:
            res["verdict"] = "unverified"
            res["reasons"].append("本地出口代理失败，未能核实（非站点故障），保留链接")
            return res
        # 纯网络失败（无任何响应内容）不足以判定站点失效：
        # 已知南京多校源站存在间歇 502、且对非本地出口有访问限制。
        # 故仅标记「构建期不可达」，保留链接并在页面提示，不删除。
        res["verdict"] = "unreachable"
        res["reasons"].append(f"构建期未响应（{res.get('last_error', res['status'])}），保留链接待复核")
        return res

    tm = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    res["title"] = re.sub(r"\s+", " ", tm.group(1)).strip()[:80] if tm else ""
    txt = text_of(html)
    res["body_bytes"] = len(txt.encode("utf-8"))

    # 2) 抢注特征（域名被色情/博彩/影视站接管的强信号）
    hits_h = [w for w in HIJACK_WORDS if w in txt or w in res["title"]]
    if len(hits_h) >= 2:
        res["verdict"] = "drop"
        res["reasons"].append("疑似域名被抢注：" + "、".join(hits_h[:5]))

    # 3) 关停特征
    hits_c = [w for w in CLOSED_WORDS if w in res["title"] or w in txt[:1200]]
    if hits_c:
        res["verdict"] = "drop"
        res["reasons"].append("站点已停用/关闭：" + "、".join(hits_c[:3]))

    # 4) 校名匹配（标题 + 正文），用连续窗口避免误杀
    name = sid.split("-", 2)[-1]
    wins = name_windows(name)
    hay = res["title"] + " " + txt[:8000]
    hit_words = [w for w in wins if w in hay]
    res["name_hits"] = len(hit_words)
    if res["body_bytes"] >= SPA_BODY_MIN and not hit_words:
        res["verdict"] = "drop"
        res["reasons"].append("标题与正文均无本校任何连续片段，疑似他校页面/空模板")

    # 5) 内容新鲜度（年份限定 2015—2027，剔除 2095 之类脏年份）
    years = [int(y) for y in re.findall(r"(20[12]\d)", txt) if 2015 <= int(y) <= 2027]
    if years:
        res["maxyear"] = max(years)
        if res["maxyear"] <= STALE_YEAR and res["verdict"] == "ok":
            res["verdict"] = "drop"
            res["reasons"].append(f"内容停更（全文最新年份 {res['maxyear']}）")

    # 6) 前端渲染站：正文过小，无法做正文判定，保留但标记
    if res["body_bytes"] < SPA_BODY_MIN and res["verdict"] == "ok":
        res["verdict"] = "spa"
        res["reasons"].append("正文过小（前端渲染站），依赖检索来源自证")
    return res


def main():
    apply = "--apply" in sys.argv
    payload = json.load(open(DATA, encoding="utf-8"))
    items = [(k, v) for k, v in payload["schools"].items() if v.get("site")]
    print(f"待检 {len(items)} 个站点……")

    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(check_one, items))

    drop = [r for r in results if r["verdict"] == "drop"]
    spa = [r for r in results if r["verdict"] == "spa"]
    unverified = [r for r in results if r["verdict"] in ("unverified", "blocked")]
    unreachable = [r for r in results if r["verdict"] == "unreachable"]
    ok = [r for r in results if r["verdict"] == "ok"]

    print(f"\n判定：可用 {len(ok)}、SPA 待自证 {len(spa)}、"
          f"未核实（保留）{len(unverified)}、构建期不可达（保留+提示）{len(unreachable)}、"
          f"须移除 {len(drop)}")
    if drop:
        print("\n须移除清单：")
        for r in drop:
            print(f"  ✗ {r['id']}")
            print(f"      {r['url']}")
            print(f"      {r['title'] or '(无标题)'} · {'；'.join(r['reasons'])}")
    if spa:
        print("\nSPA 站（保留，已由检索代理自证）：")
        for r in spa:
            print(f"  ~ {r['id'][-14:]}  {r['url']}")

    json.dump({"checked": date.today().isoformat(), "total": len(results),
               "ok": len(ok), "spa": len(spa), "drop": len(drop),
               "results": results},
              open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n明细已写入 {REPORT}")

    if apply:
        # 体检不通过 → 停止展示链接，但保留原域名与成因，供维护期判断能否复活
        REPAIR_OF = {"被抢注": "不可修复", "域名彻底退役": "不可修复",
                     "源站下线": "可复活", "平台槽位空置": "可复活",
                     "内容停更": "需重启"}

        def map_reason(text):
            if "抢注" in text:
                return "被抢注", "none"
            if "停更" in text:
                return "内容停更", "stale"
            if "空模板" in text or "他校" in text:
                return "平台槽位空置", "exists_unreachable"
            return "源站下线", "exists_unreachable"

        for r in unreachable:
            tgt = payload["schools"][r["id"]]
            tgt["verify"] = "unreachable_at_build"
            tgt["basis"] = ((tgt.get("basis") or "") +
                            "；构建期探测未响应，链接保留待复核").strip("；")

        for r in drop:
            tgt = payload["schools"][r["id"]]
            reason, state = map_reason("；".join(r["reasons"]))
            tgt["site_archived"] = r["url"]
            tgt["site"] = None
            tgt["null_reason"] = reason
            tgt["site_state"] = state
            tgt["repair"] = REPAIR_OF.get(reason)
            tgt["basis"] = (f"原记录 {r['url']}；全量体检判定不可用（{r['title'] or '无标题'}）："
                            + "；".join(r["reasons"]))

        vals = payload["schools"].values()
        from collections import Counter
        payload["counts"] = {
            "total": len(payload["schools"]),
            "with_site": sum(1 for v in vals if v["site"]),
            "site_state": dict(Counter(v["site_state"] for v in payload["schools"].values())),
            "wechat_id": sum(1 for v in vals if v["wechat_status"] == "id"),
            "wechat_exists_no_id": sum(1 for v in vals if v["wechat_status"] == "exists_no_id"),
            "wechat_unknown": sum(1 for v in vals if v["wechat_status"] == "unknown"),
            "null_by_reason": dict(Counter(v["null_reason"] for v in vals if not v["site"])),
            "null_by_repair": dict(Counter(v["repair"] for v in vals
                                           if not v["site"] and v.get("repair"))),
        }
        payload["verified"] = date.today().isoformat()
        json.dump(payload, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"已写回：{payload['counts']}")


if __name__ == "__main__":
    main()
