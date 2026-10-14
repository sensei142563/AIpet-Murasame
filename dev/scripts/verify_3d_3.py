# -*- coding: utf-8 -*-
"""把"到底验到哪一步"读准确（这次不能猜）：
   ① 状态文档的第 70~117 行（诚实分级清单）
   ② VrmArScreen.kt 里提到"真机"的所有行及其上下文
   ③ 界面上的提示文案（用户能看到什么）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
BASE = os.path.join(REPO, "app", "src", "main", "java", "com", "aipet", "murasame")

print("=== ① 状态文档 70~117 行 ===")
p = os.path.join(REPO, "docs", "手部互动-实现与验证状态.md")
ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
for i in range(69, min(len(ls), 117)):
    print("   %4d| %s" % (i + 1, ls[i].rstrip()[:112]))

print()
print("=== ② 「真机」相关的所有行（含上下文）===")
for rel in ("ui/VrmArScreen.kt", "ui/HandTracker.kt", "ui/HandDetector.kt",
            "ui/HandGesture.kt", "ui/HandTouch.kt"):
    fp = os.path.join(BASE, rel.replace("/", os.sep))
    if not os.path.isfile(fp):
        continue
    ls2 = io.open(fp, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls2):
        if re.search(r"真机|实测|复测|已验证|未验证|待验证|TODO|⏳", l):
            for j in range(max(0, i - 1), min(len(ls2), i + 3)):
                print("   %-20s %5d| %s" % (rel, j + 1, ls2[j].rstrip()[:100]))
            print("   ---")

print()
print("=== ③ 界面上用户能看到的提示 ===")
fp = os.path.join(BASE, "ui", "VrmArScreen.kt")
ls3 = io.open(fp, encoding="utf-8", errors="replace").read().split("\n")
for i, l in enumerate(ls3, 1):
    if re.search(r"Text\(|ArBtn\(|touchHint|notice|hint =", l):
        print("   %5d| %s" % (i, l.strip()[:104]))
