# -*- coding: utf-8 -*-
"""正文交叉链接：把页面里出现的其他校名变成站内链接。

解决的问题（报告 P1-5）：家长的真实决策链是
    小学 → 对口初中 → 该校中考表现 → 目标高中 → 投档线
每一环本站都写了，但链上没有一条可点的边。读到「对口初中：南京市第二十九中学初中部」
只能退回学校库重搜——而搜索引擎那边，正是本站自己反复警示的「臆造数据」聚合站。

约束：不得改坏正文。
  · 只在**文本节点**里替换，绝不碰标签属性（否则 href / id 会被改掉）；
  · 跳过 <a>（已有链接）、<code>、<h1>-<h4>（标题不挂链接，读起来断句）；
  · 跳过施教区列表与自查框（那里的「文枢」「汇文」是地名或校区名，不是学校）；
  · 同一个校名最多链 2 次，整页最多 60 条——满屏链接正文反而更难读。
"""
import re

# 不参与替换的容器：命中即整段跳过
_SKIP_TAGS = {"a", "code", "h1", "h2", "h3", "h4", "script", "style", "textarea"}
_SKIP_CLASS = ("roads", "sk-box")

MAX_PER_NAME = 2
MAX_TOTAL = 60

_TAG = re.compile(r"(<[^>]+>)")
_TAGNAME = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)")
_CLASSATTR = re.compile(r'class="([^"]*)"')


def build(names_to_href):
    """返回 linkify(html, exclude="") 函数。

    names_to_href: {校名: 相对地址}
    exclude:      当前页自身的校名，调用时逐页传入——
                  链接表编译一次供 545 页复用，不要把 545 个正则都编一遍。
    """
    names = [n for n in names_to_href if n]
    if not names:
        return lambda html, exclude="": html

    # 长名优先：「南京市第二十九中学初中部」必须先于「南京市第二十九中学」匹配，
    # 否则后者会先吃掉前半段，留下一个「初中部」孤零零留在链接外面。
    names.sort(key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(n) for n in names))

    def linkify(html, exclude=""):
        if not html:
            return html
        used = {}
        total = [0]
        skip_depth = [0]

        def repl(m):
            name = m.group(0)
            if name == exclude:
                return name
            if used.get(name, 0) >= MAX_PER_NAME or total[0] >= MAX_TOTAL:
                return name
            used[name] = used.get(name, 0) + 1
            total[0] += 1
            return f'<a class="xref" href="{names_to_href[name]}">{name}</a>'

        out = []
        for part in _TAG.split(html):
            if not part:
                continue
            if part.startswith("<"):
                m = _TAGNAME.match(part)
                name = (m.group(1).lower() if m else "")
                closing = part.startswith("</")
                is_skip = name in _SKIP_TAGS
                if not is_skip:
                    cm = _CLASSATTR.search(part)
                    if cm and any(c in cm.group(1).split() for c in _SKIP_CLASS):
                        is_skip = True
                if is_skip and not (part.endswith("/>") and not closing):
                    skip_depth[0] = max(0, skip_depth[0] + (-1 if closing else 1))
                out.append(part)
                continue

            if skip_depth[0] or total[0] >= MAX_TOTAL:
                out.append(part)
                continue
            out.append(pattern.sub(repl, part))

        return "".join(out)

    return linkify
