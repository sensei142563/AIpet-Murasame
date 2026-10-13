# -*- coding: utf-8 -*-
"""查 data/tts_model.json 的消费者 —— 确认 gpt/sovits 标签互换有没有实际后果。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SKIP = re.compile(r"\\(runtime|\.venv|site-packages|GPT-SoVITS|_import_tmp|\.git)\\", re.I)

print("=== 谁读 data/tts_model.json ===")
for dp, dn, fn in os.walk(ROOT):
    if SKIP.search(dp + "\\"):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        try:
            lines = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        for i, l in enumerate(lines, 1):
            if "tts_model.json" in l or "tts_model" in l:
                rel = p.replace(ROOT + "\\", "")
                print("   %-40s %5d| %s" % (rel[:40], i, l.strip()[:100]))
                # 打印紧随其后的 12 行（看它怎么用 gpt/sovits 字段）
                for j in range(i, min(len(lines), i + 12)):
                    if re.search(r'\["gpt"\]|\["sovits"\]|\.get\("gpt"|\.get\("sovits"|gpt\b|sovits\b', lines[j]):
                        print("        %5d| %s" % (j + 1, lines[j].strip()[:104]))
