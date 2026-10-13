# -*- coding: utf-8 -*-
"""加"握拳"手势：
  ⚠ 契约：points[0]=食指指尖（"手的位置"，命中判定用）、points[1]=拇指指尖（捏合）。
    新增的点**只能往后追加**，绝不能插到前面 —— 否则 VrmArScreen 的命中判定会跟着变。
  新布局：[0]食指8 [1]拇指4 [2]中指12 [3]无名指16 [4]小指20 [5]掌心9
  ① HandDetector 按此布局输出（点不够时优雅退化）
  ② HandGesture 加 fistRatio / isFist（复用已有的 Latch 做去抖：语义同样是"小于阈值=触发"）
  ③ 单测（含边界与对抗）
  ④ 接进 AR：握拳触发一个已有反应（不新增 JS 钩子）+ 打日志
  ⑤ 编译 + 单测
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
UI = os.path.join(REPO, "app", "src", "main", "java", "com", "aipet", "murasame", "ui")
TEST = os.path.join(REPO, "app", "src", "test", "java", "com", "aipet", "murasame")

# ---------- ① HandDetector 输出布局 ----------
HD = os.path.join(UI, "HandDetector.kt")
t = io.open(HD, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "MIDDLE_FINGER_TIP" not in t:
    t = t.replace(
        '    private const val THUMB_TIP = 4                 // 拇指指尖下标（捏合判定要用）',
        '    private const val THUMB_TIP = 4                 // 拇指指尖下标（捏合判定要用）\n'
        '    // 追加给"握拳"用的点（只在末尾追加，[0]/[1] 的位置是契约，不能动）\n'
        '    private const val MIDDLE_FINGER_TIP = 12\n'
        '    private const val RING_FINGER_TIP = 16\n'
        '    private const val PINKY_TIP = 20\n'
        '    private const val MIDDLE_MCP = 9                // 掌心参考点')
    OLD = """            lastPoints = if (hand.size > THUMB_TIP) listOf(px(INDEX_FINGER_TIP), px(THUMB_TIP))
                         else listOf(px(INDEX_FINGER_TIP))"""
    NEW = """            // ⚠ 布局是**契约**：[0] 食指（"手的位置"）、[1] 拇指（捏合），
            //   新增的点**只能往后追加**。改动这个顺序会让 VrmArScreen 的命中判定跟着变。
            //   [2]中指 [3]无名指 [4]小指 [5]掌心 —— 供"握拳"判定使用。
            lastPoints = if (hand.size > PINKY_TIP) {
                listOf(px(INDEX_FINGER_TIP), px(THUMB_TIP), px(MIDDLE_FINGER_TIP),
                       px(RING_FINGER_TIP), px(PINKY_TIP), px(MIDDLE_MCP))
            } else if (hand.size > THUMB_TIP) {
                listOf(px(INDEX_FINGER_TIP), px(THUMB_TIP))   // 点不够就只给前面两个
            } else {
                listOf(px(INDEX_FINGER_TIP))
            }"""
    if OLD in t:
        t = t.replace(OLD, NEW, 1)
        io.open(HD, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ ① HandDetector 输出 [食指,拇指,中指,无名指,小指,掌心]（前两位不变）")
    else:
        print("✗ ① 锚点未命中")

# ---------- ② HandGesture 加握拳 ----------
HG = os.path.join(UI, "HandGesture.kt")
g = io.open(HG, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "fistRatio" not in g:
    add = '''
    /** 握拳阈值：四指指尖到掌心的**平均**距离 / 画面短边 小于它就算"握拳"。 */
    const val DEFAULT_FIST_RATIO = 0.10f

    /**
     * 握拳程度：中指/无名指/小指指尖到掌心的平均距离，按画面短边归一化。
     *
     * 为什么不用"五个指尖全算"：拇指的姿势差异非常大（有人握拳拇指在外），
     * 算进去会让阈值很难定；四指（[2][3][4]）收进掌心才是"握拳"的稳定特征。
     *
     * @return 归一化平均距离；点不够（<5）或尺寸非法时返回 [Float.MAX_VALUE]（= 不可能算作握拳）
     */
    fun fistRatio(points: List<Pair<Float, Float>>?, frameW: Int, frameH: Int): Float {
        if (points == null || points.size < 6) return Float.MAX_VALUE
        if (frameW <= 0 || frameH <= 0) return Float.MAX_VALUE
        val (cx, cy) = points[5]
        if (!cx.isFinite() || !cy.isFinite()) return Float.MAX_VALUE
        var sum = 0.0
        for (i in 2..4) {
            val (x, y) = points[i]
            if (!x.isFinite() || !y.isFinite()) return Float.MAX_VALUE
            sum += hypot((x - cx).toDouble(), (y - cy).toDouble())
        }
        val avg = (sum / 3.0).toFloat()
        return avg / max(1, minOf(frameW, frameH)).toFloat()
    }

    /** 这一帧是否"握拳"。 */
    fun isFist(points: List<Pair<Float, Float>>?, frameW: Int, frameH: Int,
               threshold: Float = DEFAULT_FIST_RATIO): Boolean =
        fistRatio(points, frameW, frameH) <= threshold
'''
    # 插到 Latch 之前
    anchor = "    /**\n     * 去抖：连续 [needFrames] 帧都捏住才算\"捏了一次\""
    if anchor in g:
        g = g.replace(anchor, add.strip() + "\n\n" + anchor, 1)
    else:
        idx = g.rfind("    class Latch(")
        g = g[:idx] + add.strip() + "\n\n" + g[idx:]
    io.open(HG, "w", encoding="utf-8", newline="\n").write(g)
    print("✓ ② HandGesture 加 fistRatio / isFist（去抖复用已有 Latch，语义同为「小于阈值=触发」）")
else:
    print("· ② 已有 fistRatio")

# ---------- ③ 单测 ----------
TF = os.path.join(TEST, "HandGestureTest.kt")
tt = io.open(TF, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "fistRatio" not in tt:
    ADD = '''
    // ── 握拳 ──

    /** 造一帧：[0]食指 [1]拇指 [2]中指 [3]无名指 [4]小指 [5]掌心 */
    private fun hand(ix: Float, iy: Float, tips: List<Pair<Float, Float>>, palm: Pair<Float, Float>) =
        listOf(ix to iy, 0f to 0f) + tips + listOf(palm)

    @Test
    fun `四指收进掌心算握拳`() {
        // 三个指尖离掌心各 10px，画面 720 短边 ⇒ 10/720 ≈ 0.0139 < 0.10
        val p = hand(100f, 100f, listOf(10f to 10f, 12f to 10f, 11f to 12f), 10f to 10f)
        assertTrue(HandGesture.isFist(p, 1280, 720))
    }

    @Test
    fun `手指张开不算握拳`() {
        val p = hand(100f, 100f, listOf(200f to 10f, 200f to 12f, 200f to 11f), 10f to 10f)
        assertFalse(HandGesture.isFist(p, 1280, 720))
    }

    @Test
    fun `握拳边界：恰好等于阈值算握拳`() {
        // 短边 100 ⇒ 阈值 10px；三点都在 (10,0)，掌心 (0,0) ⇒ 平均距离 10 ⇒ 等于阈值
        val p = hand(1f, 1f, listOf(10f to 0f, 10f to 0f, 10f to 0f), 0f to 0f)
        assertTrue(HandGesture.isFist(p, 100, 100))
    }

    @Test
    fun `握拳：点不够时不误判`() {
        assertFalse(HandGesture.isFist(null, 1280, 720))
        assertFalse(HandGesture.isFist(listOf(1f to 1f, 2f to 2f), 1280, 720))
    }

    @Test
    fun `握拳：尺寸为0或NaN时不除零不误判`() {
        val p = hand(1f, 1f, listOf(10f to 0f, 10f to 0f, 10f to 0f), 0f to 0f)
        assertFalse(HandGesture.isFist(p, 0, 0))
        val bad = hand(1f, 1f, listOf(Float.NaN to 0f, 10f to 0f, 10f to 0f), 0f to 0f)
        assertFalse(HandGesture.isFist(bad, 1280, 720))
    }

    @Test
    fun `握拳与捏合互不干扰：捏合时通常也能算握拳，但两者各有阈值`() {
        // 指尖贴掌心（握拳）+ 拇指↔食指贴近（捏合）可以同时成立 —— 这是允许的，
        // 两条判定线各自去抖，谁先满足谁触发（不要让一个把另一个顶掉）。
        val p = hand(2f, 2f, listOf(10f to 0f, 10f to 0f, 10f to 0f), 0f to 0f)
        assertTrue(HandGesture.isFist(p, 1280, 720))
        assertTrue(HandGesture.isPinch(p, 1280, 720))
    }
'''
    idx = tt.rstrip().rfind("}")
    tt = tt[:idx] + ADD + tt[idx:]
    io.open(TF, "w", encoding="utf-8", newline="\n").write(tt)
    print("✓ ③ 加 6 个握拳单测")
else:
    print("· ③ 已有握拳单测")

# ---------- ④ 接进 AR ----------
AR = os.path.join(UI, "VrmArScreen.kt")
a = io.open(AR, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "fistRatio" not in a:
    OLD = '        val pinch = HandGesture.Latch(needFrames = 3, coolingFrames = 20)'
    NEW = (OLD + "\n"
           "        // 握拳也走同一条判定线（Latch 的语义就是\"比值小于阈值=触发\"，可复用）；\n"
           "        // 冷却给长一点：握拳是\"使劲\"的动作，容易连续好几帧都满足。\n"
           "        val fist = HandGesture.Latch(needFrames = 4, coolingFrames = 30)")
    if OLD in a:
        a = a.replace(OLD, NEW, 1)
        print("✓ ④a 已加握拳去抖器")
    OLD2 = """                    val pinchRatio = HandGesture.pinchRatio(pts, HandTracker.frameW, HandTracker.frameH)"""
    NEW2 = """                    // 握拳：四指指尖到掌心的平均距离。同样**只在有手时**判定。
                    // 反应复用已有的 __poke（不新增 JS 钩子）：握拳当作一次"用力戳"。
                    val fistRatio = HandGesture.fistRatio(pts, HandTracker.frameW, HandTracker.frameH)
                    if (fist.feed(fistRatio)) {
                        log("握拳触发 ratio=%.3f（阈值 %.3f）".format(fistRatio, HandGesture.DEFAULT_FIST_RATIO))
                        webRef?.evaluateJavascript("window.__poke && window.__poke('BODY')", null)
                    }

                    val pinchRatio = HandGesture.pinchRatio(pts, HandTracker.frameW, HandTracker.frameH)"""
    if OLD2 in a:
        a = a.replace(OLD2, NEW2, 1)
        io.open(AR, "w", encoding="utf-8", newline="\n").write(a)
        print("✓ ④b 已接进 AR 循环（含日志）")
    else:
        print("✗ ④b 锚点未命中")
else:
    print("· ④ 已接")

# ---------- ⑤ 验证 ----------
print()
print("=== ⑤ 编译 + 单测 ===")
env = dict(os.environ, JAVA_HOME=r"E:\Android Studio\jbr")
for task in ("assembleDebug", "testDebugUnitTest"):
    r = subprocess.run([os.path.join(REPO, "gradlew.bat"), task, "--no-daemon", "--console=plain"],
                       cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=1800)
    for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
        s = l.strip()
        if s.startswith("e: ") or "BUILD" in s or "FAILED" in s:
            print("   [%s] %s" % (task, s[:150]))
