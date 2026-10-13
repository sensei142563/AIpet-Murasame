# -*- coding: utf-8 -*-
"""修正我上一轮把 _run_agent_task / _on_agent_done 插成 8 空格（嵌套函数）的错误 —— 退回类方法（4 空格）。
并顺手给 available() 包上 try（探测失败不该带走整只桌宠）。
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
M = os.path.join(ROOT, "classes", "murasame_class.py")

lines = io.open(M, encoding="utf-8", errors="replace").read().replace("\r\n", "\n").split("\n")

# 找两个方法块（当前 8 空格缩进），整体退回 4 空格
s = next((i for i, l in enumerate(lines) if l.startswith("        def _run_agent_task")), None)
if s is None:
    print("· 没找到 8 空格版的 _run_agent_task（可能已修）")
else:
    # 块结束：下一个"缩进 <= 4 且非空"的行
    e = s + 1
    while e < len(lines):
        l = lines[e]
        if l.strip() and not l.startswith("        "):
            break
        e += 1
    print("   待退回的块：第 %d~%d 行（%d 行）" % (s + 1, e, e - s))
    print("   首行: %r" % lines[s][:80])
    fixed = []
    for l in lines[s:e]:
        fixed.append(l[4:] if l.startswith("    ") else l)
    lines = lines[:s] + fixed + lines[e:]
    print("   ✓ 已退回 4 空格")
    io.open(M, "w", encoding="utf-8", newline="\n").write("\n".join(lines))

# available() 包 try
t = io.open(M, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "av = available()" in t and "except Exception as _e_av" not in t:
    t = t.replace("""            av = available()
            if not av.get("chosen"):""",
                  """            try:
                av = available()
            except Exception as _e_av:
                # ⚠ 探测后端（找 node / DSH 的 bin.js / Codex 的 bin/codex.js）**可能抛**。
                #   以前这里没包 try：一次"探测失败"就把整只桌宠带走（异常直接冒到调用方）。
                #   探测失败按"没有可用的 agent"处理即可 —— 如实说一句，绝不上抛。
                self.show_text(f"（探测本机 agent 时出错：{_e_av}）", typing=True)
                return True
            if not av.get("chosen"):""", 1)
    io.open(M, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已给 available() 包上 try/except")

print()
print("=== 验证 ===")
try:
    py_compile.compile(M, doraise=True)
    print("   ✓ py_compile")
except py_compile.PyCompileError as e:
    print("   ✗", str(e)[:300])
    sys.exit(1)

# 真正验证"是类方法"（不是只靠编译）
code = ("import sys;sys.path.insert(0,r'%s');"
        "from classes.murasame_class import Murasame as M;"
        "print('IS_METHOD', hasattr(M, '_run_agent_task') and hasattr(M, '_on_agent_done'))" % ROOT)
r = subprocess.run([VENV, "-c", code], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "IS_METHOD" in l or "Error" in l or "error" in l:
        print("   " + l.strip()[:140])

r2 = subprocess.run([VENV, os.path.join("tests", "test_qt_lifecycle.py")], cwd=ROOT,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r2.stdout or "") + (r2.stderr or "")).split("\n"):
    if "[OK]" in l or "[FAIL]" in l or "FAILED" in l or "SECOND_RETURNED" in l or "STOPPED_IN" in l:
        print("   " + l.strip()[:150])
print("   退出码 =", r2.returncode)
