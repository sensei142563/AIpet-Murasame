# -*- coding: utf-8 -*-
"""B 第一步：合并 origin/main，并把每处冲突的"我们 vs 他们"摊开（截断显示，便于决策）。"""
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
    return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode


print("=== 现状 ===")
print("   HEAD = %s" % sh(["git", "log", "-1", "--format=%h %s"])[0][:100])
print("   origin/main = %s" % sh(["git", "log", "-1", "--format=%h %s", "origin/main"])[0][:100])
out, _ = sh(["git", "status", "--porcelain"])
tr = [l for l in out.split("\n") if l.strip() and not l.startswith("??")]
print("   已跟踪脏项 %d（应为 0）" % len(tr))
if tr:
    print("   ⚠ 先别合，工作区不干净")
    for l in tr[:5]:
        print("      " + l[:100])
    sys.exit(0)

print()
print("=== 开始合并 origin/main ===")
out2, code2 = sh(["git", "merge", "origin/main"])
for l in out2.split("\n")[:18]:
    if l.strip():
        print("   " + l.strip()[:126])
print("   退出码 = %d" % code2)

print()
print("=== 冲突清单 ===")
out3, _ = sh(["git", "status", "--porcelain"])
confs = []
for l in out3.split("\n"):
    if l.strip().startswith(("UU", "AA", "DD", "AU", "UA", "DU", "UD")):
        p = l[3:].strip()
        if p.startswith('"') and p.endswith('"'):
            p = p[1:-1]
        confs.append(p)
print("   共 %d 个冲突文件" % len(confs))

for f in confs:
    fp = os.path.join(ROOT, f.replace("/", "\\"))
    print()
    print("   ══════ %s ══════" % f)
    try:
        t = io.open(fp, encoding="utf-8", errors="replace").read()
    except Exception as e:
        print("      （读不了：%s）" % e)
        continue
    # 解析冲突块
    blocks = re.findall(r"<<<<<<<[^\n]*\n(.*?)=======\n(.*?)>>>>>>>[^\n]*\n", t, re.S)
    print("      冲突段数 = %d" % len(blocks))
    for i, (ours, theirs) in enumerate(blocks, 1):
        ol = [x for x in ours.split("\n") if x.strip()]
        tl = [x for x in theirs.split("\n") if x.strip()]
        print("      ── 第 %d 段：我们 %d 行 / 他们 %d 行" % (i, len(ol), len(tl)))
        print("         我们：")
        for x in ol[:4]:
            print("            | " + x.strip()[:92])
        if len(ol) > 4:
            print("            | …（还有 %d 行）" % (len(ol) - 4))
        print("         他们：")
        for x in tl[:4]:
            print("            | " + x.strip()[:92])
        if len(tl) > 4:
            print("            | …（还有 %d 行）" % (len(tl) - 4))
