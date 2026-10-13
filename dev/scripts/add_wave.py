# -*- coding: utf-8 -*-
"""加"挥手"手势（**时序**判定）+ 单测，并配一个专属的 __wave 反应。
  挥手和捏合/握拳不同：它不是一个"比值"，而是**一段时间内在左右之间反复**。
  ⇒ 写成一个小的状态机（纯逻辑，可 JVM 单测）：
       · 记录上一次的"极值点"与移动方向；
       · 只有从极值点折返、且幅度超过阈值，才算一次**反转**；
       · 窗口内攒够 needReversals 次反转 ⇒ 判定为挥手，然后清零；
       · 超时没有新动作 ⇒ 重置（避免"上次挥完，这次手一动就触发"）。
"""
import io
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
UI = os.path.join(REPO, "app", "src", "main", "java", "com", "aipet", "murasame", "ui")
TEST = os.path.join(REPO, "app", "src", "test", "java", "com", "aipet", "murasame")
HTML = os.path.join(REPO, "app", "src", "main", "assets", "vrm", "index.html")

# ---------- ① HandGesture 加 WaveDetector ----------
HG = os.path.join(UI, "HandGesture.kt")
g = io.open(HG, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "class WaveDetector" not in g:
    wave = '''
    /**
     * 挥手检测（**时序**，不是比值）。
     *
     * 挥手在单帧里看不出来 —— 它表现为"在一段时间内左右反复"。所以这里是一个小状态机：
     *   · 记录上一次的极值点与当前移动方向；
     *   · 只有从极值点**折返**、且幅度超过 [minAmplitude]，才算一次**反转**；
     *   · 窗口 [maxGapMs] 内攒够 [needReversals] 次反转 ⇒ 判定为挥手并清零；
     *   · 超时没有新动作 ⇒ 重置（否则"上次挥完，这次手一动"会立刻再次触发）。
     *
     * 入参 [nx] 是**横向归一化坐标**（例如食指指尖的屏幕横坐标 / 视口宽度 ∈ [0,1] 或 [-1,1]，
     * 只要量纲一致即可）；[minAmplitude] 用同一量纲。
     */
    class WaveDetector(
        private val needReversals: Int = 4,
        private val minAmplitude: Float = 0.10f,
        private val maxGapMs: Long = 2500L,
    ) {
        private var lastX = Float.NaN
        private var lastTs = 0L
        private var dir = 0                  // 1 = 向右，-1 = 向左，0 = 未知
        private var extreme = Float.NaN      // 当前方向上的极值（用来量幅度）
        private var reversals = 0

        /** 每帧调用一次；返回本次是否判定为"挥手"（判定成功后内部清零）。 */
        fun feed(nx: Float, tsMs: Long): Boolean {
            if (!nx.isFinite() || minAmplitude <= 0f) return false
            if (lastX.isNaN()) { lastX = nx; lastTs = tsMs; extreme = nx; return false }
            if (tsMs - lastTs > maxGapMs) {      // 太久没动 ⇒ 重新开始
                lastX = nx; lastTs = tsMs; dir = 0; extreme = nx; reversals = 0
                return false
            }
            val d = nx - lastX
            if (d != 0f) {
                val nd = if (d > 0f) 1 else -1
                if (dir == 0) { dir = nd; extreme = nx }
                else if (nd != dir) {
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
                }
            }
            lastX = nx
            lastTs = tsMs
            return false
        }

        fun reset() { lastX = Float.NaN; lastTs = 0L; dir = 0; extreme = Float.NaN; reversals = 0 }
    }
'''
    idx = g.rfind("}")
    g = g[:idx] + wave + g[idx:]
    io.open(HG, "w", encoding="utf-8", newline="\n").write(g)
    print("✓ ① HandGesture 加 WaveDetector")
else:
    print("· ① 已有 WaveDetector")

# ---------- ② 单测 ----------
TF = os.path.join(TEST, "HandGestureTest.kt")
tt = io.open(TF, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "WaveDetector" not in tt:
    ADD = '''
    // ── 挥手（时序） ──

    /** 按固定步长喂一串位置，返回是否在过程中触发过。 */
    private fun runWave(w: HandGesture.WaveDetector, xs: List<Float>, stepMs: Long = 50L): Boolean {
        var fired = false
        xs.forEachIndexed { i, x -> if (w.feed(x, i * stepMs)) fired = true }
        return fired
    }

    @Test
    fun `左右反复摆动算挥手`() {
        val w = HandGesture.WaveDetector(needReversals = 4, minAmplitude = 0.10f)
        // 0.0 → 0.3 → 0.0 → 0.3 → 0.0 …（每段 0.3，远超阈值）
        val xs = listOf(0.0f, 0.15f, 0.30f, 0.15f, 0.0f, 0.15f, 0.30f, 0.15f, 0.0f, 0.15f, 0.30f)
        assertTrue(runWave(w, xs))
    }

    @Test
    fun `一直朝一个方向移动不算挥手`() {
        val w = HandGesture.WaveDetector(needReversals = 2, minAmplitude = 0.10f)
        val xs = (0..20).map { it * 0.05f }      // 单调递增
        assertFalse(runWave(w, xs))
    }

    @Test
    fun `小幅抖动不算挥手（幅度门槛）`() {
        val w = HandGesture.WaveDetector(needReversals = 2, minAmplitude = 0.20f)
        // 每次只动 0.02，来回抖 20 次也不该触发
        val xs = (0..20).map { if (it % 2 == 0) 0.00f else 0.02f }
        assertFalse(runWave(w, xs))
    }

    @Test
    fun `长时间不动会重置（不会把上次的计数留到现在）`() {
        val w = HandGesture.WaveDetector(needReversals = 3, minAmplitude = 0.10f)
        // 先摆两下（不够 3 次），停 5 秒，再摆两下 —— 不该累计触发
        assertFalse(w.feed(0.0f, 0L)); assertFalse(w.feed(0.3f, 50L))
        assertFalse(w.feed(0.0f, 100L)); assertFalse(w.feed(0.3f, 150L))
        assertFalse(w.feed(0.0f, 10_000L))            // 超时 ⇒ 重置
        assertFalse(w.feed(0.3f, 10_050L))
        assertFalse(w.feed(0.0f, 10_100L))
    }

    @Test
    fun `挥手：NaN 与非法阈值不触发`() {
        val w = HandGesture.WaveDetector(needReversals = 2, minAmplitude = 0.1f)
        assertFalse(w.feed(Float.NaN, 0L))
        assertFalse(w.feed(0.0f, 10L))
        val z = HandGesture.WaveDetector(needReversals = 2, minAmplitude = 0f)
        assertFalse(z.feed(0.0f, 0L)); assertFalse(z.feed(1.0f, 10L))
    }

    @Test
    fun `触发后内部清零（不会连着触发第二次）`() {
        val w = HandGesture.WaveDetector(needReversals = 2, minAmplitude = 0.10f)
        val xs = listOf(0.0f, 0.3f, 0.0f, 0.3f, 0.0f)
        var count = 0
        xs.forEachIndexed { i, x -> if (w.feed(x, i * 50L)) count++ }
        assertEquals(1, count)
    }
'''
    idx = tt.rstrip().rfind("}")
    tt = tt[:idx] + ADD + tt[idx:]
    io.open(TF, "w", encoding="utf-8", newline="\n").write(tt)
    print("✓ ② 加 6 个挥手单测")
else:
    print("· ② 已有挥手单测")

# ---------- ③ JS：__wave ----------
h = io.open(HTML, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "window.__wave" not in h:
    WAVE = '''
// 向她挥手：她开心地**回一次招呼**（和"被戳""被捏"区分开 —— 这是"她认出你在打招呼"）。
window.__wave = function () {
  if (!window.__vrm) return false;
  try {
    const em = window.__vrm.expressionManager;
    if (em) {
      const names = Object.keys(em.expressionMap || {});
      const want = names.find(n => /happy|joy|relaxed/i.test(n)) || names[0];
      if (want) { em.setValue(want, 1.0); setTimeout(() => { try { em.setValue(want, 0); } catch (e) {} }, 1400); }
    }
    const target = window.__lookTarget;
    const s = window.__vrm.scene;
    const y0 = s.position.y;
    const t0 = performance.now();
    (function greet() {
      const k = (performance.now() - t0) / 600;
      if (k >= 1) { s.position.y = y0; if (target) target.position.x = 0; return; }
      const e = Math.sin(k * Math.PI);
      s.position.y = y0 + e * 0.05;                 // 轻轻颠一下（比被戳更"高兴"）
      if (target) target.position.x = e * 0.30;     // 视线也跟着晃一下，像在回应
      requestAnimationFrame(greet);
    })();
  } catch (e) {}
  return true;
};
'''
    anchor = "window.__setFov = function (deg) {"
    if anchor in h:
        h = h.replace(anchor, WAVE.strip() + "\n" + anchor, 1)
        io.open(HTML, "w", encoding="utf-8", newline="\n").write(h)
        print("✓ ③ 已加 window.__wave")
    else:
        print("✗ ③ 锚点未命中")
else:
    print("· ③ 已有 __wave")

# ---------- ④ 接进 AR ----------
AR = os.path.join(UI, "VrmArScreen.kt")
a = io.open(AR, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "WaveDetector" not in a:
    OLD = '        val fist = HandGesture.Latch(needFrames = 4, coolingFrames = 30)'
    NEW = (OLD + "\n"
           "        // 挥手是**时序**判定（左右反复），所以是一个状态机而不是阈值 Latch。\n"
           "        val wave = HandGesture.WaveDetector(needReversals = 4, minAmplitude = 0.10f)")
    OLD2 = """                    // 视线跟随：把食指指尖换算到屏幕再归一化到 [-1,1] 喂给 3D 页面，"""
    NEW2 = """                    // 挥手：用食指的**屏幕横向归一化坐标**喂时序状态机（量纲一致即可）。
                    runCatching {
                        val f0 = pts.first()
                        val wsc = HandTouch.toScreen(f0.first, f0.second, HandTracker.frameW,
                            HandTracker.frameH, HandTracker.rotationDeg, vw, vh, HandTracker.mirrored)
                        if (vw > 0 && wave.feed(wsc.first / vw, System.currentTimeMillis())) {
                            log("挥手触发（横向归一化=%.3f）".format(wsc.first / vw))
                            webRef?.evaluateJavascript("window.__wave && window.__wave()", null)
                        }
                    }

                    // 视线跟随：把食指指尖换算到屏幕再归一化到 [-1,1] 喂给 3D 页面，"""
    if OLD in a and OLD2 in a:
        a = a.replace(OLD, NEW, 1).replace(OLD2, NEW2, 1)
        io.open(AR, "w", encoding="utf-8", newline="\n").write(a)
        print("✓ ④ 已接进 AR（含日志）")
    else:
        print("✗ ④ 锚点未命中")
else:
    print("· ④ 已接")

# ---------- ⑤ 验证 ----------
print()
print("=== ⑤ 验证 ===")
node = shutil.which("node") or shutil.which("node.exe")
m = re.search(r"window\.__wave = function[\s\S]*?\n\};", io.open(HTML, encoding="utf-8",
                                                                 errors="replace").read())
if m and node:
    tmp = os.path.join(os.environ.get("TEMP", "."), "wave_check.js")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(m.group(0) + "\n")
    r = subprocess.run([node, "--check", tmp], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    print("   node --check __wave:", "OK ✓" if r.returncode == 0 else (r.stderr or "")[:200])
env = dict(os.environ, JAVA_HOME=r"E:\Android Studio\jbr")
for task in ("assembleDebug", "testDebugUnitTest"):
    r = subprocess.run([os.path.join(REPO, "gradlew.bat"), task, "--no-daemon", "--console=plain"],
                       cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=1800)
    for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
        s = l.strip()
        if s.startswith("e: ") or "BUILD" in s or "FAILED" in s:
            print("   [%s] %s" % (task, s[:150]))
