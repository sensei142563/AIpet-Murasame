# -*- coding: utf-8 -*-
"""修版式：让图片"尽量放大填满可用宽度"，而不是只会往下缩。
   ① 多图：先按"宽度刚好填满可用宽"求高度，再取 min(该高度, 可用高)
   ② 单图：竖图允许更高（放到 4.30in，从 2.95in 起）；横图仍 ≤ 3.4in
   然后重跑贴图 + 渲染，抽查 13 / 22 页。
"""
import io
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
OUT = os.path.join(ROOT, "dev", "ppt", "out")
ADD = os.path.join(ROOT, "dev", "scripts", "ppt_add_images.py")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

t = io.open(ADD, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

OLD = '''    h = usable_h
    if len(ims) == 1 and single_max_h:
        h = single_max_h
    for _ in range(80):
        total_w = sum(h * (w / hh) for _, w, hh in ims) + GAP_IN * (len(ims) - 1)
        if total_w <= MAX_W:
            break
        h -= 0.05'''
NEW = '''    # ★ 先按"宽度刚好填满可用宽"求高度，再受可用高限制 ——
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
        h -= 0.05'''
if OLD in t:
    t = t.replace(OLD, NEW, 1)
    print("✓ ① 缩放逻辑已改为「尽量放大填满宽度」")
else:
    print("✗ ① 锚点未命中")

# 单图：竖图给更高上限
OLD2 = "SINGLE_MAX_H = 3.40"
NEW2 = ("SINGLE_MAX_H = 3.40          # 横图单张的上限\n"
        "SINGLE_MAX_H_TALL = 4.30     # 竖图（手机截图）单张的上限：页面上竖图本来就不占便宜，放宽些\n"
        "TOP_IN_TALL = 2.95           # 竖图单张时可以从更高的位置开始（要点通常更早结束）")
if OLD2 in t:
    t = t.replace(OLD2, NEW2, 1)
    print("✓ ② 已加竖图专用上限")

OLD3 = '''    x = (SLIDE_W - total_w) / 2.0
    y = TOP_IN + (usable_h - h) / 2.0'''
NEW3 = '''    x = (SLIDE_W - total_w) / 2.0
    # 竖图单张时可用区更高一点（下探到 TOP_IN_TALL），其余按原规则
    if len(ims) == 1 and ims[0][2] > ims[0][1]:
        top = TOP_IN_TALL
        y = top + ((BOTTOM_IN - top) - h) / 2.0
    else:
        y = TOP_IN + (usable_h - h) / 2.0'''
if OLD3 in t:
    t = t.replace(OLD3, NEW3, 1)
    print("✓ ③ 竖图单张的起始位置已上移")
else:
    print("✗ ③ 锚点未命中")

io.open(ADD, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== ④ 从文字版重来 → 贴图 → 渲染 ===")
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

print()
print("=== ⑤ 再拼一张 13 / 14 / 15 / 19 / 20 / 22 的对照（重点看这几页）===")
from PIL import Image, ImageDraw  # noqa: E402
QC = os.path.join(OUT, "qc")
pick = [13, 14, 15, 19, 20, 22]
CELL_W, PAD, LAB = 520, 12, 26
cols = 2
rows = (len(pick) + cols - 1) // cols
ch = int(CELL_W * 9 / 16)
sheet = Image.new("RGB", (cols * CELL_W + (cols + 1) * PAD,
                          rows * (ch + LAB) + (rows + 1) * PAD), (240, 240, 244))
d = ImageDraw.Draw(sheet)
for i, num in enumerate(pick):
    p = os.path.join(QC, "slide-%02d.png" % num)
    if not os.path.isfile(p):
        continue
    r_, c_ = divmod(i, cols)
    x = PAD + c_ * (CELL_W + PAD)
    y = PAD + r_ * (ch + LAB + PAD)
    im = Image.open(p).convert("RGB").resize((CELL_W, ch), Image.LANCZOS)
    sheet.paste(im, (x, y))
    d.rectangle([x, y, x + CELL_W - 1, y + ch - 1], outline=(170, 170, 180))
    d.text((x + 3, y + ch + 5), "第 %d 页" % num, fill=(20, 20, 30))
sp = os.path.join(OUT, "check-pages.png")
sheet.save(sp)
print("   ✓ %s (%dx%d)" % (sp, sheet.width, sheet.height))
