# -*- coding: utf-8 -*-
"""查清 api.py 与 api_v2.py 启动时各打印什么、参数/接口有什么不同，
   以及当前版为什么从 api_v2.py 改用 api.py。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
GSV = os.path.join(ROOT, "GPT-SoVITS")
OLD_RUN = os.path.join(r"E:\university\order\python\pet\AIpet-Murasame-main_V1.17.2",
                       "AIpet-Murasame-main", "run.py")

for name in ("api.py", "api_v2.py"):
    p = os.path.join(GSV, name)
    print("=== %s ===" % name)
    if not os.path.isfile(p):
        print("   ✗ 不存在")
        continue
    src = io.open(p, encoding="utf-8", errors="replace").read()
    ls = src.split("\n")
    print("   行数 %d" % len(ls))
    # 打印语句（含中文提示）
    n = 0
    for i, l in enumerate(ls, 1):
        if re.search(r"print\(|logging\.|logger\.", l) and re.search(r"[\u4e00-\u9fff]", l):
            s = l.strip()
            print("   %5d| %s" % (i, s[:104]))
            n += 1
            if n >= 12:
                print("   …")
                break
    # 关键 API 定义
    print("   --- 接口/模型相关 ---")
    for i, l in enumerate(ls, 1):
        if re.search(r"@APP\.(get|post)|def tts|def change_|set_gpt_weights|set_sovits_weights|GPT_SoVITS|argparse", l):
            s = l.strip()
            if len(s) > 3:
                print("   %5d| %s" % (i, s[:104]))
    print()

print("=== 当前版为什么用 api.py（run.py 注释与分支）===")
ls = io.open(os.path.join(ROOT, "run.py"), encoding="utf-8",
             errors="replace").read().split("\n")
for i, l in enumerate(ls, 1):
    if 900 <= i <= 945:
        print("   %5d| %s" % (i, l.rstrip()[:112]))

print()
print("=== 旧版 run.py 的启动那一块 ===")
if os.path.isfile(OLD_RUN):
    ls = io.open(OLD_RUN, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls, 1):
        if 725 <= i <= 760:
            print("   %5d| %s" % (i, l.rstrip()[:112]))
else:
    print("   ✗ 找不到旧版 run.py")
