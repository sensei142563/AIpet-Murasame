# -*- coding: utf-8 -*-
"""提交：断言审计后的重建产物。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """build(ppt): 重建 —— 第 14 页断言收窄后的产物（看图确认一行放下、无溢出）

改了 outline 就必须重建（不然 pptx 里还是旧文案）：
```
build_deck.py    → 23 页 ✓
ppt_add_notes.py → 23 页全挂、缺备注的页：无 ✓
render_qc.ps1    → 23 张 slide-*.png + Deck.pdf ✓
目视复核第 14 页 ✓：「关系会变」那条现在是
   桌面端：按真实相处证据（天数×对话量）抬高下限（affinity_floor）；
   QQ 侧另有一套面向群聊的好感玩法，按对话内容结算
单行放下、无溢出。
```
"""
p = os.path.join(MAP, "_msg_rebuild14.txt")
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
