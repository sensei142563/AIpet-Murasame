# -*- coding: utf-8 -*-
"""提交 PPT 的口径核对与金句排版修正。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """fix(ppt): 补"诚实定位"并修金句排版 —— 对着导师讲之前先把口径核一遍

一、按调研文档**自己的结论**补诚实定位（避免过度宣称）
  `docs/AI桌宠-聊天机器人方向调研.md` 第 115 行写得很清楚：
    "并非首创，但进入了**极稀疏地带**：唯一查到把这几条同时做齐且仍在活跃的项目是
     super-agent-party（约 2.7k★）……因此我们的位置是『用现有最优组件重新组合的整合者』，
     差异化必须落在产品整合度、开箱体验与本地化深度上，**而不是『我们做了别人没做过的事』**。"
  但 PPT 里少了一句把这件事说透的话 ⇒「横向对比」页补一条：
    **诚实定位：并非首创** —— 但已进入极稀疏地带，唯一查到做齐且仍在活跃的是 super-agent-party
  并把金句出处改为「定位：**整合者，而非首创者**」。

二、金句排版修正（两轮）
  · 第一版用了全角引号 ⇒ 与管线自带的外层引号**重复**，且句尾 `”` 被挤到第二行、
    下方还多出一个孤立的项目符号；
  · 改为中文直角引号「」并缩短 ⇒ 现为**单行、无孤立符号**：
      别人做「桌面上的形象」，我们做「住在电脑里的人」  —— 定位：整合者，而非首创者

三、重新生成 + 无头渲染 + 逐页抽查
  Deck.pptx 21 页 / Deck.pdf / qc/slide-01..21.png 全部重出；
  抽查封面(01)、双栏(04)、横向对比(07)、金句(08)：无溢出/截断/重叠/豆腐块。

⚠ 踩坑记录：`subprocess.run(..., capture_output=True, text=True)` **不带 encoding** 时，
  在本机默认按 GBK 解码子进程输出 ⇒ `UnicodeDecodeError: 'gbk' codec can't decode byte 0x90`。
  凡是要读子进程输出的地方，一律显式 `encoding="utf-8", errors="replace"`。
"""
p = os.path.join(MAP, "_msg_ppt_honest.txt")
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
