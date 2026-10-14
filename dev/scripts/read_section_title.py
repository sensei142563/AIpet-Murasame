# -*- coding: utf-8 -*-
"""修 ③ 首页写死的白字：section_title 的标题色改成跟随主题明暗。
   参考本文件里已有正确写法（_is_dark_theme() 分支）。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(ROOT, "pcl_launcher", "silicon_ui.py")
t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

print("=== section_title 现状 ===")
m = re.search(r"def section_title[\s\S]{0,900}?\n\n\n", t)
if m:
    for l in m.group(0).split("\n"):
        print("   " + l.rstrip()[:116])
else:
    print("   ✗ 没找到 def section_title")
    # 找找别的名字
    for i, l in enumerate(t.split("\n"), 1):
        if re.search(r"def .*title|def .*section", l):
            print("   %5d| %s" % (i, l.strip()[:110]))
