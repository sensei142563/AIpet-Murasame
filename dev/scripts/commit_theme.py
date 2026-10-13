# -*- coding: utf-8 -*-
"""跑全量并提交 _ACTIVE_THEME_ID 的恢复。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
MAP = os.path.join(ROOT, "dev", "merge-map")

print("=== 全量 ===")
r = subprocess.run([VENV, os.path.join("tests", "run_all.py")], cwd=ROOT, capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    if re.match(r"\s*test_\w+\.py\s+-?\d", l) or "总计" in l:
        print("   " + l.strip()[:135])

MSG = """fix(theme): 补回 _ACTIVE_THEME_ID —— 一次治好 8 个图标失败（真 bug：换主题不生效）

发现路径（**先看断言要什么，再决定补代码还是改测试**）：
  test_frontend_style 第 6 节把 `C._ACTIVE_THEME_ID = "senrenbanka"`，期望
  `nav_icon_path(k)` 能取到该主题的 8 张导航图。实测 8 个键**全部**返回空串
  → 界面退回 emoji。
  一查：senrenbanka 的 `theme.json` **8 个 nav_icons 全都配了**，
  且 `themes/senrenbanka/assets/nav/*.png` **文件也都在**（8 张，300~850 KB）。
  所以不是缺图，是**主题解析**的问题：我们的 `current_theme_id()` **只读 config.json**，
  而 `_ACTIVE_THEME_ID` 这个"内存里当前真正在用的主题"机制**在换基线时丢了**
  （备份里有、我们这棵树没有 —— 早先审计时它还在"待定/双向分叉"里）。

为什么它是**真 bug 不只是测试口径**：
  换肤是「先改内存色板、config 稍后才落盘」（预览时甚至 persist=False 不落盘）。
  主题背景与资源（`background_info()` / `theme_asset()` / `nav_icon_path()`）都要按
  「当前主题」去查目录 —— 只读 config 就会拿到**上一个**主题的背景与图标。
  这正是用户报过的「切了主题背景没变」，以及导航图标取不到图而退回 emoji 的同一个根因。

改法（pcl_launcher/colors.py）：
  · `THEME_DIR` 之后加模块级 `_ACTIVE_THEME_ID = ""`（空串 = 还没换过肤 → 回退读 config）；
  · `current_theme_id()` 开头优先返回 `_ACTIVE_THEME_ID`（且该目录真实存在时才用）。

验证：
  · 直接查：`C._ACTIVE_THEME_ID='senrenbanka'` → `current_theme_id()` = senrenbanka，
    `nav_icon_path('model')` / `nav_icon_path('status')` 都不再为空。
  · `tests/test_frontend_style.py` 失败项 **12 → 4**（8 个图标项一次全消）。
  · colors.py 通过 py_compile。

⚠ 写法踩坑记录：第一版用「expr + 'str' "str" expr」跨行混拼，Python 会把字面量与名字并置
  ⇒ SyntaxError。改为「纯字符串列表 + 逐行加缩进前缀」后一次通过。
"""
p = os.path.join(MAP, "_msg_theme.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
