# -*- coding: utf-8 -*-
"""把用户 2026-10-13 的两个决定落仓：
  ① 本地视觉：不使用、仅保留接口 → 写进 doctor/测试注释与文档
  ② 状态窗：保留我们的优化 + 融合他的优化 → 写出功能级 diff 与融合方案文档
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

DOC = """# 状态窗融合方案 + 本地视觉决定（2026-10-13）

> 用户拍板：
> 1. **本地视觉：不使用，仅保留接口。**（不接上游那套 `vision_source` / `vision_local_url` /
>    `vision_local_command` 与设置页三项；现有"只留接口"的设计是对的。）
> 2. **状态页：咱们之前也有，保留部分我们的优化，融合他的优化**（具体看多了哪些功能）。
>    本文第 1 节就是那份"多了哪些功能"的对照。

---

## 1. 功能级对照（旧版 271 行 vs 新版 612 行）

### 1.1 新版（协作者的，也是当前在跑的）**多出来**的功能
| 能力 | 说明 |
|---|---|
| **四个分类页签** | 状态 / 习惯 / 记忆 / 提醒（我们旧版是**单页**） |
| **剧情风格渲染** | `_rich()`：【小标题】染深红加粗；`_diamond()`：红菱形条目标记 |
| **字体自选** | `_pick_font()`：从候选里挑一个系统**真装了**的字体，挑不到交给 Qt 回退 |
| **窗口可拖动** | `mousePressEvent/MoveEvent/ReleaseEvent` + 自绘 `paintEvent` |
| **卡片内容更丰富** | 在一起第 N 天 / 心情 / 关系 / 活跃度 / 【上次说话】/【手上的事】/【陪伴】/ 她现在的念头 / 她能自己做到哪一步 / 主人的习惯 / 作息与活跃时段 / 常用软件 … |
| **就地操作** | 「让她现在学一次」（`_study()`）、「打开记忆文件」（`_open_file()`） |

### 1.2 我们旧版**独有**、值得保留的
| 能力 | 为什么值钱 |
|---|---|
| **`WA_StyledBackground` + `QDialog#statusWindow` 的 QSS 不透明纸色底** | 用户当年报障就是"字体不明显，点刷新以后黄色的遮盖才出现"/"点刷新才出现底色" —— 这套正是那次的修法；测试里"抓图里确实有纸色底（不是全透明/壁纸透出来）"检查的就是它 |
| **「复制全部」** | 整页复制成纯文字，贴给别人 / 报 bug 最方便（新版没有） |
| **「打开数据目录」** | 新版只有「打开记忆文件」，范围偏窄 |
| **`page_titles()` / `card_count()` / `error_titles()`** | 三个**自省接口**，自检与排查"断在哪一环"靠它 |
| **`status_page_enabled` 开关** | 配置键 + 设置页开关 + 侧栏「状态」项 + 右键菜单项同受它管（默认 true，不影响老用户） |
| **出错时整张卡偏红** | 配 `error_titles()`，"一眼看出哪项坏了" |

## 2. 融合方案（待实施）

**原则：界面与信息架构留新版（他的），把上面 1.2 逐项搬进新版。**

1. `StatusWindow` 构造里补 `setAttribute(Qt.WA_StyledBackground, True)`；
   `_Card` 也补 `WA_StyledBackground`；把 `QDialog#statusWindow { background: <纸色> }` 加进 QSS。
2. 工具栏补「复制全部」（`snapshot_text()` 拼纯文本 → 剪贴板 → 提示"已复制"）。
3. 保留/补「打开数据目录」（新版已有"打开记忆文件"，两者并存）。
4. 补 `page_titles()` / `card_count()` / `error_titles()` 三个自省接口（供自检与测试用）。
5. `config.example.json` 补 `status_page_enabled: true`；设置页加同名开关；
   侧栏补「状态」项；右键菜单「她的状态」受同一开关管。
6. 出错卡片沿用"整张偏红 + `error_titles()`"。

## 3. 本地视觉：**不使用，仅保留接口**（已拍板）

