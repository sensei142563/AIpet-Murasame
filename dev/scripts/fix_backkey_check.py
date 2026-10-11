# -*- coding: utf-8 -*-
"""修 ④ 检查项：不假设起始在首页，改为"连按最多 3 次返回，必须退出"（用固定坐标点首页先）。
然后重跑完整验收。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

a = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
pat = re.compile(
    r"(?P<ind>[ \t]*)# ④ 返回键：\*\*新语义\*\*[\s\S]{0,1400}?record\(\"④ 返回键（首页连按两次退出）\"[^\n]*\n"
    r"(?:[^\n]*\n){0,2}")
m = pat.search(a)
if m:
    ind = m.group("ind")
    new = (ind + "# ④ 返回键（新语义，2026-10-11 改动后）\n"
           + ind + "#   现在的规则：只要发生\"页面切换\"，退出计时就清零（防底部误触累积成退出）。\n"
           + ind + "#   ⇒ 从子页面按一次只是回首页；在首页连按两次（2 秒内）才退出。\n"
           + ind + "#   检查方式不能假设\"当前在首页\"（之前用文字找「首页」没点中，导致误报）：\n"
           + ind + "#   先用**底部导航固定坐标**点首页，再最多按 3 次返回，必须退出。\n"
           + ind + "ensure_foreground(\"④ 返回键\")\n"
           + ind + "adb(\"shell\", \"input\", \"tap\", \"111\", \"2641\")   # 底部导航：首页\n"
           + ind + "time.sleep(2.5)\n"
           + ind + "alive = [foreground_is_app()]\n"
           + ind + "for _ in range(3):\n"
           + ind + "    adb(\"shell\", \"input\", \"keyevent\", \"KEYCODE_BACK\")\n"
           + ind + "    time.sleep(1.4)\n"
           + ind + "    alive.append(foreground_is_app())\n"
           + ind + "    if not alive[-1]:\n"
           + ind + "        break\n"
           + ind + "record(\"④ 返回键（最多按 3 次必须退出）\", verdict(alive[0] and not alive[-1]),\n"
           + ind + "       \"起始在App=%s；逐次按返回后是否仍在App=%s（期望最终 False）\"\n"
           + ind + "       % (alive[0], alive[1:]))\n")
    a = a[:m.start()] + new + a[m.end():]
    io.open(A, "w", encoding="utf-8", newline="\n").write(a)
    print("✓ ④ 检查项已改为「最多按 3 次必须退出」+ 固定坐标点首页")
else:
    print("✗ ④ 锚点未命中")

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:300])
print()
print("=== 启动完整验收（后台）===")
