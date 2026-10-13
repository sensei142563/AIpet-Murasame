# -*- coding: utf-8 -*-
"""提交 PPT 重定位（新时间线页 + 主张前置 + 讲稿错位修复）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """docs(ppt): 重定位 —— 主张前置、加一页大厂时间线、并修掉讲稿整体错位一格

起因：导师反馈"必须回答'有什么是我们有、其他人没有的'"，且"缺少一个漂亮的故事"。
原 deck 的问题有两处：① 第 8 页开场就是"定位：整合者，而非首创者"——在自评场合是加分，
要评奖/要投资时是自杀；② 市场部分缺"大厂入局"这个最有说服力的事实。

## 改了什么
1. **新增第 3 页「2026：大厂集体入局，但走的是同一条线」**（带时间线）
   2026-04 Anthropic（Claude Code 加虚拟宠物 Buddy）→ 2026-04 元空AI 仓鼠元元
   （自称"中国首个 AI 办公桌宠"）→ 2026-05 腾讯 WorkBuddy（养成玩法）→
   2026-09 腾讯 ×《和平精英》（Buddy 猫换皮肤、开放平台 100+ 伙伴）→ 2026-03 PetClaw。
   收在一句读法上：**全部是「办公/生产力 + 一只通用宠物」；它们要的是任务，
   没有人负责回答"她是不是她本人"。**（全部来自公开报道，来源见 docs 里那份调研）
2. **重写「横向对比」页 → 「我们的位置：办公线做『任务』，我们做『关系』」**
   把**主张**放到第一条（"把角色的人格连续性当变量"），把"并非首创"降为**最后一条**
   并注明细节在备注里。原来那条是开场即自我否定，现在是"先给主张、再给证据、最后给边界"。
3. **改写市场段收尾那句 quote**：
   旧："别人做「桌面上的形象」，我们做「住在电脑里」" / 落款"定位：整合者，而非首创者"
   新：**"大厂在给 AI 装一只宠物；我们做的是一个人"** / 落款"她在办公线是吉祥物，在我们这儿是角色"
4. **修掉一处真实缺陷：讲稿与页面整体错位一格。**
   核对时发现第 3~19 页的备注讲的是"下一页"的内容（第 3 页讲开源、第 4 页讲 Steam…），
   原因是此前插入 section 页后没有重挂备注。本次**按内容逐页重挂**，
   并为新页/改写页写了新讲稿；重建后核对"缺备注的页：无"。
5. 副标题补一句主张：`……｜主张：办公线做任务，我们做关系`。

## 流程（重建会丢备注，顺序不能反）
```
build_deck.py  → 已生成 dev/ppt/out/Deck.pptx（22 页）
ppt_add_notes.py → 22 页全部挂上、无缺页
render_qc.ps1 → 22 张 slide-*.png + Deck.pdf
```
视觉抽检：第 3 页（时间线）干净无溢出；第 8 页主张在最前、"并非首创"在最后一行；
第 9 页那句主张独立成页、落款正确。

## 两份开场（用户已确认"两个版本都要"）
创业/评奖版与学术/HCI 版见 `dev/docs/导师反馈拆解与定位建议-2026-10-13.md`；
deck 本身走**创业版**叙事，学术版换开场与落点即可复用其余全部页面。
"""
p = os.path.join(MAP, "_msg_ppt_reposition.txt")
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
