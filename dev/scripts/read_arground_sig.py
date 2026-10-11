# -*- coding: utf-8 -*-
"""读 ArGround 的真实函数签名（不猜）。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
F = os.path.join(PET, "chatter",
                 "app/src/main/java/com/aipet/murasame/ui/ArGround.kt")
lines = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
print("=== ArGround 的公开函数（含参数类型）===")
cur = None
for i, l in enumerate(lines, 1):
    if "fun " in l:
        cur = i
        print("   %4d| %s" % (i, l.strip()[:150]))
    elif cur and i - cur <= 3 and l.strip() and not l.strip().startswith("//"):
        print("        | %s" % l.strip()[:150])
    else:
        cur = None if l.strip().endswith("}") else cur
print()
print("=== 常量/枚举 ===")
for i, l in enumerate(lines, 1):
    if "const" in l or "enum class" in l or "object " in l:
        print("   %4d| %s" % (i, l.strip()[:130]))
