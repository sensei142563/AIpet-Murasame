# -*- coding: utf-8 -*-
"""恢复「agent 任务」这一整条链（三块，全部自包含）：
  ① classes/Worker_class.py  ← 补 AgentWorker 类
  ② classes/murasame_class.py ← 补 _run_agent_task / _on_agent_done
  ③ classes/murasame_class.py ← 在 start_thread 开头补 /agent 分发
然后 py_compile + 跑 tests/test_qt_lifecycle.py 验证。
"""
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
    return "\n".join(lines[s:e]).rstrip("\n") + "\n"


# ---------- ① AgentWorker ----------
bak_wk = show("classes/Worker_class.py").split("\n")
agent_cls = block(bak_wk, lambda l: l.startswith("class AgentWorker"),
                  lambda l: l.startswith("class ") and "AgentWorker" not in l)
W = os.path.join(ROOT, "classes", "Worker_class.py")
w = io.open(W, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "class AgentWorker" in w:
    print("· ① AgentWorker 已存在")
else:
    if not w.endswith("\n"):
        w += "\n"
    w += "\n\n" + agent_cls
    io.open(W, "w", encoding="utf-8", newline="\n").write(w)
    print("✓ ① 已补 AgentWorker（%d 行）" % len(agent_cls.split("\n")))

# ---------- ② 两个方法 ----------
bak_mc = show("classes/murasame_class.py").split("\n")
methods = block(bak_mc, lambda l: l.strip().startswith("def _run_agent_task"),
                lambda l: l.strip().startswith("def ") and "_on_agent_done" not in l and
                "_run_agent_task" not in l)
M = os.path.join(ROOT, "classes", "murasame_class.py")
m = io.open(M, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "_run_agent_task" in m:
    print("· ② 两个方法已存在")
else:
    anchor = "    # 启动一个新线程（安全版，打断旧线程）\n    def start_thread(self, text, role, t=False):"
    if anchor in m:
        m = m.replace(anchor, "    " + methods.replace("\n", "\n    ").rstrip() + "\n\n" + anchor, 1)
        print("✓ ② 已插入 _run_agent_task / _on_agent_done（%d 行）" % len(methods.split("\n")))
    else:
        # 退一步：插到 start_thread 定义之前
        m2 = re.search(r"(?m)^(\s*)def start_thread\(self, text, role, t=False\):", m)
        if m2:
            ind = m2.group(1)
            ins = "".join(ind + l + "\n" for l in methods.split("\n")).rstrip() + "\n\n"
            m = m[:m2.start()] + ins + m[m2.start():]
            print("✓ ② 已插入（备用锚点，缩进保持 %r）" % ind)
        else:
            print("✗ ② 找不到 start_thread 锚点，未插入")
            sys.exit(1)

# ---------- ③ /agent 分发 ----------
if "_t.lower().startswith(\"/agent \")" in m:
    print("· ③ /agent 分发已存在")
else:
    disp = block(bak_mc, lambda l: l.strip().startswith("# /agent <任务>：交给本机 agent"),
                 lambda l: l.strip().startswith("# 长文本模式下"))
    m2 = re.search(r"(?m)^(\s*)def start_thread\(self, text, role, t=False\):\s*\n", m)
    if m2:
        ind = re.match(r"(\s*)", m[m2.end():]).group(1) if m[m2.end():].strip() else "        "
        # 取函数体第一行的缩进
        body = m[m2.end():].split("\n")
        ind = re.match(r"(\s*)", body[0]).group(1) or "        "
        ins = "".join(ind + l + "\n" for l in disp.rstrip("\n").split("\n"))
        m = m[:m2.end()] + ins + "\n" + m[m2.end():]
        print("✓ ③ 已插入 /agent 分发（%d 行，缩进 %r）" % (len(disp.split("\n")), ind))
    else:
        print("⚠ ③ 找不到 start_thread 锚点")

io.open(M, "w", encoding="utf-8", newline="\n").write(m)

# ---------- 验证 ----------
print()
print("=== 验证 ===")
for f in ("classes/Worker_class.py", "classes/murasame_class.py"):
    try:
        py_compile.compile(os.path.join(ROOT, f), doraise=True)
        print("   ✓ py_compile %s" % f)
    except py_compile.PyCompileError as e:
        print("   ✗ %s: %s" % (f, str(e)[:400]))
        sys.exit(1)

r = subprocess.run([VENV, os.path.join("tests", "test_qt_lifecycle.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
out = ((r.stdout or "") + (r.stderr or "")).split("\n")
for l in out[-25:]:
    print("   " + l.rstrip()[:150])
print("   退出码 =", r.returncode)
