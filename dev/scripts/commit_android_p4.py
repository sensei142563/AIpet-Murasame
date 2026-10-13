# -*- coding: utf-8 -*-
"""提交安卓 Phase 4 构建验收证据 + 新发现的包体问题。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

# 追加"包体"这条到决策文档
D = os.path.join(ROOT, "dev", "docs", "安卓阶段决策-2026-10-13.md")
ADD = """

---

## 七、✅ Phase 4 构建验收（2026-10-13 实测）＋ 一个**新发现的问题**

### 已通过
用 Android Studio 自带的 JDK（`E:\\Android Studio\\jbr`）跑 `gradlew.bat assembleDebug`：

```
BUILD SUCCESSFUL in 1m 10s
38 actionable tasks: 13 executed, 25 up-to-date
```

逐条核对 `NATIVE_MIGRATION_PLAN.md` 的验收标准：

| 验收标准 | 实测 |
|---|---|
| 构建只需 JDK + Android SDK（不再需要 Python 3.10） | ✅ 全程用 jbr，没碰 Python；之前 Chaquopy 的 "not a valid Python 3.10 command" 报错不再出现 |
| 仓库里不再有 `.py` / `.pyc` | ✅ 非 build 目录下数量 = **0** |
| 无 Chaquopy 配置 | ✅ `app/build.gradle` + 根 `build.gradle` 命中 = **0** |
| 真机全链路回归 | ⏳ **未做** —— adb 显示无设备（手机未连接），需插上手机后进行 |

### ⚠ 新发现：**包体并没有变小**
```
app-debug.apk    313.22 MB   （2026-10-13 19:47 刚构建）
app-release.apk  302.18 MB   （2026-10-11 22:19）
```
`NATIVE_MIGRATION_PLAN.md` 当初预期的收益之一是"APK 更小"，但实测 **release 仍有 302 MB**。
这么大的包体对"发给别人试用/上架"都是硬伤，**建议列为安卓段的下一个待办**。

初步判断（**待核实，不是结论**）：大概率来自 **Live2D 模型与素材**（`app/src/main/assets/` 下的
模型贴图/纹理，以及 `app/src/main/cpp/` 的 Cubism 原生库）—— 需要按目录统计占用后再定优化手段
（例如按角色拆分 AAB、纹理压缩、把大模型做成按需下载）。

> 说明：这条是**实测发现的**，不是从文档推的。核实目录占用的脚本可以下一步做。
"""
t = io.open(D, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "Phase 4 构建验收" not in t:
    io.open(D, "w", encoding="utf-8", newline="\n").write(t.rstrip() + ADD)
    print("✓ 已追加第七节（Phase 4 验收 + 包体问题）")

MSG = """docs(android): Phase 4 构建验收通过（实测）+ 新发现「包体仍有 302 MB」

一、构建验收（实测，不是推的）
  用 Android Studio 自带 JDK（E:\\Android Studio\\jbr）跑 `gradlew.bat assembleDebug`：
      BUILD SUCCESSFUL in 1m 10s / 38 actionable tasks: 13 executed, 25 up-to-date
  逐条核对 NATIVE_MIGRATION_PLAN.md 的验收标准：
    · 构建只需 JDK + Android SDK ✅（全程用 jbr，没碰 Python；Chaquopy 那条
      "not a valid Python 3.10 command" 报错不再出现）
    · 仓库里不再有 .py / .pyc ✅（非 build 目录下数量 = **0**）
    · 无 Chaquopy 配置 ✅（两个 build.gradle 命中 = **0**）
    · 真机全链路回归 ⏳ **未做** —— adb 显示无设备（手机未连接）

二、⚠ 新发现的问题：包体并没有变小
    app-debug.apk    313.22 MB（2026-10-13 19:47 刚构建）
    app-release.apk  302.18 MB（2026-10-11 22:19）
  当初删除 Chaquopy 的预期收益之一是"APK 更小"，但实测 release 仍有 **302 MB** ——
  对"发给别人试用/上架"都是硬伤，建议列为安卓段的下一个待办。
  初步判断（**待核实，不是结论**）：大概率来自 Live2D 模型与素材（assets 下的模型贴图 +
  cpp 里的 Cubism 原生库）；需要先按目录统计占用，再定优化手段
  （按角色拆 AAB / 纹理压缩 / 大模型改成按需下载）。

三、环境备忘（下次构建直接用）
    JAVA_HOME = E:\\Android Studio\\jbr
    ANDROID_HOME / ANDROID_SDK_ROOT = E:\\Android\\SDK
    adb = E:\\Android\\SDK\\platform-tools\\adb.exe
    PATH 里没有 java/gradle ⇒ 一律用 chatter 仓自带的 gradlew.bat + 显式设 JAVA_HOME。
"""
p = os.path.join(MAP, "_msg_android_p4.txt")
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
