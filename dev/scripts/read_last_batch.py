# -*- coding: utf-8 -*-
"""最后一批只读诊断：
  ① api.py 的 URL 路由 / base_url（判断 qwen-vl-plus 该发去哪）
  ② api.py 的 check_shutdown 实现
  ③ 启动器 _send_control 实现（发到哪个端口/路径）
  ④ main.py 的退出看门狗段（275~320）
  ⑤ 主题里的文字颜色（首页白字嫌疑）
  ⑥ 一个"看屏幕"每轮最多几次"的现成保护是否存在
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def show(rel, start, end, tag=""):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        print("   （缺 %s）" % rel)
        return
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    print("   ── %s %s 第 %d~%d 行 ──" % (rel, tag, start, end))
    for i in range(start - 1, min(len(ls), end)):
        print("   %5d| %s" % (i + 1, ls[i].rstrip()[:114]))


print("=== ① api.py URL 路由 / base_url ===")
p = os.path.join(ROOT, "api.py")
ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
for i, l in enumerate(ls, 1):
    if re.search(r"base_url|BASE_URL|dashscope|api\.deepseek|compatible-mode|https://|"
                 r"def .*url|prefix", l):
        print("   %5d| %s" % (i, l.strip()[:110]))

print()
print("=== ② check_shutdown ===")
for i, l in enumerate(ls, 1):
    if "def check_shutdown" in l or "def set_shutdown" in l or "_shutdown" in l:
        print("   %5d| %s" % (i, l.rstrip()[:110]))

print()
print("=== ③ 启动器 _send_control ===")
p2 = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")
ls2 = io.open(p2, encoding="utf-8", errors="replace").read().split("\n")
m = next((i for i, l in enumerate(ls2) if "def _send_control" in l), None)
if m is not None:
    for j in range(m, min(len(ls2), m + 26)):
        print("   %5d| %s" % (j + 1, ls2[j].rstrip()[:112]))
else:
    print("   （没找到 def _send_control）")
for i, l in enumerate(ls2, 1):
    if "_send_control" in l and "def " not in l:
        print("   %5d| %s" % (i, l.strip()[:110]))

print()
print("=== ④ main.py 退出看门狗 ===")
show("main.py", 272, 320)

print()
print("=== ⑤ 主题文字颜色（首页白字嫌疑）===")
for rel in ("pcl_launcher/themes/senrenbanka_copy/theme.json",
            "pcl_launcher/themes/senrenbanka/theme.json"):
    p3 = os.path.join(ROOT, rel)
    if os.path.isfile(p3):
        t = io.open(p3, encoding="utf-8", errors="replace").read()
        print("   ── %s" % rel)
        for l in t.split("\n"):
            if re.search(r"color|text|fg|font|name|background", l, re.I):
                print("      " + l.strip()[:104])

print()
print("=== ⑥ 「看屏幕」每轮上限的现成保护 ===")
for rel in ("classes/murasame_class.py", "tool/chat.py", "tool/pc_control.py", "main.py"):
    p4 = os.path.join(ROOT, rel)
    if not os.path.isfile(p4):
        continue
    ls4 = io.open(p4, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls4, 1):
        if re.search(r"看屏幕.*(最多|一次|上限|limit|count)|_look_count|max_look|screenshot_count",
                     l):
            print("   %-26s %5d| %s" % (rel, i, l.strip()[:100]))
