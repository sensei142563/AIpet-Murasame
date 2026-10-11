# -*- coding: utf-8 -*-
"""修 normalize_crlf.py 的缩进错误（我插 else: 时没重排文件列表），并复核 SAFETY_GUARD。
   注意：本次**不过滤输出**，把子进程的 stdout/stderr 原样打印。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(MAIN, "dev", "scripts", "normalize_crlf.py")

print("=== 1) 先看坏在哪（原样打印，不过滤）===")
r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % P],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("STDOUT:", (r.stdout or "").strip()[:400])
print("STDERR:", (r.stderr or "").strip()[:600])
print("EXIT:", r.returncode)

# 修法：删掉 else:，改成早退（sys.exit(0)）之后正常继续
t = io.open(P, encoding="utf-8").read().replace("\r\n", "\n")
t = t.replace('''if not safety_ok(MAIN, "桌面仓"):
    main_files = []
else:''', '''if not safety_ok(MAIN, "桌面仓"):
    print("RESULT_CONVERTED: 0（桌面仓按策略跳过）")
    sys.exit(0)''')
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print()
print("=== 2) 修后语法检查（原样打印）===")
r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % P],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("STDERR:", (r.stderr or "").strip()[:500] or "(空)")
print("EXIT:", r.returncode)
if r.returncode != 0:
    sys.exit(1)

print()
print("=== 3) 跑一遍，验证 SAFETY_GUARD 真的拒绝桌面仓（原样打印全部输出）===")
r = subprocess.run([sys.executable, "-u", P], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600,
                   env=dict(os.environ, PYTHONIOENCODING="utf-8"))
print("--- STDOUT ---")
print((r.stdout or "").strip()[:1200])
print("--- STDERR ---")
print((r.stderr or "").strip()[:600] or "(空)")
print("EXIT:", r.returncode)

print()
print("=== 4) 确认工作区没被这次运行改动 ===")
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8", errors="replace").stdout.strip()
print("git status:", "干净 ✓" if not st else "\n".join(st.splitlines()[:5]))
print()
print("RESULT_GUARD:", "OK（桌面仓被拒绝、无文件被改）" if r.returncode == 0 and "SKIP" in (r.stdout or "")
      else "需要人工确认")
