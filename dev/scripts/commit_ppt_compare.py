# -*- coding: utf-8 -*-
"""提交"他们 vs 我们"对照页（23 页）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """docs(ppt): 加一页「同一个『宠物』位置，两种完全不同的做法」（对照页，23 页）

导师原话："简单的讲，就是，有什么是我们有，其他人没有的"、"不要讲雷军的那种话"。
上一轮已经把主张前置，这一轮再给一张**可以直接对质**的对照页。

## 载体选择
引擎（E:\\Codex\\workflows\\ppt）只支持 `title | section | content | two_col | quote | end`，
**没有 table 类型**，而且**引擎文件不能改**（既定纪律）。
⇒ 用 `two_col` 承载对照，实际读起来就是一张两栏对照表。

## 内容（左右各 5 条，一一对应）
左｜**他们：办公 / 生产力线**
· 宠物是通用吉祥物（一只猫、随机孵化的宠物；OpenAI 还允许自建 Custom Pet）
· 目标是任务（替你翻译/整理/跑代码/跨应用执行；WorkBuddy 想做"Agent 时代的操作系统"）
· 指标是效率与留存（识别率、任务成功率、次日留存）
· 不要求"是她本人"（所以换皮、联名、装扮都不影响产品成立）
· 场景：办公桌 / 公共场所（mmHRI 这类研究甚至以医院病房、餐厅为例）

右｜**我们：角色 / 关系线**
· 角色是具体的人（固定人设不 OOC、角色专属 GPT-SoVITS 声线、Live2D + 2D 双形态）
· 目标是关系（长期记忆、习惯、日记、关系值——按真实相处证据抬升，不靠嘴甜）
· 指标是关系感知与打扰容忍度（她该不该开口、什么时候该安静）
· **人格连续性是核心变量**（换角色 = 换一个人，而不是换一张皮）
· 场景：桌面 + 手机里的日常（QQ/微信桥接同一套人设与记忆，手机端共用同一份记忆文件）

## 位置与讲稿
插在"我们的位置"之后（新第 9 页），并**整体后移重挂讲稿** ⇒ 23 页、23 条备注、
核对输出「缺备注的页：无 ✓」。

## 流程与视觉质检
```
build_deck.py → 23 页 ✓
ppt_add_notes.py → 23 页全挂、无缺页 ✓
render_qc.ps1 → 23 张 slide-*.png + Deck.pdf ✓
抽检第 9 页：左右分栏清晰、无溢出、无截断 ✓
```

## deck 现在的故事线（23 页）
1 标题 · 2 section 市场 · **3 大厂时间线** · 4 四类做法 · 5 开源 · 6 Steam · 7 AI 聊天 ·
8 我们的位置（主张前置）· **9 他们 vs 我们（本页）** · 10 那句主张 ·
11 section 功能 · 12 她能做什么 · 13-15 怎么做到（形象/记忆/出桌面）· 16 工程质量 ·
17 section 未来 · 18-21 近期/中期/中期/远期 · 22 路线收束 · 23 谢谢
"""
p = os.path.join(MAP, "_msg_ppt_compare.txt")
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
