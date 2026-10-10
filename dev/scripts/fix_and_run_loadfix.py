# -*- coding: utf-8 -*-
"""修 fix_load_baseurl.py 里的引号病，然后执行它。"""
import io
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts\fix_load_baseurl.py"
s = io.open(P, encoding="utf-8", newline="").read()
s2 = s.replace('"读出来看看"', "「读出来看看」")
io.open(P, "w", encoding="utf-8", newline="").write(s2)
print("修复处数:", 1 if s2 != s else 0)
r = subprocess.run([sys.executable, "-c",
                    "import ast;ast.parse(open(r'%s',encoding='utf-8').read());print('语法 ✓')" % P],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print((r.stdout or r.stderr).strip()[:80])
if r.returncode == 0:
    r2 = subprocess.run([sys.executable, "-u", P], capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=7200)
    out = (r2.stdout or "") + (r2.stderr or "")
    print(out[-3000:])
    print("rc =", r2.returncode)
