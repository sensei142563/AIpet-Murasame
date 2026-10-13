# -*- coding: utf-8 -*-
"""找出所有写死的旧数字（381 / test_vision_interface 的 24）并列出，供统一修正。"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SKIP = re.compile(r"\\(runtime|\.venv|site-packages|GPT-SoVITS|_import_tmp|\.git|dev\\scripts|dev\\ppt\\out)\\", re.I)

pats = [r"\b381\b", r"\b382\b", r"\b383\b", r"\b384\b", r"\b385\b"]
print("=== 写死旧总数的地方 ===")
for dp, dn, fn in os.walk(ROOT):
    if SKIP.search(dp + "\\"):
        continue
    for f in fn:
        if not f.endswith((".md", ".json", ".py", ".txt")):
            continue
        p = os.path.join(dp, f)
        try:
            lines = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        for i, l in enumerate(lines, 1):
            if any(re.search(x, l) for x in pats) and ("项" in l or "自检" in l or "测试" in l
                                                       or "通过" in l or "总计" in l):
                print("   %-46s %5d| %s" % (p.replace(ROOT + "\\", "")[:46], i, l.strip()[:96]))

print()
print("=== test_vision_interface 的旧项数 24 ===")
for dp, dn, fn in os.walk(ROOT):
    if SKIP.search(dp + "\\"):
        continue
    for f in fn:
        if not f.endswith((".md", ".json")):
            continue
        p = os.path.join(dp, f)
        try:
            lines = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        for i, l in enumerate(lines, 1):
            if "test_vision_interface" in l:
                print("   %-46s %5d| %s" % (p.replace(ROOT + "\\", "")[:46], i, l.strip()[:96]))

print()
print("=== 当前真实数字（跑一次数出来）===")
import subprocess  # noqa: E402
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    s = l.strip()
    if "test_vision_interface" in s or "总计" in s:
        print("   " + s[:110])
o = json.loads(io.open(os.path.join(ROOT, "dev", "ppt", "outline.json"),
                       encoding="utf-8", errors="replace").read())
for i, s in enumerate(o["slides"], 1):
    blob = json.dumps(s, ensure_ascii=False)
    if "381" in blob or "自检" in blob:
        print("   PPT 第 %d 页含旧数字: %s" % (i, (s.get("title") or "")[:40]))
