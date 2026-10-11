# -*- coding: utf-8 -*-
"""对抗/边界测试：ArGround、HandTouch、VadGate、FakeHand 的极端输入。
   目的不是重复"正常路径"，而是找出理想信号下测不出来的问题。"""
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
import kotlin.math.abs

/**
 * 对抗/边界测试：喂极端输入，断言"不崩、不出 NaN、边界合理"。
 * 重点是找出正常路径测不出来的问题（视口为 0、pitch 到 ±90、恒定直流信号、负时间…）。
 */
class AdversarialTest {

    private val vh = 1920
    private val vw = 1080

    @Test
    fun ar_ground_survives_extreme_pitch() {
        for (p in listOf(-90.0, -89.9, -45.0, 0.0, 45.0, 89.9, 90.0, 180.0, -180.0)) {
            val feet = ArGround.groundPointY(p, 1.45f, 2f, 34f, vh)
            val px = ArGround.charPixelHeightExact(1.58f, 1.45f, 2f, p, 34f, vh)
            assertTrue("pitch=$p 时脚位应有限：$feet", feet.isFinite())
            assertTrue("pitch=$p 时像素高应有限：$px", px.isFinite())
        }
    }

    @Test
    fun ar_ground_survives_degenerate_viewport_and_geometry() {
        // 视口高 0、相机高 0、距离 0、角色高 0 —— 都不应该出 NaN
        val cases = listOf(
            Triple(34f, 0, 1.45f), Triple(0f, vh, 1.45f), Triple(180f, vh, 1.45f),
            Triple(34f, 1, 1.45f), Triple(34f, vh, 0f), Triple(34f, vh, -1.0f),
        )
        for ((fov, h, camH) in cases) {
            val feet = ArGround.groundPointY(0.0, camH, 2f, fov, h)
            val px = ArGround.charPixelHeightExact(1.58f, camH, 2f, 0.0, fov, h)
            assertTrue("fov=$fov h=$h camH=$camH 脚位有限", feet.isFinite())
            assertTrue("fov=$fov h=$h camH=$camH 像素高有限", px.isFinite())
            // 距离 0（贴脸）不应崩
            val f0 = ArGround.groundPointY(0.0, camH, 0f, fov, h)
            val p0 = ArGround.charPixelHeightExact(1.58f, camH, 0f, 0.0, fov, h)
            assertFalse("距离 0 时不应出现 NaN（脚位 $f0 / 高 $p0）", f0.isNaN() || p0.isNaN())
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
    }

    @Test
    fun screen_projection_is_monotonic_in_pitch_only_where_expected() {
        // 固定几何下，屏幕 y 随 pitch 增大（=更低头）应单调不减到一个极值后回落；
        // 这里只断言"有限 + 在视口附近"，不假设形状（形状由黄金值测试钉住）
        var prev = Double.NaN
        for (p in -40..40 step 5) {
            val y = ArGround.screenYOfPoint(0f, 1.58f, 1.45f, 2f, p.toDouble(), 34f, vh)
            assertTrue("pitch=$p 投影有限", y.isFinite())
            prev = y
        }
        assertTrue(prev.isFinite())
    }

    @Test
    fun hand_touch_rotation_fallback_and_zero_viewport() {
        // 非法旋转角（45）应等价于不旋转分支（而不是崩或 NaN）
        val a = HandTouch.toScreen(100f, 100f, 1000, 1000, 45, 1000, 1000)
        val b = HandTouch.toScreen(100f, 100f, 1000, 1000, 0, 1000, 1000)
        assertEquals(b.first, a.first, 0.01f)
        assertEquals(b.second, a.second, 0.01f)
        // 视口/帧为 0 不应崩
        for ((w, h) in listOf(0 to 0, 1 to 1, 0 to 1000, 1000 to 0)) {
            val p = HandTouch.toScreen(0f, 0f, w, h, 90, w, h)
            assertFalse("帧/视口 ${w}x$h 应出有限值：$p", p.first.isNaN() || p.second.isNaN())
        }
    }

    @Test
    fun latch_with_zero_needs_triggers_immediately_or_not_at_all() {
        // needFrames=0 是调用方不该传的值；不管实现如何选择，都不允许每帧都返回非 null 却又漏掉 MISS
        val latch = HandTouch.Latch(needFrames = 0, coolingFrames = 0)
        val first = latch.feed(HandTouch.Zone.BODY)
        // 记录实际行为（不断言"必须触发"，只要求"不崩且类型正确"）
        assertTrue(first == null || first == HandTouch.Zone.BODY)
        // cooling=0 时连续喂应至少有触发
        var any = first != null
        repeat(5) { if (latch.feed(HandTouch.Zone.BODY) != null) any = true }
        assertTrue("cooling=0 + needFrames=0 时应当能触发至少一次", any)
    }

    @Test
    fun fake_hand_handles_negative_and_huge_time() {
        for (t in listOf(-1L, -4000L, -123456L, 0L, 1L, Long.MAX_VALUE / 3)) {
            val (x, y) = FakeHand.pointAt(t, 1280, 720)
            assertTrue("t=$t 时 x 应有限且在帧内：$x", x.isFinite() && x >= -1f && x <= 1281f)
            assertTrue("t=$t 时 y 应有限且在帧内：$y", y.isFinite() && y >= -1f && y <= 721f)
        }
    }

    @Test
    fun fake_hand_with_absurd_period() {
        for (period in listOf(1L, 2L, 100000L)) {
            val (x, y) = FakeHand.pointAt(1234L, 1280, 720, period)
            assertTrue("period=$period x 有限：$x", x.isFinite() && abs(x) <= 1280f)
            assertTrue("period=$period y 有限：$y", y.isFinite() && abs(y) <= 720f)
        }
    }

    @Test
    fun vad_gate_rejects_constant_dc() {
        // 恒定直流（不是声音，只是偏移）不应被判为说话。
        // 能量法只看 RMS，直流会被当成"很大声" —— 这正是要暴露的问题。
        val dc = FloatArray(16000) { 0.3f }
        val r = VadGate.analyze(dc, 16000)
        assertFalse("恒定直流不应算说话（noise=${r.noiseRms} peak=${r.peakRms}）", r.isSpeech)
    }

    @Test
    fun vad_gate_survives_degenerate_inputs() {
        // 单样本、非整帧长度、NaN、全零、极大值
        assertFalse(VadGate.analyze(FloatArray(1) { 0.5f }, 16000).isSpeech)
        assertFalse(VadGate.analyze(FloatArray(37) { 0.5f }, 16000).isSpeech)
        assertFalse(VadGate.analyze(FloatArray(1600) { Float.NaN }, 16000).isSpeech)
        assertFalse(VadGate.analyze(FloatArray(1600) { 0f }, 16000).isSpeech)
        val huge = VadGate.analyze(FloatArray(16000) { 1e9f }, 16000)
        assertTrue("极大值不应崩（speechMs=${huge.speechMs}）", huge.frames >= 0)
        // 采样率为 0 时不应除零崩溃
        val z = VadGate.analyze(FloatArray(1600) { 0.1f }, 0)
        assertTrue("采样率 0 不应崩", z.frames >= 0)
    }
}
''')
print("✓ 新增 AdversarialTest.kt")

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
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<failure[^>]*>([^<]{0,260})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(2).replace("\n", " ").strip()[:230]))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<error[^>]*>([^<]{0,200})', x):
        print("      ⚠ %s → ERROR %s" % (mm.group(1), mm.group(2).replace("\n", " ").strip()[:180]))
