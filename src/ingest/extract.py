# -*- coding: utf-8 -*-
"""S1 强结构抽取：从官方公告里取批次投档控制线。

为什么先做这一项：它是白名单 6 字段里唯一「错一次就直接误导志愿填报」的，
也是格式最稳的——实测市教育局的分数线公告是**纯文字叙述**，不是表格更不是 PDF：

    普通高中指标生投档控制分数线为 593 分。
    普通高中体育特长生投档控制分数线为 455 分，艺术特长生为 490 分。

所以不需要 pdfplumber、不需要 OCR、不需要模板学习。原方案假设「PDF 附件 +
固定表头」在这条数据上是错的，按实际载体改。

抽取原则（与项目既有做法一致）：
  · 只认「一个分句里既有类别关键词又有三位数」的写法，跨句不猜
  · 抽不到就是抽不到，不做默认值填充；缺口如实列出来
  · 结果与站点现值比对，只产报告，不改模板

产出 data/facts/YYYY-MM.jsonl，一行一条事实，带来源与抽取时间。
"""
import json
import os
import re
import sys
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest import discover, fetch, htmltab      # noqa: E402
from pipeline import config                       # noqa: E402

FACTS_DIR = os.path.join(config.ROOT, "data", "facts")
SCORE_TPL = os.path.join(config.ROOT, "templates", "score.html")

# 分句符：中文逗号要切，否则「体育 455 分，艺术 490 分」只取到第一个数字。
# 顿号**不切**：它是并列符，"3+4 分段…、五年制高职与本科 5+2…" 属于同一类，
# 切开后后半段只剩"五年制高职"，会被误判成另一类。
SENT_SPLIT = re.compile(r"[。；，\n]")
NUM = re.compile(r"(\d{3})\s*分")

# 类别规则：(canonical key, 必须同时出现的词, 不能出现的词)。
# 不靠"含关键词"判断类别，而是靠「数字前面最近的锚点」——
# 原文的章节标题会和正文黏在一句里：
#     「三、体育、艺术特长生 普通高中体育特长生投档控制分数线为 455 分」
# 只看"含不含艺术"，就会把这句判成艺术 455（实际是体育 455、艺术 490）。
SCORE_RULES = [
    ("中职本科3+4", ("3+4",), ()),
    ("中职本科3+4", ("5+2",), ()),
    # 「五年制高职」在站点的 385 分那一行指"普通五年制高职专业班"，
    # 而 500 分那句是「五年制高职**与本科**5+2」，两者不同，必须排除。
    ("五年制高职", ("五年制高职",), ("与本科", "5+2", "3+4")),
    ("指标生", ("指标生",), ()),
    ("艺术特长生", ("艺术", "特长生"), ()),
    ("体育特长生", ("体育", "特长生"), ()),
    ("学科科技特长生", ("学科", "特长生"), ()),
    ("学科科技特长生", ("科技", "特长生"), ()),
    ("学科科技特长生", ("数理", "特长生"), ()),
    ("第一批次中外合作", ("中外合作",), ()),
    ("第一批次统招", ("第一批次",), ("中外合作",)),
    ("第二批次统招", ("第二批次",), ()),
    ("普职融通", ("普职融通",), ()),
    ("中职高职3+3", ("3+3",), ()),
]

# 站点模板里的行标题 → 同一个 canonical key。
# 两边用同一套键名，比对才有意义。
SITE_ROW_KEYS = [
    ("指标生", ("指标生",)),
    ("学科科技特长生", ("科技", "特长生")),
    ("艺术特长生", ("艺术特长生",)),
    ("体育特长生", ("体育特长生",)),
    ("第一批次统招", ("第一批次", "统招")),
    ("第一批次中外合作", ("中外合作",)),
    ("中职本科3+4", ("3+4",)),
    ("第二批次统招", ("第二批次",)),
    ("普职融通", ("普职融通",)),
    ("中职高职3+3", ("3+3",)),
    ("五年制高职", ("五年制高职",)),
]

