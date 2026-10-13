# -*- coding: utf-8 -*-
"""把「覆盖前备份」里的右键菜单构造代码打出来，和现在对比清楚度差异。"""
import io
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REFS = ["remotes/origin/backup/main-before-overwrite-20261001",
        "remotes/origin/backup/main-before-overwrite-20260928"]

for ref in REFS:
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:classes/murasame_class.py" % ref],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    t = r.stdout or ""
    print("=" * 78)
    print("=== %s ===  文件行数=%d" % (ref.split("/")[-1], len(t.split("\n"))))
    print("=" * 78)
    if not t:
        print("   （取不到：%s）" % (r.stderr or "")[:160])
        continue
    lines = t.split("\n")
    # 找菜单构造：出现 QMenu 或 addAction 或 菜单 的地方
    idxs = [i for i, l in enumerate(lines)
            if re.search(r"QMenu\(|addAction|menu\b.*=|菜单", l)]
    if not idxs:
        print("   没有明显的菜单构造")
        continue
    # 抽取所有 addAction / menu.addAction 的文案
    txts = re.findall(r'addAction\(\s*(?:QAction\(\s*)?["\']([^"\']{1,40})["\']', t)
    print("   addAction 文案 %d 个：" % len(txts))
    seen = []
    for x in txts:
        if x not in seen:
            seen.append(x)
    for x in seen[:60]:
        print("      • " + x)
