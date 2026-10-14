# -*- coding: utf-8 -*-
"""读 _look_screen_and_reply 现场 + 加三道闸：
  ① 冷却：路径A 两次之间至少间隔（防自我循环）
  ② 熔断：视觉模型 403/404（账号没权限）→ 暂停一段时间并明确告知主人，不再重试
  ③ 保持原有行为不变（拿到结果照常回答）
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(ROOT, "classes", "murasame_class.py")
ls = io.open(P, encoding="utf-8", errors="replace").read().split("\n")
print("=== _look_screen_and_reply 现场 ===")
start = next((i for i, l in enumerate(ls) if "def _look_screen_and_reply" in l), None)
if start is None:
    print("   ✗ 没找到")
    sys.exit(1)
for i in range(start, min(len(ls), start + 62)):
    print("   %5d| %s" % (i + 1, ls[i].rstrip()[:118]))
print()
print("=== 复位 _screen_look_busy 的地方 ===")
for i, l in enumerate(ls, 1):
    if "_screen_look_busy" in l:
        print("   %5d| %s" % (i, l.strip()[:112]))
