# -*- coding: utf-8 -*-
"""打印右键菜单构造代码（现在 vs 覆盖前备份），并抽取菜单项文案。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF = "remotes/origin/backup/main-before-overwrite-20261001"
CUR = os.path.join(ROOT, "classes", "murasame_class.py")


def show_menu_region(text, label, ctx=6):
    print("=" * 78)
    print("=== %s ===" % label)
    print("=" * 78)
    lines = text.split("\n")
    hits = [i for i, l in enumerate(lines) if "StoryMenu" in l or "StoryMenu(" in l]
    if not hits:
        print("   （没有 StoryMenu）")
        return
    lo = max(0, hits[0] - 8)
    hi = min(len(lines), hits[0] + 150)
    for i in range(lo, hi):
        print("%5d| %s" % (i + 1, lines[i].rstrip()[:150]))


cur = io.open(CUR, encoding="utf-8", errors="replace").read()
show_menu_region(cur, "现在（工作区 classes/murasame_class.py）")

r = subprocess.run(["git", "-C", ROOT, "show", "%s:classes/murasame_class.py" % REF],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
old = r.stdout or ""
if old:
    show_menu_region(old, "覆盖前（%s）" % REF)
else:
    print("取不到备份文件：", (r.stderr or "")[:200])
