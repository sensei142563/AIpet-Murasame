# -*- coding: utf-8 -*-
"""查清"两套本地视觉机制"到底哪套是活的：
  ① 用户 config.json 的 model_type / vision_model_name / vision_source
  ② tool/chat.py 的 describe_image() 完整分支（vision_source()=="local" 走 A 还是 B？）
  ③ ollama_qwen25vl 被谁调用（是否可达）
  ④ camera.py 那条链怎么调 describe_image
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

print("=== ① config.json 相关项 ===")
c = json.load(io.open(os.path.join(ROOT, "config.json"), encoding="utf-8", errors="replace"))
for k in ("model_type", "vision_model_name", "vision_source", "ollama",
          "screen_type", "camera_type"):
    print("   %-20s = %r" % (k, c.get(k, "（无此键）")))

print()
print("=== ② tool/chat.py: describe_image 及其分支 ===")
lines = io.open(os.path.join(ROOT, "tool", "chat.py"), encoding="utf-8",
                errors="replace").read().split("\n")
start = None
for i, l in enumerate(lines, 1):
    if re.match(r"\s*def describe_image", l):
        start = i
        break
if start:
    depth = 0
    for j in range(start - 1, min(len(lines), start + 90)):
        l = lines[j]
        print("   %5d| %s" % (j + 1, l.rstrip()[:112]))
        depth += l.count("(") - l.count(")")
        if j > start and re.match(r"^def |^class ", l):
            break
else:
    print("   ✗ 没找到 describe_image")

print()
print("=== ③ 谁调用 ollama_qwen25vl ===")
SKIP = re.compile(r"\\(runtime|\.venv|site-packages|GPT-SoVITS|_import_tmp|\.git)\\", re.I)
for dp, dn, fn in os.walk(ROOT):
    if SKIP.search(dp + "\\"):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        try:
            ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        for i, l in enumerate(ls, 1):
            if "ollama_qwen25vl" in l or "qwen2.5vl" in l:
                print("   %-38s %5d| %s" % (p.replace(ROOT + "\\", "")[:38], i, l.strip()[:92]))
