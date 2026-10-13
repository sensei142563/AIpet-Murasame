# -*- coding: utf-8 -*-
"""按调研文档自己的结论，给 PPT 补一条"诚实定位"，避免过度宣称。
然后重建 + 重渲染 + 抽查改动页。
"""
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(ROOT, "dev", "ppt", "outline.json")

d = json.loads(io.open(P, encoding="utf-8", errors="replace").read())
changed = []

for s in d.get("slides", []):
    if s.get("title", "").startswith("横向对比"):
        bullets = s.get("bullets") or []
        if not any("并非首创" in (b.get("text", "") if isinstance(b, dict) else b)
                   for b in bullets):
            bullets.append({
                "text": "诚实定位：并非首创",
                "sub": "但已进入极稀疏地带——唯一查到做齐且仍在活跃的是 super-agent-party"
            })
            s["bullets"] = bullets
            changed.append("横向对比页补『并非首创』")
    if s.get("type") == "quote" and "住在你电脑里的人" in s.get("text", ""):
        s["by"] = "本项目的定位：整合者，而非首创者"
        changed.append("金句出处改为『整合者，而非首创者』")

io.open(P, "w", encoding="utf-8", newline="\n").write(
    json.dumps(d, ensure_ascii=False, indent=2) + "\n")
print("✓ 改动：", changed or "（无需改）")

print()
print("=== 重建 ===")
r = subprocess.run([sys.executable, r"E:\Codex\workflows\ppt\scripts\build_deck.py",
                    "--outline", P, "--out", os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx"),
                    "--theme", os.path.join(ROOT, "dev", "ppt", "theme-murasame.json")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "ok" in l or "页" in l or "Error" in l:
        print("   " + l.strip()[:140])

print()
print("=== 重渲染 ===")
r2 = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                     r"E:\Codex\workflows\ppt\scripts\render_qc.ps1", "-Deck",
                     os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx")],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
for l in ((r2.stdout or "") + (r2.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:140])
