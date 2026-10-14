# -*- coding: utf-8 -*-
"""提交本次文字修复：3 处改动 + 图片未动的断言 + 两条设计决定写进调研文档。
   同时把体量大的 deck 备份加进 .gitignore（不提交）。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

# ---------- .gitignore：忽略体积大的备份 ----------
gi = os.path.join(ROOT, ".gitignore")
t = io.open(gi, encoding="utf-8", errors="replace").read()
ADD = ("\n# PPT deck 的临时/备份副本（体积大，不入库；Deck-文字版.pptx 是有用的回退点，保留）\n"
       "dev/ppt/out/Deck-用户版-*.pptx\n"
       "dev/ppt/out/Deck-改字前-*.pptx\n"
       "dev/ppt/out/_img_snapshot_before.json\n")
if "Deck-用户版" not in t:
    if not t.endswith("\n"):
        t += "\n"
    io.open(gi, "w", encoding="utf-8", newline="\n").write(t + ADD)
    print("✓ .gitignore 已加备份忽略规则")
else:
    print("· .gitignore 已有规则")

subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
# 把大备份从暂存区撤下（万一已被 add）
for pat in ("dev/ppt/out/Deck-用户版-", "dev/ppt/out/Deck-改字前-",
            "dev/ppt/out/_img_snapshot_before.json"):
    r = subprocess.run(["git", "-C", ROOT, "diff", "--cached", "--name-only"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    for f in (r.stdout or "").split("\n"):
        if pat in f:
            subprocess.run(["git", "-C", ROOT, "reset", "-q", "HEAD", "--", f],
                           capture_output=True)
            print("   已撤下暂存：%s" % f)

MSG = """fix(ppt): 只改 3 处文字（页码 20/21 互换 + 一处括号）—— 图片位置尺寸完全未动

## 背景
主人在 `Deck.pptx` 上自己改了一部分文字与一部分图片，要求：
"先再修一下PPT的文字吧，我改了一部分文字和一部分图片，非必要不要动图片位置和大小"
⇒ 所以**没有从 outline 重建**（那会冲掉主人的改动），只在现有 pptx 上做外科式改字。

## 先做核查（不靠猜）
1. 文件锁检查：无 `~$Deck.pptx`、可写 ✓（而且**没有**在 WPS 里打开）
2. 备份：`Deck-用户版-20261014-162734.pptx`（改前）→ 再备份 `Deck-改字前-20261014-162921.pptx`
3. 逐页导出全部文字 + 扫描客观问题：
   - `**` 残留 ✗ 无 ✓；占位符 ✗ 无 ✓；重复标点 ✗ 无 ✓；HTML 实体 ✗ 无 ✓
   - 扫出的"连续多个空格"**全是误报** —— 那是主人刻意的 `▪  关键词  说明` 双空格样式，不动
4. 最长行 85 字（第 10 页）⇒ **渲染看图确认没有溢出** ✓（85 字那行放得下）
5. 断言核实：第 15 页「按真实相处证据抬高下限（affinity_floor）」——
   `tool/state.py:188` 确有 `affinity_floor()`，`tests/test_bugfix_0930b.py` 还夹了上限 88
   ⇒ **断言为真，不改**

## 改了什么（仅 3 处，全部是 run 级文字替换，保留原格式）
```
第 20 页  页码 21 → 20      ← 与下一页**互换**了（其余页页码都正确）
第 21 页  页码 20 → 21
第  4 页  Ukagaka(SSP) → Ukagaka（SSP）   ← 全 deck 其余 30 处括号都是全角
```
说明：第 2/12/18 页的 01/02/03 是**章节号**（形状 11.0×1.4 in，比页码 12.1×0.3 in 大得多），
不是页码错误。

## 图片零改动的**程序断言**
改前先把 15 张图的 (页码, left, top, width, height, name) 存成 JSON，
改后再取一次并**逐项比对** ⇒ `✓✓ 完全一致：图片位置、尺寸、顺序、页码归属都没有变化`。

## 验证
```
页码复查：24 页无一页与页序不符 ✓
讲稿清点：页数 24 / 有讲稿 24 / 图片 15 ✓（python-pptx 保存未伤讲稿）
渲染验收：Rendered 24 slides + PDF ✓；目视复核第 4/20/21 页 ✓
```

## 附带
- 调研文档补入主人确认的两条决定：**冷热值用双轴**；**「思念」只在温度极低时触发**。
- `.gitignore` 忽略 `Deck-用户版-*.pptx` / `Deck-改字前-*.pptx`（各 2 MB+，不入库）；
  `Deck-文字版.pptx` 仍保留（99 KB，是有用的回退点）。
"""
p = os.path.join(MAP, "_msg_ppttext.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("✓ 提交：", (rc.stdout or rc.stderr or "").splitlines()[0][:150])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = [l for l in subprocess.run(["git", "-C", ROOT, "status", "--porcelain"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace").stdout.split("\n") if l.strip()]
print("   未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st)))
for l in st[:8]:
    print("      " + l[:104])
