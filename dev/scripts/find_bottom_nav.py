# -*- coding: utf-8 -*-
"""找底部导航（5 个 tab：首页/记忆/人设/设置/聊天）的实现位置，为加 insets 内边距做准备。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")

KEYS = ("NavigationBar", "navigationBars", "NavigationBarPadding", "WindowInsets",
        "systemBars", "BottomBar", "首页", "记忆", "人设", "设置", "聊天")
print("=== 含导航关键词的文件（按命中数）===")
hits = []
for base, dirs, files in os.walk(SRC):
    for f in files:
        if not f.endswith(".kt"):
            continue
        p = os.path.join(base, f)
        body = io.open(p, encoding="utf-8", errors="replace").read()
        n = sum(body.count(k) for k in KEYS)
        if n:
            hits.append((n, os.path.relpath(p, SRC), body))
for n, rel, body in sorted(hits, reverse=True)[:8]:
    print("   %-42s %d" % (rel, n))

print()
print("=== 最可能的那个文件里，导航相关行（含前后文）===")
n, rel, body = sorted(hits, reverse=True)[0]
lines = body.split("\n")
for i, l in enumerate(lines, 1):
    if re.search(r"NavigationBar|navigationBars|WindowInsets|systemBars|Scaffold|bottomBar|"
                 r'首页|记忆|人设|设置|聊天|Row\(', l):
        print("%4d| %s" % (i, l.rstrip()[:150]))
print()
print("=== 该文件是否已有 insets 处理 ===")
for k in ("navigationBarsPadding", "systemBarsPadding", "WindowInsets", "windowInsetsPadding",
          "safeDrawing", "imePadding", "statusBarsPadding"):
    print("   %-24s %s" % (k, "有" if k in body else "无"))
