# -*- coding: utf-8 -*-
"""让 chatter 的文档贴合**当前实现**（单引擎、无 Chaquopy）：
  ① PROJECT_GUIDE.md 顶部那条"双引擎…保留 Python 回退（设置页可切换）"是**假的** ⇒ 改对
  ② 同文件"BotRepo（按 config.engine 选引擎）" ⇒ 已固定 native
  ③ 同文件"两个引擎互认，切换不丢登录" ⇒ 单引擎
  ④ README.md 的"设置(引擎切换)" ⇒ 该选项已移除
每处都附**实测证据**（2026-10-13 复核），并说明证据怎么来的。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
G = os.path.join(REPO, "docs", "PROJECT_GUIDE.md")
R = os.path.join(REPO, "README.md")

# ---------- ① + ② + ③ ----------
t = io.open(G, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
fixed = []

OLD1 = """> **2026-08-30 更新（B 路线迁移）**：项目已升级为「双引擎」架构——新增 `bot/` 包实现
> **Kotlin 全原生引擎**（协议层直接复用 chatter-main 的成熟代码），并保留原 Python 后端作为
> 回退引擎（设置页可切换，共享登录态）。本文的第 0~4 节描述的 Chaquopy 数据流仍是回退引擎的
> 行为；原生引擎的数据流见文末「原生引擎一节」。"""
NEW1 = """> ✅ **2026-10-13 复核（现在是单引擎，没有回退）**：上面那条 2026-08-30 的「双引擎」说明
> **已失效**，此处更正 —— 迁移的 Phase 2 已经把 Python 回退整个删掉，现在只有 Kotlin 原生引擎，
> **设置页也没有「引擎切换」了**。复核方式（可复现）：
> · 全仓检索 `chaquopy` / `ChaquopyEngine` / `PyBridge`（`*.gradle` `*.kts` `*.kt`）⇒ **0 命中**；
> · `app/build.gradle` 里没有 `chaquopy {}` 配置块，也没有 `com.chaquo.python` 插件；
> · 只用 `JAVA_HOME=<Android Studio 自带 jbr>` 跑 `gradlew.bat assembleDebug` ⇒ **BUILD SUCCESSFUL**
>   （全程不需要 Python，当年那条 "not a valid Python 3.10 command" 报错不再出现）。
> 本文第 0~4 节里关于 Chaquopy / `bridge_api.py` / `PyBridge` 的内容，**一律只作历史参考**；
> 实际链路看下面「0.0 原生引擎」与 `NATIVE_MIGRATION_PLAN.md`。"""
if OLD1 in t:
    t = t.replace(OLD1, NEW1, 1)
    fixed.append("① 更正「双引擎/保留 Python 回退」那条失效说明")

OLD2 = "  → BotRepo（按 config.engine 选引擎，默认 native）"
NEW2 = "  → BotRepo（**只有 native 一个引擎**；迁移 Phase 2 后 `engine` 字段不再使用）"
if OLD2 in t:
    t = t.replace(OLD2, NEW2, 1)
    fixed.append("② BotRepo 描述改为单引擎")

OLD3 = "凭据/游标/context_token 仍存 data/ 下与桌面版同名的 json/txt —— 两个引擎互认，切换不丢登录。"
NEW3 = ("凭据/游标/context_token 仍存 data/ 下与桌面版同名的 json/txt —— "
        "与桌面版格式一致（已无「两个引擎」可切）。")
if OLD3 in t:
    t = t.replace(OLD3, NEW3, 1)
    fixed.append("③ 去掉「两个引擎互认/切换不丢登录」")

io.open(G, "w", encoding="utf-8", newline="\n").write(t)

# ---------- ④ ----------
r = io.open(R, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "引擎切换" in r:
    r = r.replace("设置(引擎切换)", "设置", 1)
    io.open(R, "w", encoding="utf-8", newline="\n").write(r)
    fixed.append("④ README 去掉「设置(引擎切换)」")

print("已修：")
for x in fixed:
    print("   ✓", x)
if not fixed:
    print("   （无需修，可能已对齐）")

# ---------- 复核：文档里还有没有"活的"错误描述 ----------
print()
print("=== 复核：PROJECT_GUIDE 里剩余的 Chaquopy/Python 提及（应都是历史标注）===")
g2 = io.open(G, encoding="utf-8", errors="replace").read()
import re
for m in re.finditer(r"(?m)^.*(Chaquopy|chaquopy|bridge_api|PyBridge).*$", g2):
    print("   " + m.group(0).strip()[:112])
print()
print("=== 复核：README 里还有没有「引擎切换」===")
print("   ", "还有 ✗" if "引擎切换" in io.open(R, encoding="utf-8", errors="replace").read() else "已清 ✓")
