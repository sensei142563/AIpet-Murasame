# -*- coding: utf-8 -*-
"""读 tool/memory_transfer.py 的 cmd_import 与 main（60~125 行原文）。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
lines = io.open(os.path.join(MAIN, "tool", "memory_transfer.py"),
                encoding="utf-8", errors="replace").read().split("\n")
for i in range(59, min(125, len(lines))):
    print("%4d| %s" % (i + 1, lines[i].rstrip()))
