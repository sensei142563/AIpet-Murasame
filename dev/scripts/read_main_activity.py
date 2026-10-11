# -*- coding: utf-8 -*-
"""给 App 加诊断日志：
  ① 全局未捕获异常处理器 → 把完整堆栈写到 files/crash.log（App 现在没有这个）
  ② Activity onDestroy 时记录调用栈（查出到底是谁结束了它）
  ③ tab 切换记录 + ChatScreen 进入/退出记录
先读锚点，再打补丁。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")
MA = os.path.join(SRC, "MainActivity.kt")
CS = os.path.join(SRC, "ui/ChatScreen.kt")

print("=== MainActivity: onCreate / onDestroy / Application 类 / LogBus ===")
lines = io.open(MA, encoding="utf-8", errors="replace").read().split("\n")
for i, l in enumerate(lines, 1):
    if re.search(r"class \w+|override fun onCreate|override fun onDestroy|setContent|super\.onCreate|"
                 r"application|Application\(|BotRepo\.|enableEdgeToEdge|LogBus", l):
        print("%4d| %s" % (i, l.rstrip()[:140]))

print()
print("=== MainActivity 1~100 行（看结构）===")
for i in range(0, min(100, len(lines))):
    print("%4d| %s" % (i + 1, lines[i].rstrip()[:140]))
