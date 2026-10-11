# -*- coding: utf-8 -*-
"""核对开关行插在哪个作用域：打印原始行（含缩进）。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SP = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt")
lines = io.open(SP, encoding="utf-8", errors="replace").read().split("\n")
print("=== SettingsPage 的行缩进分布（前 12 种）===")
from collections import Counter
c = Counter(len(l) - len(l.lstrip()) for l in lines if l.strip())
for ind, n in sorted(c.items())[:12]:
    print("   缩进 %2d 空格：%d 行" % (ind, n))

print()
print("=== 含「只回应呼唤」那一段的原文（含缩进）===")
for i, l in enumerate(lines, 1):
    if "只回应呼唤" in l:
        for j in range(max(0, i - 8), min(len(lines), i + 12)):
            mark = ">>" if "只回应呼唤" in lines[j] else "  "
            print("   %s %4d| %s" % (mark, j + 1, lines[j].rstrip()[:126]))
        break

print()
print("=== 花括号平衡检查（函数体范围）===")
depth = 0
fn_line = None
for i, l in enumerate(lines, 1):
    s = l.split("//")[0]
    if fn_line is None and "fun SettingsPage(" in l:
        fn_line = i
    if fn_line and i >= fn_line:
        depth += s.count("{") - s.count("}")
        if "只回应呼唤" in l:
            print("   「只回应呼唤」所在行 %d，此时函数体嵌套深度 = %d" % (i, depth))
            print("   （1 = 直接位于 SettingsPage 的函数体里 ✓；>1 = 在某个 lambda/对话框内部，需检查）")
            break
