# -*- coding: utf-8 -*-
"""档案里「官方自己都还没定」的两类信号。

为什么单独成模块：站点的立身之本是「查不到就写未获取」。但这两类不是「查不到」，
而是「查到了、官方没说死」。它们此前只写在正文里，列表页和对比页完全看不出来——
家长会把它当成确定信息去用。这里把它们提成可展示的标记。

两条判定都刻意收窄，宁可漏标也不要错标：

1. 「校名暂定」只认速览表「学校全称」那一行。
   实测全文搜「暂定名」会命中 6 份，但其中 3 份是在讲**别的学校**
   （板桥中心小学、琅琊路小学雨花分校、竹山中学都在描述「潘窑规划学校是暂定名」）。
   按速览行判定后剩 3 份，都是自己校名确实没定的。

2. 「施教区含过渡」只认本校「施教区」小节内的出现。
   实测全文搜会命中 15 份，其中古雄小学、春江小学是在表格里转述**别校**的过渡标注。
   限定到本校施教区小节后剩 11 份。
"""
import re

RE_NAME_ROW = re.compile(r"^\|\s*(?:学校全称|校名|学校名称)\s*\|\s*(.+?)\s*\|", re.M)
RE_TENTATIVE = re.compile(r"暂定名|规划学校|（筹）|\(筹\)")
RE_H2 = re.compile(r"^##\s+(.*)$", re.M)

# 标记 → 展示文案。文案就是给用户看的，不要出现内部代号
LABELS = {
    "T": "校名暂定",
    "D": "施教区含过渡",
}

# 悬停说明：讲清「这是什么意思、该怎么用」，不制造新的结论
TITLES = {
    "T": "该校校名为暂定名（区级文件原文即写「规划学校」），正式名称尚未公布",
    "D": "该校施教区含过渡性段落：过渡有期限，须以当年区教育局方案为准",
}


def _sections(text):
    marks = [(m.start(), m.group(1)) for m in RE_H2.finditer(text)]
    for i, (pos, title) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        yield title, text[pos:end]


def flags(text, name=""):
    """返回标记键列表，如 ["T"] / ["D"] / ["T", "D"] / []。"""
    out = []

    row = RE_NAME_ROW.search(text)
    if (row and RE_TENTATIVE.search(row.group(1))) or "规划学校" in (name or ""):
        out.append("T")

    for title, body in _sections(text):
        if "施教区" in title and "过渡学区" in body:
            out.append("D")
            break

    return out


def labels(text, name=""):
    """返回展示文案列表，空列表表示没有标记。"""
    return [LABELS[k] for k in flags(text, name)]


def badges(text, name=""):
    """模板用：带悬停说明的标记列表。"""
    return [{"label": LABELS[k], "title": TITLES[k]} for k in flags(text, name)]
