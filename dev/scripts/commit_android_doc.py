# -*- coding: utf-8 -*-
"""提交安卓阶段决策文档。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """docs(android): 安卓阶段决策 —— **不用 Termux**；3D 先验证别建模；AR 安卓用 ARCore

回答用户 2026-10-13 的三个开放问题（"必须 termux 吗 / 3D 建模难 / 3D AR 只见过 iPhone"）。
全部基于**手机仓 chatter 自己的文档与构建配置**，不靠印象。

一、Termux：**不需要**，而且"软件内置"这条路**已经走完了**
  chatter/docs/NATIVE_MIGRATION_PLAN.md 明确记录 Chaquopy（内嵌 Python）**已被删除**：
    · 第 8 行："Phase 1 与 Phase 2/3（**删除 Python 回退**、清理文档）已完成并提交"；
    · 验收标准："构建只需 JDK + Android SDK"、"仓库里不再有 .py / .pyc / Chaquopy 配置"；
    · 现在是纯原生 Kotlin：NativeEngine / PetBrain / ChatCore.kt / MemoryStore.kt /
      VisionClient.kt / ModelConfig.kt。
  实测核对：`app/build.gradle` 与根 `build.gradle` **没有任何** chaquopy/termux/python 字样。
  ⇒ Termux 当初只是"在手机上跑 Python 后端"的临时手段；已被原生重写取代，可**结案**。
  真正没做完的是 **Phase 4 回归验证**（assembleDebug + 真机全链路），这才是下一步。

二、3D：先做**技术验证**，别在验证前投入建模成本
  A 继续 Live2D（现状，0 成本）／B 用现成 VRM 模型（安卓有现成渲染方案，例如 Play 上的
  ISD Studio 3D/VRM；或 Unity + UniVRM，成本中、风险是"可商用模型难找、风格要统一"）／
  C 自己或外包建模（成本高、周期长）。建议先跑 B 的最小验证（眨眼 + 口型），跑通再决定换不换主角色。

三、3D AR：**安卓有，只是不叫 ARKit**
  你看到的 iPhone 生态是 ARKit；安卓的对应物是 **ARCore**，官方有 Android(Java/Kotlin) 快速开始
  （[Quickstart for Android | ARCore](https://developers.google.cn/ar/develop/java/quickstart)）；
  Live2D 官方平台支持列表里 Android 也在（[Cubism SDK 平台支持](https://docs.live2d.com/zh-CHS/cubism-sdk-manual/platform/)）。
  差别只在设备覆盖与工作量（原生 ARCore 要自己写平面识别/光照估计；Unity + ARCore 省事但包体大）。
  ⇒ 放在远期，先用 ARCore 的 HelloAR 样例验证"桌面上放一个模型"。

四、互动与毫米波：把"识别"与"表现"解耦
  · 识别侧只输出**少量标准参数**（手位置/捏合程度/头姿角度），表现侧由 Live2D/3D 消费
    ⇒ PC 与手机**共用同一套表现逻辑**，识别侧各自实现（手机侧可用 MediaPipe 系列，**功耗与
      帧率需按机型实测**，标注为待核）；
  · 毫米波按"参数流 → PC 侧先驱动桌宠 → 需要时再上手机"三步走；它的优势是不依赖光线、隐私友好，
    适合当 **PC 侧高级传感器**，不是手机端必选项。

五、建议执行顺序：Phase 4 回归 → 手机 Live2D 表现对齐 PC → VRM 渲染验证 → ARCore 验证 →
   互动最小闭环（如"她看着我的手"）→ 毫米波另线推进。
"""
p = os.path.join(MAP, "_msg_android.txt")
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
