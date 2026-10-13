# -*- coding: utf-8 -*-
"""① 给 dev/scripts/ppt_add_notes.py 加可选的目标文件参数（原来把 Deck.pptx 写死了）
   ② 缩短新第 10 页第一条（末尾"主动"换行了）
   ③ 重建 Deck_24.pptx → 挂讲稿 → 渲染 → 看图复核
"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

# ---------- ① 让挂讲稿脚本支持指定文件 ----------
P = os.path.join(ROOT, "dev", "scripts", "ppt_add_notes.py")
t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = 'DECK = os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx")'
NEW = ('# 可选：命令行给一个目标 pptx（默认仍是 Deck.pptx）。\n'
       '# 用途：Deck.pptx 被 PowerPoint/WPS 打开时会被加写锁，此时先建到别的名字再挂讲稿。\n'
       'DECK = (sys.argv[1] if len(sys.argv) > 1\n'
       '        else os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx"))')
if OLD in t and "sys.argv[1]" not in t:
    t = t.replace(OLD, NEW, 1)
    if "import sys" not in t:
        t = t.replace("import os", "import os\nimport sys", 1)
    io.open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ ① ppt_add_notes.py 现支持：python ppt_add_notes.py [目标.pptx]")
else:
    print("· ① 已支持或锚点未命中")

# ---------- ② 缩短第 10 页第一条 ----------
OUT = os.path.join(ROOT, "dev", "ppt", "outline.json")
o = json.loads(io.open(OUT, encoding="utf-8", errors="replace").read())
for s in o["slides"]:
    if s.get("title", "").startswith("更广的同类"):
        s["bullets"][0]["sub"] = ("Live2DViewerEX（Steam ¥26）：跨平台 + 面捕 + 创意工坊，"
                                  "把模型放出来做到了天花板 —— 但它不聊、不记、不主动")
        print("✓ ② 第 10 页第一条已缩短")
        break
json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)

# ---------- ③ 重建 + 挂讲稿 + 渲染 ----------
env = dict(os.environ, PYTHONIOENCODING="utf-8")
TARGET = "dev\\ppt\\out\\Deck_24.pptx"
print()
print("=== ③ 重建 %s ===" % TARGET)
r = subprocess.run([sys.executable, r"E:\Codex\workflows\ppt\scripts\build_deck.py",
                    "--outline", "dev\\ppt\\outline.json", "--out", TARGET,
                    "--theme", "dev\\ppt\\theme-murasame.json"],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env, timeout=1200)
print("   build 退出码 =", r.returncode)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if l.strip() and ("已生成" in l or "Error" in l or "Traceback" in l or "error" in l):
        print("   " + l.strip()[:110])
if r.returncode != 0:
    print("   ✗ 构建失败，后面不再继续")
    sys.exit(1)

r2 = subprocess.run([sys.executable, os.path.join(ROOT, "dev", "scripts", "ppt_add_notes.py"),
                     os.path.join(ROOT, TARGET)],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", env=env, timeout=1200)
print("   notes 退出码 =", r2.returncode)
for l in ((r2.stdout or "") + (r2.stderr or "")).split("\n"):
    if "缺备注" in l or "已写入备注" in l or "Error" in l:
        print("   " + l.strip()[:110])

r3 = subprocess.run(["powershell", "-NoProfile", "-File",
                     r"E:\Codex\workflows\ppt\scripts\render_qc.ps1",
                     "-Deck", os.path.join(ROOT, TARGET)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=2400)
for l in ((r3.stdout or "") + (r3.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:110])
