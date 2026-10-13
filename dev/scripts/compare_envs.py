# -*- coding: utf-8 -*-
"""对比全局 Python 与 runtime\venv 的包：列出「全局有、venv 没有」= 潜在炸弹。"""
import json
import os
import subprocess
import sys

ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
GLOBAL = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
CODE = ("import json, importlib.metadata as m\n"
        "d = {}\n"
        "for dist in m.distributions():\n"
        "    n = (dist.metadata['Name'] or '').strip()\n"
        "    if n:\n"
        "        d[n.lower()] = dist.version\n"
        "print(json.dumps(d))\n")


def pkgs(py):
    r = subprocess.run([py, "-c", CODE], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    try:
        return json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception:
        return {}


g = pkgs(GLOBAL)
v = pkgs(VENV)
print("   全局包数 = %d    venv 包数 = %d" % (len(g), len(v)))
only_g = sorted(set(g) - set(v))
only_v = sorted(set(v) - set(g))
print()
print("=== 全局有、venv 没有（%d 个）—— 项目跑在 venv 上时随时会炸 ===" % len(only_g))
for n in only_g:
    print("   %-34s %s" % (n, g[n]))
print()
print("=== venv 有、全局没有（%d 个）===" % len(only_v))
for n in only_v:
    print("   %-34s %s" % (n, v[n]))
