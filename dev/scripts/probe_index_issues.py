# -*- coding: utf-8 -*-
"""查证：dev/scripts 到底有多少 .py；以及 docstring 提取为什么会取到内部那个。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
SD = os.path.join(MAIN, "dev", "scripts")

files = [f for f in os.listdir(SD) if f.endswith(".py")]
print("dev/scripts 下 .py 文件数：%d" % len(files))
print("目录项总数：%d" % len(os.listdir(SD)))
sub = [d for d in os.listdir(SD) if os.path.isdir(os.path.join(SD, d))]
print("子目录：%s" % (sub[:10] or "无"))
print()
print("=== 按前缀统计（前 20）===")
from collections import Counter
c = Counter(re.sub(r"\d+", "#", f).split("_")[0] for f in files)
for k, v in c.most_common(20):
    print("   %-18s %d" % (k, v))
print()
print("=== 样例：文件名的分布（随机 15 个）===")
for f in sorted(files)[:15]:
    print("   " + f)

print()
print("=== docstring 提取验证（前 3 个实际内容 vs 我的正则结果）===")
for name in ("accept_all.py", "verify_all.py", "make_script_index.py"):
    p = os.path.join(SD, name)
    src = io.open(p, encoding="utf-8", errors="replace").read()
    print("--- %s ---" % name)
    print("   实际前 6 行：")
    for l in src.split("\n")[:6]:
        print("      " + l[:110])
    m = re.search(r'^\s*(?:#.*\n\s*)*"""(.*?)"""', src, re.S)
    print("   我的正则取到：%s" % (repr(m.group(1).strip()[:80]) if m else "(无)"))
    m2 = re.search(r'\A(?:#[^\n]*\n)*[ \t]*"""(.*?)"""', src, re.S)
    print("   收紧后取到：  %s" % (repr(m2.group(1).strip()[:80]) if m2 else "(无)"))
