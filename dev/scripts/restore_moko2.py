# -*- coding: utf-8 -*-
"""收尾：
  ① 检查主题缺 nav_icons/decor 文件时代码会不会回落（不会的话就从 senrenbanka 补齐）
  ② 直接枚举四个主题，确认「沫子的日常」能被看见
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
TH = os.path.join(ROOT, "pcl_launcher", "themes")
TD = os.path.join(TH, "senrenbanka_copy")

print("=== ① 代码对'主题缺图标文件'的处理（有没有回落）===")
for rel in ("pcl_launcher/colors.py", "pcl_launcher/silicon_window.py"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls, 1):
        if re.search(r"nav_icons|decor|isfile|exists|fallback|回落|默认图标", l):
            print("   %-24s %5d| %s" % (os.path.basename(p), i, l.strip()[:104]))

print()
print("=== ② 从 senrenbanka 补齐缺失的 assets（若有缺失）===")
src = os.path.join(TH, "senrenbanka")
need = []
for sub in ("assets", os.path.join("assets", "nav")):
    sd = os.path.join(src, sub)
    if not os.path.isdir(sd):
        continue
    for f in os.listdir(sd):
        sp = os.path.join(sd, f)
        if not os.path.isfile(sp):
            continue
        dp = os.path.join(TD, sub, f)
        if not os.path.isfile(dp):
            need.append((sp, dp))
if need:
    for sp, dp in need:
        os.makedirs(os.path.dirname(dp), exist_ok=True)
        shutil.copy2(sp, dp)
        print("   ✓ 补齐 %s" % dp.replace(TD + os.sep, ""))
else:
    print("   （没有缺失，不用补）")

print()
print("=== ③ 四个主题现在长这样 ===")
for d in sorted(os.listdir(TH)):
    p = os.path.join(TH, d)
    if not os.path.isdir(p):
        continue
    tj = os.path.join(p, "theme.json")
    nm, bg = "", ""
    if os.path.isfile(tj):
        try:
            j = json.load(io.open(tj, encoding="utf-8", errors="replace"))
            nm = j.get("name", "")
            b = j.get("background") or {}
            bg = "%s:%s" % (b.get("type", ""), b.get("source", "")) if b else ""
        except Exception as e:
            nm = "解析失败:" + str(e)
    n = sum(len(f) for _, _, f in os.walk(p))
    print("   %-20s name=%-12s %2d 文件  背景=%s" % (d, nm, n, bg[:44]))

print()
print("=== ④ 模拟启动器的主题枚举（直接读目录 + 解析）===")
found = []
for d in sorted(os.listdir(TH)):
    tj = os.path.join(TH, d, "theme.json")
    if os.path.isfile(tj):
        try:
            j = json.load(io.open(tj, encoding="utf-8", errors="replace"))
            found.append((d, j.get("name")))
        except Exception:
            found.append((d, "（解析失败）"))
    else:
        found.append((d, "（无 theme.json ⇒ 枚举不到 ✗）"))
for d, nm in found:
    mark = "  ← 就是它 ✓" if nm == "沫子的日常" else ""
    print("   %-20s %s%s" % (d, nm, mark))
print("   ⇒ 能枚举到 %d 个主题" % sum(1 for _, nm in found if not str(nm).startswith("（")))
