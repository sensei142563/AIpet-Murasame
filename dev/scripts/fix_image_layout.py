# -*- coding: utf-8 -*-
"""修正贴图版式：
  ① 从 Deck-文字版.pptx 重来（避免重复贴图）
  ② 改 ppt_add_images.py：
     · 封面（第 1 页）：图放**右侧**、高 5.6in、**紧裁白边**后居中
     · 单图页：允许放大到 3.4in 高（原来 2.95in 太小）
     · 多图页：维持等高并排
  ③ 重新贴图 + 渲染
"""
import io
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
OUT = os.path.join(ROOT, "dev", "ppt", "out")
DECK = os.path.join(OUT, "Deck.pptx")
TXT = os.path.join(OUT, "Deck-文字版.pptx")
SHOTS = r"E:\university\order\ppt-assets\shots"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

print("=== ① 从文字版重来 ===")
if os.path.isfile(TXT):
    shutil.copy2(TXT, DECK)
    print("   ✓ 已用 %s 覆盖 Deck.pptx（干净起点）" % os.path.basename(TXT))
else:
    print("   ✗ 没有文字版备份，退出")
    sys.exit(1)

print()
print("=== ② 重写 ppt_add_images.py（含封面专用规则 + 紧裁白边）===")
CODE = '''# -*- coding: utf-8 -*-
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
SHOTS = r"E:\\university\\order\\ppt-assets\\shots"

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
SINGLE_MAX_H = 3.40
GAP_IN = 0.18
MAX_W = SLIDE_W - 1.2
COVER_H, COVER_RIGHT_MARGIN = 5.60, 0.55
TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_img_tmp")


def tight_crop(src, dst, bg_tol=12):
    """把四周的纯色边（截图白边）裁掉，只留主体。失败就原样复制。"""
    from PIL import Image, ImageChops
    try:
        im = Image.open(src).convert("RGB")
        bg = Image.new("RGB", im.size, im.getpixel((0, 0)))
        diff = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > bg_tol else 0)
        box = diff.getbbox()
        if box:
            pad = 6
            box = (max(0, box[0] - pad), max(0, box[1] - pad),
                   min(im.width, box[2] + pad), min(im.height, box[3] + pad))
            im = im.crop(box)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im.save(dst)
        return dst
    except Exception as e:
        print("      ⚠ 裁边失败（用原图）: %s" % e)
        return src


def place_cover(slide, path):
    """封面：右侧大图（紧裁白边后垂直居中）。"""
    from PIL import Image
    if not os.path.isfile(path):
        print("      ⚠ 封面图不存在: %s" % os.path.basename(path))
        return 0
    cropped = tight_crop(path, os.path.join(TMP, "cover.png"))
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
    h = usable_h
    if len(ims) == 1 and single_max_h:
        h = single_max_h
    for _ in range(80):
        total_w = sum(h * (w / hh) for _, w, hh in ims) + GAP_IN * (len(ims) - 1)
        if total_w <= MAX_W:
            break
        h -= 0.05
    total_w = sum(h * (w / hh) for _, w, hh in ims) + GAP_IN * (len(ims) - 1)
    x = (SLIDE_W - total_w) / 2.0
    y = TOP_IN + (usable_h - h) / 2.0
    for p, w, hh in ims:
        ww = h * (w / hh)
        slide.shapes.add_picture(p, Inches(x), Inches(y), width=Inches(ww), height=Inches(h))
        x += ww + GAP_IN
    return len(ims)


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
'''
p = os.path.join(ROOT, "dev", "scripts", "ppt_add_images.py")
io.open(p, "w", encoding="utf-8", newline="\n").write(CODE)
print("   ✓ 已重写（封面右侧大图 + 紧裁白边 + 单图放大）")

print()
print("=== ③ 贴图 + 渲染 ===")
r = subprocess.run([sys.executable, p, DECK], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=ENV, timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if l.strip():
        print("   " + l.strip()[:130])
r2 = subprocess.run(["powershell", "-NoProfile", "-File",
                     r"E:\Codex\workflows\ppt\scripts\render_qc.ps1", "-Deck", DECK],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=2400)
for l in ((r2.stdout or "") + (r2.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:120])