LABELS = {
    "指标生": "普通高中指标生",
    "学科科技特长生": "科技/学科/数理特长生",
    "艺术特长生": "普通高中艺术特长生",
    "体育特长生": "普通高中体育特长生",
    "第一批次统招": "第一批次普通高中统招",
    "第一批次中外合作": "第一批次中外合作/国际课程班",
    "中职本科3+4": "中职本科 3+4 / 五年制高职本科 5+2",
    "第二批次统招": "第二批次普通高中统招",
    "普职融通": "普职融通班/综合高中班",
    "中职高职3+3": "中职与高职 3+3",
    "五年制高职": "五年制高职专业班",
}

# 抽取任务：每条都写清「去哪个栏目、认哪个标题、用哪个抽取器」。
# 栏目地址是人工核实过的具体入口，不按规律猜；条目数超过 5 条时再考虑外置成配置。
#   compare  site_score       与 templates/score.html 的批次线逐项比
#            archive_lottery  与各档案「2026 电脑派位计划」字段逐校比
JOBS = [
    {
        "id": "score-lines-2026",
        "name": "2026 中招投档控制线",
        "list_url": "https://edu.nanjing.gov.cn/zb/gzzs/",
        # 标题必须同时是「分数线的发布动作」，不能只提到分数线：
        # 栏目里有一篇「第二批次录取进程过半 在投档控制分数线上未被录取的考生…」，
        # 只按「投档控制分数线」匹配会把新闻稿当成发布页，抽出空结果。
        "title_pattern": r"投档(?:控制)?分数线[^的]{0,6}(?:揭晓|公布|出炉|发布)",
        "extractor": "score_lines",
        "compare": "site_score",
        "year": "2026",
    },
    {
        "id": "lottery-2026-gulou",
        "name": "2026 鼓楼区热点公办与民办小学电脑派位计划",
        # 这份文件没有可遍历的栏目页，直接给定公告地址（已核实可达）
        "page_url": "https://www.njgl.gov.cn/glqrmzf/202606/t20260601_5849294.html",
        "extractor": "lottery_plans",
        "compare": "archive_lottery",
        "year": "2026",
        "district": "鼓楼区",
    },
    {
        "id": "zone-2023-gulou",
        "name": "鼓楼区主城小学施教区（区政府公开问答）",
        # 注意这是 2023 年发布的问答，用于「收录对账」而非「当年政策依据」：
        # 施教区每年 5 月可能调整，比对结论必须回落到当年文件再确认。
        "page_url": "https://www.njgl.gov.cn/znwd/zsk/kjjy/202306/t20230629_3949864.html",
        "extractor": "district_zones",
        "compare": "archive_zone",
        "year": "2023",
        "district": "鼓楼区",
    },
    {
        "id": "school-list-2026-gulou",
        "name": "鼓楼区 2026 年小学招生入学名单（区政府办法附件）",
        # 比 2023 年的施教区问答更适合做「在办学校」判定：
        # 附件是当年实际招生的全部公办与民办小学，撤并校不会出现在里面。
        "page_url": "https://www.njgl.gov.cn/ztzl47815/jyzt/zchj/202605/t20260508_5836466.html",
        "extractor": "school_phone_list",
        "compare": "archive_schools",
        "year": "2026",
        "district": "鼓楼区",
    },
]


def _is_line(sent):
    """只认「投档控制分数线」的句子。招生计划人数句里也有三位数，不能混。"""
    return "控制分数线" in sent or "控制线" in sent


def _anchor(sent, keywords, pos):
    """类别**核心词**（规则里的第一个词）在数字前最后出现的位置；没有返回 -1。

    只取核心词、不取整组词的位置，是因为「艺术特长生」与「体育特长生」共用
    「特长生」——按组取最大位置会双双落到同一个「特长生」上，区分度归零
    （实测两者都得到 17，于是艺术把体育那句抢走）。核心词才是区分点。
    """
    return sent.rfind(keywords[0], 0, pos)


def _pick_key(sent, pos):
    """取「数字前面最近的那个类别」作为归属。

    近者优先的依据很实在：章节标题会黏在正文前（「三、体育、艺术特长生 普通高中
    体育特长生投档控制分数线为 455 分」），而真正限定这个数字的类别词紧贴数字。
    位置相同时用更长的关键词（更具体的那个）。
    """
    best, best_pos, best_len = None, -1, 0
    for key, must, mustnot in SCORE_RULES:
        if not all(k in sent for k in must):
            continue
        if any(k in sent for k in mustnot):
            continue
        idx = _anchor(sent, must, pos)
        if idx < 0:
            continue
        ln = max(len(k) for k in must)
        if idx > best_pos or (idx == best_pos and ln > best_len):
            best, best_pos, best_len = key, idx, ln
    return best


