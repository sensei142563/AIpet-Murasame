# -*- coding: utf-8 -*-
"""看 ②c / ④ / ⑤b / ⑥ 四段检查项的真实代码 + 看诊断包里 ⑤b 的日志，判断 ⑤b 是不是真问题。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")
DIAG = os.path.join(MAIN, "dev", "shots", "diag-1011-211904-fail")

t = io.open(A, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
for key in ("②c 手部试手", "④ 返回键两次退出", "⑤b 离线 TTS 合成", "⑥ Silero VAD", "识别自检"):
    i = t.find(key)
    if i < 0:
        print("=== %s：未找到 ===" % key)
        continue
    print("=== %s 附近的检查代码 ===" % key)
    lo = t.rfind("\n    #", 0, i)
    print(t[max(0, lo - 200):i + 700])
    print()

print("=== 诊断包里与 TTS 有关的日志 ===")
if os.path.isdir(DIAG):
    for f in sorted(os.listdir(os.path.join(DIAG, "logs"))) if os.path.isdir(os.path.join(DIAG, "logs")) else []:
        p = os.path.join(DIAG, "logs", f)
        body = io.open(p, encoding="utf-8", errors="replace").read()
        if "tts" in body.lower() or "tts" in f.lower():
            print("   --- %s（最后 12 行）---" % f)
            for l in body.splitlines()[-12:]:
                print("      " + l.strip()[:160])
