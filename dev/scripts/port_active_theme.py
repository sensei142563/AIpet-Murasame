# -*- coding: utf-8 -*-
"""把 `_ACTIVE_THEME_ID` 机制补进 pcl_launcher/colors.py（备份里有、我们这棵树丢了）。

为什么现在必须补：test_frontend_style 第 6 节把 C._ACTIVE_THEME_ID 设成 'senrenbanka'，
期望 nav_icon_path() 能取到该主题的 8 张图；而我们的 current_theme_id() 只读 config.json，
主题目录里明明有图也取不到（实测 8 个图标全空 → 退回 emoji）。

写法注意：**不要**用「expr + 'str' "str" expr」这种跨行混拼（Python 会把字面量与名字并置 → 语法错）。
这里统一用「纯字符串列表 + 逐行加缩进前缀」。
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
P = os.path.join(ROOT, "pcl_launcher", "colors.py")

t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

if "_ACTIVE_THEME_ID" in t:
    print("· colors.py 已有 _ACTIVE_THEME_ID")
else:
    lines = t.split("\n")

    # ① 模块级变量：接在 THEME_DIR = ... 之后
    k = next(i for i, l in enumerate(lines) if re.match(r"\s*THEME_DIR\s*=", l))
    var = [
        "",
        "# 内存里「当前真正在用的主题」：换肤时写，current_theme_id() 优先用它。",
        "# 空串 = 还没换过肤（启动阶段）→ 回退读 config.json 的 ui_theme。",
        '_ACTIVE_THEME_ID = ""',
    ]
    lines = lines[:k + 1] + var + lines[k + 1:]
    t = "\n".join(lines)

    # ② current_theme_id() 开头插入优先分支（整段按函数体缩进加前缀）
    m = re.search(r"(?m)^([ \t]*)def current_theme_id\(\)[^\n]*:\n", t)
    if not m:
        print("✗ 找不到 current_theme_id")
        sys.exit(1)
    ind = m.group(1) + "    "          # 函数体缩进
    body = [
        '"""当前主题 id：**以内存里正在用的为准**，其次才看 config.json。',
        "",
        "为什么不能只读 config.json：换肤是「先改内存色板、config 稍后才落盘」",
        "（预览时甚至 persist=False 不落盘）。而主题背景与资源（background_info /",
        "theme_asset / nav_icon_path）都要按「当前主题」去查目录 —— 只看 config",
        "就会拿到**上一个**主题的背景与图标：用户报的「切了主题背景没变」，",
        "以及导航图标取不到图而退回 emoji，都是这个根因。",
        '"""',
        "if _ACTIVE_THEME_ID and os.path.isdir(os.path.join(THEME_DIR, _ACTIVE_THEME_ID)):",
        "    return _ACTIVE_THEME_ID",
    ]
    ins = "\n".join((ind + b) if b else "" for b in body) + "\n"
    t = t[:m.end()] + ins + t[m.end():]
    io.open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已补 _ACTIVE_THEME_ID 变量 + current_theme_id() 的优先分支")

print()
print("=== 验证 ===")
try:
    py_compile.compile(P, doraise=True)
    print("   ✓ py_compile colors.py")
except py_compile.PyCompileError as e:
    print("   ✗", str(e)[:300])
    sys.exit(1)

code = ("import sys;sys.path.insert(0,r'%s');"
        "import pcl_launcher.colors as C;"
        "C._ACTIVE_THEME_ID='senrenbanka';"
        "print('THEME', C.current_theme_id());"
        "print('ICON', bool(C.nav_icon_path('model')));"
        "print('ICON_STATUS', bool(C.nav_icon_path('status')))" % ROOT)
r = subprocess.run([VENV, "-c", code], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if l.startswith(("THEME", "ICON")) or "Error" in l:
        print("   " + l.strip()[:140])

r2 = subprocess.run([VENV, os.path.join("tests", "test_frontend_style.py")], cwd=ROOT,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r2.stdout or "") + (r2.stderr or "")).split("\n"):
    if "[FAIL]" in l or "FAILED" in l:
        print("   " + l.strip()[:150])
