# -*- coding: utf-8 -*-
"""① 补挑漏掉的手机端脚本（termux/apk/chatter/android 关键词）
   ② 找网易云音乐插件并说明怎么用
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(a, timeout=900):
    r = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip()


print("=== ① 补挑手机端脚本 ===")
PHONE = re.compile(r"termux|apk|chatter|android|安卓|_vrm|vrm\d|hotspot|热点", re.I)
files = [f for f in sh(["git", "ls-files", "dev/scripts"]).split("\n") if f.strip()]
targets = [f for f in files if PHONE.search(os.path.basename(f))]
print("   命中 %d 个（dev/scripts 下）" % len(targets))
for f in targets:
    print("      " + f)
removed = 0
for f in targets:
    o, c = subprocess.run(["git", "rm", "--cached", "--quiet", "--", f], cwd=ROOT,
                          capture_output=True).returncode, None
    if o == 0:
        removed += 1
print("   ✓ 已从 git 摘掉 %d 个（文件仍在硬盘 ✓）" % removed)

# 顺带把整个 dev/scripts 下其它手机相关目录也查一遍（非 dev/docs）
others = []
for f in sh(["git", "ls-files"]).split("\n"):
    f = f.strip()
    if not f or f.startswith("dev/docs/") or f.endswith((".md", ".txt")):
        continue
    if PHONE.search(f):
        others.append(f)
print()
print("   全仓再扫一遍（非文档）：")
if others:
    for f in others:
        print("      " + f)
else:
    print("      ✓ 干净")

print()
print("=== ② 网易云音乐插件 ===")
found = []
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp for s in (".git", "runtime", "GPT-SoVITS", "F5-TTS_Models", "dev\\tmp",
                             ".venv", "__pycache__", "node_modules", "NapCat", "_internal")):
        continue
    for f in fn:
        if f == "plugin.json":
            found.append(os.path.join(dp, f))
for p in found:
    rel = os.path.relpath(p, ROOT)
    t = io.open(p, encoding="utf-8", errors="replace").read()
    nm = re.search(r'"name"\s*:\s*"([^"]*)"', t)
    en = re.search(r'"enabled"\s*:\s*"?(\w+)"?', t)
    de = re.search(r'"description"\s*:\s*"([^"]*)"', t)
    mark = "★" if ("网易" in t or "music" in t.lower() or "163" in t) else " "
    print("   %s %-46s name=%s enabled=%s" % (mark, rel[:46],
                                              nm.group(1) if nm else "?",
                                              en.group(1) if en else "?"))
    if de:
        print("        %s" % de.group(1)[:96])
    if mark == "★":
        print("        ---- 文件内容 ----")
        for l in t.split("\n")[:22]:
            print("        " + l.rstrip()[:100])
