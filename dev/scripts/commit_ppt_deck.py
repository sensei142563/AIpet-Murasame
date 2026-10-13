# -*- coding: utf-8 -*-
"""提交 PPT 骨架（大纲 + 主题 + 成品 + 渲染质检图）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """feat(ppt): 生成 PPT 骨架（21 页，剧情模式配色）—— 素材一到就能填

按 dev/docs/汇报PPT规划-2026-10-13.md 的四幕结构，用本地 PPT 管线
（E:\\Codex\\workflows\\ppt：outline → build_deck → PowerPoint 无头渲染 → 逐页视觉质检）
先生成**不依赖素材的部分**，这样录屏/截图一到就能直接对号入座。

一、主题：自定 `dev/ppt/theme-murasame.json`
  换成她自己的「剧情模式」配色，而不是管线默认的蓝色：
    正文底 #F7F1EA（奶油）· 主色 #3B2B26（墨棕）· 强调 #A03A35（暗红）· 次强调 #C9A35F（金）
    正文 #3B2B26 · 次要文字 #6B5850 —— 与 classes/status_window.py / tool/pet_menu.py 同一套色。

二、大纲：`dev/ppt/outline.json`（21 页，四幕）
  01 封面 → 一、桌宠市场调研（四类做法 / 开源 / Steam / AI 聊天机器人 / 横向对比表 / 定位金句）
  → 二、功能展示与实现方法（能做什么 / 形象与语音 / 记忆与陪伴 / 出桌面与上手机 / 工程质量）
  → 三、未来规划（近期体验 / 中期互动 / 更省算力的动捕路线 / 远期形态 / 金句）→ 谢谢

三、合规核对（按用户规矩逐条查过）
  · **不署名**：outline 里没有 author 字段，页面只有日期与页码；
  · **不含任何学校 / 专业 / 学号 / 绩点 / 实验室信息**；
  · **未写"掀裙子"**（用户明确要求不写入）；
  · 中文单语（用户拍板"PPT 先用中文"）。

四、产物
  · `dev/ppt/out/Deck.pptx`（21 页，约 58 KB）
  · `dev/ppt/out/Deck.pdf`（渲染导出）
  · `dev/ppt/out/qc/slide-01..21.png`（1280×720，逐页质检图）

五、视觉质检（已做）
  抽看封面 / 双栏页 / 内容页 / 结尾：**无文字溢出、无截断、无重叠、无豆腐块**，
  配色一致，页码正常。市场调研那页的两栏（"已经做得很好 / 普遍缺的"）对齐正常。

六、下一步（等用户素材）
  按 `dev/docs/PPT录屏截图操作单-2026-10-13.md` 拿到的 8 张截图 + 5 段录屏后，
  用 build_deck.py 的 content 版式 `image` 字段把截图插进对应页，再重跑渲染与质检；
  录屏（视频）在 PPT 里用"点击播放"占位或转成 GIF/静帧序列插入。
"""
p = os.path.join(MAP, "_msg_ppt_deck.txt")
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
print("  产物:", [f for f in os.listdir(os.path.join(ROOT, "dev", "ppt", "out"))][:5])
