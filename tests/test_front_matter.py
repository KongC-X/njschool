# -*- coding: utf-8 -*-
"""档案 front-matter 的回归测试。

为什么要有：2026-11-01 起，索引的全部字段都来自档案头部，正文渲染也依赖
「先剥离 front-matter」。这两件事一旦出问题，表现都很隐蔽——
YAML 会当成正文显示在页面上、标题会变成两个 H1，而构建本身不报错。
这里把边界行为钉死，改 source.py 时能立刻发现。
"""
import glob
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pipeline import mdtext, source  # noqa: E402

FM = '---\nname: "南京市示例小学"\nshort: "示例"\ndistrict: "鼓楼区"\nlevel: "小学"\ntype: "公办"\ntier: "第一梯队"\ntagline: "示例定位"\nrank: 7\n---\n# 南京市示例小学\n\n正文\n'


class TestSplit(unittest.TestCase):
    def test_parses_meta_and_body(self):
        meta, body = source.split_front_matter(FM)
        self.assertEqual(meta["name"], "南京市示例小学")
        self.assertEqual(meta["rank"], "7")
        self.assertTrue(body.startswith("# 南京市示例小学"))

    def test_value_keeps_cjk_punct_and_colon(self):
        # tagline 里常年出现中文引号、书名号和半角冒号，不能把它们当成 YAML 语法
        src = '---\ntagline: "含「引号」与: 冒号 **加粗**"\n---\n正文'
        self.assertEqual(source.split_front_matter(src)[0]["tagline"],
                         "含「引号」与: 冒号 **加粗**")

    def test_no_front_matter_is_passthrough(self):
        # 没有头部时必须是完全透明的：正文第 5 行左右就有一条 --- 水平线
        src = "# 标题\n\n> 定位\n\n---\n\n## 一节\n"
        meta, body = source.split_front_matter(src)
        self.assertEqual(meta, {})
        self.assertEqual(body, src)

    def test_unclosed_fence_is_not_meta(self):
        # 只有开头没有结尾：说明那是正文里的一条水平线，不能吞掉后文
        src = "---\n# 标题\n\n正文"
        meta, body = source.split_front_matter(src)
        self.assertEqual(meta, {})
        self.assertEqual(body, src)

    def test_crlf(self):
        meta, body = source.split_front_matter('---\r\nname: "A"\r\n---\r\n正文')
        self.assertEqual(meta["name"], "A")
        self.assertEqual(body, "正文")


class TestRealArchive(unittest.TestCase):
    """对全部档案做一次体检——这里失败意味着站点上会直接露出 YAML。"""

    @classmethod
    def setUpClass(cls):
        rels = []
        for lv in ("小学", "初中", "高中"):
            for path in glob.glob(str(ROOT / lv / "*" / "*.md")):
                rels.append(str(pathlib.Path(path).relative_to(ROOT)))
        cls.rels = sorted(rels)
        cls.metas = {r: source.meta(r) for r in cls.rels}
        cls.bodies = {r: source.text(r) for r in cls.rels}

    def test_every_archive_has_front_matter(self):
        missing = [r for r in self.rels if not self.metas[r]]
        self.assertEqual(missing, [], f"以下档案缺 front-matter：{missing[:5]}")

    def test_body_never_leaks_front_matter(self):
        leaked = [r for r in self.rels
                  if self.bodies[r].lstrip().startswith("---")
                  or '\nname: "' in self.bodies[r][:200]]
        self.assertEqual(leaked, [], f"以下档案正文混入了 front-matter：{leaked[:5]}")

    def test_required_fields_present(self):
        bad = [f"{r}:{k}" for r in self.rels for k in
               ("name", "district", "level", "type", "tier", "tagline")
               if not self.metas[r].get(k)]
        self.assertEqual(bad, [], f"以下档案缺少必填字段：{bad[:5]}")

    def test_rank_is_int(self):
        bad = [r for r in self.rels if not str(self.metas[r].get("rank", "")).isdigit()]
        self.assertEqual(bad, [], f"以下档案 rank 不是整数：{bad[:5]}")

    def test_strip_leading_h1_still_works(self):
        # 剥离 front-matter 之后，首行必须回到 H1，否则详情页会出现两个 H1
        body = mdtext.strip_leading_h1(self.bodies[self.rels[0]])
        self.assertTrue(body.lstrip().startswith(">") or body.lstrip().startswith("##"),
                        f"首行既不是引用也不是小标题，实际为：{body[:60]!r}")


if __name__ == "__main__":
    unittest.main()
