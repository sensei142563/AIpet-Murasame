# -*- coding: utf-8 -*-
"""封面再改进：把**与四边相连**的白色填成透明（PNG 带 alpha，PowerPoint 显示为透明），
   这样她就"站"在深咖封面上了，而不是贴一块白纸。
   —— 只填连通区，不动她身上的白色。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
ADD = os.path.join(ROOT, "dev", "scripts", "ppt_add_images.py")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

t = io.open(ADD, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

OLD = '''def tight_crop(src, dst, bg_tol=12):
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
        return src'''

NEW = '''def cut_background(src, dst, thresh=30, pad=4):
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
        return src'''

if OLD in t:
    t = t.replace(OLD, NEW, 1)
    t = t.replace('cropped = tight_crop(path, os.path.join(TMP, "cover.png"))',
                  'cropped = cut_background(path, os.path.join(TMP, "cover.png"))')
    print("✓ ① 已把封面改成填透明背景（只填连通区）")
else:
    print("✗ ① 锚点未命中")

# 封面尺寸微调：略小一点、别顶到上下边
t = t.replace("COVER_H, COVER_RIGHT_MARGIN = 5.60, 0.55",
              "COVER_H, COVER_RIGHT_MARGIN = 5.10, 0.60")
print("✓ ② 封面图高度 5.60 → 5.10in（留出上下呼吸）")
io.open(ADD, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== ③ 从文字版重来 → 贴图 → 渲染 ===")
import shutil  # noqa: E402
OUT = os.path.join(ROOT, "dev", "ppt", "out")
shutil.copy2(os.path.join(OUT, "Deck-文字版.pptx"), os.path.join(OUT, "Deck.pptx"))
r = subprocess.run([sys.executable, ADD, os.path.join(OUT, "Deck.pptx")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if l.strip():
        print("   " + l.strip()[:126])
r2 = subprocess.run(["powershell", "-NoProfile", "-File",
                     r"E:\Codex\workflows\ppt\scripts\render_qc.ps1",
                     "-Deck", os.path.join(OUT, "Deck.pptx")],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=2400)
for l in ((r2.stdout or "") + (r2.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:120])
