# -*- coding: utf-8 -*-
"""提交 PPT 讲稿备注。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """feat(ppt): 给 21 页加讲稿备注（写在脚本层，未改引擎）

动机：`E:\\Codex\\workflows\\ppt\\scripts\\build_deck.py` **不支持备注**。
按该技能的约定——"不要改引擎文件来适配单次需求；要新能力先在 outline/脚本层加"——
所以新开一个**后处理脚本**，而不是去动引擎。

新增：
· `dev/ppt/notes.json`：21 页的口语化讲稿（每页 2~4 句，照着念即可）。
  其中第 7 页专门写了"诚实定位"那段的说辞：**并非首创**，唯一查到做齐且活跃的是
  super-agent-party，我们是**整合者**，差异化在产品整合度/开箱体验/本地化深度。
· `dev/scripts/ppt_add_notes.py`：读 notes.json → 用 python-pptx 写入各页
  `notes_slide.notes_text_frame` → 保存 → **再读回逐页核对**。

验证（读回）：
  页数 = 21，备注条数 = 21；
  "读回验证：21 页有备注"，"缺备注的页：无 ✓"；
  抽查第 1 / 2 / 3 / 4 / 20 / 21 页内容正确。

用法（以后改讲稿）：
  改 `dev/ppt/notes.json` → 跑 `python dev/scripts/ppt_add_notes.py` 即可，
  不用重新生成 pptx，也不会碰到版式。

⚠ 注意：**重新跑 build_deck.py 会覆盖 Deck.pptx，备注会丢** ——
  正确顺序是：改 outline → 重建 → **再跑一次 ppt_add_notes.py** 补备注。
  这一条已写进脚本头部注释。
"""
p = os.path.join(MAP, "_msg_ppt_notes.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
