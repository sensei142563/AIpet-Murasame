# -*- coding: utf-8 -*-
"""诊断用户报的 5 个问题（只读，不改）：
  ① 关闭桌宠不掐进程：找退出/杀进程路径
  ② 视觉识别：找 _14 NameError、qwen-vl 404、以及"看屏幕"为何无限刷屏
  ③ 启动器总览页有没有写死的白色字
  ④ Live2D 大小：设置里那个"桌宠大小"是否只作用于 2D；有没有 Live2D 独立缩放
  ⑤ F3~F12 那套调节热键还在不在
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def scan(title, files, pat, limit=16, ctx=0):
    print("=== %s ===" % title)
    n = 0
    for rel in files:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            continue
        ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
        for i, l in enumerate(ls):
            if re.search(pat, l):
                if ctx:
                    for j in range(max(0, i - ctx), min(len(ls), i + ctx + 1)):
                        print("   %-26s %5d| %s" % (rel, j + 1, ls[j].strip()[:104]))
                else:
                    print("   %-26s %5d| %s" % (rel, i + 1, l.strip()[:104]))
                n += 1
                if n >= limit:
                    print("   …（截断）")
                    return
    if n == 0:
        print("   （无命中）")


scan("② _14 这个名字出现在哪", ["tool/chat.py", "main.py", "tool/vision.py", "tool/pc_control.py",
                          "qq/qq_bridge.py"], r"_14\b", 20)
scan("② 视觉/看屏幕 的触发与重试", ["tool/chat.py", "main.py"], r"看屏幕|抓屏|vision|qwen-vl|_vl",
     30)
scan("④ Live2D 大小 / 2D 大小", ["tool/config.py", "main.py", "pcl_launcher/silicon_window.py",
                          "tool/pet_window.py", "config.json"],
     r"pet_scale|live2d_scale|scale|尺寸|大小", 26)
scan("⑤ F3~F12 热键", ["main.py", "tool/chat.py", "tool/pet_window.py"],
     r"F3|F4|F5|F6|F7|F8|F9|F10|F11|F12|Key_|hotkey|热键", 26)
scan("① 关闭/退出 桌宠", ["main.py", "tool/pet_window.py", "tool/chat.py"],
     r"关闭桌宠|退出|quit|sys\.exit|os\._exit|taskkill|terminate|kill", 24)
scan("③ 启动器里写死的白色", ["pcl_launcher/silicon_window.py", "pcl_launcher/silicon_ui.py"],
     r"#fff|#FFF|white|rgba\(255|255, 255, 255", 26)
