# -*- coding: utf-8 -*-
"""读 tool/memory_transfer.py 的函数与数据格式（为对抗测试做准备）。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
F = os.path.join(MAIN, "tool", "memory_transfer.py")
lines = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
print("文件共 %d 行" % len(lines))
print()
print("=== 函数定义 ===")
for i, l in enumerate(lines, 1):
    if re.match(r"^(def |class |[A-Z_]+ = )", l):
        print("   %4d| %s" % (i, l.rstrip()[:140]))
print()
print("=== 关键键名/字段（schema 相关）===")
for i, l in enumerate(lines, 1):
    if re.search(r'"(id|text|content|role|ts|time|key|user|assistant|pet|version|schema)"', l):
        print("   %4d| %s" % (i, l.strip()[:130]))
print()
print("=== 前 60 行（看格式约定）===")
for i in range(0, min(60, len(lines))):
    print("   %4d| %s" % (i + 1, lines[i].rstrip()[:130]))
