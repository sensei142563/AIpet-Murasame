# -*- coding: utf-8 -*-
"""把渲染出的 24 页拼成一张总览图，一次性验收全部页面的版式。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image, ImageDraw

QC = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\ppt\out\qc"
OUT = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\ppt\out\all-slides.png"

files = []
for i in range(1, 25):
    p = os.path.join(QC, "slide-%02d.png" % i)
    if os.path.isfile(p):
        files.append((i, p))
print("   找到 %d 页渲染图" % len(files))

CELL_W, PAD, LAB = 400, 10, 22
cols = 4
rows = (len(files) + cols - 1) // cols
ch = int(CELL_W * 9 / 16)
W = cols * CELL_W + (cols + 1) * PAD
H = rows * (ch + LAB) + (rows + 1) * PAD
sheet = Image.new("RGB", (W, H), (240, 240, 244))
d = ImageDraw.Draw(sheet)
for idx, (num, p) in enumerate(files):
    r, c = divmod(idx, cols)
    x = PAD + c * (CELL_W + PAD)
    y = PAD + r * (ch + LAB + PAD)
    im = Image.open(p).convert("RGB")
    im = im.resize((CELL_W, ch), Image.LANCZOS)
    sheet.paste(im, (x, y))
    d.rectangle([x, y, x + CELL_W - 1, y + ch - 1], outline=(170, 170, 180))
    d.text((x + 3, y + ch + 4), "第 %d 页" % num, fill=(20, 20, 30))
sheet.save(OUT)
print("   ✓ %s (%dx%d)" % (OUT, sheet.width, sheet.height))
