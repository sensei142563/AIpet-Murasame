# -*- coding: utf-8 -*-
"""① 盘点 E:\\university\\order\\python\\pet\\新建文件夹 里的截图/视频
   ② 按类型拷进 E:\\university\\order\\ppt-assets\\shots|clips（仓库外）
   ③ 拼一张带编号的对照图，供我"看图认素材"
"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image, ImageDraw

SRC = r"E:\university\order\python\pet\新建文件夹"
ASSETS = r"E:\university\order\ppt-assets"
SHOTS = os.path.join(ASSETS, "shots")
CLIPS = os.path.join(ASSETS, "clips")
SHEET = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\ppt\out\user-assets-sheet.png"

IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
VID_EXT = (".mp4", ".mkv", ".webm", ".avi", ".mov")

print("=== ① 盘点 %s ===" % SRC)
if not os.path.isdir(SRC):
    print("   ✗ 目录不存在")
    sys.exit(1)
imgs, vids, other = [], [], []
for dp, dn, fn in os.walk(SRC):
    for f in sorted(fn):
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, SRC)
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext in IMG_EXT:
            imgs.append((rel, p, sz))
        elif ext in VID_EXT:
            vids.append((rel, p, sz))
        else:
            other.append((rel, p, sz))

print("   图片 %d 个：" % len(imgs))
for rel, p, sz in imgs:
    try:
        im = Image.open(p)
        info = "%sx%s %s" % (im.width, im.height, im.mode)
    except Exception as e:
        info = "打不开: %s" % str(e)[:40]
    print("      %-46s %9.1f KB  %s" % (rel[:46], sz / 1024, info))
print("   视频 %d 个：" % len(vids))
for rel, p, sz in vids:
    print("      %-46s %9.1f MB" % (rel[:46], sz / 1048576))
if other:
    print("   其他 %d 个：" % len(other))
    for rel, p, sz in other[:10]:
        print("      %-46s %9.1f KB" % (rel[:46], sz / 1024))

# ---------- ② 拷进 ppt-assets ----------
print()
print("=== ② 拷进 %s ===" % ASSETS)
os.makedirs(SHOTS, exist_ok=True)
os.makedirs(CLIPS, exist_ok=True)
copied = 0
for rel, p, sz in imgs:
    dst = os.path.join(SHOTS, os.path.basename(rel))
    if not os.path.isfile(dst):
        shutil.copy2(p, dst)
        copied += 1
for rel, p, sz in vids:
    dst = os.path.join(CLIPS, os.path.basename(rel))
    if not os.path.isfile(dst):
        shutil.copy2(p, dst)
        copied += 1
print("   新拷入 %d 个文件（已存在的跳过）" % copied)
print("   shots 现有：%d 个" % len(os.listdir(SHOTS)))
print("   clips 现有：%d 个" % len(os.listdir(CLIPS)))

# ---------- ③ 拼对照图 ----------
if not imgs:
    print()
    print("   （没有图片，拼不了对照图）")
    sys.exit(0)
CELL, PAD, LAB = 460, 14, 40
cols = 3
rows = (len(imgs) + cols - 1) // cols
W = cols * CELL + (cols + 1) * PAD
H = rows * (CELL + LAB) + (rows + 1) * PAD
# 图片通常不是正方形 ⇒ 按 16:9 给格子
CH = int(CELL * 9 / 16)
H = rows * (CH + LAB) + (rows + 1) * PAD
sheet = Image.new("RGB", (W, H), (246, 246, 249))
d = ImageDraw.Draw(sheet)
for i, (rel, p, sz) in enumerate(imgs):
    r, c = divmod(i, cols)
    x = PAD + c * (CELL + PAD)
    y = PAD + r * (CH + LAB + PAD)
    d.rectangle([x, y, x + CELL - 1, y + CH - 1], fill=(255, 255, 255),
                outline=(190, 190, 200))
    try:
        im = Image.open(p).convert("RGB")
        im.thumbnail((CELL - 8, CH - 8), Image.LANCZOS)
        sheet.paste(im, (x + (CELL - im.width) // 2, y + (CH - im.height) // 2))
    except Exception as e:
        d.text((x + 8, y + 8), "打不开 %s" % str(e)[:30], fill=(200, 40, 40))
    d.text((x + 4, y + CH + 4), "%d) %s" % (i + 1, rel[:56]), fill=(20, 20, 30))
    d.text((x + 4, y + CH + 20), "%.0f KB" % (sz / 1024), fill=(110, 110, 125))
sheet.save(SHEET)
print()
print("   ③ 对照图：%s (%dx%d)" % (SHEET, sheet.width, sheet.height))
