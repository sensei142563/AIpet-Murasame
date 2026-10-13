# -*- coding: utf-8 -*-
"""找 widgets.py 里所有把 vision_source 默认写成 local 的地方。"""
import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
F = r"E:\university\order\python\pet\AIpet-Murasame-main\pcl_launcher\widgets.py"
t = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
print("=== 含 vision_source 的行 + 后 3 行上下文 ===")
for i, l in enumerate(t, 1):
    if "vision_source" in l:
        for j in range(i - 1, min(len(t), i + 3)):
            mark = ">>" if j + 1 == i else "  "
            print("%s %5d| %s" % (mark, j + 1, t[j].rstrip()[:116]))
        print()
print("=== 精确匹配断言用的那个片段 ===")
pat = '["local", "cloud"], "local"'
for i, l in enumerate(t, 1):
    if pat in l:
        print("   ✗ 第 %d 行: %s" % (i, l.strip()[:116]))
print("=== 也查一下单引号写法 ===")
pat2 = "['local', 'cloud'], 'local'"
for i, l in enumerate(t, 1):
    if pat2 in l:
        print("   ✗ 第 %d 行: %s" % (i, l.strip()[:116]))
