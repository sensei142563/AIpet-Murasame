# -*- coding: utf-8 -*-
"""① 撤掉我刚装进 venv 的 3 个包（f5-tts / pypinyin / cached_path）—— 它们会误导"选谁跑"的探测
   ② 读 run.py 里 F5-TTS 的"候选解释器"逻辑，看它为什么没选上全局那个能用的
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
PY = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

print("=== ① 卸载刚才那 3 个（venv 恢复原状）===")
r = subprocess.run([PY, "-m", "pip", "uninstall", "-y", "f5-tts", "pypinyin", "cached_path"],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=ENV, timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n")[-8:]:
    if l.strip():
        print("   " + l.strip()[:120])
print("   退出码 =", r.returncode)

print()
print("=== ② 复查：venv 里应该又没有了 ===")
code = ("import importlib.util as u\n"
        "for m in ('f5_tts','pypinyin','cached_path'):\n"
        "    print('   %-12s %s' % (m, '有' if u.find_spec(m) else '缺'))\n")
r2 = subprocess.run([PY, "-c", code], cwd=ROOT, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", env=ENV, timeout=300)
print((r2.stdout or "").rstrip())

print()
print("=== ③ run.py 里的 F5-TTS 候选逻辑（原样打印）===")
p = os.path.join(ROOT, "run.py")
ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
for i in range(555, 675):
    if i < len(ls):
        print("   %5d| %s" % (i + 1, ls[i].rstrip()[:116]))
