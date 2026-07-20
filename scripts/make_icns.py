#!/usr/bin/env python3
"""从 images/logo.png 生成 macOS 应用图标 build/icon.icns。

流程：
1. 在 logo 中用红色像素外接框定位红圈 R mark；
2. 合成 1024x1024 的 macOS Big Sur 风格图标（透明画布 + 白色圆角矩形 + 居中红圈 mark）；
3. 导出 build/icon_1024.png 与 build/icon.iconset/（10 个规范尺寸）；
4. 调用 iconutil 生成 build/icon.icns。

运行：uv run python scripts/make_icns.py
仅依赖 Pillow 与标准库（iconutil 为 macOS 自带命令）。
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = PROJECT_ROOT / "images" / "logo.png"
BUILD_DIR = PROJECT_ROOT / "build"
ICONSET_DIR = BUILD_DIR / "icon.iconset"
ICON_1024_PATH = BUILD_DIR / "icon_1024.png"
ICNS_PATH = BUILD_DIR / "icon.icns"

CANVAS = 1024          # 最终图标画布
SQUIRCLE = 820         # 白色圆角矩形边长（Big Sur 风格留边距）
CORNER_RADIUS = 185    # 圆角半径
MARK_WIDTH = 560       # 红圈 mark 缩放后的宽度
SUPERSAMPLE = 4        # 圆角矩形抗锯齿的超采样倍数

# iconset 规范：(基准尺寸, 是否 @2x)
ICONSET_SIZES = [
    (16, False), (16, True),
    (32, False), (32, True),
    (128, False), (128, True),
    (256, False), (256, True),
    (512, False), (512, True),
]


def find_red_mark_bbox(img: Image.Image) -> tuple[int, int, int, int]:
    """返回红色像素（R>180, G<80, B<80）的外接框 (left, top, right, bottom)。"""
    rgb = img.convert("RGB")
    r, g, b = rgb.split()
    # 三个通道分别二值化后取交集，得到红色像素掩码
    r_mask = r.point(lambda v: 255 if v > 180 else 0)
    g_mask = g.point(lambda v: 255 if v < 80 else 0)
    b_mask = b.point(lambda v: 255 if v < 80 else 0)
    from PIL import ImageChops

    mask = ImageChops.multiply(ImageChops.multiply(r_mask, g_mask), b_mask)
    bbox = mask.getbbox()
    if bbox is None:
        raise RuntimeError(f"在 {LOGO_PATH} 中未找到红色像素，请检查素材")
    return bbox


def crop_mark(img: Image.Image) -> Image.Image:
    """裁出红圈 mark（正方形，略留白边避免圆边被切）。"""
    left, top, right, bottom = find_red_mark_bbox(img)
    w, h = right - left, bottom - top
    # 取长边扩成正方形，并各边加 2% 余量
    side = max(w, h)
    pad = int(side * 0.02)
    cx, cy = (left + right) // 2, (top + bottom) // 2
    half = side // 2 + pad
    box = (
        max(0, cx - half),
        max(0, cy - half),
        min(img.width, cx + half),
        min(img.height, cy + half),
    )
    return img.convert("RGBA").crop(box)


def build_icon_1024(mark: Image.Image) -> Image.Image:
    """透明画布 + 白色圆角矩形 + 居中 mark。"""
    # 超采样绘制圆角矩形，缩回后边缘平滑
    big = CANVAS * SUPERSAMPLE
    big_sq = SQUIRCLE * SUPERSAMPLE
    big_radius = CORNER_RADIUS * SUPERSAMPLE
    plate = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(plate)
    offset = (big - big_sq) // 2
    draw.rounded_rectangle(
        (offset, offset, offset + big_sq, offset + big_sq),
        radius=big_radius,
        fill=(255, 255, 255, 255),
    )
    canvas = plate.resize((CANVAS, CANVAS), Image.LANCZOS)

    # mark 等比缩放到目标宽度后居中贴上（mark 底色为白，与白色圆角矩形融合）
    scale = MARK_WIDTH / mark.width
    mark_resized = mark.resize(
        (MARK_WIDTH, int(mark.height * scale)), Image.LANCZOS
    )
    mx = (CANVAS - mark_resized.width) // 2
    my = (CANVAS - mark_resized.height) // 2
    canvas.paste(mark_resized, (mx, my), mark_resized)
    return canvas


def export_iconset(icon_1024: Image.Image) -> None:
    ICONSET_DIR.mkdir(parents=True, exist_ok=True)
    for base, is_2x in ICONSET_SIZES:
        px = base * 2 if is_2x else base
        suffix = "@2x" if is_2x else ""
        out = ICONSET_DIR / f"icon_{base}x{base}{suffix}.png"
        icon_1024.resize((px, px), Image.LANCZOS).save(out)


def main() -> None:
    if not LOGO_PATH.exists():
        sys.exit(f"素材不存在：{LOGO_PATH}")
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    logo = Image.open(LOGO_PATH)
    mark = crop_mark(logo)
    icon_1024 = build_icon_1024(mark)
    icon_1024.save(ICON_1024_PATH)
    print(f"已生成 {ICON_1024_PATH}")

    export_iconset(icon_1024)
    print(f"已生成 iconset：{ICONSET_DIR}（{len(ICONSET_SIZES)} 个尺寸）")

    subprocess.run(
        ["iconutil", "-c", "icns", str(ICONSET_DIR), "-o", str(ICNS_PATH)],
        check=True,
    )
    size = ICNS_PATH.stat().st_size
    if size <= 0:
        sys.exit("icon.icns 为空，生成失败")
    print(f"已生成 {ICNS_PATH}（{size} 字节）")


if __name__ == "__main__":
    main()
