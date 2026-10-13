# -*- coding: utf-8 -*-
"""修 tool/stt.py:128 的顶层配置读取式下标，然后复跑 test_config_contracts。"""
import io
import os
import py_compile
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
P = os.path.join(ROOT, "tool", "stt.py")

t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
lines = t.split("\n")
print("=== 附近代码 ===")
for j in range(max(0, 124), min(len(lines), 134)):
    print("   %4d| %s" % (j + 1, lines[j].rstrip()[:130]))

# 把所有 get_config(...)[ "顶层键" ] 改成 .get("顶层键", 默认)
pat = re.compile(r'(get_config\(([^)]*)\))\[\s*"([a-zA-Z_][a-zA-Z0-9_]*)"\s*\]')
n = 0
for m in list(pat.finditer(t)):
    key = m.group(3)
    # 只替换"顶层键"的读取式下标；若后面紧跟 ["子键"] 也一起安全化
    repl = '%s.get("%s", ""))' % (m.group(1), key)
    # 生成时注意括号：原形式 get_config(x)["k"] → (get_config(x).get("k", ""))
    repl = '(get_config(%s).get("%s", ""))' % (m.group(2), key)
    t = t[:m.start()] + repl + t[m.end():]
    n += 1
    print("   替换: %s → %s" % (m.group(0)[:60], repl[:60]))

if n:
    io.open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 共替换 %d 处" % n)
else:
    print("· 没有需要替换的（可能写法不同）")

print()
print("=== 验证 ===")
try:
    py_compile.compile(P, doraise=True)
    print("   ✓ py_compile tool/stt.py")
except py_compile.PyCompileError as e:
    print("   ✗", str(e)[:300])
    sys.exit(1)

r = subprocess.run([VENV, os.path.join("tests", "test_config_contracts.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
out = ((r.stdout or "") + (r.stderr or "")).split("\n")
for l in out:
    if "[FAIL]" in l or "FAILED" in l or "通过" in l or "项" in l and "FAILED" not in l and "项通过" in l:
        print("   " + l.strip()[:150])
tail = [l for l in out if l.strip()][-3:]
for l in tail:
    print("   " + l.strip()[:150])
print("   退出码 =", r.returncode)
