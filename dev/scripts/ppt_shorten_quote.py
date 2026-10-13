# -*- coding: utf-8 -*-
"""金句再缩短，争取单行；重建 + 重渲染。"""
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
    if s.get("type") == "quote" and "住在" in s.get("text", ""):
        s["text"] = "别人做「桌面上的形象」，我们做「住在电脑里的人」"
        s["by"] = "定位：整合者，而非首创者"
        print("✓ 金句改为：", s["text"], "/", s["by"])
io.open(P, "w", encoding="utf-8", newline="\n").write(
    json.dumps(d, ensure_ascii=False, indent=2) + "\n")

# 注意：subprocess 输出用 utf-8 + errors=replace，避免 GBK 解码炸（上一轮踩过）
subprocess.run([sys.executable, r"E:\Codex\workflows\ppt\scripts\build_deck.py",
                "--outline", P, "--out", os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx"),
                "--theme", os.path.join(ROOT, "dev", "ppt", "theme-murasame.json")],
               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
print("✓ 已重建")
r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    r"E:\Codex\workflows\ppt\scripts\render_qc.ps1", "-Deck",
                    os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:130])
