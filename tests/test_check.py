# -*- coding: utf-8 -*-
"""构建门禁自身的测试。

为什么需要：check.py 是硬门禁（不通过则拒绝构建），但它此前**零测试**——
「门禁失效」这件事没人验证过。实测发现它会放行「学校库整页白屏」：
删掉 schools-data.js 的 districts 键，门禁报 0 错误，而前端在模块顶层抛 TypeError。

这些用例就是把那几次变异固化下来：喂进「坏掉的产物」，断言门禁必须报错。
运行：python -m unittest discover -s tests -p "test_*.py"
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pipeline.check import check_payload_shape  # noqa: E402
from pipeline.schema import Report  # noqa: E402


def run_check(payload, cpayload):
    rep = Report()
    check_payload_shape(payload, cpayload, rep)
    return rep


GOOD_DATA = {
    "cols": ["name", "level", "district"],
    "rows": [["南京市琅琊路小学", "小学", "鼓楼区"]],
    "districts": ["鼓楼区"],
}

GOOD_COMPARE = {
    "cols": ["name", "facts"],
    "rows": [["南京市琅琊路小学", {"founded": "1934 年"}]],
    "factLabels": {"founded": "创办时间"},
    "missing": {},
}


class TestPayloadShape(unittest.TestCase):
    def test_good_payloads_pass(self):
        rep = run_check(GOOD_DATA, GOOD_COMPARE)
        self.assertEqual(rep.errors, [])

    def test_missing_districts_is_error(self):
        # 变异 1：删掉 districts。真实后果是 schools.js 顶层抛错、整页白屏。
        broken = {k: v for k, v in GOOD_DATA.items() if k != "districts"}
        rep = run_check(broken, GOOD_COMPARE)
        self.assertTrue(rep.errors, "删掉 districts 必须报错")
        self.assertTrue(any("districts" in e for e in rep.errors))

    def test_empty_districts_is_error(self):
        # 存在但为空，同样会让筛选器一个选项都没有
        broken = dict(GOOD_DATA, districts=[])
        rep = run_check(broken, GOOD_COMPARE)
        self.assertTrue(any("districts" in e for e in rep.errors))

    def test_missing_factlabels_is_error(self):
        # 变异 2：删掉 factLabels。旧逻辑 `if clabels and ...` 会整段跳过，
        # 于是对比页标签全显示 undefined，而门禁 0 错误。
        broken = {k: v for k, v in GOOD_COMPARE.items() if k != "factLabels"}
        rep = run_check(GOOD_DATA, broken)
        self.assertTrue(rep.errors, "删掉 factLabels 必须报错")
        self.assertTrue(any("factLabels" in e for e in rep.errors))

    def test_facts_key_without_label_is_error(self):
        # factLabels 存在，但 facts 里用了没登记中文名的字段
        broken = dict(GOOD_COMPARE,
                      rows=[["南京市琅琊路小学", {"tuition": "公办免费"}]])
        rep = run_check(GOOD_DATA, broken)
        self.assertTrue(any("未定义字段" in e for e in rep.errors))

    def test_missing_cols_is_error(self):
        broken = {k: v for k, v in GOOD_DATA.items() if k != "cols"}
        rep = run_check(broken, GOOD_COMPARE)
        self.assertTrue(any("cols" in e for e in rep.errors))

    def test_missing_file_is_not_reported_here(self):
        # payload 为 None 表示文件缺失/非法 JSON，前面已单独报过，
        # 这里不应重复刷错误（否则一个根因会刷出满屏红）
        rep = run_check(None, None)
        self.assertEqual(rep.errors, [])


if __name__ == "__main__":
    unittest.main()
