# -*- coding: utf-8 -*-
"""开机问候三档：查 main.py 现状、care.py 的接口、play_voice_wav 的定义与备份里的做法。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF_BAK = "remotes/origin/backup/main-before-overwrite-20261001"


def show(ref, path):
    if ref is None:
        p = os.path.join(ROOT, path)
        return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


print("=== ① 全仓 play_voice_wav 的定义与调用 ===")
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp + "\\" for s in (".venv", ".git", "site-packages", "__pycache__", "runtime")):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        t = io.open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
        for i, l in enumerate(t.split("\n"), 1):
            if "play_voice_wav" in l:
                print("   %-30s %5d| %s" % (f, i, l.strip()[:110]))

print()
print("=== ② main.py 里问候相关代码 ===")
mj = show(None, "main.py").split("\n")
for i, l in enumerate(mj, 1):
    if re.search(r"问候|greeting|startup_greeting|开机", l):
        print("   %5d| %s" % (i, l.rstrip()[:125]))

print()
print("=== ③ tool/care.py 的 startup_greeting 接口 ===")
c = show(None, "tool/care.py").split("\n")
for i, l in enumerate(c, 1):
    if "startup_greeting" in l:
        print("   %5d| %s" % (i, l.rstrip()[:125]))

print()
print("=== ④ 备份里 main.py 是怎么处理三档的（有无 == \"off\" / == \"voice\" / 老行为）===")
bak = show(REF_BAK, "main.py").split("\n")
for i, l in enumerate(bak, 1):
    if re.search(r'== "off"|== "voice"|老行为|play_voice_wav|startup_greeting', l):
        lo = max(0, i - 6)
        print("   --- 行 %d ---" % i)
        for j in range(lo, min(len(bak), i + 8)):
            print("   %5d| %s" % (j + 1, bak[j].rstrip()[:125]))
        print("   " + "-" * 56)
