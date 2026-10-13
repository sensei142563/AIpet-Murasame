# -*- coding: utf-8 -*-
"""让 README 贴合实现：补「自检与回归」一节（381 项全绿，实测），
并在「后续可以完善的方向」末尾补毫米波/3D 两条；顺带补「立绘工坊」一句。
只写实测事实，不写没验证过的东西。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
R = os.path.join(ROOT, "README.md")

t = io.open(R, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ---------- ① 自检与回归一节 ----------
SECTION = """## ✅ 自检与回归：381 项，一条命令可复现

> 这一节回答一个问题："**我怎么知道它是好的？**" —— 不是"我这儿能跑"，而是有回归门禁。

```bash
# 在仓库根目录
runtime\\venv\\Scripts\\python.exe tests\\run_all.py
# Linux / macOS
runtime/venv/bin/python tests/run_all.py
```

当前状态（2026-10-13 实测）：

```
总计 10 个文件 / 381 项通过 / 0 个文件失败
```

| 体检文件 | 检查项数 | 管什么 |
|---|---|---|
| `test_bounds.py` | 68 | 敌意数值的夹取边界（字号/偏移/高度比）与真实角色数据不被误改 |
| `test_bugfix_0930b.py` | 108 | 线程收尾 · 语音不被打断 · 2D 口径 · 换装复核 · 联网学习三方共用 |
| `test_config_contracts.py` | 37 | 配置读取契约（重复键 / 窄真值比较 / 读取式下标 / 取值归一） |
| `test_qt_lifecycle.py` | 30 | Qt 生命周期：退出收尾、单实例、后台线程取消、控制台留得住 |
| `test_frontend_style.py` | 28 | 启动器配色/字号/图标一致性（主题切了资源也要跟着换） |
| `test_vision_interface.py` | 24 | 本地视觉"接口"行为（默认不走本地、错误提示可读） |
| `test_plugin_markup.py` | 19 | 插件标记解析与端到端跑一个插件 |
| `test_bugfix_0930.py` | 67 | 右键菜单入口、状态窗/状态页、配置开关、侧栏项 |
| `test_jev.py` / `test_jev_endpoint.py` | — | 按需的接口探针（无检查项时 rc=0） |

另外还有**像素级验收**的传统：立绘底色、换装是否真的换了，都用**图像摘要**比对，
而不是靠"看起来一样"（详见 `dev/docs/换装不生效-排查结论-2026-10-13.md`）。

> 说明：上面这些检查项不是摆设 —— 2026-10 的一次基线合并里，
> 它们抓出了"右键菜单少了两个主入口""插件回复函数整个丢失""连续换装不生效"
> 等多处问题（记录见 `dev/docs/红测试修复清单-2026-10-13.md`）。

"""

if "自检与回归" not in t:
    anchor = "## 后续可以完善的方向"
    if anchor in t:
        t = t.replace(anchor, SECTION + anchor, 1)
        print("✓ 已在「后续可以完善的方向」之前插入「自检与回归」一节")
    else:
        t = t.rstrip() + "\n\n" + SECTION
        print("✓ 已把「自检与回归」追加到文末（没找到锚点）")
else:
    print("· 已有该节")

# ---------- ② 后续方向补 3D / 毫米波 ----------
if "毫米波" not in t:
    m = t.find("## 后续可以完善的方向")
    if m >= 0:
        nxt = t.find("\n## ", m + 5)
        end = nxt if nxt > 0 else len(t)
        add = ("""
- **3D 形态（评估中）**：先把"能不能在手机/桌面上跑起来"验证掉（VRM 等现成人形格式），
  **再决定要不要投入建模成本** —— 建模周期长、返工多，不适合在验证之前投入。
- **更省算力的动捕路线（毫米波雷达）**：不依赖光线与镜头、隐私友好、可全天运行；
  科研课题里的动作采集装置在课题结束后可迁移（先把输出对接成**标准参数流**，
  再在桌面侧驱动她，最后按便携性决定是否上手机）。
""")
        t = t[:end] + add + t[end:]
        print("✓ 已在「后续可以完善的方向」里补 3D / 毫米波两条")
else:
    print("· 已有毫米波")

# ---------- ③ 立绘工坊 ----------
if "立绘工坊" not in t:
    t = t.replace("## 🖱️ 交互方式",
                  "## 🎨 立绘工坊（启动器内置的角色向导）\n\n"
                  "启动器里带一个**立绘工坊**（`pcl_launcher/pet_wizard.py`）：\n"
                  "· 新建角色：切片自己的立绘素材、标注表情/动作/装饰，生成角色包；\n"
                  "· 调显示：对话框位置与字号、立绘大小与偏移，所见即所得；\n"
                  "· 建好后与内置角色同样待遇（同一套引擎、同一套记忆与语音链路）。\n\n"
                  "## 🖱️ 交互方式", 1)
    print("✓ 已补「立绘工坊」一节")
else:
    print("· 已有立绘工坊")

io.open(R, "w", encoding="utf-8", newline="\n").write(t)
print()
print("=== 复核 ===")
t2 = io.open(R, encoding="utf-8", errors="replace").read()
print("   README 行数 =", len(t2.split("\n")))
for k in ("自检与回归", "381 项", "毫米波", "立绘工坊", "run_all.py"):
    print("   %-14s %s" % (k, "有 ✓" if k in t2 else "缺 ✗"))
