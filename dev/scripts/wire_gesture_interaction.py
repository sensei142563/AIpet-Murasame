# -*- coding: utf-8 -*-
"""把捏合接进 AR 交互，并**显式固定**"命中判定只用食指"：
  · 命中（碰到她）：只用 pts[0]（食指）—— 与接真检测器之前**完全一致**
    （原来 pts 只有 1 个点，我上一轮加了拇指后若不显式限定，拇指会顺带参与命中 = 隐性行为变化）
  · 捏合（捏脸）：用 pts[0]/pts[1] 两点距离，独立去抖，独立日志，触发 window.__pinch()
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
AR = os.path.join(REPO, "app", "src", "main", "java", "com", "aipet", "murasame", "ui",
                  "VrmArScreen.kt")

t = io.open(AR, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ① 多一个捏合去抖器
OLD1 = "                val latch = HandTouch.Latch(needFrames = 3, coolingFrames = 12)"
NEW1 = ("                val latch = HandTouch.Latch(needFrames = 3, coolingFrames = 12)\n"
        "                // 捏合（捏脸）独立一条判定线 + 独立去抖：不能和\"碰到她\"共用计数，\n"
        "                // 否则捏一下会被当成碰一次、两个动作互相顶掉。\n"
        "                val pinch = HandGesture.Latch(needFrames = 3, coolingFrames = 20)")
if OLD1 in t and "HandGesture.Latch" not in t:
    t = t.replace(OLD1, NEW1, 1)
    print("✓ ① 已加捏合去抖器")
else:
    print("· ① 跳过（已加或锚点未命中）")

# ② 命中只用第一个点（显式），并加捏合判定
OLD2 = """                    var triggered: HandTouch.Zone? = null
                    for ((lx, ly) in pts) {
                        val z = HandTouch.onLandmark(
                            lx, ly, HandTracker.frameW, HandTracker.frameH, HandTracker.rotationDeg,
                            vw, vh, HandTracker.mirrored, rect, latch)
                        if (z != null) { triggered = z; break }
                    }"""
NEW2 = """                    var triggered: HandTouch.Zone? = null
                    // ⚠ **命中只用 [0]（食指指尖）**：这里以前 pts 只有 1 个点，
                    //   接真检测器后变成 [食指, 拇指]；若不显式限定，拇指会顺带参与
                    //   "碰到她"的判定 —— 那是**隐性行为变化**，不是这次要改的东西。
                    //   拇指的位置另有用途：捏合（见下）。
                    val hitPts = listOf(pts.first())
                    for ((lx, ly) in hitPts) {
                        val z = HandTouch.onLandmark(
                            lx, ly, HandTracker.frameW, HandTracker.frameH, HandTracker.rotationDeg,
                            vw, vh, HandTracker.mirrored, rect, latch)
                        if (z != null) { triggered = z; break }
                    }
                    // 捏合（捏脸）：两点距离按画面短边归一化后过阈值 + 去抖。
                    // 与命中互不影响：手可以既没碰到她又捏了一下。
                    val pinchRatio = HandGesture.pinchRatio(pts, HandTracker.frameW, HandTracker.frameH)
                    if (pinch.feed(pinchRatio)) {
                        log("捏合触发 ratio=%.3f（阈值 %.3f 帧=%dx%d）"
                            .format(pinchRatio, HandGesture.DEFAULT_PINCH_RATIO,
                                HandTracker.frameW, HandTracker.frameH))
                        webRef?.evaluateJavascript(
                            "window.__pinch && window.__pinch()", null)
                    }"""
if OLD2 in t:
    t = t.replace(OLD2, NEW2, 1)
    print("✓ ② 命中限定为食指 + 已加捏合判定（含日志）")
else:
    print("✗ ② 锚点未命中")

io.open(AR, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 复核 ===")
for i, l in enumerate(io.open(AR, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if "HandGesture" in l or "hitPts" in l or "__pinch" in l:
        print("   %4d| %s" % (i, l.strip()[:116]))

print()
print("=== 编译 + 单测 ===")
env = dict(os.environ, JAVA_HOME=r"E:\Android Studio\jbr")
for task in ("assembleDebug", "testDebugUnitTest"):
    r = subprocess.run([os.path.join(REPO, "gradlew.bat"), task, "--no-daemon", "--console=plain"],
                       cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=1800)
    out = (r.stdout or "") + (r.stderr or "")
    for l in out.split("\n"):
        s = l.strip()
        if s.startswith("e: ") or "BUILD" in s or "FAILED" in s:
            print("   [%s] %s" % (task, s[:150]))
