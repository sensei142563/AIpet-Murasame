# -*- coding: utf-8 -*-
"""读 bot/ilink 目录：文件清单、函数签名、关键逻辑行（凭据/收件箱/同步缓冲/令牌）。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
D = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame/bot/ilink")
if not os.path.isdir(D):
    print("✗ 目录不存在：%s" % D)
    sys.exit(0)
for f in sorted(os.listdir(D)):
    p = os.path.join(D, f)
    if not f.endswith(".kt"):
        continue
    lines = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    print("=== %s（%d 行）===" % (f, len(lines)))
    for i, l in enumerate(lines, 1):
        if re.match(r"\s*(fun|object|class|data class|private fun|internal fun|suspend fun)", l):
            print("   %4d| %s" % (i, l.rstrip()[:130]))
    print("   --- 关键行 ---")
    for i, l in enumerate(lines, 1):
        if re.search(r"token|expire|过期|cred|凭据|pending|inbox|收件箱|sync|缓冲|"
                     r"messageId|去重|seen|Files\.move|writeText|readText", l):
            print("   %4d| %s" % (i, l.strip()[:125]))
    print()
