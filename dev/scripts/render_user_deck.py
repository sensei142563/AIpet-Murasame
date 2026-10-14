# -*- coding: utf-8 -*-
"""渲染用户当前版本的 Deck.pptx，并把"最长行"的几页 + 全部页拼成两张对照图。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image, ImageDraw

ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
OUT = os.path.join(ROOT, "dev", "ppt", "out")
QC = os.path.join(OUT, "qc")
DECK = os.path.join(OUT, "Deck.pptx")

print("=== 渲染 ===")
r = subprocess.run(["powershell", "-NoProfile", "-File",
                    r"E:\Codex\workflows\ppt\scripts\render_qc.ps1", "-Deck", DECK],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   timeout=2400)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:120])


def sheet(pages, out_name, cols, cell_w):
    ch = int(cell_w * 9 / 16)
    rows = (len(pages) + cols - 1) // cols
    PAD, LAB = 12, 26
    W = cols * cell_w + (cols + 1) * PAD
    H = rows * (ch + LAB) + (rows + 1) * PAD
    im = Image.new("RGB", (W, H), (240, 240, 244))
    d = ImageDraw.Draw(im)
    for i, num in enumerate(pages):
        p = os.path.join(QC, "slide-%02d.png" % num)
        if not os.path.isfile(p):
            continue
        rr, cc = divmod(i, cols)
        x = PAD + cc * (cell_w + PAD)
        y = PAD + rr * (ch + LAB + PAD)
        s = Image.open(p).convert("RGB").resize((cell_w, ch), Image.LANCZOS)
        im.paste(s, (x, y))
        d.rectangle([x, y, x + cell_w - 1, y + ch - 1], outline=(170, 170, 180))
        d.text((x + 3, y + ch + 5), "第 %d 页" % num, fill=(20, 20, 30))
    fp = os.path.join(OUT, out_name)
    im.save(fp)
    print("   ✓ %s (%dx%d)" % (fp, im.width, im.height))
    return fp


print()
print("=== 拼图 ===")
sheet([3, 10, 15, 21], "check-long.png", 2, 620)
sheet(list(range(1, 25)), "all-slides.png", 4, 400)
