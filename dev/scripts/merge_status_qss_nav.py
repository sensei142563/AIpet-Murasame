# -*- coding: utf-8 -*-
"""行级精确插入两处：
  ① classes/status_window.py 第 112 行 `QSS = \"\"\"` 之后插入 QDialog#statusWindow 的不透明纸色底
  ② pcl_launcher/silicon_window.py 的 NAV 列表里补 ("status", "", "状态", …)
然后验证（含"真的在 S.QSS 里"这一条）。
"""
import io
import os
import py_compile
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")

# ---------- ① QSS ----------
P = os.path.join(ROOT, "classes", "status_window.py")
lines = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n").split("\n")
k = next(i for i, l in enumerate(lines) if l.startswith("QSS = "))
print("① QSS 起始行 %d: %r" % (k + 1, lines[k][:40]))
if "QDialog#statusWindow {" not in "\n".join(lines[k:k + 12]):
    rule = [
        "/* 窗自身的**不透明纸色底**：首次显示就要有底（不能等样式 polish）——",
        "   否则用户看到的是「字压在壁纸上看不清，点刷新后那块底色才出现」。 */",
        "QDialog#statusWindow {",
        "    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,",
        "                                stop:0 #f4ece5, stop:1 #e7dbd0);",
        "}",
    ]
    lines = lines[:k + 1] + rule + lines[k + 1:]
    io.open(P, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print("   ✓ 已在 QSS 里插入 %d 行" % len(rule))
else:
    print("   · 已在")

# ---------- ② NAV ----------
SW = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")
t = io.open(SW, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
m = re.search(r"(?ms)^NAV = \[(.*?)^\]", t)
if m and '"status"' not in m.group(1):
    blk = m.group(1)
    anchor = '    ("memory",  "", "记忆",  "对话与备份"),'
    if anchor in blk:
        nb = blk.replace(anchor,
                         '    ("status",  "", "状态",  "状态 · 习惯 · 记忆 · 提醒"),\n' + anchor, 1)
        t = t[:m.start(1)] + nb + t[m.end(1):]
        io.open(SW, "w", encoding="utf-8", newline="\n").write(t)
        print("② ✓ NAV 已补「状态」项")
    else:
        print("② ✗ NAV 锚点未命中")
else:
    print("② · NAV 已有 status 或没找到 NAV")

print()
print("=== 验证 ===")
for f in ("classes/status_window.py", "pcl_launcher/silicon_window.py"):
    try:
        py_compile.compile(os.path.join(ROOT, f), doraise=True)
        print("   ✓ py_compile %s" % f)
    except py_compile.PyCompileError as e:
        print("   ✗ %s: %s" % (f, str(e)[:250]))
        sys.exit(1)

code = ("import sys;sys.path.insert(0,r'%s');"
        "import classes.status_window as S;"
        "print('IN_QSS', 'QDialog#statusWindow' in S.QSS and 'background' in "
        "S.QSS.split('QDialog#statusWindow')[1][:80])" % ROOT)
r = subprocess.run([VENV, "-c", code], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "IN_QSS" in l or "Error" in l:
        print("   " + l.strip()[:140])

r2 = subprocess.run([VENV, os.path.join("tests", "test_bugfix_0930.py")], cwd=ROOT,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r2.stdout or "") + (r2.stderr or "")).split("\n"):
    if "[FAIL]" in l or "FAILED" in l:
        print("   " + l.strip()[:150])
