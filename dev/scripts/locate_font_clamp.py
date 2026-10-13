# -*- coding: utf-8 -*-
"""定位 font_scale 的夹取逻辑与未被 num() 包住的读取点。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SKIP = ("\\.venv\\", "\\.git\\", "site-packages", "__pycache__", "\\runtime\\", "\\dev\\scripts\\")

print("=== 含 font_scale 夹取/边界的地方 ===")
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp + "\\" for s in SKIP):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        t = io.open(p, encoding="utf-8", errors="replace").read()
        for i, l in enumerate(t.split("\n"), 1):
            if "font_scale" in l and re.search(r"num\(|clamp|max\(|min\(|[0-9]\.[0-9]", l):
                print("   %-34s %5d| %s" % (f, i, l.strip()[:125]))

print()
print("=== 测试里对 font_scale 的期望（test_bounds.py）===")
tb = io.open(os.path.join(ROOT, "tests", "test_bounds.py"), encoding="utf-8",
             errors="replace").read().split("\n")
for i, l in enumerate(tb, 1):
    if "font_scale" in l or "portrait_height_ratio" in l:
        print("   %5d| %s" % (i, l.rstrip()[:130]))

print()
print("=== murasame_class.py 里 portrait_height_ratio 的读取点 ===")
mc = io.open(os.path.join(ROOT, "classes", "murasame_class.py"), encoding="utf-8",
             errors="replace").read().split("\n")
for i, l in enumerate(mc, 1):
    if "portrait_height_ratio" in l:
        for j in range(max(0, i - 4), min(len(mc), i + 4)):
            print("   %5d| %s" % (j + 1, mc[j].rstrip()[:130]))
        print("   " + "-" * 60)
