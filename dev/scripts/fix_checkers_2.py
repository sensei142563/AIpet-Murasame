# -*- coding: utf-8 -*-
"""用容忍缩进的写法修 ④；并修 ⑤b（带日志尾部，只"准备构造"则 SKIP）与 ⑥（设置页可滚动，先滑动再找）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(A, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ---------- ④ 用正则（容忍缩进） ----------
pat4 = re.compile(
    r"(?P<ind>[ \t]*)# ④ 返回键[\s\S]{0,900}?record\(\"④ 返回键两次退出\", verdict\(\(fg1 and not fg2\)\),\n"
    r"[ \t]*\"第一次前台=%s 第二次前台=%s（期望 True → False）\" % \(fg1, fg2\)\)\n")
m4 = pat4.search(t)
if m4:
    ind = m4.group("ind")
    new4 = (ind + "# ④ 返回键：**新语义**（2026-10-11 改动后）\n"
            + ind + "#   现在只要发生\"页面切换\"，退出计时就清零（防底部误触累积成退出）。\n"
            + ind + "#   正确行为：首页连按两次（2 秒内）才退出；从子页面按一次只是回首页。\n"
            + ind + "ensure_foreground(\"④ 返回键\")\n"
            + ind + "tap_text_any(dump(\"b_back0\"), [\"首页\"])\n"
            + ind + "time.sleep(1.5)\n"
            + ind + "fg_a = foreground_is_app()\n"
            + ind + "adb(\"shell\", \"input\", \"keyevent\", \"KEYCODE_BACK\")\n"
            + ind + "time.sleep(1.6)\n"
            + ind + "fg_b = foreground_is_app()\n"
            + ind + "adb(\"shell\", \"input\", \"keyevent\", \"KEYCODE_BACK\")\n"
            + ind + "time.sleep(3.0)\n"
            + ind + "fg_c = foreground_is_app()\n"
            + ind + "record(\"④ 返回键（首页连按两次退出）\", verdict(fg_a and fg_b and not fg_c),\n"
            + ind + "       \"首页=%s 按1次后=%s 按2次后=%s（期望 True → True → False）\"\n"
            + ind + "       % (fg_a, fg_b, fg_c))\n")
    t = t[:m4.start()] + new4 + t[m4.end():]
    print("✓ ④ 已按新语义重写（容忍缩进）")
else:
    print("✗ ④ 正则仍未命中")

# ---------- ⑥ 设置页可滚动：找「识别自检」前先滑动 ----------
pat6 = re.compile(r'(?P<ind>[ \t]*)if tap_text_any\(dump\("b\d+"\), \["识别自检"\]\):')
m6 = pat6.search(t)
if m6:
    ind = m6.group("ind")
    add = (ind + "# 设置页是可滚动的（我们新加的「离线识别（实验）」把下面几行推下去了）\n"
           + ind + "# ⇒ 找不到就先往下滑几次再找，别因为「看不见」就判 SKIP。\n"
           + ind + "for _ in range(4):\n"
           + ind + "    if \"识别自检\" in dump(\"b_scroll\"):\n"
           + ind + "        break\n"
           + ind + "    adb(\"shell\", \"input\", \"swipe\", \"612\", \"1900\", \"612\", \"1000\", \"250\")\n"
           + ind + "    time.sleep(1.2)\n")
    t = t[:m6.start()] + add + t[m6.start():]
    print("✓ ⑥ 已在找「识别自检」前加滚动")
else:
    print("⚠ ⑥ 锚点未命中（可能是别的写法）")
    i = t.find("识别自检")
    print(t[max(0, i - 600):i + 200])

io.open(A, "w", encoding="utf-8", newline="\n").write(t)

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print()
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:400])
if r.returncode != 0:
    sys.exit(1)
print()
print("=== dry-run 复核 ===")
r2 = subprocess.run([sys.executable, "-u", A, "--dry-run"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=900,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
j = out.find("=== 汇总")
print(out[j:] if j > 0 else out[-700:])
