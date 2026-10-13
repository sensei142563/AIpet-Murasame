# -*- coding: utf-8 -*-
"""修最后三项里的两项：
  ② pause_all_ai 默认 stop_voice=False；focusInEvent 用无参调用；
     "用户主动输入"的调用点显式传 stop_voice=True
  ③ 2D 字体判据改判：我们的代码**有意**改用 _resolve_pet_font()
     （旧写法 self._font_family 正是"换界面字体不生效"那个 bug），测试不该再要求旧写法。
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

# ---------- ② pause_all_ai ----------
M = os.path.join(ROOT, "classes", "murasame_class.py")
m = io.open(M, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

print("=== pause_all_ai 的全部调用点 ===")
for i, l in enumerate(m.split("\n"), 1):
    if "pause_all_ai(" in l and "def pause_all_ai" not in l:
        print("   %5d| %s" % (i, l.strip()[:118]))

if "def pause_all_ai(self, stop_voice: bool = True)" in m:
    m = m.replace("def pause_all_ai(self, stop_voice: bool = True)",
                  "def pause_all_ai(self, stop_voice: bool = False)", 1)
    print("✓ 默认值改为 stop_voice: bool = False")
if "self.pause_all_ai(stop_voice=False)" in m:
    m = m.replace("self.pause_all_ai(stop_voice=False)", "self.pause_all_ai()", 1)
    print("✓ focusInEvent 改为无参 self.pause_all_ai()")

# 用户主动输入的调用点必须显式传 True（默认值变了，不传就漏掉"停语音"）
# 先看有哪些无参调用，逐个判断（打印出来人工确认，只有明确属于"用户输入"的才加 True）
print()
print("=== 改后：所有 pause_all_ai( 调用点（供核对）===")
for i, l in enumerate(m.split("\n"), 1):
    if "pause_all_ai(" in l and "def pause_all_ai" not in l:
        print("   %5d| %s" % (i, l.strip()[:118]))
io.open(M, "w", encoding="utf-8", newline="\n").write(m)

# ---------- ③ 测试判据改判 ----------
T = os.path.join(ROOT, "tests", "test_bugfix_0930b.py")
t = io.open(T, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = '''check("2D 字体按 v1.16.1 构造（QFont(字体名, 点数)）",
      "self.text_font = QFont(self._font_family, max(8, int(scaled_font_size)))" in _mc5)'''
NEW = '''# 2026-10-13 改判：本项目**有意**不再用 self._font_family（它的初值就是写死的
# "思源黑体Bold.otf"），改成 self._resolve_pet_font() —— 旧写法正是
# 「主题页换了界面字体，桌宠对话框的字还是老样子（用户反馈"没变成"）」那个 bug 的根因。
# 所以这里断言**修好后的写法**；想要"真加载字体 + 像素字号"的老做法可开 text_font_native。
check("2D 字体走 _resolve_pet_font()（不再用写死的 _font_family）",
      "self.text_font = QFont(self._resolve_pet_font(), max(8, int(scaled_font_size)))" in _mc5)'''
if OLD in t:
    t = t.replace(OLD, NEW, 1)
    io.open(T, "w", encoding="utf-8", newline="\n").write(t)
    print()
    print("✓ ③ 2D 字体判据已改判")
else:
    print("· ③ 判据锚点未命中（可能已改）")

print()
print("=== 验证 ===")
for f in ("classes/murasame_class.py", "tests/test_bugfix_0930b.py"):
    try:
        py_compile.compile(os.path.join(ROOT, f), doraise=True)
        print("   ✓ py_compile %s" % f)
    except py_compile.PyCompileError as e:
        print("   ✗ %s: %s" % (f, str(e)[:250]))
        sys.exit(1)
r = subprocess.run([VENV, os.path.join("tests", "test_bugfix_0930b.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "[FAIL]" in l or "FAILED" in l or "通过" in l:
        print("   " + l.strip()[:150])
print("   退出码 =", r.returncode)
