# -*- coding: utf-8 -*-
"""打印 accept_all.py 出错区域（含行号），看清正则替换切坏了什么。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(MAIN, "dev", "scripts", "accept_all.py")
lines = io.open(P, encoding="utf-8").read().split("\n")
print("文件共 %d 行" % len(lines))
for i in range(222, min(len(lines), 252)):
    print("   %4d| %s" % (i + 1, lines[i].rstrip()))
