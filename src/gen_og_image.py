# -*- coding: utf-8 -*-
"""生成分享卡片图（og:image）。

一次性脚本：产物提交到 assets/og/site.png，构建时只是拷贝。
不把 Pillow 变成构建期依赖——它只在需要重做这张图时才跑一次。

    python src/gen_og_image.py

尺寸 1200×630 是 Open Graph 的通行比例，微信/Twitter/Telegram 都能正确裁切。
配色直接取 tokens.css 的值，避免和站内视觉脱节。
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "og", "site.png")

W, H = 1200, 630
BG = "#f6f7fb"
SURFACE = "#ffffff"
INK = "#0d1220"
TEXT = "#1a1f2b"
MUTED = "#5f6b7f"
ACCENT = "#2563eb"
ACCENT_WEAK = "#eef3ff"
LINE = "#e5e7ef"

# 系统中文字体候选。TTC 需要指定 index。
FONT_CANDIDATES = [
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),
    ("/Library/Fonts/Arial Unicode.ttf", 0),
]


def load_font(size):
    for path, idx in FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size, index=idx)
            except OSError:
                continue
    raise SystemExit("找不到可用的中文字体，请补一条 FONT_CANDIDATES")


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # 主卡片
    d.rounded_rectangle([48, 48, W - 48, H - 48], radius=28, fill=SURFACE, outline=LINE, width=2)
    # 左侧强调条
    d.rounded_rectangle([48, 48, 58, H - 48], radius=5, fill=ACCENT)

    f_label = load_font(30)
    f_title = load_font(92)
    f_sub = load_font(40)
    f_foot = load_font(30)

    x = 112
    d.text((x, 132), "南京 · 2026", font=f_label, fill=ACCENT)

    d.text((x, 196), "南京中小学档案", font=f_title, fill=INK)

    # 标题下划线
    d.rounded_rectangle([x + 4, 322, x + 300, 332], radius=5, fill=ACCENT)

    d.text((x, 372), "545 所中小学 · 施教区 / 招生 / 投档线", font=f_sub, fill=TEXT)

    # 底部说明用浅色块托一下
    d.rounded_rectangle([x - 4, 470, x + 940, 542], radius=14, fill=ACCENT_WEAK)
    d.text((x + 20, 490), "逐条标注信息来源 · 查不到就写「未获取」", font=f_foot, fill=ACCENT)

    d.text((x, 566), "nj · 公开信息汇编，不构成择校建议", font=f_foot, fill=MUTED)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"已生成 {OUT}（{os.path.getsize(OUT) / 1024:.0f} KB，{W}×{H}）")


if __name__ == "__main__":
    sys.exit(main())
