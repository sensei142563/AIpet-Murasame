# -*- coding: utf-8 -*-
"""修 WaveDetector 的真 bug（单测抓到的）：
  折返判定原本比较 abs(extreme - lastX) —— 而同向那一步刚把 extreme 设成 lastX，
  所以差值恒为 0，反转永远数不到 ⇒ 永远不触发。
  正确：比较**新位置 nx 与 extreme**；幅度不够时**不翻 dir、不推进 extreme**，继续观察。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
HG = os.path.join(REPO, "app", "src", "main", "java", "com", "aipet", "murasame", "ui",
                  "HandGesture.kt")

g = io.open(HG, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

OLD = """                else if (nd != dir) {
                    // 折返：先看看上一段走了多远，够幅度才算一次有效反转
                    if (kotlin.math.abs(extreme - lastX) >= minAmplitude) {
                        reversals++
                        if (reversals >= needReversals) {
                            reset(); lastX = nx; lastTs = tsMs; extreme = nx
                            return true
                        }
                    }
                    dir = nd
                    extreme = nx
                } else {
                    extreme = nx               // 同向继续 ⇒ 推进极值
                }"""
NEW = """                else if (nd != dir) {
                    // 折返：量的是**新位置离开极值走了多远**。
                    // ⚠ 曾经写成 abs(extreme - lastX) —— 那恒等于 0（同向那一步刚把
                    //   extreme 设成 lastX），结果反转永远数不到、永远不触发。
                    //   是单测（左右反复摆动算挥手 / 触发后内部清零）把这个 bug 抓出来的。
                    if (kotlin.math.abs(nx - extreme) >= minAmplitude) {
                        reversals++
                        dir = nd
                        extreme = nx
                        if (reversals >= needReversals) {
                            reset(); lastX = nx; lastTs = tsMs; extreme = nx
                            return true
                        }
                    }
                    // 幅度不够 ⇒ **不翻 dir、不推进 extreme**，继续观察这一次折返
                } else {
                    extreme = nx               // 同向继续 ⇒ 推进极值
                }"""
if OLD in g:
    g = g.replace(OLD, NEW, 1)
    io.open(HG, "w", encoding="utf-8", newline="\n").write(g)
    print("✓ 已修折返判定")
else:
    print("✗ 锚点未命中")

print()
print("=== 重跑单测 ===")
env = dict(os.environ, JAVA_HOME=r"E:\Android Studio\jbr")
r = subprocess.run([os.path.join(REPO, "gradlew.bat"), "testDebugUnitTest", "--no-daemon",
                    "--console=plain"], cwd=REPO, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=env, timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    s = l.strip()
    if s.startswith("e: ") or "BUILD" in s or "FAILED" in s or "> HandGestureTest" in s:
        print("   " + s[:150])

# 看结果 XML
x = os.path.join(REPO, "app", "build", "test-results", "testDebugUnitTest",
                 "TEST-com.aipet.murasame.HandGestureTest.xml")
if os.path.exists(x):
    import xml.etree.ElementTree as ET
    root = ET.parse(x).getroot()
    print()
    print("=== HandGestureTest 结果 XML ===")
    print("   tests=%s failures=%s errors=%s skipped=%s"
          % (root.get("tests"), root.get("failures"), root.get("errors"), root.get("skipped")))
    for tc in root.findall("testcase"):
        bad = tc.find("failure") is not None or tc.find("error") is not None
        print("      %s %s" % ("✗" if bad else "✓", tc.get("name")))
