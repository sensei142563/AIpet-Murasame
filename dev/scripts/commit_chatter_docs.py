# -*- coding: utf-8 -*-
"""在 chatter 仓提交文档与实现对齐。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"

MSG = """docs: 文档与实现对齐 —— 更正「双引擎/可切回 Python」这条已经失效的说明

背景：`NATIVE_MIGRATION_PLAN.md` 的 Phase 3 要求"README / PROJECT_GUIDE 删掉 Python 引擎、
Chaquopy、迁移对照表的回退侧描述，架构图简化为单引擎"。这次逐条核对，发现**文档自相矛盾**。

## 复核证据（2026-10-13，可复现）
- 全仓检索 `chaquopy` / `ChaquopyEngine` / `PyBridge`（`*.gradle` `*.kts` `*.kt`）⇒ **0 命中**；
- `app/build.gradle` 无 `chaquopy {}` 配置块、无 `com.chaquo.python` 插件；
- 只用 Android Studio 自带 JDK 跑 `gradlew.bat assembleDebug` ⇒ **BUILD SUCCESSFUL in 1m 10s**
  （全程不需要 Python；当年 "not a valid Python 3.10 command" 报错不再出现）；
- 仓库里 `.py` / `.pyc`（非 build 目录）⇒ **0 个**。
⇒ 代码侧早就干净了，**是文档没跟上**。

## 改了什么
1. `docs/PROJECT_GUIDE.md` 顶部有**两条相反的说明**：
   第 5~8 行说"Python 后端已移除、只保留 Kotlin 原生引擎"（正确），
   第 10~13 行却说"已升级为**「双引擎」**架构……**保留原 Python 后端作为回退引擎
   （设置页可切换，共享登录态）**"（**假的**，Phase 2 已删）。
   ⇒ 把失效那条**原地更正**为「✅ 2026-10-13 复核（现在是单引擎，没有回退）」，
     并把上面三条复核证据写进注释，方便下次不用再查。
2. 同文件数据流里的 `BotRepo（按 config.engine 选引擎，默认 native）`
   ⇒ 改为「**只有 native 一个引擎**；迁移 Phase 2 后 `engine` 字段不再使用」。
3. 同文件结尾「两个引擎互认，切换不丢登录」
   ⇒ 改为「与桌面版格式一致（已无「两个引擎」可切）」。
4. `README.md` 的目录注释 `设置(引擎切换)` ⇒ `设置`（该选项已随 Phase 2 移除）。

## 没动的部分（有意）
`PROJECT_GUIDE.md` 第 0~4 节仍保留 Chaquopy / `bridge_api.py` / `PyBridge` 的历史描述 ——
顶部说明已明确标注它们**只作历史参考**，实际链路看「0.0 原生引擎」。
**不改历史正文**：那是 255 行的叙述性文档，逐段重写风险大于收益；
真正要紧的是"别让读者以为现在还能切回 Python"，这一条已经解决。
"""
p = os.path.join(MAP, "_msg_chatter_docs.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", REPO, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", REPO, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", REPO, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", REPO, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
