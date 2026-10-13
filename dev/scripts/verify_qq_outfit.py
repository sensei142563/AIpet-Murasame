# -*- coding: utf-8 -*-
"""① 记录"QQ 立绘与桌宠同一套装扮"的验证过程与结论
   ② 把这条结论补进调研文档的"预设问答"里（导师/评委很可能问）。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

D = os.path.join(ROOT, "dev", "docs", "验证-QQ立绘与桌宠同一套装扮-2026-10-13.md")
io.open(D, "w", encoding="utf-8", newline="\n").write("""# 验证：deck 那句「QQ 侧立绘与桌宠同一套装扮」是否成立

> 为什么单独验：这句话出现在 deck 第 15 页（出桌面、上手机），
> 之前的依据只是**代码注释**（"QQ 立绘同步生效"之类），**没有端到端核过**。
> 演示时它是最容易被追问的一句（"那你在 QQ 里看到的和桌面上是同一套吗？"）。

## 一、两边是不是同一份数据

| 侧 | 入口 | 指向 |
|---|---|---|
| 桌宠 | `tool/portrait_outfit.py:116/118` | `<BASE>/data/portrait_choice.json` |
| QQ 立绘 | `qq/qq_portrait.py:210-215` `_choice_path()` → `tool.portrait_outfit.choice_path` | **同一个文件**（导入统一模块，兜底才回落到同路径） |

## 二、更要紧的：QQ 侧会不会只看一种布局

`data/portrait_choice.json` 有**两种布局**：
- 顶层 `a` / `b` / `active`：给**没有** `pets.<id>.portrait.sets` 的角色；
- `pets.<id>.<set>`：给**有** `portrait.sets` 的角色 —— **丛雨（murasame）属于这一种**。
（判定逻辑在 `tool/portrait_outfit.py` 的 `_pet_tables()`。）

如果 QQ 侧自己实现了一套读取、且只认第一种布局，那么**对丛雨就会读错/回落默认装扮** ——
这正是本工程反复出现的那类"看起来对、其实对错了对象"的问题。所以专门查了：

```
qq/qq_portrait.py:218-225  load_choice()  → from tool.portrait_outfit import load_outfit
qq/qq_portrait.py:228-239  save_choice()  → from tool.portrait_outfit import save_outfit
qq/qq_portrait.py:210-215  _choice_path() → from tool.portrait_outfit import choice_path
```
⇒ QQ 侧**委托给与桌宠完全相同的那一个模块**，而该模块本身就同时处理两种布局
⇒ **对丛雨（`pets.<id>.<set>`）同样成立**。

## 三、结论

deck 那句「QQ 侧立绘与桌宠同一套装扮」**成立**，依据是：
1. 两侧读/写**同一个** `data/portrait_choice.json`；
2. 通过**同一个** `tool/portrait_outfit` 模块，因此两种存储布局都能正确落到丛雨身上；
3. 写入侧同样共用：`classes/murasame_class.py:3253/3699`（右键换装"写共享配置 → QQ 立绘与桌宠同时生效"）、
   `qq/qq_bridge.py:709/720`（AI 自主换装"桌宠 + QQ 立绘同步生效、持久化"）。

## 四、仍未验的部分（诚实）
- **没有在真实 QQ 群里发一张图、再和桌面上的她逐像素比对**（那需要 QQ 环境与真机）；
  本次是**代码级**验证（同文件 + 同模块 + 同一读写入口），比注释强，但不等同于"我看到过同一套"。
- 若要把这条写进 PPT 的"现场可演示"清单，建议录一段：
  桌面右键换装 → 立刻在 QQ 里让她发一张立绘 → 两张同一套装扮。
""")
print("✓ ① 已写 dev/docs/验证-QQ立绘与桌宠同一套装扮-2026-10-13.md")

# ---------- ② 补进调研文档的预设问答 ----------
R = os.path.join(ROOT, "docs", "大厂入局与对标补查-2026-10-13.md")
t = io.open(R, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
ROW = ("| QQ 里看到的和桌面上是同一套装扮吗？ | 是。两侧读/写同一个 "
       "`data/portrait_choice.json`，且都走同一个 `tool/portrait_outfit` 模块，"
       "因此两种存储布局（含丛雨的 `pets.<id>.<set>`）都成立。"
       "（代码级已核；真机逐像素比对未做，见 `dev/docs/验证-QQ立绘与桌宠同一套装扮-2026-10-13.md`） |")
if "QQ 里看到的和桌面上是同一套装扮吗" not in t:
    if "| 腾讯都做了生态，你们还有什么？ |" in t:
        t = t.replace("| 腾讯都做了生态，你们还有什么？ |",
                      ROW + "\n| 腾讯都做了生态，你们还有什么？ |", 1)
        io.open(R, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ ② 已把这条问答补进 docs/大厂入局与对标补查")
    else:
        print("✗ ② 锚点未命中")
else:
    print("· ② 已有该问答")

MSG = """docs: 验证 deck 那句「QQ 侧立绘与桌宠同一套装扮」——成立（代码级）

## 为什么单独验
这句话在 deck 第 15 页，之前依据只是**代码注释**，没端到端核过；
演示时它最容易被追问（"QQ 里看到的和桌面上是同一套吗？"）。

## 关键点：不能只看"路径相同"，要看**两种布局**
`data/portrait_choice.json` 有两种布局：顶层 `a/b/active`（无 `portrait.sets` 的角色）
与 `pets.<id>.<set>`（**丛雨属于这一种**）。若 QQ 侧自己实现读取且只认第一种，
对丛雨就会回落默认装扮 —— 正是本工程反复出现的"对错了对象"。

## 查证结果：成立
```
qq/qq_portrait.py:210-215  _choice_path() → from tool.portrait_outfit import choice_path
qq/qq_portrait.py:218-225  load_choice()  → from tool.portrait_outfit import load_outfit
qq/qq_portrait.py:228-239  save_choice()  → from tool.portrait_outfit import save_outfit
tool/portrait_outfit.py:116/118  → <BASE>/data/portrait_choice.json（与桌宠同一份）
```
⇒ QQ 侧**委托给与桌宠完全相同的那一个模块**，该模块本身处理两种布局
⇒ 对丛雨的 `pets.<id>.<set>` 同样成立。写入侧也共用：
`murasame_class.py:3253/3699`（右键换装）、`qq/qq_bridge.py:709/720`（AI 自主换装）。

## 仍未验的（写进文档，不夸大）
**没有**在真实 QQ 群里发图后与桌面逐像素比对（需要 QQ 环境与真机）。
本次是**代码级**验证（同文件 + 同模块 + 同一读写入口）——比注释强，但不等同于"亲眼见过同一套"。
建议录一段可演示证据：桌面换装 → 立刻在 QQ 里发一张立绘 → 两张同套装扮。

顺带把这条结论补进 `docs/大厂入局与对标补查-2026-10-13.md` 的**预设问答**表。
"""
p = os.path.join(MAP, "_msg_qq_outfit.txt")
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
