# -*- coding: utf-8 -*-
"""把 SCHOOLS 元数据迁入每份档案的 front-matter。

为什么做这件事：元数据（简称/区/学段/性质/梯队/一句话定位）此前只存在于
build_index.py 的 175KB 硬编码列表里，而正文在 545 份 md 里。同一所学校的
信息写两处，新增学校必须改代码，天然会漂移（README 记的「204 所」与索引
实际 545 所就是这类漂移）。迁到 front-matter 后，档案自带元数据，
build_index.py 退化为扫描器，新增学校只需新建一个 md 文件。

rank 字段说明：
  索引的最终顺序是「学段 → 梯队优先级 → 区 → 人工顺序」。前三项由代码决定，
  最后一项此前**隐式**依赖 SCHOOLS 列表的排列（靠 Python 排序的稳定性兜底）。
  一旦不再遍历 SCHOOLS，这个兜底就消失了，实测 545 所里有 406 个位置会换位。
  所以把人工顺序显式写进档案：rank = 该校在原 SCHOOLS 列表中的序号。
  新增学校不写 rank 时排在同类末尾，顺序仍可预期。

设计上的三个安全约束：
  1. 默认 dry-run，必须显式 --apply 才写盘
  2. 幂等：已有完整 front-matter 的文件直接跳过，重复跑不会叠加
  3. 只认「首行是 H1」或「首行是 ---」的文件；其余一律不碰并报出来
     ——迁移脚本不该有"猜"的行为，异常文件交给人看

用法：
  python3 src/migrate_front_matter.py            # 预演，只打印将写入的内容
  python3 src/migrate_front_matter.py --apply    # 真正写入
  python3 src/migrate_front_matter.py --check    # 校验现存 front-matter 与 SCHOOLS 是否一致
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_index import SCHOOLS          # noqa: E402  顶层只有列表定义，import 不会触发构建
from pipeline import source              # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 字段顺序固定：git diff 才读得下去，也便于人工核对
FIELDS = ("name", "short", "district", "level", "type", "tier", "tagline")


def render_front_matter(meta):
    """生成 YAML front-matter 文本（文本值统一 JSON 字符串，rank 为裸整数）。"""
    lines = ["---"]
    for key in FIELDS:
        lines.append(f"{key}: {json.dumps(meta[key], ensure_ascii=False)}")
    lines.append(f"rank: {meta['rank']}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def rel_of(row):
    name, _short, district, level, _stype, _tier, _tagline = row
    return f"{level}/{district}/{name}.md"


def to_meta(idx, row):
    meta = dict(zip(FIELDS, row))
    meta["rank"] = idx
    return meta


def insert_rank(text, rank):
    """在已有 front-matter 的闭合 --- 之前插入 rank 行。找不到就原样返回。"""
    m = source.FM_OPEN.match(text)
    if not m:
        return text
    end = source.FM_CLOSE.search(text, m.end())
    if not end:
        return text
    return text[:end.start()] + f"rank: {rank}\n" + text[end.start():]


def plan(limit=None):
    """返回 (全量写入, 仅补 rank, 已完成, 文件缺失, 异常)。"""
    full, addrank, done, missing, odd = [], [], [], [], []
    for idx, row in enumerate(SCHOOLS):
        rel = rel_of(row)
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            missing.append(rel)
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()

        if text.startswith("---"):
            meta = source.split_front_matter(text)[0]
            if "rank" in meta:
                done.append(rel)
            else:
                addrank.append((rel, text, idx))
        elif text.startswith("# "):
            full.append((rel, text, to_meta(idx, row)))
        else:
            odd.append(rel)
        if limit and len(full) + len(addrank) >= limit:
            break
    return full, addrank, done, missing, odd


def check():
    """校验已迁移的 front-matter 与 SCHOOLS 逐字段一致。返回不一致清单。"""
    bad = []
    for idx, row in enumerate(SCHOOLS):
        rel = rel_of(row)
        if not os.path.isfile(os.path.join(ROOT, rel)):
            continue
        got = source.meta(rel)
        if not got:
            bad.append((rel, "缺少 front-matter"))
            continue
        for key in FIELDS:
            if got.get(key) != row[FIELDS.index(key)]:
                bad.append((rel, f"{key}: 文件={got.get(key)!r} 期望={row[FIELDS.index(key)]!r}"))
        if str(got.get("rank")) != str(idx):
            bad.append((rel, f"rank: 文件={got.get('rank')!r} 期望={idx!r}"))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写盘")
    ap.add_argument("--check", action="store_true", help="只校验现存 front-matter")
    ap.add_argument("--limit", type=int, default=None, help="只处理前 N 份（试点用）")
    args = ap.parse_args()

    if args.check:
        bad = check()
        if bad:
            print(f"✗ 不一致 {len(bad)} 处")
            for rel, why in bad[:20]:
                print(f"   {rel}  {why}")
            return 1
        print("✓ 全部 front-matter 与 SCHOOLS 一致（含 rank）")
        return 0

    full, addrank, done, missing, odd = plan(args.limit)
    print(f"全量写入 {len(full)} / 仅补 rank {len(addrank)} / 已完成 {len(done)} "
          f"/ 文件缺失 {len(missing)} / 异常跳过 {len(odd)}")
    if missing:
        print("  文件缺失：")
        for rel in missing[:10]:
            print(f"    - {rel}")
    if odd:
        print("  首行既不是 H1 也不是 ---（不碰）：")
        for rel in odd[:10]:
            print(f"    - {rel}")

    if full:
        rel, text, meta = full[0]
        print(f"\n样例（{rel}）：")
        print("-" * 60)
        print(render_front_matter(meta) + text[:60])
        print("-" * 60)
    if addrank:
        rel, text, idx = addrank[0]
        print(f"\n补 rank 样例（{rel}，rank={idx}）：")
        print("-" * 60)
        print(insert_rank(text, idx)[:260])
        print("-" * 60)

    if not args.apply:
        print("\n预演结束，未写入任何文件。加 --apply 执行。")
        return 0

    for rel, text, meta in full:
        with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n") as f:
            f.write(render_front_matter(meta) + text)
    for rel, text, idx in addrank:
        path = os.path.join(ROOT, rel)
        new = insert_rank(text, idx)
        if new == text:
            print(f"  ! 未能定位 front-matter 闭合行，跳过：{rel}")
            continue
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
    print(f"\n已写入：全量 {len(full)} 份，补 rank {len(addrank)} 份")
    return 0


if __name__ == "__main__":
    sys.exit(main())
