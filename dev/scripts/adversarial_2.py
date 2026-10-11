# -*- coding: utf-8 -*-
"""按 ArGround 的**真实签名**（全 Float、参数顺序照抄）重写对抗测试并运行。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

io.open(os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/AdversarialTest.kt"),
        "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import com.aipet.murasame.ui.ArGround
import com.aipet.murasame.ui.FakeHand
import com.aipet.murasame.ui.HandTouch
import com.aipet.murasame.ui.VadGate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 对抗/边界测试：喂极端输入，断言"不崩、不出 NaN、边界合理"。
 *
 * 说明：本文件第一版我**没读签名就写调用**，结果 10 个编译错误（ArGround 全用 Float，
 * 且 screenYOfPoint 的参数顺序是 (pitchDeg, cameraHeightM, yWorldM, distanceM, fovYDeg, viewportH)）。
 * 现在全部按 ArGround.kt 里的真实签名书写。
 */
class AdversarialTest {

    private val vh = 1920
    private val vw = 1080

    @Test
    fun ar_ground_survives_extreme_pitch() {
        for (p in listOf(-90f, -89.9f, -45f, 0f, 45f, 89.9f, 90f, 180f, -180f)) {
            val feet = ArGround.groundPointY(p, 1.45f, 2f, 34f, vh)
            val px = ArGround.charPixelHeightExact(1.58f, 1.45f, 2f, p, 34f, vh)
            val hz = ArGround.horizonY(p, 34f, vh)
            assertTrue("pitch=$p 脚位应有限：$feet", feet.isFinite())
            assertTrue("pitch=$p 像素高应有限：$px", px.isFinite())
            assertTrue("pitch=$p 地平线应有限：$hz", hz.isFinite())
        }
    }

    @Test
    fun ar_ground_survives_degenerate_viewport_and_geometry() {
        val cases = listOf(
            Triple(34f, 0, 1.45f), Triple(0f, vh, 1.45f), Triple(180f, vh, 1.45f),
            Triple(34f, 1, 1.45f), Triple(34f, vh, 0f), Triple(34f, vh, -1f),
            Triple(-10f, vh, 1.45f), Triple(360f, vh, 1.45f),
        )
        for ((fov, h, camH) in cases) {
            val feet = ArGround.groundPointY(0f, camH, 2f, fov, h)
            val px = ArGround.charPixelHeightExact(1.58f, camH, 2f, 0f, fov, h)
            assertFalse("fov=$fov h=$h camH=$camH 出现 NaN（脚位 $feet / 高 $px）",
                feet.isNaN() || px.isNaN())
            // 距离 0（贴脸）：实现里用 coerceAtLeast(0.05f) 兜底，不应 NaN
            val f0 = ArGround.groundPointY(0f, camH, 0f, fov, h)
            val p0 = ArGround.charPixelHeightExact(1.58f, camH, 0f, 0f, fov, h)
            assertFalse("距离 0 出现 NaN（脚位 $f0 / 高 $p0）", f0.isNaN() || p0.isNaN())
        }
    }

    @Test
    fun collision_rect_is_well_formed_for_absurd_heights() {
        for (px in listOf(-100f, 0f, 1f, 1000f, 1e7f)) {
            val r = ArGround.collisionRect(vw / 2f, vh / 2f, px)
            assertTrue("px=$px 矩形应有限：${r.toList()}", r.all { it.isFinite() })
            assertTrue("px=$px 左≤右（${r[0]} ≤ ${r[2]}）", r[2] >= r[0])
            assertTrue("px=$px 上≤下（${r[1]} ≤ ${r[3]}）", r[3] >= r[1])
        }
        // aspect 为负/0 时也不应崩
        for (a in listOf(-1f, 0f, 0.001f, 10f)) {
            val r = ArGround.collisionRect(100f, 100f, 200f, a)
            assertTrue("aspect=$a 应有限", r.all { it.isFinite() })
        }
    }

    @Test
    fun screen_projection_extremes_are_finite() {
        for (p in listOf(-89f, -45f, 0f, 45f, 89f)) {
            val y = ArGround.screenYOfPoint(p, 1.45f, 1.58f, 2f, 34f, vh)
            assertTrue("pitch=$p 投影有限：$y", y.isFinite())
        }
        // yWorld 极端（远高于相机 / 远低于地面）
        for (yw in listOf(-100f, 0f, 1.58f, 100f)) {
            val y = ArGround.screenYOfPoint(0f, 1.45f, yw, 2f, 34f, vh)
            assertTrue("yWorld=$yw 投影有限：$y", y.isFinite())
        }
        // 视口高 1 与 0 的边界
        for (h in listOf(0, 1, 2)) {
            val f = ArGround.focalPx(h, 34f)
            assertTrue("viewportH=$h focal 有限：$f", f.isFinite())
        }
    }

    @Test
    fun horizon_and_coverage_stay_in_range() {
        for (p in listOf(-60f, -10f, 0f, 10f, 60f, 90f, 180f)) {
            val c = ArGround.groundCoverage(p, 34f, vh)
            assertTrue("pitch=$p 地面占比应在 0..1：$c", c.isFinite() && c >= -0.001f && c <= 1.001f)
        }
    }

    @Test
    fun pitch_from_accelerometer_extremes() {
        // 手机翻到各种姿态：不应 NaN（水平分量为 0 时 atan2 仍定义良好）
        for (g in listOf(
            Triple(0f, 0f, 0f), Triple(0f, 0f, 9.8f), Triple(0f, 0f, -9.8f),
            Triple(9.8f, 0f, 0f), Triple(0f, 9.8f, 0f), Triple(9.8f, 9.8f, 9.8f),
            Triple(-9.8f, -9.8f, -9.8f))) {
            val d = ArGround.pitchDeg(g.first, g.second, g.third)
            assertFalse("g=$g 俯仰角不应 NaN", d.isNaN())
            assertTrue("g=$g 俯仰角应在 -90..90：$d", d >= -90.001f && d <= 90.001f)
        }
    }

    @Test
    fun hand_touch_rotation_fallback_and_zero_viewport() {
        val a = HandTouch.toScreen(100f, 100f, 1000, 1000, 45, 1000, 1000)
        val b = HandTouch.toScreen(100f, 100f, 1000, 1000, 0, 1000, 1000)
        assertEquals("非法旋转角应等价于不旋转", b.first, a.first, 0.01f)
        assertEquals(b.second, a.second, 0.01f)
        for ((w, h) in listOf(0 to 0, 1 to 1, 0 to 1000, 1000 to 0)) {
            val p = HandTouch.toScreen(0f, 0f, w, h, 90, w, h)
            assertFalse("帧/视口 ${w}x$h 不应 NaN：$p", p.first.isNaN() || p.second.isNaN())
        }
    }

    @Test
    fun latch_with_zero_needs_still_can_trigger() {
        val latch = HandTouch.Latch(needFrames = 0, coolingFrames = 0)
        var any = latch.feed(HandTouch.Zone.BODY) != null
        repeat(5) { if (latch.feed(HandTouch.Zone.BODY) != null) any = true }
        assertTrue("cooling=0 + needFrames=0 时应至少能触发一次", any)
    }

    @Test
    fun fake_hand_handles_negative_and_huge_time() {
        for (t in listOf(-1L, -4000L, -123456L, 0L, 1L, Long.MAX_VALUE / 3)) {
            val (x, y) = FakeHand.pointAt(t, 1280, 720)
            assertTrue("t=$t 时 x 应在帧内：$x", x.isFinite() && x >= -1f && x <= 1281f)
            assertTrue("t=$t 时 y 应在帧内：$y", y.isFinite() && y >= -1f && y <= 721f)
        }
    }

    @Test
    fun fake_hand_with_absurd_period() {
        for (period in listOf(1L, 2L, 100000L)) {
            val (x, y) = FakeHand.pointAt(1234L, 1280, 720, period)
            assertTrue("period=$period x 应在帧内：$x", x.isFinite() && x >= -1f && x <= 1281f)
            assertTrue("period=$period y 应在帧内：$y", y.isFinite() && y >= -1f && y <= 721f)
        }
    }

    @Test
    fun vad_gate_rejects_constant_dc() {
        // 恒定直流不是声音，只是偏移。能量法只看 RMS ⇒ 会把直流当成"很大声"，
        // 这正是本测试要暴露的问题（对照：Silero 模型能正确拒绝）。
        val dc = FloatArray(16000) { 0.3f }
        val r = VadGate.analyze(dc, 16000)
        assertFalse("恒定直流不应算说话（noise=${r.noiseRms} peak=${r.peakRms}）", r.isSpeech)
    }

    @Test
    fun vad_gate_survives_degenerate_inputs() {
        assertFalse(VadGate.analyze(FloatArray(1) { 0.5f }, 16000).isSpeech)
        assertFalse(VadGate.analyze(FloatArray(37) { 0.5f }, 16000).isSpeech)
        assertFalse(VadGate.analyze(FloatArray(1600) { Float.NaN }, 16000).isSpeech)
        assertFalse(VadGate.analyze(FloatArray(1600) { 0f }, 16000).isSpeech)
        val huge = VadGate.analyze(FloatArray(16000) { 1e9f }, 16000)
        assertTrue("极大值不应崩（frames=${huge.frames}）", huge.frames >= 0)
        val z = VadGate.analyze(FloatArray(1600) { 0.1f }, 0)
        assertTrue("采样率 0 不应崩（frames=${z.frames}）", z.frames >= 0)
    }
}
''')
print("✓ 已按真签名重写 AdversarialTest.kt")

print()
print("=== 跑对抗测试 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.AdversarialTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
for l in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:180])
p2 = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.AdversarialTest.xml")
if os.path.isfile(p2):
    x = io.open(p2, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   AdversarialTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,300})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:260]))
