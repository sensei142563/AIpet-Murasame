# -*- coding: utf-8 -*-
"""给录屏操作单加 C7：桌面换装 → QQ 里发立绘 → 两张同套装扮。
   目的：deck 第 15 页那句「QQ 侧立绘与桌宠同一套装扮」目前只有**代码级**验证，
        加这段录屏后就有**现场证据**，演示时被追问可以直接放。
   同时更新媒体映射表（第 15 页补上 C7）。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
F = os.path.join(ROOT, "dev", "docs", "PPT录屏截图操作单-2026-10-13.md")

t = io.open(F, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

C7 = """
### C7 · 换一套衣服，QQ 里立刻也是这一套（约 40s，**第 15 页的现场证据**）

**为什么要这一段**：deck 第 15 页写着「QQ 侧立绘与桌宠同一套装扮」。
这句话目前只做过**代码级**验证（两侧读同一个 `data/portrait_choice.json`、
走同一个 `tool/portrait_outfit` 模块，因此含丛雨的 `pets.<id>.<set>` 布局都成立）——
**没有**拍过"两张图确实是同一套"。这段录屏就是补上它。

**怎么录**
1. 桌宠在桌面上，右键 → **换装与立绘** → 换一件明显不同的衣服（例如 刀服 → 制服）；
2. 立刻截图或让画面停一下，能看清桌面立绘换了；
3. 在 QQ 里 @ 她、让她发一张立绘（触发词见 `qq/qq_chat.py` 的 `[立绘:情绪]` 标记；
   简单办法是说一句带情绪的话，例如"今天好开心呀"）；
4. **把 QQ 里那张立绘和桌面立绘并排入镜**，让"同一套衣服"一眼看得出来。

**这段讲**：她不是"两个形象"——桌面和 QQ 里是**同一个人、同一套装扮**，
换装写的是**共享配置**，所以两边同时生效、并且记住到下次启动。

**注意**
- 换装后如果 QQ 那边的形象没立刻变，**先确认换的是"当前显示那套"**（`a` / `b` 是两套独立配置）；
- 若两张确实不一致，**那就是真 bug**：请把两张图都发我，我按
  `dev/docs/验证-QQ立绘与桌宠同一套装扮-2026-10-13.md` 里的链路逐段回查。
"""

# 插到 C6 那节之后（即"## 7. 录完之后我怎么接"之前）
anchor = "## 7. 录完之后我怎么接"
if "C7 · 换一套衣服" in t:
    print("· 已有 C7")
elif anchor in t:
    t = t.replace(anchor, C7.strip() + "\n\n" + anchor, 1)
    print("✓ 已插入 C7（换装 → QQ 同套装扮）")
else:
    print("✗ 锚点未命中")

# 映射表：第 15 页补 C7
old_row = "| 15 | 怎么做到的（三）：出桌面、上手机 | **S6 / S7**（启动器）、**S9 / S10**（手机） | 手机那两张见第 6 节 |"
new_row = "| 15 | 怎么做到的（三）：出桌面、上手机 | **S6 / S7**（启动器）、**S9 / S10**（手机）、**C7**（换装→QQ 同套） | 手机那两张见第 6 节；C7 见第 2 节 |"
if old_row in t:
    t = t.replace(old_row, new_row, 1)
    print("✓ 已更新映射表：第 15 页补上 C7")
else:
    print("· 映射表那行未命中（可能格式不同），待人工看")

io.open(F, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 复核 ===")
t2 = io.open(F, encoding="utf-8", errors="replace").read()
for k in ("C7", "同一套装扮", "portrait_choice.json", "验证-QQ立绘"):
    print("   %-22s %s" % (k, "有 ✓" if k in t2 else "缺 ✗"))
print("   行数 =", len(t2.split("\n")))

MSG = """docs(ppt): 操作单加 C7 —— 桌面换装 → QQ 里同一套（把第 15 页的断言变成可演示证据）

上一轮把 deck 第 15 页那句「QQ 侧立绘与桌宠同一套装扮」做了**代码级**验证（成立），
但明确留下一条没做到的：**没有在真实 QQ 群里发图后与桌面逐像素比对**。
这一段录屏就是补上那个缺口。

## C7 · 换一套衣服，QQ 里立刻也是这一套（约 40s）
1. 右键 → 换装与立绘 → 换一件明显不同的衣服（如 刀服 → 制服）；
2. 停一下让画面看清桌面立绘已换；
3. 在 QQ 里让她发一张立绘（说一句带情绪的话触发 `[立绘:情绪]`）；
4. **把 QQ 那张和桌面立绘并排入镜**，让"同一套"一眼看得出。

要点与排错也写进去了：
- 先确认换的是"当前显示那套"（`a` / `b` 是两套独立配置）；
- 若两张确实不一致 ⇒ **那是真 bug**，按
  `dev/docs/验证-QQ立绘与桌宠同一套装扮-2026-10-13.md` 的链路逐段回查。

## 媒体映射表同步
第 15 页原来只标了 `S6 / S7`（启动器）与 `S9 / S10`（手机），补上 **C7**。
"""
p = os.path.join(MAP, "_msg_c7.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
