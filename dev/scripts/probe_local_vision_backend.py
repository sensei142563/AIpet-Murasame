# -*- coding: utf-8 -*-
"""核实：本地视觉到底走 Ollama（qwen2.5vl）还是 tool/vision_service.py（Qwen2-VL-2B）？
   决定 README 1477 行那句"ollama pull qwen2.5vl:7b # 如需本地屏幕识别"是否过时。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SKIP = re.compile(r"\\(runtime|\.venv|site-packages|GPT-SoVITS|_import_tmp|\.git|dev\\tts_model_cache)\\", re.I)

keys = ["qwen2.5vl", "qwen2_5vl", "ollama", "Ollama", "OLLAMA",
        "vision_service", "vision_local", "11434"]
print("=== 搜这些关键字（谁在用哪个）===")
for dp, dn, fn in os.walk(ROOT):
    if SKIP.search(dp + "\\"):
        continue
    for f in fn:
        if not f.endswith((".py", ".json", ".md")):
            continue
        p = os.path.join(dp, f)
        try:
            lines = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        for i, l in enumerate(lines, 1):
            for k in keys:
                if k in l and ("vision" in l.lower() or "识别" in l or "vl" in l.lower()
                               or k in ("ollama", "Ollama", "OLLAMA", "11434")):
                    rel = p.replace(ROOT + "\\", "")
                    if rel.startswith("dev\\scripts\\"):
                        continue
                    print("   %-42s %5d| [%s] %s" % (rel[:42], i, k, l.strip()[:80]))
                    break
