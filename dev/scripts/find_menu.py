# -*- coding: utf-8 -*-
"""定位"右键菜单"实现：扫仓库源码（排除 venv/git/site-packages），列出命中的文件与行。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SKIP = ("\\.venv\\", "\\.git\\", "site-packages", "node_modules", "\\__pycache__\\",
        "\\dist\\", "\\build\\", "\\_internal\\", "\\tmp\\", "\\_import_tmp\\",
        "\\F5-TTS_Models\\", "\\GPT-SoVITS\\", "\\models\\", "\\runtime\\")
PAT = re.compile(r"右键|contextMenu|ContextMenu|customContextMenu|QMenu|addAction|"
                 r"addMenu|menu\b|Menu\(", re.I)

hits = {}
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp + "\\" for s in SKIP):
        continue
    for f in fn:
        if not f.endswith((".py", ".md", ".json", ".kv", ".ui")):
            continue
        p = os.path.join(dp, f)
        try:
            t = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        n = len(PAT.findall(t))
        if n:
            hits[p] = n

print("=== 命中「右键/菜单」最多的 22 个文件 ===")
for p, n in sorted(hits.items(), key=lambda kv: -kv[1])[:22]:
    print("   %4d 处  %s" % (n, p.replace(ROOT + "\\", "")))
