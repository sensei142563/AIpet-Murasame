# -*- coding: utf-8 -*-
"""修 remove_video.py 的提示文字替换（改用正则），然后执行。"""
import io
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts\remove_video.py"
s = io.open(P, encoding="utf-8", newline="").read()
old = '''s = s.replace('Text("点按拍照 · 长按录像 · 点按画面可对焦"',
              'Text("点按拍照 · 点按画面可对焦"', 1)
note("提示文字去掉长按录像", "长按录像" not in s)'''
new = '''# 提示文字：把任何含"长按录像"的 Text 文案整句换掉（正则，容忍空格/中点差异）
s2 = re.sub(r'"点按拍照[^"]*长按录像[^"]*"', '"点按拍照 · 点按画面可对焦"', s)
if s2 == s:
    # 退路：直接删掉"长按录像"这几个字所在的那一小段
    s2 = re.sub(r'\\s*·\\s*长按录像', '', s)
print("   提示文字是否仍含长按录像:", "长按录像" in s2)
s = s2
note("提示文字去掉长按录像", "长按录像" not in s)'''
assert old in s, "✗ 找不到该段"
s = s.replace(old, new, 1)
io.open(P, "w", encoding="utf-8", newline="").write(s)
print("✓ 已改为正则替换，开始执行\n")

r = subprocess.run([sys.executable, "-u", P], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
i = out.find("=== 编译 ===")
print(out[i:i + 3500] if i >= 0 else out[-3500:])
print("rc =", r.returncode)
