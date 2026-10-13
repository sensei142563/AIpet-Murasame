# -*- coding: utf-8 -*-
"""确认三处丢失里哪些是"真的会坏"：查 handle_reply / secondary_text / decor_rules 的调用点。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SKIP = ("\\.venv\\", "\\.git\\", "site-packages", "__pycache__", "\\runtime\\", "\\dist\\",
        "\\build\\", "\\_internal\\", "\\GPT-SoVITS\\", "\\dev\\scripts\\")

TARGETS = ("handle_reply", "secondary_text", "decor_rules", "pending_results",
           "due_schedules", "results_note", "summary_text", "load_plugin", "manifest_dirs")

found = {k: [] for k in TARGETS}
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp + "\\" for s in SKIP):
        continue
    for f in fn:
        if not f.endswith((".py", ".json")):
            continue
        p = os.path.join(dp, f)
        try:
            t = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for k in TARGETS:
            for i, l in enumerate(t.split("\n"), 1):
                if k in l:
                    found[k].append("%s:%d  %s" % (p.replace(ROOT + "\\", ""), i, l.strip()[:90]))

for k in TARGETS:
    print("=== %s ===" % k)
    if not found[k]:
        print("   （当前树里没有任何引用 —— 说明这处丢失**目前不会报错**，但功能缺失）")
    else:
        for x in found[k][:8]:
            print("   " + x)
    print()
