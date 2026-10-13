# -*- coding: utf-8 -*-
"""修掉刚才的缩进翻倍：把 /agent 分发块重新按 8 空格缩进，并验证。"""
import io
import os
import py_compile
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
M = os.path.join(ROOT, "classes", "murasame_class.py")

lines = io.open(M, encoding="utf-8", errors="replace").read().replace("\r\n", "\n").split("\n")
# 找到那段被插坏的行（首行以 16 空格开头的注释 "# /agent"）
bad_start = next((i for i, l in enumerate(lines)
                  if l.startswith("                # /agent <任务>")), None)
if bad_start is None:
    print("· 没找到坏块（可能已修）")
else:
    bad_end = bad_start
    while bad_end < len(lines) and (lines[bad_end].strip() == "" or
                                    lines[bad_end].startswith("                ")):
        # 遇到空行就停止（块与后续代码之间有空行）
        if lines[bad_end].strip() == "":
            break
        bad_end += 1
    fixed = []
    for l in lines[bad_start:bad_end]:
        fixed.append(("        " + l.strip()) if l.strip() else "")
    print("   被替换的行数：%d（第 %d~%d 行）" % (bad_end - bad_start, bad_start + 1, bad_end))
    lines = lines[:bad_start] + fixed + lines[bad_end:]
    io.open(M, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print("✓ 已重排为 8 空格缩进")

print()
print("=== 验证 ===")
try:
    py_compile.compile(M, doraise=True)
    print("   ✓ py_compile murasame_class.py")
except py_compile.PyCompileError as e:
    print("   ✗", str(e)[:400])
    sys.exit(1)

r = subprocess.run([VENV, os.path.join("tests", "test_qt_lifecycle.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
out = ((r.stdout or "") + (r.stderr or "")).split("\n")
for l in out[-26:]:
    print("   " + l.rstrip()[:150])
print("   退出码 =", r.returncode)
