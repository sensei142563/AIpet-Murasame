# -*- coding: utf-8 -*-
"""读准安装检查与 ⑧2 的代码并精确修补：
  ② 安装检查改为 lastUpdateTime >= 本地 APK 时间；装完后自动关华为市场弹窗
  ③ ⑧2 之后若前台不是本应用则 SKIP（不是 FAIL）
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")

print("=== 安装那一段的真实代码 ===")
i = t.find('安装')
# 找 record("安装" 的位置
j = t.find('record("安装"')
lo = t.rfind("\n", 0, t.rfind("\n", 0, t.rfind("\n", 0, j)))
print(t[max(0, j - 900):j + 300])
print()
print("=== ⑧2 那一段的真实代码 ===")
k = t.find('⑧2 资产种子')
print(t[max(0, k - 900):k + 700])
