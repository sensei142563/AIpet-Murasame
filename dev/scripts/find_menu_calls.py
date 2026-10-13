# -*- coding: utf-8 -*-
"""找右键菜单的调用点，并抽取菜单项清单（现在 vs 覆盖前备份），用于对比"是不是不如以前清楚"。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SKIP = ("\\.venv\\", "\\.git\\", "site-packages", "\\__pycache__\\", "\\dist\\", "\\build\\",
        "\\_internal\\", "\\dev\\three-demo\\")


def walk_py():
    for dp, dn, fn in os.walk(ROOT):
        if any(s in dp + "\\" for s in SKIP):
            continue
        for f in fn:
            if f.endswith(".py"):
                yield os.path.join(dp, f)


print("=== 谁在造右键菜单（contextMenuEvent / RightButton / StoryMenu / QMenu）===")
pat = re.compile(r"contextMenuEvent|Qt\.RightButton|StoryMenu|QMenu\(", re.I)
for p in walk_py():
    t = io.open(p, encoding="utf-8", errors="replace").read()
    hits = pat.findall(t)
    if hits:
        rel = p.replace(ROOT + "\\", "")
        print("   %-46s %s" % (rel, sorted(set(hits))))
