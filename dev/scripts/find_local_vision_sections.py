# -*- coding: utf-8 -*-
"""按标题（不是行号）定位 README 里与"本地模型/本地视觉"相关的章节，并打印其内容，
   逐段判断口径是否与"本地视觉不使用、仅保留接口"一致。"""
import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
R = r"E:\university\order\python\pet\AIpet-Murasame-main\README.md"
lines = io.open(R, encoding="utf-8", errors="replace").read().split("\n")

print("=== 所有标题里含「本地」「模型」「视觉」的章节 ===")
heads = [(i, l) for i, l in enumerate(lines, 1) if re.match(r"^#{2,4}\s", l)]
for i, l in heads:
    if any(k in l for k in ("本地", "模型", "视觉", "语音")):
        print("   %5d| %s" % (i, l.strip()[:110]))

print()
print("=== 逐段检查：哪些地方还把'本地'写成默认/必装 ===")
pat = re.compile(r"本地(视觉|模型)|vision_source|vision_local")
for i, l in enumerate(lines, 1):
    if pat.search(l):
        flag = ""
        if re.search(r"默认|必装|需要安装|勾.{0,4}同时配置", l):
            flag = "  ← 可能是过时口径"
        print("   %5d| %s%s" % (i, l.strip()[:104], flag))
