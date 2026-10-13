# -*- coding: utf-8 -*-
"""提交五页签修正后的重建产物。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """build(ppt): 重建 —— 第 14 页「状态页五个页签」修正后的产物

改了 outline 就必须重建，并按既定顺序：
```
build_deck.py    → 23 页
ppt_add_notes.py → 23 页全挂、缺备注的页：无 ✓
render_qc.ps1    → 23 张 PNG + Deck.pdf ✓
目视复核第 14 页 ✓：四条要点各一行、无溢出；
「状态看得见」已改为「状态页五个页签：现在 / 习惯 / 心里 / 提醒 / 记忆」。
```
"""
p = os.path.join(MAP, "_msg_rebuild14b.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
