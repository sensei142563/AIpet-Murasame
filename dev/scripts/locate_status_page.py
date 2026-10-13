# -*- coding: utf-8 -*-
"""把 status_page_enabled 整套接上 + 补 QSS 那条：
  ① QSS 里 QDialog#statusWindow（确认/强制）
  ② config.example.json 加 status_page_enabled: true
  ③ 侧栏「状态」项（受开关管，默认开）
  ④ 设置页开关
  ⑤ 右键菜单「她的状态」受同一开关管
先查侧栏/设置页/菜单的实现位置。
"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SKIP = ("\\.venv\\", "\\.git\\", "site-packages", "__pycache__", "\\runtime\\", "\\dev\\scripts\\")

print("=== ① status_window.py 里 QDialog#statusWindow 是否写进去了 ===")
t = io.open(os.path.join(ROOT, "classes", "status_window.py"), encoding="utf-8",
            errors="replace").read()
print("   含 QDialog#statusWindow:", "有 ✓" if "QDialog#statusWindow" in t else "**没有** ✗")
print("   含 setObjectName(\"statusWindow\"):", "有 ✓" if 'setObjectName("statusWindow")' in t else "没有 ✗")

print()
print("=== ② 侧栏项定义在哪（找 'themes' / 'settings' 这类 id 列表）===")
for dp, dn, fn in os.walk(ROOT):
    if any(x in dp + "\\" for x in SKIP):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        s = io.open(p, encoding="utf-8", errors="replace").read()
        if re.search(r'"themes"', s) and re.search(r"SIDEBAR|sidebar|侧栏|nav_", s):
            print("   ── %s ──" % f)
            for i, l in enumerate(s.split("\n"), 1):
                if re.search(r'themes|sidebar|侧栏|SIDEBAR|nav_item|_ITEMS', l):
                    print("      %5d| %s" % (i, l.strip()[:120]))

print()
print("=== ③ 右键菜单里「她的状态」当前怎么挂的 ===")
mc = io.open(os.path.join(ROOT, "classes", "murasame_class.py"), encoding="utf-8",
             errors="replace").read().split("\n")
for i, l in enumerate(mc, 1):
    if "她的状态" in l or "show_status_window" in l:
        lo = max(0, i - 3)
        for j in range(lo, min(len(mc), i + 3)):
            print("   %5d| %s" % (j + 1, mc[j].rstrip()[:125]))
        print("   " + "-" * 55)

print()
print("=== ④ config.example.json 现有键（抽样）===")
ex = json.loads(io.open(os.path.join(ROOT, "config.example.json"), encoding="utf-8",
                        errors="replace").read())
print("   含 status_page_enabled:", "有 ✓" if "status_page_enabled" in ex else "**没有** ✗")
print("   顶层键数:", len(ex))
