# -*- coding: utf-8 -*-
"""查 ChatCore 185-215 的条件结构 + 两个角色的表情包资源是否为空。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CC = r"E:\university\order\python\pet\chatter\app\src\main\java\com\aipet\murasame\bot\chat\ChatCore.kt"
ASSETS = r"E:\university\order\python\pet\chatter\app\src\main\assets"

print("=== ChatCore.kt 178~215 ===")
for i, l in enumerate(io.open(CC, encoding="utf-8", errors="replace").read().splitlines(), 1):
    if 178 <= i <= 215:
        print("   %5d| %s" % (i, l.rstrip()[:120]))

print()
print("=== assets 下的角色与表情包目录 ===")
if os.path.isdir(ASSETS):
    for d in sorted(os.listdir(ASSETS)):
        p = os.path.join(ASSETS, d)
        if not os.path.isdir(p):
            continue
        subs = sorted(os.listdir(p))
        print("   %s/ → %s" % (d, subs[:12]))
        for s in subs:
            q = os.path.join(p, s)
            if os.path.isdir(q) and re.search(r"(sticker|biaoqing|表情)", s, re.I):
                files = sorted(os.listdir(q))
                print("      %s: %d 个文件  %s" % (s, len(files), files[:8]))
else:
    print("   ✗ 没有 assets 目录")

print()
print("=== Store.listStickers / CharacterRepo.stickerNames 的实现 ===")
for f in (r"E:\university\order\python\pet\chatter\app\src\main\java\com\aipet\murasame\bot\chat\CharacterRepo.kt",
          r"E:\university\order\python\pet\chatter\app\src\main\java\com\aipet\murasame\bot\Store.kt"):
    if not os.path.isfile(f):
        continue
    L = io.open(f, encoding="utf-8", errors="replace").read().splitlines()
    print("--- %s ---" % os.path.basename(f))
    for i, l in enumerate(L, 1):
        if re.search(r"(fun stickerNames|fun listStickers|sticker)", l):
            print("   %5d| %s" % (i, l.strip()[:118]))
