# -*- coding: utf-8 -*-
"""修第 19 页渲染出的两个问题：
  ① 最后一条要点过长（换行贴到幻灯片边缘）⇒ 缩短
  ② 用了 ⚠ 符号，与 deck 其余页面（无符号）风格不一致 ⇒ 换成文字
"""
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
OUT = os.path.join(ROOT, "dev", "ppt", "outline.json")

o = json.loads(io.open(OUT, encoding="utf-8", errors="replace").read())
for s in o["slides"]:
    if s.get("title", "").startswith("互动：从"):
        for b in s["bullets"]:
            if b.get("text", "").startswith("⚠") or "真机调优" in b.get("text", ""):
                b["text"] = "还没做：真机调优"
                b["sub"] = "编译与单测都过了，但「手伸过去她眼睛是否跟着转」要真机确认；偏差只调相机"
            if "捏合=捏脸" in (b.get("sub") or ""):
                b["sub"] = "捏合=捏脸、握拳、挥手；各自独立去抖（21 个单测：9+6+6）"
        print("✓ 已缩短最后一条并去掉符号")
        break
json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)

print()
print("=== 重建 + 渲染 ===")
env = dict(os.environ, PYTHONIOENCODING="utf-8")
for cmd in ([sys.executable, r"E:\Codex\workflows\ppt\scripts\build_deck.py",
             "--outline", "dev\\ppt\\outline.json", "--out", "dev\\ppt\\out\\Deck.pptx",
             "--theme", "dev\\ppt\\theme-murasame.json"],
            [sys.executable, os.path.join(ROOT, "dev", "scripts", "ppt_add_notes.py")]):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=900)
    for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
        if "已生成" in l or "缺备注" in l or "已写入备注" in l:
            print("   " + l.strip()[:100])
r = subprocess.run(["powershell", "-NoProfile", "-File",
                    r"E:\Codex\workflows\ppt\scripts\render_qc.ps1",
                    "-Deck", os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:100])
