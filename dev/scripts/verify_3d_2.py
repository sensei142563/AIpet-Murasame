# -*- coding: utf-8 -*-
"""决定性核实：VRM(3D) 界面到底吃什么输入？手部数据有没有真的驱动它？
   ① 读 chatter 的权威状态文档 docs/手部互动-实现与验证状态.md
   ② 逐个看 VRM/AR 界面文件里与"手/视线/输入"相关的行
   ③ 看 HandTracker/HandDetector/HandTouch 的输出去向
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
BASE = os.path.join(REPO, "app", "src", "main", "java", "com", "aipet", "murasame")

print("=== ① 权威状态文档 ===")
p = os.path.join(REPO, "docs", "手部互动-实现与验证状态.md")
if os.path.isfile(p):
    t = io.open(p, encoding="utf-8", errors="replace").read()
    print("   （%d 行）" % len(t.split("\n")))
    for l in t.split("\n")[:70]:
        print("   " + l.rstrip()[:112])
else:
    print("   ✗ 不在")

print()
print("=== ② VRM/AR 界面：吃什么输入、驱动什么 ===")
for rel in ("ui/VrmScreen.kt", "ui/VrmArScreen.kt", "ui/ArGround.kt"):
    fp = os.path.join(BASE, rel.replace("/", os.sep))
    if not os.path.isfile(fp):
        print("   ✗ 缺 %s" % rel)
        continue
    t = io.open(fp, encoding="utf-8", errors="replace").read()
    print("   ── %s（%d 行）" % (rel, len(t.split("\n"))))
    for i, l in enumerate(t.split("\n"), 1):
        if re.search(r"hand|landmark|gesture|pinch|视线|eye|look|gaze|rotate|rotation|"
                     r"track|input|onHand|handState|State<|remember", l, re.I):
            s = l.strip()
            if s and not s.startswith("//"):
                print("      %5d| %s" % (i, s[:104]))

print()
print("=== ③ 手部模块的输出去向（谁调用了它们）===")
for name in ("HandTracker", "HandDetector", "HandGesture", "HandTouch"):
    print("   ── %s 被谁引用：" % name)
    n = 0
    for dp, dn, fn in os.walk(os.path.join(REPO, "app", "src")):
        for f in fn:
            if not f.endswith(".kt"):
                continue
            fp = os.path.join(dp, f)
            try:
                t = io.open(fp, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if name in t and not os.path.basename(f).startswith(name):
                rel = os.path.relpath(fp, REPO)
                lines = [l.strip() for l in t.split("\n") if name in l]
                print("      %-64s %d 处" % (rel[:64], len(lines)))
                for l in lines[:3]:
                    print("          " + l[:96])
                n += 1
    if n == 0:
        print("      （无人引用）")
