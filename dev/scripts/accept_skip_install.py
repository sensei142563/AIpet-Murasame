# -*- coding: utf-8 -*-
"""装之前先比对：设备上已经是当前这版就**跳过安装** ——
安装动作会触发华为的"统一身份验证"与市场安装页，把前台抢走，导致后面所有 UI 检查都跑不了。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
old = '''    print("=== 1. 安装 ===")
    r = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", APK],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=3600) if not DRY else None'''
new = '''    print("=== 1. 安装 ===")
    # 【先比对，已经是当前这版就跳过安装】
    # 为什么：安装动作会弹出华为的"统一身份验证"对话框和市场安装页，把前台抢走，
    # 导致后面所有 UI 检查都被前台守卫 SKIP（实测两轮都是这个原因）。
    # 这些系统弹窗不该由自动化去点（安全弹窗）。所以：不需要装就不装。
    _cur = adb("shell", "dumpsys", "package", PKG)
    _m0 = re.search(r"lastUpdateTime=([^\\n]+)", _cur or "")
    already = False
    if _m0 and not DRY:
        try:
            already = time.mktime(time.strptime(_m0.group(1).strip(), "%Y-%m-%d %H:%M:%S")) \\
                >= os.path.getmtime(APK) - 120
        except Exception:
            already = False
    if already and not DRY:
        print("   设备上已经是当前这版（lastUpdateTime=%s）⇒ **跳过安装**，避免系统弹窗抢前台"
              % _m0.group(1).strip())
        r = None
    else:
        r = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", APK],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=3600) if not DRY else None'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 安装步骤已加「已是最新则跳过」")
else:
    print("✗ 安装锚点未命中")

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:300])