def score_lines(text):
    """从公告纯文本抽批次控制线，返回 {canonical_key: int}。

    同一类别在一篇公告里可能出现多次（如重复强调），取第一次。
    """
    out = {}
    for sent in SENT_SPLIT.split(text or ""):
        sent = sent.strip()
        if not sent or not _is_line(sent):
            continue
        m = NUM.search(sent)
        if not m:
            continue
        val = int(m.group(1))
        if not 300 <= val <= 700:      # 中考总分 700，控制线实测 385–593
            continue
        key = _pick_key(sent, m.start())
        if key and key not in out:
            out[key] = val
    return out


# ---------------------------------------------------------------- 派位计划

RE_PREFIX = re.compile(r"^(?:江苏省)?南京(?:市)?")
# 官方全称里的常见缩写。只收实测真的对不上的，不预设：
# 公告写「南京师范大学附属中学 鲁迅园小学」，档案里是「南师附中鲁迅园小学」。
# 「附属小学→附小」是通用简写，几乎每所高校附小都会这么写，属结构等价而非猜测。
NAME_EQUIV = [
    ("师范大学附属中学", "南师附中"),
    ("附属小学", "附小"),
    ("附属中学", "附中"),
    ("南京大学", "南大"),
    ("南京财经大学", "财大"),
    ("江苏第二师范学院", "二师院"),
    ("南京师范大学", "南师"),
]


def _norm(name):
    """去空格与行政区前缀。只去这一层——「附属/实验/小学」一旦抹掉就会串校。"""
    return RE_PREFIX.sub("", re.sub(r"\s+", "", name or "")).strip()


def name_keys(name):
    """一个校名的全部可比形式。

    两个细节都是踩过的：
      1. 替换必须**累积**：「南京财经大学附属小学」要先变「南京财经大学附小」、
         再变「财大附小」，才能对上公告里的「财大附小」。
      2. 起点必须**同时包含原名片与去前缀名**：单看去前缀的形式，
         「南京大学附属丁家桥小学」会变成「大学附属丁家桥小学」，
         「南京大学→南大」这条规则就永远匹配不上了。
    """
    raw = re.sub(r"\s+", "", name or "")
    if not raw:
        return set()
    keys = {raw}
    # 去学段括号：档案里写「南京市力人学校（小学部）」，公告里写「南京市力人学校小学部」。
    # 括号只在这里当分隔符用——若去掉后与多所档案同名（如陶行知学校的小学部与初中部），
    # match_school 会判歧义返回 None，仍然是安全的。
    stripped = re.sub(r"[（(][^）)]*[）)]", "", raw)
    starts = {raw, stripped, RE_PREFIX.sub("", raw), RE_PREFIX.sub("", stripped)}
    for start in starts:
        if not start:
            continue
        keys.add(start)
        frontier = {start}
        for full, short in NAME_EQUIV:
            fresh = set()
            for s in frontier:
                if full in s:
                    t = s.replace(full, short)
                    if t not in keys:
                        keys.add(t)
                        fresh.add(t)
            frontier |= fresh
    return keys


def lottery_plans(html):
    """从派位办法页抽 {公告校名: 计划人数}。

    判据是「表头同时含学校与计划」：政府页里还有公文元信息表和页脚，
    它们没有这两个词，自然被排除。
    """
    out = {}
    for _hi, cols, rows in htmltab.pick_tables(html, ("学校", "计划")):
        ni = htmltab.column(cols, "学校名称", "学校")
        pi = htmltab.column(cols, "派位计划（人）", "派位计划", "计划")
        if ni is None or pi is None:
            continue
        for row in rows:
            if len(row) <= max(ni, pi):
                continue
            name = row[ni].strip()
            m = re.search(r"\d+", row[pi])
            if not name or not m:
                continue
            if name == "学校名称" or "序号" in name:
                continue
            out[name] = int(m.group(0))
    return out


