# -*- coding: utf-8 -*-
"""状态窗融合（第 1 步：样式机制）——
  ① _Card 基类 QFrame → QGroupBox（测试按 QGroupBox 找卡片；QGroupBox 也是 QWidget，行为等价）
     并开 WA_StyledBackground（QSS 里写了 background，Qt 必须靠这个属性才会真画）
  ② StatusWindow 开 WA_StyledBackground + objectName + QSS 里补 QDialog#statusWindow 的不透明纸色底
"""
import io
import os
import py_compile
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
P = os.path.join(ROOT, "classes", "status_window.py")

t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ① 导入 QGroupBox
if "QGroupBox" not in t:
    t = t.replace("from PyQt5.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,\n"
                  "                             QSizeGrip, QStackedWidget, QVBoxLayout, QWidget)",
                  "from PyQt5.QtWidgets import (QDialog, QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton,\n"
                  "                             QScrollArea, QSizeGrip, QStackedWidget, QVBoxLayout, QWidget)",
                  1)
    print("✓ ① 已导入 QGroupBox")

# ② _Card 基类改 QGroupBox + 开 WA_StyledBackground
t = t.replace("class _Card(QFrame):", "class _Card(QGroupBox):", 1)
t = t.replace('''        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)''',
              '''        super().__init__(parent)
        self.setObjectName("card")
        # ⚠ QSS 里给 #card 写了 background，但 Qt 对**自定义子类**默认不画样式表背景，
        #   必须显式开 WA_StyledBackground —— 否则要等一次样式 polish（表现就是
        #   "字压在壁纸上看不清，点刷新后那块底色才出现"，用户报过）。
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self)''', 1)
print("✓ ② _Card → QGroupBox + WA_StyledBackground")

# QSS 选择器：QFrame#card → #card（QGroupBox 也要命中）
t = t.replace("QFrame#card {", "#card {", 1)

# ③ 状态窗自身：开属性 + objectName + QSS 补 QDialog#statusWindow
t = t.replace('''        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet(QSS)''',
              '''        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("statusWindow")
        # ⚠ 开 WA_StyledBackground：让 QSS 里 QDialog#statusWindow 的**不透明纸色底**在
        #   首次显示就画出来（自绘 paintEvent 仍在其上画渐变与圆角，两者不冲突）。
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(QSS)''', 1)

if "QDialog#statusWindow" not in t:
    t = t.replace('QSS = """\n', 'QSS = """\n'
                  '/* 窗自身的**不透明纸色底**：首次显示就要有底，不能等样式 polish */\n'
                  'QDialog#statusWindow {\n'
                  '    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,\n'
                  '                                stop:0 #f4ece5, stop:1 #e7dbd0);\n'
                  '}\n', 1)
    print("✓ ③ QSS 已补 QDialog#statusWindow 的不透明纸色底")

io.open(P, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 验证 ===")
try:
    py_compile.compile(P, doraise=True)
    print("   ✓ py_compile")
except py_compile.PyCompileError as e:
    print("   ✗", str(e)[:300])
    sys.exit(1)

r = subprocess.run([VENV, os.path.join("tests", "test_bugfix_0930.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "[OK]" in l or "[FAIL]" in l or "FAILED" in l:
        print("   " + l.strip()[:150])
