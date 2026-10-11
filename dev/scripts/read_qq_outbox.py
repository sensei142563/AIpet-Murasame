# -*- coding: utf-8 -*-
"""读 qq/qq_outbox.py 全文（投递可靠性审查前置）。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
F = os.path.join(MAIN, "qq", "qq_outbox.py")
lines = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
print("文件共 %d 行" % len(lines))
for i, l in enumerate(lines, 1):
    print("%4d| %s" % (i, l.rstrip()))
