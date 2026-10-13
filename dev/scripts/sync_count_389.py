# -*- coding: utf-8 -*-
"""386 → 389：查清是哪个体检文件的项数变了，并把 README / PPT / 操作单 的数字全部同步。"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

print("=== ① 各体检文件项数（找出变化来源）===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
rows = []
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    m = re.match(r"\s*(\S+\.py)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)s", l)
    if m:
        rows.append((m.group(1), int(m.group(3))))
        print("   %-34s %4d 项" % (m.group(1), int(m.group(3))))
total = None
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    m = re.search(r"总计\s+(\d+)\s+个文件\s*/\s*(\d+)\s+项", l)
    if m:
        total = int(m.group(2))
        print("   ⇒ 总计 %s 项" % total)
if total is None:
    print("   ✗ 没解析到总计")
    sys.exit(1)

print()
print("=== ② 全仓把 386 更新为 %d ===" % total)
SKIP_DIRS = ("\\.git", "\\runtime", "\\GPT-SoVITS", "\\_internal", "\\build", "\\.venv",
             "\\NapCat", "\\__pycache__", "\\F5-TTS_Models", "\\models", "\\dev\\merge-map",
             "\\dev\\scripts")
changed = []
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp for s in SKIP_DIRS):
        continue
    for f in fn:
        if not f.endswith((".md", ".json")):
            continue
        p = os.path.join(dp, f)
        try:
            t = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if "386" not in t:
            continue
        if not re.search(r"386\s*项|自检.{0,8}386|386.{0,8}自检|项通过", t):
            continue
        n = t.replace("386 项", "%d 项" % total).replace("386项", "%d项" % total)
        n = re.sub(r"(总计[^\n]*?/\s*)386(\s*项)", r"\g<1>%d\g<2>" % total, n)
        n = n.replace("| 386 |", "| %d |" % total)
        if n != t:
            io.open(p, "w", encoding="utf-8", newline="\n").write(n)
            changed.append(p.replace(ROOT + os.sep, ""))
            print("   ✓ %s" % p.replace(ROOT + os.sep, ""))
if not changed:
    print("   （没有需要改的）")

print()
print("=== ③ PPT 大纲/讲稿里的数字 ===")
for rel in ("dev/ppt/outline.json", "dev/ppt/notes.json"):
    p = os.path.join(ROOT, rel)
    t = io.open(p, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r"[^\n]{0,40}\d{3}\s*项[^\n]{0,40}", t):
        print("   %-22s %s" % (rel, m.group(0).strip()[:80]))
