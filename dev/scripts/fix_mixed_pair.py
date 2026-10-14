# -*- coding: utf-8 -*-
"""第 13 页那类"一横一竖"搭配：不再强制等高，改成**各自按比例尽量放大**（底部对齐）。
   同时核对 Deck.pptx 的讲稿还在（我是从"文字版"重来的，讲稿应该带着）。
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

OLD = '''    for p, w, hh in ims:
        ww = h * (w / hh)
        slide.shapes.add_picture(p, Inches(x), Inches(y), width=Inches(ww), height=Inches(h))
        x += ww + GAP_IN
    return len(ims)'''
NEW = '''    # ★ 一横一竖搭配时**不强制等高**：各自按比例放大到"高度上限"或"宽度份额"，
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
    return len(placed)'''
if OLD in t:
    t = t.replace(OLD, NEW, 1)
    print("✓ ① 已改为「各自按比例放大 + 底部对齐」")
else:
    print("✗ ① 锚点未命中")

# 单图时不走这条（len==1 时 share/height 逻辑等价，无妨）
io.open(ADD, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== ② 从文字版重来 → 贴图 → 渲染 → 核对讲稿 ===")
shutil.copy2(os.path.join(OUT, "Deck-文字版.pptx"), os.path.join(OUT, "Deck.pptx"))
r = subprocess.run([sys.executable, ADD, os.path.join(OUT, "Deck.pptx")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if l.strip():
        print("   " + l.strip()[:126])

r2 = subprocess.run([sys.executable, "-c",
                     "from pptx import Presentation\n"
                     "p=Presentation(r'dev/ppt/out/Deck.pptx')\n"
                     "n=len(p.slides._sldIdLst)\n"
                     "notes=sum(1 for s in p.slides if s.has_notes_slide "
                     "and s.notes_slide.notes_text_frame.text.strip())\n"
                     "pics=sum(1 for s in p.slides for sh in s.shapes if sh.shape_type==13)\n"
                     "print('   页数=%d  有讲稿=%d  图片=%d' % (n, notes, pics))\n"],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", env=ENV, timeout=600)
print((r2.stdout or "").rstrip())

r3 = subprocess.run(["powershell", "-NoProfile", "-File",
                     r"E:\Codex\workflows\ppt\scripts\render_qc.ps1",
                     "-Deck", os.path.join(OUT, "Deck.pptx")],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=2400)
for l in ((r3.stdout or "") + (r3.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:120])
