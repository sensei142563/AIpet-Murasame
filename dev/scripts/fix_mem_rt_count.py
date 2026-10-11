# -*- coding: utf-8 -*-
"""修脚本的计数：手机包 275 = 短 251 + 长 24，桌面侧也必须把两者相加再比。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
F = os.path.join(MAIN, "dev", "scripts", "mem_device_roundtrip.py")

t = io.open(F, encoding="utf-8").read().replace("\r\n", "\n")
old = '''hist = os.path.join(rt, "memory", "history.json")
n_desk = None
if os.path.isfile(hist):
    short, _ = counts(hist)
    n_desk = short
    row("手机 → 桌面 无损", (n_phone is None) or (n_desk == n_phone),
        "手机包 %s 条 → 桌面 %s 条" % (n_phone, n_desk))
else:
    row("手机 → 桌面 无损", False, "桌面没有生成 %s" % hist)'''
new = '''hist = os.path.join(rt, "memory", "history.json")
longf = os.path.join(rt, "memory", "long_history.json")
n_desk = None
n_short = n_long = 0
if os.path.isfile(hist):
    n_short = counts(hist)[0] or 0
    # 长记忆单独一个文件；互通的条数必须是**两者相加**
    # （第一版只数了 history.json，于是把"完全无损"误判成 FAIL —— 自己的数数错）
    for cand in (longf, os.path.join(rt, "memory", "long_term.json"),
                 os.path.join(rt, "memory", "long.json")):
        if os.path.isfile(cand):
            n_long = counts(cand)[0] or counts(cand)[1] or 0
            break
    n_desk = n_short + n_long
    row("手机 → 桌面 无损", (n_phone is None) or (n_desk == n_phone),
        "手机包 %s 条 → 桌面 %s 条（短 %d + 长 %d）" % (n_phone, n_desk, n_short, n_long))
else:
    row("手机 → 桌面 无损", False, "桌面没有生成 %s" % hist)'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(F, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已修：桌面侧条数 = 短 + 长")
else:
    print("✗ 锚点未命中")

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % F],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:300])
print()
print("=== 重跑真机往返 ===")
r2 = subprocess.run([sys.executable, "-u", F], capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=1800, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
print((r2.stdout or "") + (r2.stderr or ""))
print("退出码:", r2.returncode)