def load_schools(level=None):
    """读 index.json 的学校名单，返回 [(id, name, 可比形式集合)]。

    level 用来收窄范围：小学招生名单拿去和全库匹配时，「金陵汇文学校小学部」
    会同时撞上同名的初中与小学档案，被判成歧义而匹配失败。
    名单本身已经限定学段，匹配也该限定在同一学段内。

    简称也进可比形式：官方名单里写「树人附小」、档案写「南师附中树人学校附属小学」，
    规则拼不出「树人附小」这种取头取尾的缩写，只能靠档案自己的 short 字段。
    只收**全库唯一**的简称——「力小」「拉小」这类两字简称有多校共用，
    进表会让匹配返回第一所，把别家的数字安到这所头上。
    """
    if not os.path.isfile(config.INDEX):
        return []
    with open(config.INDEX, encoding="utf-8") as f:
        idx = json.load(f)
    rows = idx["schools"]
    if level:
        rows = [s for s in rows if s.get("level") == level]
    # 唯一性要在**收窄后的范围**内判：全库重名的简称，在小学段内可能只有一个
    short_used = {}
    for s in rows:
        k = s.get("short") or ""
        if k:
            short_used[k] = short_used.get(k, 0) + 1
    out = []
    for s in rows:
        keys = name_keys(s["name"])
        short = s.get("short") or ""
        if short and short_used.get(short) == 1:
            keys |= name_keys(short)
        out.append((s["id"], s["name"], keys))
    return out


def match_school(name, schools):
    """把公告里的校名对到档案 id；对不上返回 None，不猜。

    两级：精确相等（含缩写等价）→ 唯一子串包含。
    多所命中一律判为对不上：「XX 小学」与「XX 小学某分校」一旦按包含放宽，
    分校的数字就会被安到本部头上，而这种错误在页面上看不出来。
    """
    if not _norm(name):
        return None
    keys = name_keys(name)
    for sid, _n, skeys in schools:
        if keys & skeys:
            return sid
    hits = [sid for sid, _n, skeys in schools
            if any(k and s and (k in s or s in k) for k in keys for s in skeys)]
    return hits[0] if len(hits) == 1 else None


def nearest(name, schools, n=2):
    """库里与该校名最相近的几个，仅作线索供人判断。"""
    import difflib
    return difflib.get_close_matches(name, [s[1] for s in schools], n=n, cutoff=0.3)


def archive_lottery():
    """从档案正文抽各校派位计划数，返回 {school_id: int}。

    档案里这项写成「2026 年电脑派位 21 人」这类自由文本，取第一个带「人」的数字；
    没有就不入表——抽不到是常态，不能当 0。
    """
    from pipeline import facts, source
    if not os.path.isfile(config.INDEX):
        return {}
    with open(config.INDEX, encoding="utf-8") as f:
        idx = json.load(f)
    out = {}
    for s in idx["schools"]:
        try:
            got = facts.extract(source.text(s["file"]))
        except OSError:
            continue
        raw = got.get("lottery")
        if not raw:
            continue
        m = re.search(r"(\d{1,4})\s*人", raw) or re.search(r"(\d{2,4})", raw)
        if m:
            out[s["id"]] = int(m.group(1))
    return out


def compare_lottery(plans, schools, archive):
    """返回 (一致, 数值不同, 档案未记, 校名对不上)。

    四类分开列：把「档案没记」和「记错了」混在一起，等于让真错误躲在缺口里。
    """
    same, diff, missing, unmatched = [], [], [], []
    for name, n in plans.items():
        sid = match_school(name, schools)
        if not sid:
            unmatched.append((name, n))
            continue
        old = archive.get(sid)
        if old is None:
            missing.append((sid, name, n))
        elif old != n:
            diff.append((sid, name, n, old))
        else:
            same.append((sid, name, n))
    return same, diff, missing, unmatched


# ---------------------------------------------------------------- 施教区

# 「校名：范围」是政府问答页的统一写法，冒号是关键分隔符。
# 校名必须以小学/学校/附小收尾——否则会把「一、鼓楼区主城小学施教区」
# 这种小节标题也吃进来（实测「…小学」出现 50 次，其中只有 43 次是真条目）。
ZONE_ITEM = re.compile(
    r"([\u4e00-\u9fa5A-Za-z（）()·]{2,20}(?:小学|学校|附小))\s*[：:]\s*")
# 行政说明段的起点：从这里往后不属于名单
ZONE_TAIL = "二、相关说明"


