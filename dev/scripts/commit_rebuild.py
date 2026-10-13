# -*- coding: utf-8 -*-
"""提交重建后的 deck/PDF/QC 图（数字已同步为 386）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """build(ppt): 重建 deck —— 第 16 页数字同步为 386（源码改了就必须重建，否则产物与源不一致）

上一条改了 outline.json（381→386）与 notes.json，但**没有重建** ⇒ `Deck.pptx` 里还是 381。
这条把产物补齐，并**读回 pptx 文本验证**：

```
读 dev/ppt/out/Deck.pptx：
   第 16 页: ['▪  386 项自带自检  边界 / 配置契约 / 生命周期 / 前端一致性 / 语音链路']
   没有 381 残留 ✓
```

流程（顺序不能反，重建会丢备注）：
```
build_deck.py       → 23 页 ✓
ppt_add_notes.py    → 23 页全挂、缺备注的页：无 ✓
render_qc.ps1       → 23 张 slide-*.png + Deck.pdf ✓
```
"""
p = os.path.join(MAP, "_msg_rebuild.txt")
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
