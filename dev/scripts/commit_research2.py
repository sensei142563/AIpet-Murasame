# -*- coding: utf-8 -*-
"""提交"大厂入局与对标补查"调研（补齐导师点名的三个对标）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """docs(research): 补齐导师点名的三个对标（仓鼠元元 / WorkBuddy×和平精英 / 大厂入局）

上一版调研里这三个**全仓 0 命中**，导师一问就会崩。本提交查完并写成带来源的调研，
同时得出一个对我们**极其有利**的结论。

## 补到的事实（都有来源）
· **第三波**：1997 大眼夹（不懂意图，被移除）→ 约 2006 QQ 宠物（无生产力，失去生命力）
  → 2026 本轮（前提不同：AI 本身已有生产力）。
· **腾讯 WorkBuddy**：2026-05 上线"成长计划"（积分/盲盒/装扮/派它去旅行）；
  2026-09 与《和平精英》金秋联动；开放平台首批 **100+ 伙伴、10+ 品类、30+ 品牌**，
  官方目标是 **"Agent 时代的操作系统"**，让**账号/任务/记忆/产物在设备间流转**。
· **Anthropic**：2026-04 在 Claude Code 加虚拟宠物 Buddy。
· **OpenAI**：Codex Pets 出现在桌面、**随任务状态变化**，并支持用户**自建 Custom Pet**。
· **元空AI（北大团队）仓鼠元元**：2026-04，自称"中国首个 AI 办公桌宠"，
  定位**办公效率**（划词即用/常驻多轮对话），随 ChatExcel 客户端分发。
· **PetClaw**：2026-03，自称 24 小时运行，跨应用执行任务 + **长期记忆**。

## 关键结论（对我们有利的那一点）
大厂与已融资团队**几乎全部走"办公/生产力"线**：他们的宠物是**通用吉祥物**
（一只猫、一只随机孵化的宠物），要的是"**任务**"。
**没有人在回答"这个角色是不是她本人"。**
而那篇综述自己的结论恰好点在这里："真正有价值的是宠物背后的东西：**人格、记忆和任务**"、
"可能成为用户与 AI 之间**长期存在的身份锚点**"、"用户会记住自己的那只猫
**叫什么、长什么样、有什么性格**"。
⇒ **人格（角色一致性）与记忆（关系连续性）正是我们在做的，也是办公线结构性地不需要的。**

## 产出的差异表（按"他们做不了/不做"分级）
1. 角色一致性（不 OOC、换角色=换人）—— 中→强，需量化证据；
2. 记忆与关系连续性、跨端同源 —— 中（他们能追上）；
3. 微信/QQ 原生接入 —— **中，但必须写成"渠道"，不写成壁垒**；
4. 非摄像头常驻感知（毫米波）—— **潜在最强，但标"待查"**：未查证前不进结论；
5. 手机端本身 —— 弱，不作为卖点（导师已拆，我同意）。

## 两个版本的开场（用户已确认"两个都要，共用内容换开场"）
· 创业/评奖版：「大厂都在给 AI 装一只宠物；我们做的是**一个人**……没有人回答'她还是不是她'。」
· 学术/HCI 版：研究问题 = 陪伴型智能体的**人格连续性**如何影响关系感知与打扰容忍度，
  并引入**非摄像头感知**作为隐私友好的在场信号。

另附**预设问答**表，专门接导师那几刀（为什么上手机/手机端难不难/别人为什么不做/
是不是又一个 QQ 宠物/腾讯做了生态你们还有什么）。

## 仍未查证（诚实清单）
毫米波在陪伴场景的已有工作、仓鼠元元的用户量、WorkBuddy 与 Codex Pets 的留存效果、
二次元向桌宠的竞品用户规模 —— 均未找到公开数据，已在文末列明，不写进结论。
"""
p = os.path.join(MAP, "_msg_research2.txt")
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
