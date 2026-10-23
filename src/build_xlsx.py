# -*- coding: utf-8 -*-
"""
从 index.json 生成《南京学校对比表.xlsx》。

数据源：index.json
输出：总览 / 全部学校 / 小学 / 初中 / 高中 五个工作表，含筛选、冻结窗格与条件着色。
"""
import json
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = "/Users/kongc/WorkBuddy/南京学校"
INDEX = os.path.join(ROOT, "index.json")
OUT = os.path.join(ROOT, "南京学校对比表.xlsx")

LEVELS = ["小学", "初中", "高中"]
COLS = [
    ("学校全称", "name", 30),
    ("简称", "short", 14),
    ("行政区", "district", 11),
    ("学段", "level", 7),
    ("性质", "type", 7),
    ("梯队定位", "tier", 26),
    ("一句话定位", "tagline", 78),
    ("档案路径", "file", 46),
]

HEAD_FILL = PatternFill("solid", fgColor="1F2937")
HEAD_FONT = Font(color="FFFFFF", bold=True, size=11)
PRIV_FILL = PatternFill("solid", fgColor="FEF3C7")
PUB_FILL = PatternFill("solid", fgColor="F0FDF4")
THIN = Side(style="thin", color="D1D5DB")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def style_header(ws, row, ncol):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER
    ws.row_dimensions[row].height = 24


def write_sheet(ws, rows, title=None):
    r = 1
    if title:
        ws.cell(row=1, column=1, value=title).font = Font(bold=True, size=13)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(COLS))
        ws.row_dimensions[1].height = 22
        r = 2
    for i, (label, _, _) in enumerate(COLS, start=1):
        ws.cell(row=r, column=i, value=label)
    style_header(ws, r, len(COLS))
    head_row = r
    r += 1
    for s in rows:
        fill = PRIV_FILL if s["type"] == "民办" else PUB_FILL
        for i, (_, key, _) in enumerate(COLS, start=1):
            v = s.get(key, "")
            cell = ws.cell(row=r, column=i, value=v)
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=(key in ("tagline", "tier")))
            if key == "type":
                cell.fill = fill
                cell.alignment = Alignment(horizontal="center", vertical="center")
            if key in ("district", "level"):
                cell.alignment = Alignment(horizontal="center", vertical="center")
        r += 1
    for i, (_, _, w) in enumerate(COLS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=head_row + 1, column=1)
    ws.auto_filter.ref = f"A{head_row}:{get_column_letter(len(COLS))}{r-1}"
    return r - 1


def build():
    with open(INDEX, encoding="utf-8") as f:
        d = json.load(f)
    schools = d["schools"]
    cov = d["coverage"]
    districts = d["districts"]

    wb = Workbook()

    # ---- 总览 ----
    ws = wb.active
    ws.title = "总览"
    ws.cell(row=1, column=1, value="南京中小学档案总览").font = Font(bold=True, size=15)
    ws.cell(row=2, column=1, value=f"数据版本 {d.get('version','—')}　更新时间 {d.get('updated','—')}　共 {len(schools)} 所")
    ws.cell(row=2, column=1).font = Font(color="6B7280", size=10)

    r = 4
    headers = ["行政区"] + LEVELS + ["合计"]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, len(headers))
    r += 1
    col_tot = {lv: 0 for lv in LEVELS}
    for dist in districts:
        row = [dist] + [sum(1 for s in schools if s["level"] == lv and s["district"] == dist) for lv in LEVELS]
        tot = sum(row[1:])
        if not tot:
            continue
        for lv_i, n in zip(range(1, 4), row[1:]):
            col_tot[LEVELS[lv_i - 1]] += n
        for i, v in enumerate(row + [tot], start=1):
            cell = ws.cell(row=r, column=i, value=v if v else "—")
            cell.border = BORDER
            cell.alignment = Alignment(horizontal="center")
        r += 1
    for i, v in enumerate(["合计"] + [col_tot[lv] for lv in LEVELS] + [len(schools)], start=1):
        cell = ws.cell(row=r, column=i, value=v)
        cell.font = Font(bold=True)
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center")
    for i, w in enumerate([14, 9, 9, 9, 9], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ---- 全部学校 ----
    ws2 = wb.create_sheet("全部学校")
    write_sheet(ws2, schools)

    # ---- 分学段 ----
    for lv in LEVELS:
        w = wb.create_sheet(lv)
        write_sheet(w, [s for s in schools if s["level"] == lv], title=f"{lv}（{cov.get(lv,0)} 所）")

    wb.save(OUT)
    print(f"已生成：{OUT}")
    print(f"  工作表：总览 / 全部学校 / " + " / ".join(LEVELS))
    print(f"  共 {len(schools)} 行数据")


if __name__ == "__main__":
    build()
