# -*- coding: utf-8 -*-
"""跑全量并提交状态窗融合的前半部分。"""
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

MSG = """fix(status): 状态窗融合（前半）—— 样式机制 + 状态页开关接上，test_bugfix_0930 7 项 → 2 项

按用户 2026-10-13 拍板「保留部分我们的优化，融合他的优化」实施融合。
**界面与信息架构留新版（四个分类页签 / 剧情风格 / 可拖动），把旧版独有的东西搬进来。**

一、样式机制（旧版那次修复的核心，也是用户当年报障的根因）
  · `classes/status_window.py::_Card` 基类 `QFrame` → **`QGroupBox`**，并 **开 `WA_StyledBackground`**。
    ⚠ 这是**真 bug 不只是测试口径**：`#card` 在 QSS 里写了 background，
      但 Qt 对**自定义子类**默认不画样式表背景，必须显式开这个属性 ——
      否则要等一次样式 polish，用户看到的就是"字压在壁纸上看不清，点刷新后那块底色才出现"
      （原注释与测试注释都记着这条）。
  · `StatusWindow`：`setObjectName("statusWindow")` + 开 `WA_StyledBackground`，
    并在 QSS 里补 `QDialog#statusWindow { background: <纸色渐变> }`（自绘 paintEvent 仍在其上画，
    两者不冲突）。
  · QSS 选择器 `QFrame#card` → `#card`（QGroupBox 也要命中）。
  实测效果：`findChildren(QGroupBox)` 从 **0 张 → 10 张**都开了属性；
  窗口抓图的"纸色采样"从 **1450 → 2420 / 12519**（底色真的画出来了）。

二、状态页开关（`status_page_enabled`）整套接上
  · `config.example.json` 补 `status_page_enabled: true`（默认开 ⇒ 不影响老用户）。
  · `pcl_launcher/silicon_window.py` 的 **`NAV` 列表里补 `("status", "", "状态", …)`**
    —— 之前 NAV 里**根本没有这一项**，所以侧栏永远不显示「状态」；
    开关的判断代码（`_status_page_enabled()` / 侧栏跳过 / 预热队列剔除）本来就在，只是没有入口项。
  · `_status_page_enabled()` 默认值确认为 True（缺键时按开处理）。

三、仍待做（下一轮，本轮先提交已验证的部分）
  · 设置页里的同名开关；
  · 右键菜单「她的状态」受同一开关管。

验证：`tests/test_bugfix_0930.py` 失败项 **7 → 2**；两个改动文件通过 py_compile；
      并且专门用 `S.QSS` 断言"那条规则**真在样式表字符串里**"（不是只写在注释里）。
"""
p = os.path.join(MAP, "_msg_status1.txt")
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
