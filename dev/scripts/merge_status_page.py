# -*- coding: utf-8 -*-
"""状态页收尾：
  ① NAV 列表补 ("status", …, "状态", …)（现在根本没有这一项 ⇒ 侧栏永远不出「状态」）
  ② _status_page_enabled() 默认值确认为 True（缺键时不影响老用户）
  ③ config.example.json 补 status_page_enabled: true
  ④ 诊断 QSS 里 QDialog#statusWindow 为何没生效
"""
import io
import json
import os
import py_compile
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
SW = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")

t = io.open(SW, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
lines = t.split("\n")

print("=== ② _status_page_enabled 定义 ===")
k = next((i for i, l in enumerate(lines) if l.startswith("def _status_page_enabled")), None)
if k is not None:
    for j in range(k, min(len(lines), k + 12)):
        print("   %5d| %s" % (j + 1, lines[j].rstrip()[:130]))

# ① NAV 补 status 项
if re.search(r'\(\s*"status"', t) is None:
    old = '''    ("memory",  "", "记忆",  "对话与备份"),'''
    new = '''    ("status",  "", "状态",  "状态 · 习惯 · 记忆 · 提醒"),
    ("memory",  "", "记忆",  "对话与备份"),'''
    if old in t:
        t = t.replace(old, new, 1)
        io.open(SW, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ ① NAV 已补「状态」项")
    else:
        print("✗ ① NAV 锚点未命中")
else:
    print("· ① NAV 已有 status 项")

print()
print("=== ④ 诊断 QSS ===")
code = ("import sys;sys.path.insert(0,r'%s');"
        "import classes.status_window as S;"
        "q=S.QSS;"
        "print('IN_QSS', 'QDialog#statusWindow' in q);"
        "i=q.find('QDialog#statusWindow');"
        "print('AFTER80', repr(q[i+len('QDialog#statusWindow'):i+len('QDialog#statusWindow')+80]))"
        % ROOT)
r = subprocess.run([VENV, "-c", code], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "IN_QSS" in l or "AFTER80" in l or "Error" in l:
        print("   " + l.strip()[:140])

print()
print("=== ③ config.example.json 补键 ===")
P = os.path.join(ROOT, "config.example.json")
ex = json.loads(io.open(P, encoding="utf-8", errors="replace").read())
if "status_page_enabled" not in ex:
    ex["status_page_enabled"] = True
    io.open(P, "w", encoding="utf-8", newline="\n").write(
        json.dumps(ex, ensure_ascii=False, indent=2) + "\n")
    print("✓ 已加 status_page_enabled: true（顶层键 %d 个）" % len(ex))
else:
    print("· 已有")

print()
print("=== 验证：py_compile + 重跑 test_bugfix_0930 ===")
try:
    py_compile.compile(SW, doraise=True)
    print("   ✓ py_compile silicon_window.py")
except py_compile.PyCompileError as e:
    print("   ✗", str(e)[:250])
    sys.exit(1)
r2 = subprocess.run([VENV, os.path.join("tests", "test_bugfix_0930.py")], cwd=ROOT,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r2.stdout or "") + (r2.stderr or "")).split("\n"):
    if "[FAIL]" in l or "FAILED" in l:
        print("   " + l.strip()[:150])
