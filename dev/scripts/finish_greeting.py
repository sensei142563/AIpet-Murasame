# -*- coding: utf-8 -*-
"""收尾 test_bugfix_0930b：补 config.example.json 的两个开机问候键，然后验证。"""
import io
import json
import os
import py_compile
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
P = os.path.join(ROOT, "config.example.json")

ex = json.loads(io.open(P, encoding="utf-8", errors="replace").read())
print("=== 现有 care_startup / startup_greeting 相关键 ===")
for k in list(ex.keys()):
    if "startup" in k or "care_" in k:
        print("   %-30s = %r" % (k, ex[k]))

added = []
if ex.get("startup_greeting_mode") != "voice":
    ex["startup_greeting_mode"] = "voice"
    added.append(("startup_greeting_mode", "voice"))
if ex.get("startup_greeting_voice") != "":
    ex["startup_greeting_voice"] = ""
    added.append(("startup_greeting_voice", ""))
if added:
    io.open(P, "w", encoding="utf-8", newline="\n").write(
        json.dumps(ex, ensure_ascii=False, indent=2) + "\n")
    print()
    print("=== 已补/修正 ===")
    for k, v in added:
        print("   %-30s = %r" % (k, v))
else:
    print()
    print("· 两个键都已符合（voice / 空串）")

ex2 = json.loads(io.open(P, encoding="utf-8", errors="replace").read())
print("   复核: mode=%r voice=%r  顶层键 %d 个"
      % (ex2.get("startup_greeting_mode"), ex2.get("startup_greeting_voice"), len(ex2)))

print()
print("=== 验证 ===")
try:
    py_compile.compile(os.path.join(ROOT, "main.py"), doraise=True)
    print("   ✓ py_compile main.py")
except py_compile.PyCompileError as e:
    print("   ✗", str(e)[:250])
    sys.exit(1)

r = subprocess.run([VENV, os.path.join("tests", "test_bugfix_0930b.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "[FAIL]" in l or "FAILED" in l or "通过" in l:
        print("   " + l.strip()[:150])
print("   退出码 =", r.returncode)
