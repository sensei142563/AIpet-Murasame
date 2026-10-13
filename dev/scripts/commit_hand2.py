# -*- coding: utf-8 -*-
"""在 chatter 仓提交真手部检测器（MediaPipe HandLandmarker）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"

MSG = """feat(hand): 接入真手部检测器（MediaPipe HandLandmarker）—— 把"假手"换成真手

用户指示："先不管手机软件大小先实现功能"。手部互动正是要落地的那个功能。

## 为什么是这一处
`ui/HandTracker.kt` 自己写着："现状（诚实说明）：**还没有接真正的手部检测器**……
所以这里只定义接口 + 一个确定性的假手，让『关键点 → 屏幕坐标 → 命中她 → 反应』
整条链路现在就能在真机上被人工验证（按钮「试手」），等接入检测器时只需给 provider 赋值"。
⇒ 下游链路**本来就是通的**，缺的只是"真检测器"这一环。这正是"让她看着我的手"的第一步。

## 做了什么
1. `app/build.gradle`：加 `com.google.mediapipe:tasks-vision:0.10.35`。
2. 下载官方模型 `assets/hand_landmarker.task`（float16，7.46 MB，21 关键点）。
3. 新增 `ui/HandDetector.kt`：
   · 用 HandLandmarker（LIVE_STREAM + CPU delegate，GPU delegate 在部分机型不稳）加载 assets 模型；
   · `onFrame(ImageProxy, rotationDeg)` 送帧 —— **忙就丢帧**（实时流要求时间戳严格递增，
     积压反而更糟），时间戳用 `System.currentTimeMillis()`；
   · 取**食指指尖（landmark 8）**换算到**帧坐标系（像素）**，写进 `HandTracker.provider`；
   · 全程 try/catch，失败只记 `lastError`，**绝不抛**（桌宠可以退化回假手继续跑）；
   · `release()` 释放原生资源并把 provider 交还成"永远没有手"。
4. 坐标口径（**踩过一次才定下来的**）：`VrmArScreen` 拿到点后会调用
   `HandTouch.toScreen(x, y, frameW, frameH, rotationDeg, vw, vh, mirrored)`
   **自己**做旋转/镜像/缩放。所以检测器**不能**预旋转、**不能**自行镜像、**更不能**改写
   `HandTracker.rotationDeg` / `mirrored` —— 否则就是**双重变换**。
   现在：只交相机原始帧里的点 + 如实写 frameW/frameH。

## 验证
- `gradlew.bat assembleDebug`（JAVA_HOME=Android Studio 自带 jbr）⇒ **BUILD SUCCESSFUL**；
- 中途真实踩到并修掉一个编译错：MediaPipe 的 `Delegate` 是 `com.google.mediapipe.tasks.core.Delegate`
  **顶层枚举**，不是 `BaseOptions.Delegate` 的嵌套类。

## ⚠ 还没做完的一步（诚实标注，下一步就做）
**没有任何调用点**：`HandDetector.init(context, ...)` 与 `HandDetector.onFrame(imageProxy, deg)`
还没有接进相机回调（`ArScreen.kt` 的 CameraX `ImageAnalysis`/`ImageCapture` 那条路）。
在接上之前，它**只是一个编译通过、还没被使用的组件** —— 所以还不能说"手部互动能用"了。
接的时候要做三件事：① 建 `ImageAnalysis` 用例并把帧送 `HandDetector.onFrame`；
② 进页面 `init`、离开 `release`；③ 真机上把「试手」关掉，用真手验证一次。
"""
p = os.path.join(MAP, "_msg_hand2.txt")
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