def district_zones(text):
    """从「施教区是如何划分的」问答页抽 {公告校名: 施教区原文}。

    按「校名：」的位置切分，而不是按句号切：范围文本里本身就带句号
    （「小市村[1-100号（不分单双）。」），按句号切会把一条拆成两条。
    """
    body = text or ""
    cut = body.find(ZONE_TAIL)
    if cut > 0:
        body = body[:cut]

    marks = list(ZONE_ITEM.finditer(body))
    out = {}
    for i, m in enumerate(marks):
        name = m.group(1).strip()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        zone = body[m.end():end].strip().strip("。;； ")
        if len(zone) >= 8:          # 太短的不是施教区，是排版残留
            out[name] = zone
    return out


def compare_zones(zones, schools):
    """返回 (能对上档案的, 库中无此校的)。

    这里只做「有没有」的判断，不做内容比对：档案里施教区的写法各家不同
    （有的列表、有的整段叙述），机械比对会制造大量假差异。
    真正的价值在于第二项——官方名单里有、库里没有，就是缺档。
    """
    hit, missing = [], []
    for name, zone in zones.items():
        sid = match_school(name, schools)
        if sid:
            hit.append((sid, name, zone))
        else:
            missing.append((name, zone))
    return hit, missing


# ---------------------------------------------------------------- 学校名单

# 已撤并 / 已注销的学校：旧名单里名字还在，建制其实没了。
#
# 为什么需要这张表：zone-2023-gulou 用的是 2023 年施教区问答，那份名单里
# 汉口路、察哈尔路、回龙桥都还是独立学校。拿它跟当前档案比对，这三所必然
# 报「库中无此校」——每一轮抽取都报同一批假缺口，看起来像库里漏了三所，
# 实际是名单版本旧。假缺口比不报更坏：它会把人的注意力引去补一份不该存在的档案。
#
# 表里只收**有官方文件可查**的撤并，并记下并入去向，便于反查新校档案是否已收录：
# 汉口路→琅小、察哈尔路+回龙桥→鲁迅园小学，三者的新归属在库中都有档案。
# 新增条目必须同时改这里和下面报告里的措辞，别让它变成「猜」。
MERGED = {
    "汉口路小学": ("南京市琅琊路小学", "2024-05 并入，现为琅小汉口路校区"),
    "察哈尔路小学": ("南师附中鲁迅园小学", "2025 年与回龙桥小学合并挂牌"),
    "回龙桥小学": ("南师附中鲁迅园小学", "2025-12-01 注销，与察哈尔路小学合并"),
}


def merged_into(name):
    """旧校名 → (新校名, 说明)；不是已撤并校则返回 None。

    两级匹配：先比规范化后的完全相等，相等不成立时再退回子串
    （名单里可能带「（本部）」「（小学部）」这类后缀）。
    去掉「南京市」前缀是必须的，因为名单里有时写全称、有时写简称。

    子串这一级**必须卡长度**：「小学」「路小学」这种片段会命中任何一所校名，
    一旦被误判成「已撤并」，真实缺口就会被静默归进「不需补档」而不报警——
    这是比误报更坏的失败模式。宁可漏判，漏判会在报告里多出一条，人看得见。
    """
    no = _norm(name)
    if not no:
        return None
    for old, info in MERGED.items():
        if _norm(old) == no:
            return info
    if len(no) < 4:
        return None
    for old, info in MERGED.items():
        o = _norm(old)
        if o in no or no in o:
            return info
    return None


# 招生办法附件的格式是「校名 咨询电话」，校区用括号跟在后面。
# 结尾词要把「小学部」放在「小学」之前，否则「…汇文学校小学部」会被截成
# 「…汇文学校小学」，剩下一个「部」字对不上号（实测漏了 2 所）。
RE_SCHOOL_PHONE = re.compile(
    r"([\u4e00-\u9fa5A-Za-z（）()·]{4,30}?(?:小学部|小学|学校|附小))\s*"
    r"(?:[（(][^）)]{0,12}[）)])?\s*(\d{7,8}(?:[-－]\d{2,4})?)")

