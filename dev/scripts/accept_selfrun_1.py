# -*- coding: utf-8 -*-
"""让验收能自己跑完：
  ① 装完后自动关掉华为市场的"安装完成/增强防护"弹窗（只在前台确实是市场时才点，绝不碰别的应用）
  ② 安装检查改用 lastUpdateTime >= 本地 APK 时间（比看命令输出可靠）
  ③ ⑧2 在 ensure_foreground 之后**再确认一次**前台，不是我们的就 SKIP 而不是 FAIL
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

# ---------- ① 加 dismiss_market_dialog 助手 ----------
if "dismiss_market_dialog" not in t:
    helper = '''

def dismiss_market_dialog():
    """关掉华为应用市场在安装后弹出的"安装完成/建议开启增强防护"页。

    为什么要它：这个弹窗会**一直压在最上面**，导致后面所有 UI 检查都 dump 到市场界面
    （要么误判 FAIL，要么被前台守卫全部 SKIP）。只在**确认前台就是市场**时才点它的按钮，
    其他情况一律不动手 —— 绝不碰用户正在用的应用。
    """
    if DRY:
        return False
    fg = resumed_activity().lower()
    if "appmarket" not in fg and "appgallery" not in fg:
        return False
    x = dump("mk_auto")
    for label in ("完成", "开启", "取消", "关闭"):
        for pat in (r'text="%s"[^>]*bounds="\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]"' % label,
                    r'<node[^>]*bounds="\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]"[^>]*text="%s"' % label):
            m = re.search(pat, x)
            if m:
                adb("shell", "input", "tap", str((int(m.group(1)) + int(m.group(3))) // 2),
                    str((int(m.group(2)) + int(m.group(4))) // 2))
                time.sleep(3)
                print("   （已自动关闭华为市场弹窗：点了「%s」）" % label)
                return True
    adb("shell", "am", "force-stop", "com.huawei.appmarket")
    time.sleep(2)
    print("   （已自动关闭华为市场弹窗：force-stop）")
    return True
'''
    t = t.replace("\ndef open_app(", helper + "\n\ndef open_app(", 1)
    print("✓ ① 已加 dismiss_market_dialog()")

# ---------- ② 安装检查改用 lastUpdateTime ----------
old_ins = re.search(r'\n[ \t]*# 1\. 安装[\s\S]{0,900}?\n(?=[ \t]*# 2\.)', t)
if old_ins:
    print("   现有安装检查代码：")
    for l in old_ins.group(0).split("\n")[:22]:
        print("      " + l.rstrip()[:140])

io.open(A, "w", encoding="utf-8", newline="\n").write(t)

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print()
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:300])
