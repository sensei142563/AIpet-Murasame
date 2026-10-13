# -*- coding: utf-8 -*-
"""审 deck 第 14 页那句「关系值按真实相处证据抬升，不靠嘴甜」。
   要找的是：关系值/好感度在哪里加、加的条件是什么（是"相处证据"还是"说了好听话"）。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SKIP = re.compile(r"\\(runtime|\.venv|site-packages|GPT-SoVITS|_import_tmp|\.git|dev\\)", re.I)

KEYS = ["关系值", "好感", "affection", "intimacy", "favor", "relationship", "亲密度", "关系"]
print("=== 搜关系值/好感相关代码 ===")
hits = 0
for dp, dn, fn in os.walk(ROOT):
    if SKIP.search(dp + "\\"):
        continue
    for f in fn:
        if not f.endswith((".py", ".json")):
            continue
        p = os.path.join(dp, f)
        try:
            ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        for i, l in enumerate(ls, 1):
            if any(k in l for k in KEYS) and re.search(
                    r"\+|加|提升|抬升|increase|add|update|计算|score|值", l):
                rel = p.replace(ROOT + "\\", "")
                if rel.startswith(("dev\\", "docs\\")):
                    continue
                print("   %-42s %5d| %s" % (rel[:42], i, l.strip()[:92]))
                hits += 1
                if hits > 32:
                    print("   …（截断）")
                    sys.exit(0)
print("   命中 =", hits)
