# -*- coding: utf-8 -*-
"""给 Deck.pptx 加**讲稿备注**（写在脚本层，不改 E:\\Codex\\workflows\\ppt 的引擎文件）。

用法：
  python dev/scripts/ppt_add_notes.py
读 dev/ppt/notes.json（{"notes": {"1": "...", ...}}），按页码写进对应页的备注。
验证：写完重新打开 pptx 逐页读回备注，核对条数与内容。
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
# 可选：命令行给一个目标 pptx（默认仍是 Deck.pptx）。
# 用途：Deck.pptx 被 PowerPoint/WPS 打开时会被加写锁，此时先建到别的名字再挂讲稿。
DECK = (sys.argv[1] if len(sys.argv) > 1
        else os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx"))
NOTES = os.path.join(ROOT, "dev", "ppt", "notes.json")

from pptx import Presentation            # noqa: E402

notes = json.loads(io.open(NOTES, encoding="utf-8", errors="replace").read()).get("notes") or {}
prs = Presentation(DECK)
print("页数 =", len(prs.slides.__iter__.__self__._sldIdLst), "备注条数 =", len(notes))

written = 0
for idx, slide in enumerate(prs.slides, 1):
    txt = notes.get(str(idx))
    if not txt:
        continue
    try:
        slide.notes_slide.notes_text_frame.text = txt
        written += 1
    except Exception as e:
        print("   ✗ 第 %d 页写备注失败: %s" % (idx, e))
prs.save(DECK)
print("✓ 已写入备注 %d 页 → %s" % (written, DECK))

# 读回验证
prs2 = Presentation(DECK)
back = []
for idx, slide in enumerate(prs2.slides, 1):
    try:
        t = (slide.notes_slide.notes_text_frame.text or "").strip()
    except Exception:
        t = ""
    if t:
        back.append((idx, t))
print("=== 读回验证：%d 页有备注 ===" % len(back))
for idx, t in back[:4]:
    print("   %2d| %s" % (idx, t[:66]))
print("   …")
for idx, t in back[-2:]:
    print("   %2d| %s" % (idx, t[:66]))
missing = [i for i in range(1, len(prs2.slides._sldIdLst) + 1) if i not in [b[0] for b in back]]
print("   缺备注的页：", missing or "无 ✓")
