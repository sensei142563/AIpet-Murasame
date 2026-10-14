# -*- coding: utf-8 -*-
"""① 复查 24 页页码（含前导零判定）
   ② 确认 24 段讲稿还在
   ③ 重新渲染 + 拼图（第 4/20/21 页 + 全页总览）
   ④ 把主人确认的两条设计决定补进调研文档
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pptx import Presentation
from PIL import Image, ImageDraw

ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
OUT = os.path.join(ROOT, "dev", "ppt", "out")
QC = os.path.join(OUT, "qc")
DECK = os.path.join(OUT, "Deck.pptx")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

prs = Presentation(DECK)
print("=== ① 页码复查（页码形状约 12.1 x 0.3 in；章节号 11.0 x 1.4 in 不算）===")
bad = []
for i, slide in enumerate(prs.slides, 1):
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        for para in sh.text_frame.paragraphs:
            t = "".join(r.text for r in para.runs).strip()
            if not re.fullmatch(r"\d{2}", t):
                continue
            w = (sh.width or 0) / 914400.0
            if abs(w - 12.1) > 0.4:
                continue                      # 章节号，跳过
            if int(t) != i:
                bad.append((i, t))
print("   页码与页序不符的：%s" % (bad if bad else "无 ✓"))

print()
print("=== ② 讲稿清点 ===")
notes = sum(1 for s in prs.slides
            if s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip())
pics = sum(1 for s in prs.slides for sh in s.shapes if sh.shape_type == 13)
print("   页数 %d / 有讲稿 %d / 图片 %d" % (len(prs.slides._sldIdLst), notes, pics))

print()
print("=== ③ 渲染 ===")
r = subprocess.run(["powershell", "-NoProfile", "-File",
                    r"E:\Codex\workflows\ppt\scripts\render_qc.ps1", "-Deck", DECK],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   timeout=2400)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:120])


def sheet(pages, name, cols, cw):
    ch = int(cw * 9 / 16)
    rows = (len(pages) + cols - 1) // cols
    PAD, LAB = 12, 26
    im = Image.new("RGB", (cols * cw + (cols + 1) * PAD, rows * (ch + LAB) + (rows + 1) * PAD),
                   (240, 240, 244))
    d = ImageDraw.Draw(im)
    for i, num in enumerate(pages):
        p = os.path.join(QC, "slide-%02d.png" % num)
        if not os.path.isfile(p):
            continue
        rr, cc = divmod(i, cols)
        x = PAD + cc * (cw + PAD)
        y = PAD + rr * (ch + LAB + PAD)
        im.paste(Image.open(p).convert("RGB").resize((cw, ch), Image.LANCZOS), (x, y))
        d.rectangle([x, y, x + cw - 1, y + ch - 1], outline=(170, 170, 180))
        d.text((x + 3, y + ch + 5), "第 %d 页" % num, fill=(20, 20, 30))
    fp = os.path.join(OUT, name)
    im.save(fp)
    print("   ✓ %s" % fp)


sheet([4, 20, 21], "check-fixed.png", 3, 620)

print()
print("=== ④ 把主人确认的设计决定补进调研文档 ===")
doc = os.path.join(ROOT, "dev", "docs", "调研-冷热值与记忆检索-2026-10-14.md")
t = io.open(doc, encoding="utf-8", errors="replace").read()
ADD = """

---

## 五、主人已确认的决定（2026-10-14）

> 以下为拍板结果，落地时直接照此实现：

1. **冷热值采用「双轴」** —— 温度（warmth，可涨可落，决定当下话多话少与亲昵度）
   ＋ 耐久维度（trust / security / attachment / familiarity，只由事件驱动、不被动漂移）。
2. **「思念」只在「温度极低」时触发** —— 不是"稍冷就触发"，也不是"久未互动就触发"，
   而是**温度落到极低档位**才允许触发（温和、稀有、有分量）。
   建议实现：`warmth <= 极低阈值`（例如 ≤ -60 或分档里的最低档）时才让"心结/想念"字段累积，
   且触发一次后回落，避免连续刷屏。
3. 其余问题（半衰期具体数值、是否在状态页可视化、记忆检索是否先做 BM25）**仍待定**。
"""
if "主人已确认的决定" not in t:
    t = t.rstrip() + "\n" + ADD
    io.open(doc, "w", encoding="utf-8", newline="\n").write(t)
    print("   ✓ 已补入两条决定")
else:
    print("   · 已存在，跳过")
