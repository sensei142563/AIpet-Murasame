# -*- coding: utf-8 -*-
"""深挖三个 bug（只读）：
  ① 全仓库找 `_14`（NameError 的来源）
  ② "看屏幕"为什么无限触发 —— 找触发条件与调用点
  ③ 「关闭桌宠」的完整链路：启动器按钮 → API → main.py 退出
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

print("=== ① 全仓库找 _14 ===")
n = 0
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp for s in (".git", "runtime", "GPT-SoVITS", "F5-TTS_Models", "\\models",
                             "dev\\tmp", ".venv", "__pycache__", "NapCat", "node_modules",
                             "_internal", "\\build", "\\dist")):
        continue
    for f in fn:
        if not f.endswith((".py", ".json", ".txt", ".md")):
            continue
        p = os.path.join(dp, f)
        try:
            t = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if re.search(r"_14\b", t):
            rel = os.path.relpath(p, ROOT)
            for j, l in enumerate(t.split("\n"), 1):
                if re.search(r"_14\b", l):
                    print("   %-40s %5d| %s" % (rel[:40], j, l.strip()[:100]))
                    n += 1
                    if n > 24:
                        break
        if n > 24:
            break
    if n > 24:
        break
if n == 0:
    print("   ✗ 代码/配置里**没有** _14 这个字面量")
    print("   ⇒ 说明它是**运行时拼出来的**：常见于")
    print("      · QTimer.singleShot(延迟, lambda: ...) 里被写成了变量名")
    print("      · exec/eval 的模板串里留了占位符")
    print("      · 变量名被动态生成（如 f'_1{n}'）")

print()
print("=== ② 排队判断失败 这句日志的来源 ===")
for rel in ("tool/chat.py", "main.py"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls, 1):
        if "排队判断失败" in l:
            for j in range(max(0, i - 30), min(len(ls), i + 6)):
                print("   %-18s %5d| %s" % (rel, j + 1, ls[j].rstrip()[:108]))
            print("   ---")

print()
print("=== ③ 看屏幕 的触发点 ===")
for rel in ("tool/chat.py", "main.py", "tool/pc_control.py"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls, 1):
        if re.search(r"看屏幕|抓屏|screen_look|look_screen|让我看", l):
            print("   %-18s %5d| %s" % (rel, i, l.strip()[:106]))

print()
print("=== ④ 关闭桌宠 链路（启动器侧 → 桌宠侧）===")
for rel in ("main.py", "pcl_launcher/silicon_window.py"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls, 1):
        if re.search(r"关闭桌宠|toggle_pet|stop_pet|/shutdown|shutdown|kill_pet|关闭请求",
                     l):
            print("   %-34s %5d| %s" % (rel, i, l.strip()[:100]))
