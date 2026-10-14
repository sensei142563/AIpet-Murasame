# -*- coding: utf-8 -*-
"""只改 3 处文字，然后断言：图片位置尺寸与改前**完全一致**。
   ① 第 20 页页码 21 → 20
   ② 第 21 页页码 20 → 21
   ③ 第 4 页 Ukagaka(SSP) → Ukagaka（SSP）
"""
import io
import json
import os
import re
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pptx import Presentation

ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
OUT = os.path.join(ROOT, "dev", "ppt", "out")
DECK = os.path.join(OUT, "Deck.pptx")
SNAP = os.path.join(OUT, "_img_snapshot_before.json")

# 备份
stamp = time.strftime("%Y%m%d-%H%M%S")
bak = os.path.join(OUT, "Deck-改字前-%s.pptx" % stamp)
shutil.copy2(DECK, bak)
print("✓ 已备份 %s" % os.path.basename(bak))

prs = Presentation(DECK)
slides = list(prs.slides)
changed = []


def set_run_text(shape, old_para_text, new_para_text):
    """把某段落里匹配的文字换掉：优先整段一个 run，否则改包含目标的那个 run。"""
    for para in shape.text_frame.paragraphs:
        cur = "".join(r.text for r in para.runs)
        if cur.strip() == old_para_text.strip():
            if len(para.runs) == 1:
                para.runs[0].text = new_para_text
            else:
                # 只改第一个 run，其余清空（保持第一个 run 的格式）
                para.runs[0].text = new_para_text
                for r in para.runs[1:]:
                    r.text = ""
            return True
    return False


# ① 页码：20 页的 "21" → "20"，21 页的 "20" → "21"
for idx, (page, old, new) in enumerate([(20, "21", "20"), (21, "20", "21")], 1):
    slide = slides[page - 1]
    done = False
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        for para in sh.text_frame.paragraphs:
            t = "".join(r.text for r in para.runs).strip()
            if t == old and len(para.runs) >= 1:
                para.runs[0].text = new
                for r in para.runs[1:]:
                    r.text = ""
                changed.append("第 %d 页 页码 %s → %s" % (page, old, new))
                done = True
                break
        if done:
            break
    if not done:
        print("   ⚠ 第 %d 页没找到页码 %s" % (page, old))

# ② 第 4 页半角括号
slide4 = slides[3]
done4 = False
for sh in slide4.shapes:
    if not sh.has_text_frame:
        continue
    for para in sh.text_frame.paragraphs:
        t = "".join(r.text for r in para.runs)
        if "Ukagaka(SSP)" in t:
            newt = t.replace("Ukagaka(SSP)", "Ukagaka（SSP）")
            if len(para.runs) == 1:
                para.runs[0].text = newt
            else:
                para.runs[0].text = newt
                for r in para.runs[1:]:
                    r.text = ""
            changed.append("第 4 页 Ukagaka(SSP) → Ukagaka（SSP）")
            done4 = True
            break
    if done4:
        break
if not done4:
    print("   ⚠ 第 4 页没找到 Ukagaka(SSP)（可能已改过）")

prs.save(DECK)
print()
print("=== 本次改动 ===")
for c in changed:
    print("   ✓ " + c)

# ---------- 断言：图片完全没动 ----------
print()
print("=== 断言：图片位置/尺寸与改前一致 ===")
before = json.loads(io.open(SNAP, encoding="utf-8").read())
prs2 = Presentation(DECK)
after = []
for i, slide in enumerate(prs2.slides, 1):
    for sh in slide.shapes:
        if sh.shape_type == 13:
            after.append([i, sh.left, sh.top, sh.width, sh.height, sh.name])
print("   改前 %d 张 / 改后 %d 张" % (len(before), len(after)))
if before == after:
    print("   ✓✓ **完全一致**：图片位置、尺寸、顺序、页码归属都没有变化")
else:
    print("   ✗ 有差异：")
    for b, a in zip(before, after):
        if b != a:
            print("      前 %s" % b)
            print("      后 %s" % a)
    if len(before) != len(after):
        print("      ✗ 数量不同！")

# ---------- 复核文字 ----------
print()
print("=== 复核修改后的文字 ===")
for i, slide in enumerate(Presentation(DECK).slides, 1):
    if i not in (4, 20, 21):
        continue
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        for para in sh.text_frame.paragraphs:
            t = "".join(r.text for r in para.runs).strip()
            if not t:
                continue
            if re.fullmatch(r"\d{1,3}", t) or "Ukagaka" in t:
                print("   第 %2d 页：%s" % (i, t[:100]))
