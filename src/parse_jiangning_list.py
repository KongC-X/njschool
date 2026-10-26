# -*- coding: utf-8 -*-
"""解析《2026年江宁区义务教育招生咨询电话》附件，输出各类别学校名录。

来源：http://hyxx.jnjy.net.cn/html/202605/NewShow-f19b93e68b.html（附件 6）
该附件由江宁区教育局发布，是**官方口径的学校名录**，可作为应收清单底稿。
只读本地已下载的 HTML，不改任何数据。
"""
import html
import re

RAW = "/tmp/jn_call.html"

# 类别标题行模板
CAT_PAT = re.compile(r"^[（(]\s*(\d+)\s*[）)]\s*(.+)$")


def load_lines():
    raw = open(RAW, "rb").read()
    text = None
    for enc in ("utf-8", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|li|h\d|td)>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\u3000]+", " ", text)
    return [l.strip() for l in text.split("\n") if l.strip()]


def parse(lines):
    # 只取正文附件部分：从「附件 6」之后
    start = 0
    for i, l in enumerate(lines):
        if l.startswith("附件"):
            start = i
    body = lines[start:]

    cats = []          # [(category, [(name, addr, tel), ...])]
    cur_name = None
    cur_rows = []
    buf = []           # 当前条目累积行
    idx = None

    def flush():
        nonlocal buf, idx
        if idx is None and not buf:
            return
        if not buf:
            idx = None
            return
        name = buf[0]
        rest = buf[1:]
        addr = []
        tel = []
        for x in rest:
            if re.search(r"\d{7,8}|-\s*\d", x.replace(" ", "")):
                tel.append(x)
            else:
                addr.append(x)
        cur_rows.append((name, " ".join(addr), " ".join(tel)))
        buf = []
        idx = None

    for l in body:
        m = CAT_PAT.match(l)
        if m:
            flush()
            if cur_rows:
                cats.append((cur_name, cur_rows))
            cur_name = m.group(2).strip()
            cur_rows = []
            continue
        # 序号行：原文存在「4 4」「1 8」这类数字间带空格的写法，先去空格再判断
        compact = l.replace(" ", "")
        if re.fullmatch(r"\d{1,3}", compact):
            flush()
            idx = int(compact)
            continue
        if l.startswith("附件") or l.startswith("2026 年江宁区义务教育招生咨询电话"):
            continue
        if idx is not None and len(l) < 60:
            buf.append(l)

    flush()
    if cur_rows:
        cats.append((cur_name, cur_rows))
    return cats


def main():
    cats = parse(load_lines())
    total = 0
    for name, rows in cats:
        print(f"\n===== {name}（{len(rows)} 所）=====")
        for n, a, t in rows:
            print(f"{n:<22}| {a:<46}| {t}")
        total += len(rows)
    print(f"\n合计 {total} 条记录，共 {len(cats)} 个类别")


if __name__ == "__main__":
    main()