# 附件段落的两端。左界取其标题，右界取「外来务工人员随迁子女」——
# 但这个词在正文前半部分也出现过，所以右界必须从标题之后开始找，
# 否则 find 返回的是前文位置，段落被截成空串（实测抽到 0 所）。
LIST_HEAD = "咨询方式一览表"
LIST_TAIL = "外来务工人员随迁子女"


def school_phone_list(text):
    """从招生办法附件抽 {校名: 咨询电话}。括号里的校区会被去掉。"""
    body = text or ""
    i = body.find(LIST_HEAD)
    if i < 0:
        return {}
    j = body.find(LIST_TAIL, i)
    seg = body[i:j] if j > i else body[i:]

    out = {}
    for m in RE_SCHOOL_PHONE.finditer(seg):
        name = re.sub(r"[（(][^）)]*[）)]", "", m.group(1)).strip()
        if len(name) >= 4:
            out[name] = m.group(2)
    return out


def site_baseline(path=SCORE_TPL):
    """从 templates/score.html 读站点现值，返回 {canonical_key: int}。

    用正则而不是 HTML 解析库：模板结构由本站控制，只有一张两列的表，
    为它引入 bs4/lxml 不划算。取不到就返回空，让比对如实显示「站点无此值」。
    """
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        html = f.read()
    out = {}
    for row in re.findall(r"<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>", html, re.S):
        label = re.sub(r"<[^>]+>", "", row[0])
        cell = re.sub(r"<[^>]+>", "", row[1])
        m = NUM.search(cell)
        if not m:
            continue
        val = int(m.group(1))
        for key, kws in SITE_ROW_KEYS:
            if key in out:
                continue
            if all(k in label for k in kws):
                out[key] = val
                break
    return out


def compare(official, baseline):
    """比对官方值与站点现值，返回 [(key, 官方, 站点)] 的差异清单。

    官方没抽到、站点也没有的项不列出——那是「两边都不知道」，
    不是数据错误，放进缺口清单即可。
    """
    out = []
    for key in LABELS:
        a, b = official.get(key), baseline.get(key)
        if a is None:
            continue
        if b != a:
            out.append((key, a, b))
    return out


def page_text(html):
    """公告页正文（去掉脚本样式与标签）。"""
    h = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()


EXTRACTORS = {
    # 名称 → (函数, 输入形态)。批次线是纯文字叙述，派位与施教区是表格/长文本，
    # 输入不同由任务声明，免得抽取器内部各自猜。
    "score_lines": (score_lines, "text"),
    "lottery_plans": (lottery_plans, "html"),
    "district_zones": (district_zones, "text"),
    "school_phone_list": (school_phone_list, "text"),
}


def find_page(fetcher, job):
    """在栏目页里按标题模式找目标公告，返回 (标题, 地址, 错误)。

    取最上面一条：栏目页按发布时间倒序，最上面就是最新一次发布。
    """
    res = fetcher.get(job["list_url"])
    if not res.text:
        return None, None, "栏目页无正文"
    for title, url in discover.entries(res.text, job["list_url"]):
        if re.search(job["title_pattern"], title):
            return title, url, ""
    return None, None, "栏目页未找到匹配标题"


def run_job(fetcher, job):
    """执行一个抽取任务，返回记录 dict。"""
    if job.get("page_url"):
        # 部分文件没有可遍历的栏目页，直接给定已核实的公告地址
        title, url, err = job.get("name", ""), job["page_url"], ""
    else:
        title, url, err = find_page(fetcher, job)
    if err:
        return {"job": job["id"], "ok": False, "reason": err}

    res = fetcher.get(url)
    if not res.text:
        return {"job": job["id"], "ok": False, "reason": f"公告页无正文：{url}"}

    fn, kind = EXTRACTORS[job["extractor"]]
    values = fn(page_text(res.text) if kind == "text" else res.text)
    return {
        "job": job["id"],
        "ok": bool(values),
        "reason": "" if values else "页面未抽到任何条目",
        "title": title,
        "url": url,
        "year": job.get("year", ""),
        "values": values,
        "text_len": len(res.body),
    }


