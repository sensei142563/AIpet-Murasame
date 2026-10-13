# -*- coding: utf-8 -*-
"""打印 test_config_contracts 三项失败涉及的确切代码行，便于精确修复。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def show(path, lines, ctx=2, label=""):
    p = os.path.join(ROOT, path)
    t = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    print("=== %s %s（共 %d 行）===" % (path, label, len(t)))
    for n in lines:
        lo, hi = max(0, n - 1 - ctx), min(len(t), n + ctx)
        for j in range(lo, hi):
            mark = ">>" if j == n - 1 else "  "
            print("   %s %4d| %s" % (mark, j + 1, t[j].rstrip()[:130]))
        print("   " + "-" * 60)


show("tool/jp_names.py", [43, 63, 67, 76])
show("qq/qq_config.py", [274])
show("chat.py", [18, 19, 23])
