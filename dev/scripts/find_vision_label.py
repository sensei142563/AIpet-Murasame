# -*- coding: utf-8 -*-
"""查"视觉模型：本地视觉模型（本地部署）"这行字从哪来，以及它与既定决策的关系。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

KEYS = ["本地视觉模型", "本地部署", "视觉模型", "vision_source", "vision_model",
        "本地视觉"]

print("=== ① 全仓（排除 venv/runtime）搜这些字串 ===")
SKIP = re.compile(r"\\(runtime|\.venv|site-packages|node_modules|\.git|GPT-SoVITS|_import_tmp)\\")
hits = 0
for dp, dn, fn in os.walk(ROOT):
    if SKIP.search(dp + "\\"):
        continue
    for f in fn:
        if not f.lower().endswith((".py", ".json", ".md", ".txt", ".yaml", ".yml")):
            continue
        p = os.path.join(dp, f)
        try:
            t = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for k in KEYS:
            for m in re.finditer(re.escape(k), t):
                line_no = t.count("\n", 0, m.start()) + 1
                line = t.split("\n")[line_no - 1].strip()
                rel = p.replace(ROOT + "\\", "")
                print("   %-46s %5d| [%s] %s" % (rel[:46], line_no, k, line[:74]))
                hits += 1
                if hits > 40:
                    print("   …（截断）")
                    sys.exit(0)
print("   命中 =", hits)
