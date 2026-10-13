# -*- coding: utf-8 -*-
"""修操作单 S5 那行的"四个分类页签" —— 实为**五个**（现在/习惯/心里/提醒/记忆）。
   这是 deck 里刚修过的同一处错，操作单里还留着；用户照着录会找不到。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
F = os.path.join(ROOT, "dev", "docs", "PPT录屏截图操作单-2026-10-13.md")

t = io.open(F, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = "四个分类页签（状态 / 习惯 / 记忆 / 提醒）里最丰富的那一页"
NEW = "五个页签（现在 / 习惯 / 心里 / 提醒 / 记忆）里最丰富的那一页"
if OLD in t:
    t = t.replace(OLD, NEW, 1)
    io.open(F, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已修 S5 那行：四个 → 五个页签（并写出真实标题）")
else:
    print("· 未命中，当前含该关键词的行：")
    for i, l in enumerate(t.split("\n"), 1):
        if "分类页签" in l or "页签" in l:
            print("   %4d| %s" % (i, l.strip()[:130]))

# 顺带核对：全文件是否还有"四个"这种旧说法
print()
print("=== 复查（找 四个 / 状态 / 习惯 / 记忆 / 提醒 的组合）===")
for i, l in enumerate(io.open(F, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if "四个" in l and ("页签" in l or "分类" in l):
        print("   ⚠ %4d| %s" % (i, l.strip()[:120]))
    elif "五个页签" in l:
        print("   ✓ %4d| %s" % (i, l.strip()[:120]))

MSG = """docs(ppt): 录屏操作单 S5 那行「四个分类页签」改为「五个页签」（与 deck 同步）

deck 第 14 页刚审出并修掉的同一处错，**操作单里还留着**：
    S5 原写「四个分类页签（状态 / 习惯 / 记忆 / 提醒）」
    实为**五个**：现在 / 习惯 / 心里 / 提醒 / 记忆（tool/status_snapshot.py:141/163/223/243/264）

为什么必须改：用户是**照着操作单去录**的 —— 他打开状态页会数到 5 个、且第一个叫"现在"，
照着单子找不到"状态"那一栏，就会以 为功能不对（其实是文档没同步）。
⇒ 已改为「五个页签（现在 / 习惯 / 心里 / 提醒 / 记忆）」。
"""
p = os.path.join(MAP, "_msg_sheet5.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
