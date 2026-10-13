# -*- coding: utf-8 -*-
"""用备份里的 /agent 分发原块（相对缩进正确）替换我插坏的那几行，然后验证。"""
import io
import os
import py_compile
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF = "remotes/origin/backup/main-before-overwrite-20261001"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
M = os.path.join(ROOT, "classes", "murasame_class.py")

r = subprocess.run(["git", "-C", ROOT, "show", "%s:classes/murasame_class.py" % REF],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
bak = (r.stdout or "").split("\n")
s = next(k for k, l in enumerate(bak) if l.strip().startswith("# /agent <任务>"))
e = next(k for k in range(s + 1, len(bak)) if bak[k].strip().startswith("# 长文本模式下"))
good = [l for l in bak[s:e] if l.strip()]
print("=== 备份原块（相对缩进正确，%d 行）===" % len(good))
for l in good:
    print("   %r" % l[:100])

lines = io.open(M, encoding="utf-8", errors="replace").read().replace("\r\n", "\n").split("\n")
# 找当前那 8 行坏块：以 "# /agent <任务>" 开头的行起，到连续非空行为止
bad_start = next((i for i, l in enumerate(lines) if l.strip().startswith("# /agent <任务>")), None)
if bad_start is None:
    print("· 没找到该块")
    sys.exit(1)
bad_end = bad_start
while bad_end < len(lines) and lines[bad_end].strip():
    bad_end += 1
print()
print("   替换第 %d~%d 行" % (bad_start + 1, bad_end))
lines = lines[:bad_start] + good + lines[bad_end:]
io.open(M, "w", encoding="utf-8", newline="\n").write("\n".join(lines))

print()
print("=== 验证 ===")
try:
    py_compile.compile(M, doraise=True)
    print("   ✓ py_compile 通过")
except py_compile.PyCompileError as ex:
    print("   ✗", str(ex)[:400])
    sys.exit(1)

r2 = subprocess.run([VENV, os.path.join("tests", "test_qt_lifecycle.py")], cwd=ROOT,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
out = ((r2.stdout or "") + (r2.stderr or "")).split("\n")
for l in out[-26:]:
    print("   " + l.rstrip()[:150])
print("   退出码 =", r2.returncode)
