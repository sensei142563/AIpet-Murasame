# -*- coding: utf-8 -*-
"""读 Store.kt 的结构：函数、安装流程、registry、锁与回滚。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
F = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame/Store.kt")
lines = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
print("共 %d 行" % len(lines))
print()
print("=== 函数与顶层声明 ===")
for i, l in enumerate(lines, 1):
    if re.match(r"\s*(fun|object|class|data class|private fun|internal fun|val |var |const )", l):
        print("   %4d| %s" % (i, l.rstrip()[:140]))
print()
print("=== 关键流程行（安装/注册/锁/回滚/校验）===")
for i, l in enumerate(lines, 1):
    if re.search(r"install|registry|lock|rollback|回滚|校验|verify|missing|缺|catch|finally|"
                 r"delete|mkdirs|copyTo|listFiles|assets", l):
        print("   %4d| %s" % (i, l.strip()[:135]))
