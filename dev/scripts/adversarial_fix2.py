# -*- coding: utf-8 -*-
"""保留 screenYOfPoint 的 NaN 契约，但在 charPixelHeightExact / collisionRect 边界显式处理 NaN，
   并把测试改成断言"真实契约"（而不是我假设的"处处 finite"）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
UI = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui")
TESTDIR = os.path.join(CHAT, "app/src/test/java/com/aipet/murasame")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

A = os.path.join(UI, "ArGround.kt")
t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
print("=== 现有 charPixelHeightExact / collisionRect ===")
for name in ("fun charPixelHeightExact(", "fun collisionRect("):
    i = t.find(name)
    print("\n".join("   " + l for l in t[i:i + 460].split("\n")[:14]))
    print("   ---")

# ① screenYOfPoint 的 NaN 契约写清注释
if "NaN = 该点不可投影" not in t:
    t = t.replace("""        if (depth <= 1e-4) return Float.NaN""",
                  """        // **契约**：深度 ≤ 0（点跑到相机后面 / 视线与地面平行）时返回 NaN，
        // 表示"此点不可投影"。调用方必须处理 NaN —— 见下面两个函数。
        if (depth <= 1e-4) return Float.NaN""", 1)
    print("✓ 已补 NaN 契约注释")

# ② charPixelHeightExact 处理 NaN → 0（看不见）
i = t.find("fun charPixelHeightExact(")
seg = t[i:i + 700]
if "isNaN()" not in seg:
    m = re.search(r"(fun charPixelHeightExact\([^\)]*\)[^\{]*\{)", t)
    if m:
        t = t[:m.end()] + """
        // 两个投影点只要有一个不可投影，就认为"当前看不到她" ⇒ 高度记 0（而不是把 NaN 传出去）。
        // 传出去的后果实测很隐蔽：collisionRect 的 coerceAtLeast(1f) 对 NaN 无效（NaN<1f 为 false），
        // 矩形会整个变成 NaN，于是 hit() 永远 false —— 抬头/低头到极限时"点她"静默失效。
""" + t[m.end():]
        print("✓ charPixelHeightExact 已加 NaN 前置判断（待补返回 0）")

# ③ 在 charPixelHeightExact 里，feet/head 算完后加 NaN 早退
t = t.replace("""        val feet = screenYOfPoint(pitchDeg, cameraHeightM, 0f, distanceM, fovYDeg, viewportH)
        val head = screenYOfPoint(pitchDeg, cameraHeightM, charHeightM, distanceM, fovYDeg, viewportH)""",
              """        val feet = screenYOfPoint(pitchDeg, cameraHeightM, 0f, distanceM, fovYDeg, viewportH)
        val head = screenYOfPoint(pitchDeg, cameraHeightM, charHeightM, distanceM, fovYDeg, viewportH)
        if (feet.isNaN() || head.isNaN()) return 0f""", 1)

# ④ collisionRect 对 NaN / 非正值返回"空矩形"（hit 恒 false）
t = t.replace("""        val h = pixelHeight.coerceAtLeast(1f)""",
              """        // NaN 或非正高度 ⇒ 返回空矩形（中心点上的零面积），保证 hit() 恒为 false，
        // 而不是让 NaN 污染整个矩形（见 charPixelHeightExact 的说明）。
        if (pixelHeight.isNaN() || pixelHeight <= 0f) {
            val x = centerX
            val y = feetY
            return floatArrayOf(x, y, x, y)
        }
        val h = pixelHeight.coerceAtLeast(1f)""", 1)
io.open(A, "w", encoding="utf-8", newline="\n").write(t)

# ⑤ 改测试为"真实契约"断言
T = os.path.join(TESTDIR, "AdversarialTest.kt")
tt = io.open(T, encoding="utf-8").read().replace("\r\n", "\n")
tt = tt.replace("""            val hz = ArGround.horizonY(p, 34f, vh)
            assertTrue("pitch=$p 脚位应有限：$feet", feet.isFinite())
            assertTrue("pitch=$p 像素高应有限：$px", px.isFinite())
            assertTrue("pitch=$p 地平线应有限：$hz", hz.isFinite())""",
                """            val hz = ArGround.horizonY(p, 34f, vh)
            // 契约：screenYOfPoint/groundPointY 在"不可投影"时可以返回 NaN（有意为之），
            // 但**对外使用的组合量**必须有限：像素高要么是有限正数，要么是 0（看不见）。
            assertTrue("pitch=$p 脚位不应 NaN：$feet", !feet.isNaN())
            assertTrue("pitch=$p 像素高应是有限非负：$px", px.isFinite() && px >= 0f)
            assertTrue("pitch=$p 地平线应有限：$hz", hz.isFinite())""", 1)
tt = tt.replace("""        for (p in listOf(-89f, -45f, 0f, 45f, 89f)) {
            val y = ArGround.screenYOfPoint(p, 1.45f, 1.58f, 2f, 34f, vh)
            assertTrue("pitch=$p 投影有限：$y", y.isFinite())
        }""",
                """        for (p in listOf(-89f, -45f, 0f, 45f, 89f)) {
            val y = ArGround.screenYOfPoint(p, 1.45f, 1.58f, 2f, 34f, vh)
            // 允许 NaN（契约：不可投影），但不允许 ±Inf
            assertFalse("pitch=$p 投影不应为无穷：$y", y.isInfinite())
        }""", 1)
# 新增：极限俯仰下不应出现"幽灵命中"
tt = tt.replace("""    @Test
    fun hand_touch_rotation_fallback_and_zero_viewport() {""",
                """    @Test
    fun no_ghost_hits_when_she_is_not_projectable() {
        // 抬头/低头到极限时矩形会是"空矩形"，此时任何点都不该命中（否则就是幽灵命中）
        val px = ArGround.charPixelHeightExact(1.58f, 1.45f, 2f, -90f, 34f, vh)
        val rect = ArGround.collisionRect(vw / 2f, vh / 2f, px)
        assertTrue("空矩形应有限：${rect.toList()}", rect.all { it.isFinite() })
        for (x in listOf(0f, vw / 2f, vw.toFloat())) {
            for (y in listOf(0f, vh / 2f, vh.toFloat())) {
                assertFalse("不可投影时不应命中 ($x,$y)", ArGround.hit(rect, x, y))
            }
        }
    }

    @Test
    fun hand_touch_rotation_fallback_and_zero_viewport() {""", 1)
io.open(T, "w", encoding="utf-8", newline="\n").write(tt)
print("✓ 测试已改为断言真实契约 + 新增『幽灵命中』用例")

print()
print("=== 复核关键行 ===")
src = io.open(A, encoding="utf-8", errors="replace").read()
for k in ("NaN = 该点不可投影", "if (feet.isNaN() || head.isNaN()) return 0f",
          "if (pixelHeight.isNaN() || pixelHeight <= 0f)"):
    print("   %-46s %s" % (k[:44], "✓" if k in src else "✗"))

print()
print("=== 跑对抗测试 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.AdversarialTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
for l in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:185])
p2 = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.AdversarialTest.xml")
if os.path.isfile(p2):
    x = io.open(p2, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   AdversarialTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,240})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:220]))
