# -*- coding: utf-8 -*-
"""打印 OneBotAdversarialTest.kt 第 28~44 行原文（含行号与字符码，看清语法错在哪）。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
F = os.path.join(PET, "chatter",
                 "app/src/test/java/com/aipet/murasame/OneBotAdversarialTest.kt")
lines = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
for i in range(27, min(45, len(lines))):
    l = lines[i]
    print("%4d| %s" % (i + 1, l))
print()
print("=== 第 36 行逐字符（看有没有隐藏字符）===")
if len(lines) >= 36:
    l = lines[35]
    print(repr(l))
    print("长度:", len(l))
