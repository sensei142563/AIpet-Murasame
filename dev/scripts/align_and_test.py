# -*- coding: utf-8 -*-
"""① 把 pet.json 的 decor_rules 与 origin/main 完全对齐（a=[]、b=[{...}]）
   ② 用能跑 pytest 的解释器跑 tests/test_plugin_markup.py，验证 handle_reply 恢复后测试转绿"""
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")

print("=== ① 对齐 decor_rules ===")
p = os.path.join(ROOT, "pets", "natsume", "pet.json")
cur = json.loads(io.open(p, encoding="utf-8", errors="replace").read())
sets = ((cur.get("portrait") or {}).get("sets") or {})
sets.setdefault("a", {})["decor_rules"] = []
sets.setdefault("b", {})["decor_rules"] = [{"decor": "嫌弃阴影", "emotion": "嫌弃"}]
io.open(p, "w", encoding="utf-8", newline="\n").write(
    json.dumps(cur, ensure_ascii=False, indent=4) + "\n")
print("   a =", json.dumps(sets["a"]["decor_rules"], ensure_ascii=False))
print("   b =", json.dumps(sets["b"]["decor_rules"], ensure_ascii=False))
json.loads(io.open(p, encoding="utf-8").read())
print("   ✓ JSON 合法")

print()
print("=== ② 找能跑 pytest 的解释器 ===")
cands = [VENV, sys.executable,
         r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe",
         r"E:\university\order\Anaconda\python.exe"]
runner = None
for exe in cands:
    if not os.path.isfile(exe):
        continue
    r = subprocess.run([exe, "-c", "import pytest,sys;print(pytest.__version__)"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    v = ((r.stdout or "") + (r.stderr or "")).strip().split("\n")[-1]
    print("   %-70s %s" % (exe, v[:60]))
    if r.returncode == 0 and runner is None:
        runner = exe

if runner is None:
    print("   ⇒ 到处都没有 pytest，给项目 venv 装一个（清华镜像）")
    r = subprocess.run([VENV, "-m", "pip", "install", "-q", "-i",
                        "https://pypi.tuna.tsinghua.edu.cn/simple", "pytest"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=1800)
    print("   pip 退出码 =", r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()[-120:])
    runner = VENV

print()
print("=== ③ 跑那条红测试（tests/test_plugin_markup.py）===")
r = subprocess.run([runner, "-m", "pytest", "tests/test_plugin_markup.py", "-q", "--no-header",
                    "-p", "no:cacheprovider"],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   timeout=900)
out = ((r.stdout or "") + (r.stderr or "")).strip().split("\n")
for l in out[-15:]:
    print("   " + l.strip()[:155])
print("   退出码 =", r.returncode)