- 不实现上游的 `vision_source` / `vision_local_url` / `vision_local_command` 与设置页三项。
- `tool/vision_local.py` 作为**接口**保留（198 行，三方一致），但**不作为默认路径**。
- 因此 `tests/test_vision_interface.py` 与 `tests/test_frontend_style.py` 里按**上游语义**写的
  那些检查项，判据与已拍板的设计不符 —— 应改为校验"**接口保留、默认不使用**"。
"""

D = os.path.join(ROOT, "dev", "docs", "状态窗融合方案与本地视觉决定-2026-10-13.md")
io.open(D, "w", encoding="utf-8", newline="\n").write(DOC)
print("✓ 已写出", os.path.basename(D))

# 在 vision_local.py 顶部写明决定
P = os.path.join(ROOT, "tool", "vision_local.py")
t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
MARK = "★ 2026-10-13 用户拍板"
if MARK not in t:
    lines = t.split("\n")
    # 插到首个非注释/非文档字符串之后的最小安全位置：文件前几行注释之后
    ins = ("# %s：**本地视觉不使用，仅保留接口**。\n"
           "#   不接上游那套 `vision_source` / `vision_local_url` / `vision_local_command` 与设置页三项；\n"
           "#   本模块作为**接口**留着（谁想接自己接），但**不是默认路径**。\n"
           "#   因此任何「缺省就该走本地视觉」的写法都是**与设计相反**的，不要加回来。\n" % MARK)
    # 放在 shebang / coding 之后
    k = 0
    while k < len(lines) and (lines[k].startswith("#!") or "coding" in lines[k] or
                              lines[k].strip().startswith('"""') or lines[k].strip() == ""):
        if k > 8:
            break
        k += 1
    lines = lines[:k] + ins.split("\n") + lines[k:]
    io.open(P, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print("✓ 已在 tool/vision_local.py 顶部写明决定")
else:
    print("· vision_local.py 已有决定记录")

subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
MSG = """docs: 落仓两个决定 —— 本地视觉"仅保留接口" + 状态窗融合方案（含功能级 diff）

用户 2026-10-13 拍板：
1) **本地视觉：不使用，仅保留接口。**
   → 不接上游那套 vision_source / vision_local_url / vision_local_command 与设置页三项；
     现有"只留接口"的设计是对的。已在 tool/vision_local.py 顶部写明，
     并注明"任何『缺省就该走本地视觉』的写法都是与设计相反的，不要加回来"。
   → tests/test_vision_interface.py 与 test_frontend_style.py 里按上游语义写的检查项，
     判据与已拍板的设计不符，应改为校验"接口保留、默认不使用"（下一步做）。

2) **状态页：保留我们的优化 + 融合他的优化。**
   新增 dev/docs/状态窗融合方案与本地视觉决定-2026-10-13.md，含功能级对照：
   · 新版（612 行）多出：四个分类页签（状态/习惯/记忆/提醒）、剧情风格渲染（_rich/_diamond）、
     字体自选（_pick_font）、窗口可拖动 + 自绘 paintEvent、卡片内容更丰富
     （在一起第 N 天/心情/关系/活跃度/【上次说话】/【手上的事】/【陪伴】/念头/自主/习惯/作息…）、
     就地操作（让她现在学一次 / 打开记忆文件）。
   · 我们旧版（271 行）独有且值得保留：WA_StyledBackground + QDialog#statusWindow 的 QSS
     不透明纸色底（正是用户当年"字体不明显/点刷新才出现底色"那次的修法）、「复制全部」、
     「打开数据目录」、page_titles/card_count/error_titles 三个自省接口、
     status_page_enabled 开关（含设置页开关 + 侧栏「状态」项）、出错整张卡偏红。
   · 融合方案 6 条已写进文档第 2 节（界面与信息架构留新版，把旧版这几样搬进去）。
"""
p = os.path.join(ROOT, "dev", "merge-map", "_msg_sw.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
r = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print()
print("桌面仓:", (r.stdout or r.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
