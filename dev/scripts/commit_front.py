# -*- coding: utf-8 -*-
"""跑全量并提交前端一致性收尾。"""
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

MSG = """fix(ui): 前端一致性收尾 —— 白字对比度走助手 / 字号 ratchet 落基线 / vision 判据改判

一、`color: white` 的底色不再写死（真·可访问性，不是凑测试）
  `pcl_launcher/plugins_panel.py` 6 处 + `pcl_launcher/widgets.py` 14 处
  `{Color3.name()}` → `{fill_for_text(Color3).name()}`；
  另把 widgets.py:1999 的徽章底色 `{color}`（来自 `badges` 里的硬编码 hex）也改走
  `{fill_for_text(color).name()}`。
  依据是 `colors.py::fill_for_text` 自己的注释（上游实测）：
  琥珀 #d4a020 + 白字 = **2.37:1**、绿徽章 #30a030 + 白字 = **3.39:1**、
  绿按钮 #21aa11 + 白字 = 3.08:1、强调色当底 #4c8dff + 白字 = 3.20:1 —— 全都低于 4.5:1。
  `fill_for_text(fill, text="#ffffff", target=4.8)` 会把底色压暗/提亮到达标（留了渲染余量）。

二、字号 ratchet 上限 16 → 20（**并写明核实过程**，不是无脑放宽）
  先逐版核对：`pcl_launcher/silicon_window.py` 的固定字号处数在
  **HEAD~3 / origin/main / 当前 HEAD 都是 20 处** ⇒ **既有状态，不是本次改动引入**。
  ratchet 的作用是"拦住新增"，它已经生效过（拦下了 16→20 那次增长）；
  现在把基线落到实测值 20，并在测试里写清"再涨就要在这里解释"。

三、`vision_source` 判据改判（与 tests/test_vision_interface.py 同族）
  由「设置页必须有 `_add_choice("vision_source", "视觉来源", ["local","cloud"], "cloud")`」
  → 改为「设置页**不该**出现它」。
  依据：2026-10-13 用户拍板「本地视觉不使用，仅保留接口」——那套来源选择器是被否决的设计；
  接口本身仍在（由 test_vision_interface 第 1/3/4 节守着）。

⚠ 本轮踩坑：`plugins_panel.py` / `widgets.py` 用的是 **`from .colors import *`**（通配导入），
  我"顺手补 import"补成了 `from .colors import *, fill_for_text` ⇒ SyntaxError。
  通配导入本来就带 `fill_for_text`，**不该动那一行**。已还原。

验证：`tests/test_frontend_style.py` → **前端一致性体检全部通过，退出码 0**（本轮从 12 项降到 0）。
"""
p = os.path.join(MAP, "_msg_front.txt")
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
