# -*- coding: utf-8 -*-
"""按映射把截图贴到 Deck.pptx 的指定页（脚本层，不动 ppt 引擎）。

用法：python dev/scripts/ppt_add_images.py [目标.pptx]
页码 1-based，与讲稿/操作单一致。

版式规则：
  · 封面（第 1 页）：图放**右侧**、高 5.6in、**紧裁白边**后垂直居中（白底方块尽量小）；
  · 其他页：图片放下半区（y 4.30→7.25in，居中）；
      - 单张：最多用 3.4in 高（放得大一些）
      - 多张：等高并排，间距 0.18in
"""
import os
import sys

from pptx import Presentation
from pptx.util import Inches

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx")
SHOTS = r"E:\university\order\ppt-assets\shots"

PLAN = {
    1:  ["S1-cover.png"],
    13: ["S2-menu.png", "S4b-chat.png"],
    14: ["S3a-outfit.png", "S3b-outfit.png"],
    15: ["S5-status.png", "S5b-memory.png"],
    16: ["S6-launcher.png", "S9-phone-home.jpg", "S10b-im-list.jpg"],
    17: ["S8-tests.png"],
    19: ["S9-phone-home.jpg", "S11-ar1.jpg"],
    20: ["S11-ar2.jpg"],
    22: ["S11-ar1.jpg"],
}

SLIDE_W, SLIDE_H = 13.333, 7.5
TOP_IN, BOTTOM_IN = 4.30, 7.25
SINGLE_MAX_H = 3.40          # 横图单张的上限
SINGLE_MAX_H_TALL = 4.30     # 竖图（手机截图）单张的上限：页面上竖图本来就不占便宜，放宽些
TOP_IN_TALL = 2.95           # 竖图单张时可以从更高的位置开始（要点通常更早结束）
GAP_IN = 0.18
MAX_W = SLIDE_W - 1.2
COVER_H, COVER_RIGHT_MARGIN = 5.10, 0.60
TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_img_tmp")


def cut_background(src, dst, thresh=30, pad=4):
    """封面专用：把**与四边相连**的浅色背景填成透明，再按 alpha 裁到主体。

    为什么不用"全局白色键控"：她头发/衣服也是浅色，全局键控会把它们一起吃掉。
    只填**从四角出发能连到**的区域就安全得多（主体在画面中间、四周有留白）。
    """
    from PIL import Image, ImageDraw
    try:
        im = Image.open(src).convert("RGBA")
        w, h = im.size
        for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            try:
                ImageDraw.floodfill(im, corner, (0, 0, 0, 0), thresh=thresh)
            except Exception:
                pass
        box = im.getbbox()          # 按非透明像素裁
        if box:
            box = (max(0, box[0] - pad), max(0, box[1] - pad),
                   min(w, box[2] + pad), min(h, box[3] + pad))
            im = im.crop(box)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im.save(dst)
        return dst
    except Exception as e:
        print("      ⚠ 去背失败（用原图）: %s" % e)
        return src


def place_cover(slide, path):
    """封面：右侧大图（紧裁白边后垂直居中）。"""
    from PIL import Image
    if not os.path.isfile(path):
        print("      ⚠ 封面图不存在: %s" % os.path.basename(path))
        return 0
    cropped = cut_background(path, os.path.join(TMP, "cover.png"))
    im = Image.open(cropped)
    h = COVER_H
    w = h * (im.width / im.height)
    max_w = SLIDE_W * 0.42
    if w > max_w:
        w = max_w
        h = w * (im.height / im.width)
    x = SLIDE_W - w - COVER_RIGHT_MARGIN
    y = (SLIDE_H - h) / 2.0 + 0.25
    slide.shapes.add_picture(cropped, Inches(x), Inches(y),
                             width=Inches(w), height=Inches(h))
    return 1


def add_row(slide, paths, single_max_h=None):
    from PIL import Image
    usable_h = BOTTOM_IN - TOP_IN
    ims = []
    for p in paths:
        if not os.path.isfile(p):
            print("      ⚠ 跳过（没有这张）: %s" % os.path.basename(p))
            continue
        try:
            im = Image.open(p)
            ims.append((p, im.width, im.height))
        except Exception as e:
            print("      ⚠ 打不开 %s: %s" % (os.path.basename(p), e))
    if not ims:
        return 0
    # ★ 先按"宽度刚好填满可用宽"求高度，再受可用高限制 ——
    #   原来只会从 usable_h 往下缩，导致"图很小、两边大片空白"（第 13 页就是这样）。
    ratio_sum = sum(w / hh for _, w, hh in ims)
    h_by_width = (MAX_W - GAP_IN * (len(ims) - 1)) / max(1e-6, ratio_sum)
    h = min(usable_h, h_by_width)
    if len(ims) == 1 and single_max_h:
        h = min(h, single_max_h)
    for _ in range(80):
        total_w = sum(h * (w / hh) for _, w, hh in ims) + GAP_IN * (len(ims) - 1)
        if total_w <= MAX_W and h <= usable_h:
            break
        h -= 0.05
    total_w = sum(h * (w / hh) for _, w, hh in ims) + GAP_IN * (len(ims) - 1)
    x = (SLIDE_W - total_w) / 2.0
    # 竖图单张时可用区更高一点（下探到 TOP_IN_TALL），其余按原规则
    if len(ims) == 1 and ims[0][2] > ims[0][1]:
        top = TOP_IN_TALL
        y = top + ((BOTTOM_IN - top) - h) / 2.0
    else:
        y = TOP_IN + (usable_h - h) / 2.0
    # ★ 一横一竖搭配时**不强制等高**：各自按比例放大到"高度上限"或"宽度份额"，
    #   底部对齐 —— 否则竖图会把整体高度压小，宽图两侧留一大片空白（第 13 页就是这样）。
    ratios = [w / hh for _, w, hh in ims]
    share = MAX_W / max(1e-6, sum(ratios))          # 按比例分宽度
    placed = []
    for (p, w, hh), rt in zip(ims, ratios):
        h_i = min(usable_h, share)
        w_i = h_i * rt
        if w_i > MAX_W:
            w_i = MAX_W
            h_i = w_i / rt
        placed.append((p, w_i, h_i))
    total_w = sum(w_i for _, w_i, _ in placed) + GAP_IN * (len(placed) - 1)
    x = (SLIDE_W - total_w) / 2.0
    bottom = TOP_IN + usable_h
    for p, w_i, h_i in placed:
        y_i = bottom - h_i                            # 底部对齐
        slide.shapes.add_picture(p, Inches(x), Inches(y_i), width=Inches(w_i), height=Inches(h_i))
        x += w_i + GAP_IN
    return len(placed)


prs = Presentation(DECK)
slides = list(prs.slides)
print("   目标：%s（%d 页）" % (os.path.basename(DECK), len(slides)))
n = 0
for page, names in sorted(PLAN.items()):
    if page > len(slides):
        print("   ⚠ 第 %d 页不存在，跳过" % page)
        continue
    paths = [os.path.join(SHOTS, nm) for nm in names]
    if page == 1:
        k = place_cover(slides[0], paths[0])
        if k:
            print("   ✓ 第  1 页（封面，右侧大图，已裁白边）")
    else:
        k = add_row(slides[page - 1], paths,
                    single_max_h=SINGLE_MAX_H if len(paths) == 1 else None)
        if k:
            print("   ✓ 第 %2d 页贴了 %d 张：%s" % (page, k, "、".join(names[:k])))
    n += k
prs.save(DECK)
print("   共贴入 %d 张 → %s" % (n, DECK))
