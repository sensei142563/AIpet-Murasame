# -*- coding: utf-8 -*-
"""在**用户已编辑过的** Deck.pptx 上工作：
  ① 检查文件锁（WPS/PPT 打开着就写不进去）
  ② 备份一份带时间戳的
  ③ 把当前每一页的**文字**逐形状导出（含位置/大小），看用户改了什么、有没有要修的问题
  ④ 图片单独统计（数量/位置/大小）—— 之后改字时要保证这些**完全不变**
"""
import io
import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pptx import Presentation
from pptx.util import Emu

ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
OUT = os.path.join(ROOT, "dev", "ppt", "out")
DECK = os.path.join(OUT, "Deck.pptx")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

print("=== ① 文件锁检查 ===")
lock = os.path.join(OUT, "~$Deck.pptx")
print("   ~$Deck.pptx 存在？", "是 ✗（可能正被打开）" if os.path.exists(lock) else "否 ✓")
can_write = True
try:
    with open(DECK, "r+b"):
        pass
    print("   可写测试：✓ 能打开写入")
except Exception as e:
    can_write = False
    print("   可写测试：✗ %s" % e)

print()
print("=== ② 备份 ===")
stamp = time.strftime("%Y%m%d-%H%M%S")
bak = os.path.join(OUT, "Deck-用户版-%s.pptx" % stamp)
shutil.copy2(DECK, bak)
print("   ✓ %s (%.1f KB)" % (os.path.basename(bak), os.path.getsize(bak) / 1024))

print()
print("=== ③ 当前每一页的文字 ===")
prs = Presentation(DECK)
print("   页数 %d，幻灯片尺寸 %.3f x %.3f in"
      % (len(prs.slides._sldIdLst), prs.slide_width / 914400, prs.slide_height / 914400))
for i, slide in enumerate(prs.slides, 1):
    print("   ── 第 %d 页 ──" % i)
    for sh in slide.shapes:
        kind = str(sh.shape_type).split()[0] if sh.shape_type is not None else "?"
        if sh.has_text_frame and sh.text_frame.text.strip():
            for para in sh.text_frame.paragraphs:
                t = "".join(r.text for r in para.runs)
                if t.strip():
                    print("      [txt lvl%d] %s" % (para.level, t.strip()[:104]))
        elif sh.shape_type == 13 or "PICTURE" in kind:
            print("      [img] x=%.2f y=%.2f w=%.2f h=%.2f in"
                  % (sh.left / 914400, sh.top / 914400, sh.width / 914400, sh.height / 914400))

print()
print("=== ④ 图片总览（改字时必须保持这些不变）===")
tot = 0
for i, slide in enumerate(prs.slides, 1):
    pics = [sh for sh in slide.shapes if sh.shape_type == 13]
    if pics:
        tot += len(pics)
        print("   第 %2d 页：%d 张  %s" % (i, len(pics),
              " | ".join("(%.2f,%.2f %.2fx%.2f)" % (p.left / 914400, p.top / 914400,
                                                   p.width / 914400, p.height / 914400)
                         for p in pics)[:100]))
print("   合计 %d 张" % tot)
