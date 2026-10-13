# -*- coding: utf-8 -*-
"""实现"她的眼睛看着我的手"（视线跟随）：
  ① vrm/index.html：加 window.__lookAt(nx, ny) —— 用 three-vrm 的 lookAt.target（Object3D）
  ② VrmArScreen：每帧把食指指尖经 HandTouch.toScreen 换算到屏幕 → 归一化 [-1,1] → 调用 __lookAt
  ③ JS 用 node --check 验；Kotlin 编译 + 单测
"""
import io
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
HTML = os.path.join(REPO, "app", "src", "main", "assets", "vrm", "index.html")
AR = os.path.join(REPO, "app", "src", "main", "java", "com", "aipet", "murasame", "ui",
                  "VrmArScreen.kt")

# ---------- ① JS ----------
h = io.open(HTML, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
LOOK = '''
// 她的视线跟着手：three-vrm 的 lookAt.target 接受一个 Object3D，
// 把它的位置放到"眼前一小块区域"里，眼睛（以及自动跟动的头）就会看向那里。
// 入参是**屏幕归一化坐标** nx, ny ∈ [-1, 1]（0,0 = 屏幕中心，y 向下为正）。
window.__lookTarget = null;
window.__lookAt = function (nx, ny) {
  if (!window.__vrm) return false;
  try {
    if (!window.__lookTarget) {
      window.__lookTarget = new THREE.Object3D();
      scene.add(window.__lookTarget);
      if (window.__vrm.lookAt) window.__vrm.lookAt.target = window.__lookTarget;
    }
    const cx = Math.max(-1, Math.min(1, Number(nx) || 0));
    const cy = Math.max(-1, Math.min(1, Number(ny) || 0));
    // 角色站在原点、脸朝 +Z（相机在 +Z 侧）：把目标放在她前方 0.6m 的一个小平面内。
    // 范围刻意收窄（±0.45 / ±0.30 米），否则手一挥眼睛就"翻"到极限，看着不自然。
    window.__lookTarget.position.set(cx * 0.45, 1.30 - cy * 0.30, 0.6);
    return true;
  } catch (e) {
    return false;
  }
};
'''
if "window.__lookAt" in h:
    print("· ① 已有 __lookAt")
else:
    anchor = "window.__setFov = function (deg) {"
    if anchor in h:
        h = h.replace(anchor, LOOK.strip() + "\n" + anchor, 1)
        io.open(HTML, "w", encoding="utf-8", newline="\n").write(h)
        print("✓ ① 已加 window.__lookAt（lookAt.target）")
    else:
        print("✗ ① 锚点未命中")

# ---------- ② Kotlin ----------
t = io.open(AR, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = """                    // 捏合（捏脸）：两点距离按画面短边归一化后过阈值 + 去抖。"""
NEW = """                    // 视线跟随：把食指指尖换算到屏幕再归一化到 [-1,1] 喂给 3D 页面，
                    // 让她"看着我的手"。⚠ 只在**有手**时调用；没手就不动（保持上一次视线，
                    // 免得手一消失她的眼睛就"啪"地弹回正前方，反而突兀）。
                    runCatching {
                        val p0 = pts.first()
                        val sc = HandTouch.toScreen(p0.first, p0.second, HandTracker.frameW,
                            HandTracker.frameH, HandTracker.rotationDeg, vw, vh, HandTracker.mirrored)
                        if (vw > 0 && vh > 0) {
                            val nx = (sc.first / vw) * 2f - 1f
                            val ny = (sc.second / vh) * 2f - 1f
                            webRef?.evaluateJavascript(
                                "window.__lookAt && window.__lookAt(%.3f,%.3f)".format(nx, ny), null)
                        }
                    }

                    // 捏合（捏脸）：两点距离按画面短边归一化后过阈值 + 去抖。"""
if OLD in t:
    t = t.replace(OLD, NEW, 1)
    io.open(AR, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ ② 已在 AR 循环里加视线跟随调用")
else:
    print("✗ ② 锚点未命中")

# ---------- ③ 验证 ----------
print()
print("=== ③ 验证 ===")
node = shutil.which("node") or shutil.which("node.exe")
m = re.search(r"window\.__lookAt = function[\s\S]*?\n\};", io.open(HTML, encoding="utf-8",
                                                                  errors="replace").read())
if m and node:
    tmp = os.path.join(os.environ.get("TEMP", "."), "look_check.js")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(m.group(0) + "\n")
    r = subprocess.run([node, "--check", tmp], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    print("   node --check __lookAt:", "OK ✓" if r.returncode == 0 else (r.stderr or "")[:200])
else:
    print("   ⚠ 没抽到片段或没有 node")

env = dict(os.environ, JAVA_HOME=r"E:\Android Studio\jbr")
for task in ("assembleDebug", "testDebugUnitTest"):
    r = subprocess.run([os.path.join(REPO, "gradlew.bat"), task, "--no-daemon", "--console=plain"],
                       cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=1800)
    for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
        s = l.strip()
        if s.startswith("e: ") or "BUILD" in s or "FAILED" in s:
            print("   [%s] %s" % (task, s[:150]))
