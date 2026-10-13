# -*- coding: utf-8 -*-
"""按真实锚点补完 agent 链：① 两个方法插到 start_thread 之前 ② /agent 分发插到 start_thread 的 docstring 之后。"""
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


def show(path):
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (REF, path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


def block(lines, start_pred, end_pred):
    s = next(k for k, l in enumerate(lines) if start_pred(l))
    e = len(lines)
    for j in range(s + 1, len(lines)):
        if end_pred(lines[j]):
            e = j
            break
    return "\n".join(lines[s:e]).rstrip("\n")


bak = show("classes/murasame_class.py").split("\n")
methods = block(bak, lambda l: l.strip().startswith("def _run_agent_task"),
                lambda l: l.strip().startswith("def ") and "agent" not in l)
dispatch = block(bak, lambda l: l.strip().startswith("# /agent <任务>"),
                 lambda l: l.strip().startswith("# 长文本模式下"))

m = io.open(M, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
lines = m.split("\n")

# --- ② 两个方法：插到 start_thread 定义之前（保持 4 空格方法缩进）---
if "_run_agent_task" in m:
    print("· 两个方法已存在")
else:
    k = next(i for i, l in enumerate(lines) if l.startswith("    def start_thread(self, text, role"))
    ins = ["    " + x if x.strip() else "" for x in methods.split("\n")]
    lines = lines[:k] + ins + ["", ""] + lines[k:]
    print("✓ 已在第 %d 行前插入 _run_agent_task / _on_agent_done（%d 行）" % (k + 1, len(ins)))

# --- ③ /agent 分发：插到 start_thread 的 docstring 之后 ---
m2 = "\n".join(lines)
if "_t.lower().startswith(\"/agent \")" in m2:
    print("· /agent 分发已存在")
else:
    lines = m2.split("\n")
    k = next(i for i, l in enumerate(lines) if l.startswith("    def start_thread(self, text, role"))
    # 找 docstring 结束行（从 k+1 起第一个含三引号且成对的行）
    j = k + 1
    endq = None
    if '"""' in lines[j]:
        if lines[j].count('"""') >= 2:
            endq = j
        else:
            for t in range(j + 1, min(len(lines), j + 60)):
                if '"""' in lines[t]:
                    endq = t
                    break
    if endq is None:
        endq = k                      # 没有 docstring：直接插在函数体第一行
    ind = "        "
    ins = [ind + x if x.strip() else "" for x in dispatch.split("\n")]
    lines = lines[:endq + 1] + ins + [""] + lines[endq + 1:]
    print("✓ 已在 start_thread 的 docstring 之后（第 %d 行后）插入 /agent 分发（%d 行）"
          % (endq + 1, len(ins)))

io.open(M, "w", encoding="utf-8", newline="\n").write("\n".join(lines))

print()
print("=== 验证 ===")
ok = True
for f in ("classes/Worker_class.py", "classes/murasame_class.py"):
    try:
        py_compile.compile(os.path.join(ROOT, f), doraise=True)
        print("   ✓ py_compile %s" % f)
    except py_compile.PyCompileError as e:
        ok = False
        print("   ✗ %s: %s" % (f, str(e)[:400]))
if not ok:
    sys.exit(1)

r = subprocess.run([VENV, os.path.join("tests", "test_qt_lifecycle.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
out = ((r.stdout or "") + (r.stderr or "")).split("\n")
for l in out[-24:]:
    print("   " + l.rstrip()[:150])
print("   退出码 =", r.returncode)