def write_facts(records, when=None):
    """把抽取结果追加到 data/facts/YYYY-MM.jsonl，同一天同内容不重复写。

    追加而不是覆盖，是为了留下「哪天抽到了什么」的历史；
    但同一天反复跑（调试、手动重试）不该产生重复行，否则文件很快就读不下去。
    去重键是「任务 + 抽取结果」，时间戳不同但内容相同视为同一条。
    """
    import time
    when = when or time.strftime("%Y-%m", time.localtime())
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    os.makedirs(FACTS_DIR, exist_ok=True)
    path = os.path.join(FACTS_DIR, f"{when}.jsonl")

    def key(rec):
        return (rec.get("job"),
                json.dumps(rec.get("values"), sort_keys=True, ensure_ascii=False))

    seen = set()
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    seen.add(key(json.loads(line)))
                except ValueError:
                    continue

    fresh = [r for r in records if key(r) not in seen]
    if not fresh:
        return path, 0
    with open(path, "a", encoding="utf-8") as f:
        for r in fresh:
            f.write(json.dumps({"extracted_at": stamp, **r}, ensure_ascii=False) + "\n")
    return path, len(fresh)


def report_score(rec):
    """批次线报告：与 templates/score.html 逐项比。"""
    print(f"   抽到 {len(rec['values'])} 项：")
    for k in LABELS:
        if k in rec["values"]:
            print(f"     {LABELS[k]:<28} {rec['values'][k]} 分")

    baseline = site_baseline()
    diffs = compare(rec["values"], baseline)
    missing = [k for k in LABELS if k not in rec["values"] and k in baseline]
    if diffs:
        print(f"\n   ⚠ 与站点现值不一致 {len(diffs)} 项（需人工核实后改模板）：")
        for k, a, b in diffs:
            print(f"     {LABELS[k]:<28} 官方 {a}　站点 {b if b is not None else '无'}")
    else:
        same = [k for k in rec["values"] if k in baseline]
        print(f"\n   ✓ 与站点现值一致（比对 {len(same)} 项）")
    if missing:
        print(f"   本公告未覆盖、站点已有：{'、'.join(LABELS[k] for k in missing)}")
        print("   （批次线分批发布，第二批次等在其后续公告里）")


def report_lottery(rec):
    """派位计划报告：与各档案「2026 电脑派位计划」字段逐校比。"""
    print(f"   抽到 {len(rec['values'])} 所学校：")
    for name, n in list(rec["values"].items()):
        print(f"     {name:<32} {n} 人")

    schools = load_schools(level="小学")
    if not schools:
        print("\n   ✗ 缺少 index.json，无法与档案比对（先跑 src/build_index.py）")
        return
    same, diff, missing, unmatched = compare_lottery(rec["values"], schools, archive_lottery())
    print(f"\n   与档案比对：一致 {len(same)} / 数值不同 {len(diff)} / "
          f"档案未记 {len(missing)} / 校名对不上 {len(unmatched)}")

    if diff:
        print("\n   ⚠ 数值不同（需人工核实后改档案）：")
        for sid, name, new, old in diff:
            print(f"     {name:<32} 官方 {new}　档案 {old}")
    if missing:
        print("\n   档案未记（可作为补充项）：")
        for sid, name, n in missing:
            print(f"     {name:<32} 官方 {n} 人")
    if unmatched:
        print("\n   校名对不上（不改档案，需人工判断是写法差异还是档案未收录）：")
        for name, n in unmatched:
            near = nearest(name, schools)
            tip = "、".join(near) if near else "库中无相近校名，疑似未收录"
            print(f"     {name:<32} {n} 人")
            print(f"       最相近：{tip}")


