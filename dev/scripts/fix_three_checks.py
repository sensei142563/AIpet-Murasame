# -*- coding: utf-8 -*-
"""修三个检查项（都是脚本层面的）：
  ④ 允许最多 5 次返回（子页面处理器可能还开着，需要先逐层关掉）
  ⑤b 触发前清空 live2d.log（否则读到的是累积旧日志）
  ⑥ 与 ⑧3 对齐：离线识别停用时判 SKIP（前提不成立）"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

a = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")

# ---------- ④ 最多 5 次 ----------
if "for _ in range(3):" in a and "最多按 3 次" in a:
    a = a.replace('record("④ 返回键（最多按 3 次必须退出）"', 'record("④ 返回键（最多按 5 次必须退出）"', 1)
    a = a.replace("for _ in range(3):", "for _ in range(5):", 1)
    a = a.replace("#   先用**底部导航固定坐标**点首页，再最多按 3 次返回，必须退出。",
                  "#   先用**底部导航固定坐标**点首页，再最多按 5 次返回，必须退出。\n"
                  "#   （用 5 次是因为前面几节可能还开着子页面的 BackHandler：AR/VRM 层要先被逐层关掉。）", 1)
    print("✓ ④ 改为最多 5 次返回")
else:
    print("⚠ ④ 锚点未命中")

# ---------- ⑤b 触发前清空日志 ----------
old5 = '''                  sel = tap_text_any(dump("b5"), ["离线音色"])'''
new5 = '''                  # 先清空 live2d.log：否则读到的是之前累积的旧 [tts] 行（上一轮就是这么误判的）
                  if not DRY:
                      adb("shell", "rm", "-f", EXT + "/live2d.log")
                  sel = tap_text_any(dump("b5"), ["离线音色"])'''
if old5 in a:
    a = a.replace(old5, new5, 1)
    print("✓ ⑤b 触发前清空 live2d.log")
else:
    print("⚠ ⑤b 锚点未命中")

# ---------- ⑥ 与 ⑧3 对齐 ----------
i6 = a.find('⑥ Silero VAD')
print()
print("=== ⑥ 的现有代码片段 ===")
print("\n".join("   " + l.rstrip()[:150] for l in a[max(0, i6 - 700):i6 + 400].split("\n")[-20:]))

io.open(A, "w", encoding="utf-8", newline="\n").write(a)
r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print()
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:300])
