# -*- coding: utf-8 -*-
"""生成 app.ico（蓝紫渐变圆角方块 + 白色上传箭头）。

用法：python make_icon.py
输出：app.ico（含 256/128/64/48/32/24/16 多尺寸，托盘与 EXE 共用）
"""
import os

from PIL import Image, ImageDraw


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def render(size):
    # 背景渐变（顶部亮蓝 -> 底部紫）
    top = (79, 137, 250)      # #4F89FA
    bottom = (103, 63, 237)   # #673FED
    radius = int(size * 0.22)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(size):
        t = y / max(size - 1, 1)
        for x in range(size):
            px[x, y] = lerp(top, bottom, t) + (255,)

    mask = rounded_mask(size, radius)
    img.putalpha(mask)

    d = ImageDraw.Draw(img)

    # 顶部高光（柔和的半透明弧，增加立体感）
    hl = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    inset = int(size * 0.06)
    hd.ellipse(
        [inset, int(size * 0.02), size - inset, int(size * 0.42)],
        fill=(255, 255, 255, 40))
    hl = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    hd.pieslice(
        [int(size * 0.08), int(size * 0.02), int(size * 0.92), int(size * 0.72)],
        start=180, end=0, fill=(255, 255, 255, 34))
    img = Image.alpha_composite(img, hl)

    # 中央白色上传箭头（与 64px 托盘同形状放大）
    arrow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ad = ImageDraw.Draw(arrow)
    cx = size / 2
    tip_y = size * 0.26
    mid_y = size * 0.42
    bot_y = size * 0.66
    half_w = size * 0.24
    stem_w = size * 0.14
    ad.polygon([
        (cx, tip_y),
        (cx - half_w, mid_y),
        (cx - stem_w, mid_y),
        (cx - stem_w, bot_y),
        (cx + stem_w, bot_y),
        (cx + stem_w, mid_y),
        (cx + half_w, mid_y),
    ], fill=(255, 255, 255, 255))

    # 底部存储横线
    line_w = size * 0.50
    line_h = size * 0.08
    ad.rounded_rectangle(
        [cx - line_w / 2, size * 0.76, cx + line_w / 2, size * 0.76 + line_h],
        radius=line_h / 2, fill=(255, 255, 255, 255))

    # 白图形加 3% 内缩避免贴边发虚
    arrow = arrow.resize((int(size * 0.94), int(size * 0.94)),
                         resample=Image.LANCZOS)
    img = Image.alpha_composite(
        img, Image.new("RGBA", (size, size), (0, 0, 0, 0)))
    img.paste(arrow, (int(size * 0.03), int(size * 0.03)), arrow)

    return img


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "app.ico")
    master = render(256)
    master.save(out, format="ICO",
                sizes=[(256, 256), (128, 128), (64, 64),
                       (48, 48), (32, 32), (24, 24), (16, 16)])
    print("OK:", out)


if __name__ == "__main__":
    main()