def report_zones(rec):
    """施教区报告：与库内档案对校名，重点是「官方有、库里没有」。"""
    zones = rec["values"]
    print(f"   抽到 {len(zones)} 所学校的施教区：")
    for name, zone in list(zones.items())[:5]:
        print(f"     {name:<22} {zone[:38]}…")
    if len(zones) > 5:
        print(f"     ……（其余 {len(zones) - 5} 所略）")

    schools = load_schools(level="小学")
    if not schools:
        print("\n   ✗ 缺少 index.json，无法与档案比对（先跑 src/build_index.py）")
        return
    hit, missing = compare_zones(zones, schools)
    # 缺口里先摘掉已撤并的：它们在建制上已经不存在，补一份档案只会造出一所
    # 「纸面学校」。留下的是真缺口，数量才对得上。
    real, gone = [], []
    for name, zone in missing:
        info = merged_into(name)
        (gone if info else real).append((name, zone, info))
    print(f"\n   与档案比对：能对上 {len(hit)} / 库中无此校 {len(missing)}"
          + (f"（其中 {len(gone)} 所已撤并）" if gone else ""))
    if real:
        print("\n   ⚠ 官方名单里有、库中没有（缺档线索，需人工核实后补建）：")
        for name, zone, _ in real:
            near = nearest(name, schools, n=1)
            tip = near[0] if near else "库中无相近校名"
            print(f"     {name:<22} 施教区 {len(zone)} 字　最相近：{tip}")
    if gone:
        print("\n   已撤并 / 已注销，不需补档（旧名单残留）：")
        for name, _zone, (new, why) in gone:
            print(f"     {name:<22} → {new}　{why}")
    if hit:
        print(f"\n   已收录的 {len(hit)} 所（施教区原文已抽到，可逐条核对档案第五节）：")
        print("     " + "、".join(n for _sid, n, _z in hit[:12])
              + ("…" if len(hit) > 12 else ""))


def report_schools(rec):
    """在办学校名单：与库内小学档案对校名，重点是「当年在招、库里没有」。"""
    got = rec["values"]
    print(f"   抽到 {len(got)} 所学校及咨询电话：")
    for name, phone in list(got.items())[:5]:
        print(f"     {name:<26} {phone}")
    if len(got) > 5:
        print(f"     ……（其余 {len(got) - 5} 所略）")

    schools = load_schools(level="小学")
    if not schools:
        print("\n   ✗ 缺少 index.json，无法与档案比对（先跑 src/build_index.py）")
        return

    # 特殊教育学校不在中小学档案范围，单列出来，别混进缺档
    regular = {n: "" for n in got
               if not any(w in n for w in ("特殊教育", "特教", "盲校", "聋校"))}
    hit, missing = compare_zones(regular, schools)
    extra = len(got) - len(regular)
    # 理论上「当年在招」的名单不该出现已撤并校；真出现了说明名单本身有问题，
    # 单列出来比混进缺档里更值得看。
    gone = [(n, z) for n, z in missing if merged_into(n)]
    missing = [(n, z) for n, z in missing if not merged_into(n)]
    print(f"\n   与档案比对：能对上 {len(hit)} / 库中无此校 {len(missing)}"
          + (f"（另 {extra} 所特教类不收录）" if extra else ""))

    if missing:
        print("\n   ⚠ 当年在招生、库里没有档案：")
        for name, _zone in missing:
            near = nearest(name, schools, n=1)
            tip = f"　最相近：{near[0]}" if near else ""
            print(f"     {name}{tip}")
    if gone:
        print("\n   ⚠ 名单里出现已撤并校（名单版本可能有误，建议核对来源）：")
        for name, _zone in gone:
            new, why = merged_into(name)
            print(f"     {name:<22} → {new}　{why}")


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="从官方公告抽取批次控制线，并与站点现值比对。默认只报告，不改任何文件。")
    ap.add_argument("--job", default=None, help="只跑指定任务 id")
    ap.add_argument("--write", action="store_true", help="追加写入 data/facts/")
    ap.add_argument("--interval", type=float, default=1.0)
    args = ap.parse_args()

    jobs = [j for j in JOBS if not args.job or j["id"] == args.job]
    if not jobs:
        print(f"✗ 没有匹配的任务：{args.job}")
        return 1

    f = fetch.Fetcher(min_interval=args.interval)
    records = []
    for job in jobs:
        print(f"\n── {job['id']}　{job['name']}")
        rec = run_job(f, job)
        records.append(rec)
        if not rec["ok"]:
            print(f"   ✗ {rec['reason']}")
            continue
        print(f"   来源：{rec['title']}")
        print(f"         {rec['url']}")
        compare = job.get("compare")
        if compare == "archive_lottery":
            report_lottery(rec)
        elif compare == "archive_zone":
            report_zones(rec)
        elif compare == "archive_schools":
            report_schools(rec)
        else:
            report_score(rec)

    f.flush()
    if args.write:
        path, n = write_facts(records)
        if n:
            print(f"\n已追加 {n} 条到 {path}")
        else:
            print(f"\n无新增（{path} 里已有相同内容）")
    else:
        print("\n未写入。加 --write 落盘到 data/facts/。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
