# -*- coding: utf-8 -*-
"""用历史里的好图修复诺瓦头像（三份：avatar.png / avatar.jpg / 诺瓦.jpg），并目视验收。"""
import io
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image, ImageDraw

ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
ND = os.path.join(ROOT, "pets", "noir")
OUT = os.path.join(ROOT, "dev", "ppt", "out")

# 好图来源：8ecb1589 的 avatar.jpg（2026-09-24，目视确认是正常的诺瓦头像）
GOOD_SRC = "8ecb1589:pets/noir/avatar.jpg"
good_bytes = subprocess.run(["git", "-C", ROOT, "show", GOOD_SRC],
                            capture_output=True).stdout
print("=== ① 取好图 ===")
print("   %s → %d 字节" % (GOOD_SRC, len(good_bytes)))
if len(good_bytes) < 1000:
    print("   ✗ 没取到，退出")
    sys.exit(1)
tmp_good = os.path.join(ROOT, "dev", "tmp", "noir_good.jpg")
os.makedirs(os.path.dirname(tmp_good), exist_ok=True)
with open(tmp_good, "wb") as f:
    f.write(good_bytes)
im = Image.open(tmp_good)
print("   %s  %sx%s" % (im.mode, im.width, im.height))

print()
print("=== ② 修复三份文件（坏的先备份）===")
# 1) avatar.jpg / 诺瓦.jpg：直接换成好图
for name in ("avatar.jpg", "诺瓦.jpg"):
    p = os.path.join(ND, name)
    if os.path.isfile(p):
        bak = p + ".broken.bak"
        if not os.path.isfile(bak):
            shutil.copy2(p, bak)
    shutil.copy2(tmp_good, p)
    print("   ✓ %-14s %d B（坏图备份为 %s.broken.bak）" % (name, os.path.getsize(p), name))

# 2) avatar.png：从好图正确转出真 PNG
jj = Image.open(tmp_good)
jj = jj.convert("RGBA" if jj.mode in ("RGBA", "LA", "P") else "RGB")
jj.save(os.path.join(ND, "avatar.png"), "PNG")
print("   ✓ %-14s %d B（真 PNG，由好图转出）"
      % ("avatar.png", os.path.getsize(os.path.join(ND, "avatar.png"))))

print()
print("=== ③ 目视验收表（坏 vs 修复后 vs 其他角色）===")
items = [
    ("诺瓦 坏图(备份)", os.path.join(ND, "avatar.png.broken.bak")),
    ("诺瓦 修复后 png", os.path.join(ND, "avatar.png")),
    ("诺瓦 修复后 jpg", os.path.join(ND, "avatar.jpg")),
]
import re  # noqa: E402
for d in ("murasame", "natsume", "arona", "hiyori"):
    pj = os.path.join(ROOT, "pets", d, "pet.json")
    if not os.path.isfile(pj):
        continue
    t = io.open(pj, encoding="utf-8", errors="replace").read()
    m = re.search(r'"avatar"\s*:\s*"([^"]+)"', t)
    if m:
        items.append((d, os.path.join(ROOT, "pets", d, m.group(1).replace("/", os.sep))))

CELL, PAD, LAB = 200, 12, 34
cols = 4
rows = (len(items) + cols - 1) // cols
sheet = Image.new("RGB", (cols * CELL + (cols + 1) * PAD,
                          rows * (CELL + LAB) + (rows + 1) * PAD), (246, 246, 249))
dr = ImageDraw.Draw(sheet)
for i, (name, path) in enumerate(items):
    r, c = divmod(i, cols)
    x = PAD + c * (CELL + PAD)
    y = PAD + r * (CELL + LAB + PAD)
    dr.rectangle([x, y, x + CELL - 1, y + CELL - 1], fill=(255, 255, 255),
                 outline=(190, 190, 200))
    if os.path.isfile(path):
        ii = Image.open(path).convert("RGBA")
        ii.thumbnail((CELL - 10, CELL - 10), Image.LANCZOS)
        sheet.paste(ii, (x + (CELL - ii.width) // 2, y + (CELL - ii.height) // 2), ii)
    else:
        dr.text((x + 8, y + 8), "缺文件", fill=(200, 40, 40))
    dr.text((x + 4, y + CELL + 5), name, fill=(20, 20, 30))
    dr.text((x + 4, y + CELL + 19), os.path.basename(path)[:28], fill=(110, 110, 125))
p = os.path.join(OUT, "avatar-health2.png")
sheet.save(p)
print("   ✓ %s (%dx%d)" % (p, sheet.width, sheet.height))
