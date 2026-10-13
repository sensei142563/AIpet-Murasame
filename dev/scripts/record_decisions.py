# -*- coding: utf-8 -*-
"""把用户的三条决定写进仓库：
  ① 不恢复表情符号（菜单保持金色菱形标记）
  ② PPT 用中文、不署名
  ③ opencv/numpy 的版本组合**不要动**（两边唯一都能用的组合）—— 在 requirements.txt 里写明
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

# ---------- ① 菜单：不恢复表情符号 ----------
P = os.path.join(ROOT, "classes", "murasame_class.py")
t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
MARK = "★ 用户 2026-10-13 拍板："
if MARK not in t:
    anchor = "            # ★★ 第一层必须留两个「主操作」（2026-10-13 补回）"
    note = ("            # ★ 用户 2026-10-13 拍板：**不恢复表情符号**（旧版的 💬🎭📖 不回填），\n"
            "            #   继续用金色菱形标记 + 暗红小标题这套「剧情模式」视觉语言。\n"
            "            #   本条为设计决定，别再\"顺手\"把 emoji 加回来。\n")
    if anchor in t:
        t = t.replace(anchor, note + anchor, 1)
        io.open(P, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ ① 已在右键菜单代码里写明「不恢复表情符号」")
    else:
        print("⚠ ① 菜单锚点未命中")
else:
    print("· ① 已有决定记录")

# ---------- ③ requirements.txt：写明 opencv/numpy 不要动 ----------
R = os.path.join(ROOT, "requirements.txt")
rt = io.open(R, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "不要动" not in rt and "唯一" not in rt:
    note = ("# ⚠ 用户 2026-10-13 明确要求：**opencv-python 与 numpy 的版本组合不要动**。\n"
            "#   原因：`opencv-python 4.12.x` + `numpy 1.26.x` 是**唯一**在\"协作者机器\"和\"本机\"\n"
            "#   两边都能跑的组合。pip check 会提示 \"opencv-python requires numpy>=2\"——那是**已知且接受**的，\n"
            "#   不要为了消除这条告警去升 numpy（升了会破坏其中一台）。\n")
    if "opencv-python" in rt:
        rt = re.sub(r"(opencv-python[^\n]*\n)", note + r"\1", rt, count=1)
    else:
        rt = note + rt
    io.open(R, "w", encoding="utf-8", newline="\n").write(rt)
    print("✓ ③ 已在 requirements.txt 写明「不要动 opencv/numpy 组合」")
else:
    print("· ③ 已有说明")

# ---------- ② PPT 规划：中文、不署名 ----------
D = os.path.join(ROOT, "dev", "docs", "汇报PPT规划-2026-10-13.md")
dt = io.open(D, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = ("> ⚠ 有一个前置问题需要你定：**PPT 是中文还是中英混排**、**是否需要\"校园/实验室\"署名样式**。\n"
       "> 另外按你之前的要求，**任何学校/专业/绩点等个人身份信息一律不写进 PPT**。")
NEW = ("> ✅ **用户 2026-10-13 已定**：\n"
       "> · **PPT 用中文**（不中英混排）。\n"
       "> · **不署名** —— 不加姓名/学号/学校/学院/实验室等身份信息，也不做\"校园/实验室\"署名样式。\n"
       "> · 页面底部只保留**页码**；需要标识时用\"本项目\"或\"AIpet-Murasame\"指代即可。\n"
       ">\n"
       "> 另外沿用既有规矩：**草稿里也不要出现任何个人身份信息**（宁可留空，等你需要时再填）。")
if OLD in dt:
    dt = dt.replace(OLD, NEW, 1)
    io.open(D, "w", encoding="utf-8", newline="\n").write(dt)
    print("✓ ② 已把「中文、不署名」写进 PPT 规划")
elif "中文" in dt and "不署名" in dt:
    print("· ② 已有决定")
else:
    dt = dt.rstrip() + "\n\n---\n\n" + NEW + "\n"
    io.open(D, "w", encoding="utf-8", newline="\n").write(dt)
    print("✓ ② 已追加决定到 PPT 规划末尾")

print()
print("=== 复核 ===")
for f in ("classes/murasame_class.py", "requirements.txt", "dev/docs/汇报PPT规划-2026-10-13.md"):
    p = os.path.join(ROOT, f)
    txt = io.open(p, encoding="utf-8", errors="replace").read()
    hit = ("不恢复表情符号" in txt) or ("不要动" in txt) or ("不署名" in txt)
    print("   %-44s %s" % (f, "已写入 ✓" if hit else "没找到决定 ✗"))
