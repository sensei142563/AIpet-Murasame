# -*- coding: utf-8 -*-
"""修金句页排版：全角引号与外层引号重复 + 超长换行 ⇒ 改用「」并缩短；重建+重渲染+看该页。"""
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(ROOT, "dev", "ppt", "outline.json")

d = json.loads(io.open(P, encoding="utf-8", errors="replace").read())
for s in d.get("slides", []):
    if s.get("type") == "quote" and "住在你电脑里的人" in s.get("text", ""):
        s["text"] = "别人做的是「桌面上的一个形象」，我们做的是「住在你电脑里的人」"
        print("✓ 已改金句：", s["text"])
io.open(P, "w", encoding="utf-8", newline="\n").write(
    json.dumps(d, ensure_ascii=False, indent=2) + "\n")

subprocess.run([sys.executable, r"E:\Codex\workflows\ppt\scripts\build_deck.py",
                "--outline", P, "--out", os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx"),
                "--theme", os.path.join(ROOT, "dev", "ppt", "theme-murasame.json")],
               capture_output=True, text=True, timeout=600)
print("✓ 已重建")
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                r"E:\Codex\workflows\ppt\scripts\render_qc.ps1", "-Deck",
                os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx")],
               capture_output=True, text=True, timeout=1800)
print("✓ 已重渲染")
