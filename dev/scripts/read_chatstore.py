# -*- coding: utf-8 -*-
"""读 ChatStore.kt 的存储结构：文件位置、写读方式、是否原子、有无备份。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
F = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame/bot/chat/ChatStore.kt")
lines = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
print("共 %d 行" % len(lines))
print()
print("=== 函数定义 ===")
for i, l in enumerate(lines, 1):
    if re.match(r"\s*(fun|object|data class|private fun|internal fun|val |var )", l):
        print("   %4d| %s" % (i, l.rstrip()[:140]))
print()
print("=== 所有文件 I/O 相关行 ===")
for i, l in enumerate(lines, 1):
    if re.search(r"writeText|readText|File\(|outputStream|delete|renameTo|os\.replace|Json|json", l):
        print("   %4d| %s" % (i, l.strip()[:135]))
