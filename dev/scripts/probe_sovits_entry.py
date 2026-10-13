# -*- coding: utf-8 -*-
"""查清楚：桌宠/启动器到底拉起了 GPT-SoVITS 的哪个脚本、带什么参数；
   GPT-SoVITS 目录里还有哪些入口（api.py / api_v2.py / webui / go-webui.bat …）。
   目的是回答"为什么这个终端和你以前看到的不一样"。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
GS = os.path.join(ROOT, "GPT-SoVITS")

print("=== ① GPT-SoVITS 目录里的入口脚本（.py/.bat）===")
if os.path.isdir(GS):
    for f in sorted(os.listdir(GS)):
        p = os.path.join(GS, f)
        if os.path.isfile(p) and f.lower().endswith((".py", ".bat", ".sh", ".ps1")):
            print("   %-34s %8d B  改于 %s" % (f, os.path.getsize(p),
                  __import__("datetime").datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d %H:%M")))
else:
    print("   ✗ 没找到目录", GS)

print()
print("=== ② run.py 里启动 TTS 的代码（api.py? api_v2.py? 什么参数?）===")
rp = os.path.join(ROOT, "run.py")
lines = io.open(rp, encoding="utf-8", errors="replace").read().split("\n")
for i, l in enumerate(lines, 1):
    if re.search(r"api\.py|api_v2|GPT-SoVITS|sovits|SoVITS|9880|-s\b|-g\b", l):
        print("   %5d| %s" % (i, l.rstrip()[:118]))

print()
print("=== ③ 启动器里是否也有一套（可能两处不同）===")
sw = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")
for i, l in enumerate(io.open(sw, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if re.search(r"api\.py|api_v2|sovits|9880", l, re.I):
        print("   %5d| %s" % (i, l.strip()[:118]))
