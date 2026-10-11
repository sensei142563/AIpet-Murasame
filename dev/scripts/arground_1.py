# -*- coding: utf-8 -*-
"""地板识别 + 碰撞箱的数学件（纯 Kotlin、零 Android 依赖 → 可 JVM 单测）：
   ① ui/ArGround.kt   俯仰角 → 地平线/地面/脚位/缩放/碰撞盒
   ② test/.../ArGroundTest.kt  断言退化情形与单调性
   ③ gradlew test 取证（不需要手机）
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
MOD = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ArGround.kt")
TEST = os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/ArGroundTest.kt")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

io.open(MOD, "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame.ui

import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.sqrt
import kotlin.math.tan

/**
 * 地板识别 / 碰撞箱的**几何基础件**（纯计算，不依赖 Android，便于单元测试）。
 *
 * 为什么不用 ARCore：本 App 的 AR 是 CameraX + Live2D/GL 叠加，引入 ARCore 要换整条渲染与
 * 生命周期通路（且要适配设备支持情况）。这里先用**姿态法**拿到"地面在哪"：
 *   · 相机光轴水平时，视线中心即地平线；
 *   · 手机下俯 θ 度后，地平线在画面中**上移** f·tanθ（f 为焦距像素）；
 *   · 因此画面中"地平线所在的行"以下就是地面区域，丛雨的脚要贴在这条线**下方**合适距离；
 *   · 她的缩放按"距离越远越小"的透视关系给出。
 *
 * 坐标系约定（全程统一，避免符号混乱）：
 *   · pitchDeg = 0  → 光轴水平（看远处地平线）
 *   · pitchDeg > 0  → **下俯**（低头看地面）
 *   · 屏幕 y 轴向下为正；视图中心 y = h/2
 *   · cameraHeightM = 相机离地高度（手持约 1.4~1.6m，可配置）
 *
 * 能力边界（诚实标注）：这是**单目 + 姿态估计**，不是深度传感器。
 *   · 能给出地平线位置、地面区域、脚的贴地位置、按距离的缩放、屏幕空间碰撞盒；
 *   · **不能**知道真实距离/遮挡（要 ARCore 深度或多帧视觉 SLAM 才能做到）。
 */
object ArGround {

    /** 由加速度计读数算俯仰角（度）：光轴与水平面的夹角，下俯为正。 */
    fun pitchDeg(gx: Float, gy: Float, gz: Float): Float {
        // 竖直向下方向 ≈ 重力方向；光轴（屏幕朝向）与水平面的夹角用 gz 与水平分量比
        val horizontal = sqrt((gx * gx + gy * gy).toDouble())
        return Math.toDegrees(atan2(gz.toDouble(), horizontal)).toFloat()
    }

    /** 焦距（像素）：由竖直 FOV 与视图高度得出。 */
    fun focalPx(viewportH: Int, fovYDeg: Float): Float =
        (viewportH / 2.0 / tan(Math.toRadians(fovYDeg / 2.0))).toFloat()

    /**
     * 地平线在屏幕上的 y（像素）。下俯越大，地平线越靠上（y 越小）。
     */
    fun horizonY(pitchDeg: Float, fovYDeg: Float, viewportH: Int): Float =
        viewportH / 2f - focalPx(viewportH, fovYDeg) * tan(Math.toRadians(pitchDeg.toDouble())).toFloat()

    /**
     * 距离相机水平距离 distanceM、位于地面上的点，投影到屏幕的 y。
     * 脚踩在这条线上；distanceM 越大越接近地平线。
     */
    fun groundPointY(pitchDeg: Float, cameraHeightM: Float, distanceM: Float,
                     fovYDeg: Float, viewportH: Int): Float {
        val f = focalPx(viewportH, fovYDeg)
        // 地面点相对光轴的竖直夹角 = pitch + atan(cameraHeight / distance)
        val ang = Math.toRadians(pitchDeg.toDouble()) +
            atan2(cameraHeightM.toDouble(), distanceM.coerceAtLeast(0.05))
        return viewportH / 2f + (f * tan(ang)).toFloat()
    }

    /**
     * 某个距离上、身高 charHeightM 的角色在屏幕上的像素高度（透视缩放）。
     * 用于把 Live2D 缩放到"看起来站在那个距离"。
     */
    fun charPixelHeight(charHeightM: Float, distanceM: Float, fovYDeg: Float, viewportH: Int): Float {
        val f = focalPx(viewportH, fovYDeg)
        return (f * charHeightM / distanceM.coerceAtLeast(0.05))
    }

    /**
     * 屏幕空间碰撞盒（左, 上, 右, 下）。用于"戳她一下"这类手部互动：
     * 命中即触发动作/台词/表情。
     */
    fun collisionRect(centerX: Float, feetY: Float, pixelHeight: Float, aspect: Float = 0.55f):
        FloatArray {
        val h = pixelHeight.coerceAtLeast(1f)
        val w = h * aspect
        return floatArrayOf(centerX - w / 2f, feetY - h, centerX + w / 2f, feetY)
    }

    /** 点是否在碰撞盒内。 */
    fun hit(rect: FloatArray, x: Float, y: Float): Boolean =
        x >= rect[0] && x <= rect[2] && y >= rect[1] && y <= rect[3]

    /**
     * 给定视图高度与期望的"脚贴地"效果，返回给 Live2D 的竖直平移量：
     * 让角色脚部落在 groundY 附近（正值向下）。
     */
    fun feetOffset(feetY: Float, charPixelHeight: Float, viewportH: Int): Float =
        feetY - viewportH.toFloat()   // Live2D 默认贴底，这里给相对底边的偏移

    /** 地平线是否在画面内（用于判断"当前能看到地面吗"）。 */
    fun horizonVisible(pitchDeg: Float, fovYDeg: Float, viewportH: Int): Boolean {
        val y = horizonY(pitchDeg, fovYDeg, viewportH)
        return y > 0f && y < viewportH
    }

    /** 地面占画面下部的比例（0..1）；下俯越多越大。用于提示"再低一点头就看到地了"。 */
    fun groundCoverage(pitchDeg: Float, fovYDeg: Float, viewportH: Int): Float {
        val y = horizonY(pitchDeg, fovYDeg, viewportH).coerceIn(0f, viewportH.toFloat())
        return (viewportH - y) / viewportH
    }

    /** 调试用一行摘要。 */
    fun describe(pitchDeg: Float, cameraHeightM: Float, fovYDeg: Float, viewportH: Int,
                 distanceM: Float = 2f): String {
        val hz = horizonY(pitchDeg, fovYDeg, viewportH)
        val feet = groundPointY(pitchDeg, cameraHeightM, distanceM, fovYDeg, viewportH)
        val ph = charPixelHeight(1.5f, distanceM, fovYDeg, viewportH)
        return "pitch=%.1f° 地平线y=%.0f 地面覆盖=%.0f%% 距离%.1fm 脚y=%.0f 身高像素=%.0f %s"
            .format(pitchDeg, hz, groundCoverage(pitchDeg, fovYDeg, viewportH) * 100f,
                distanceM, feet, ph, if (abs(hz - viewportH / 2f) < 1f) "(水平)" else "")
    }
}
''')
print("✓ 写了 ui/ArGround.kt")

io.open(TEST, "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import com.aipet.murasame.ui.ArGround
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** ArGround（地板识别/碰撞箱的几何件）单元测试 —— 纯 JVM，不需要手机。 */
class ArGroundTest {

    private val fov = 60f
    private val h = 2000

    @Test
    fun pitch_zero_means_horizon_at_center() {
        val y = ArGround.horizonY(0f, fov, h)
        assertEquals(h / 2f, y, 0.5f)
    }

    @Test
    fun looking_down_moves_horizon_up() {
        val y0 = ArGround.horizonY(0f, fov, h)
        val y15 = ArGround.horizonY(15f, fov, h)
        val y30 = ArGround.horizonY(30f, fov, h)
        assertTrue("下俯后地平线应上移", y15 < y0)
        assertTrue("下俯越多越靠上", y30 < y15)
    }

    @Test
    fun horizon_leaves_view_when_looking_far_down() {
        // 竖直向下看：地平线应跑出画面上方
        val y = ArGround.horizonY(85f, fov, h)
        assertTrue("地平线应在画面之上(y<0)，实际 $y", y < 0f)
        assertFalse(ArGround.horizonVisible(85f, fov, h))
        assertTrue(ArGround.horizonVisible(0f, fov, h))
    }

    @Test
    fun ground_coverage_grows_with_tilt() {
        val c0 = ArGround.groundCoverage(0f, fov, h)
        val c30 = ArGround.groundCoverage(30f, fov, h)
        val c45 = ArGround.groundCoverage(45f, fov, h)
        assertTrue(c0 < c30 && c30 < c45)
        assertTrue("水平时地面约占一半", kotlin.math.abs(c0 - 0.5f) < 0.02f)
        assertTrue("低头 45° 时地面应占大部分", c45 > 0.7f)
    }

    @Test
    fun feet_below_horizon_and_farther_is_higher() {
        // 相机高 1.5m，下俯 20°：2m 处的脚点应在地平线之下
        val hz = ArGround.horizonY(20f, fov, h)
        val feet2 = ArGround.groundPointY(20f, 1.5f, 2f, fov, h)
        val feet5 = ArGround.groundPointY(20f, 1.5f, 5f, fov, h)
        assertTrue("脚点在地平线下方", feet2 > hz)
        assertTrue("越远越接近地平线（y 越小）", feet5 < feet2)
        assertTrue("脚点仍在画面内或下方", feet2 > h / 2f)
    }

    @Test
    fun pixel_height_shrinks_with_distance() {
        val near = ArGround.charPixelHeight(1.5f, 1f, fov, h)
        val far = ArGround.charPixelHeight(1.5f, 4f, fov, h)
        assertTrue("近大远小", near > far)
        // 1.5m 高、2m 远、60° FOV、2000px 高 → 约 1299px（f≈1732）
        val at2 = ArGround.charPixelHeight(1.5f, 2f, fov, h)
        assertEquals(1299f, at2, 25f)
    }

    @Test
    fun focal_length_matches_fov() {
        // 竖直 60° FOV、高 2000 → f = 1000 / tan(30°) ≈ 1732
        assertEquals(1732f, ArGround.focalPx(h, 60f), 3f)
        // 更窄的 FOV → 更长焦距
        assertTrue(ArGround.focalPx(h, 40f) > ArGround.focalPx(h, 60f))
    }

    @Test
    fun collision_rect_contains_body_and_rejects_outside() {
        val feet = 1500f
        val ph = 800f
        val rect = ArGround.collisionRect(500f, feet, ph)
        // 盒子的底边=脚，顶边=头顶
        assertEquals(feet, rect[3], 0.01f)
        assertEquals(feet - ph, rect[1], 0.01f)
        assertTrue("盒心命中", ArGround.hit(rect, 500f, feet - ph / 2f))
        assertTrue("头部附近命中", ArGround.hit(rect, 500f, feet - ph + 5f))
        assertFalse("脚下未命中", ArGround.hit(rect, 500f, feet + 5f))
        assertFalse("太靠左未命中", ArGround.hit(rect, rect[0] - 5f, feet - ph / 2f))
        assertFalse("太靠右未命中", ArGround.hit(rect, rect[2] + 5f, feet - ph / 2f))
    }

    @Test
    fun pitch_from_accelerometer() {
        // 手机竖直（屏幕朝前）：此时重力主要在 y 轴（竖屏坐标）→ gz≈0 → pitch≈0
        assertEquals(0f, ArGround.pitchDeg(0f, 9.8f, 0f), 0.6f)
        // 手机平放朝下（屏幕朝地）：重力压在 z 轴 → pitch≈90°
        assertEquals(90f, ArGround.pitchDeg(0f, 0f, 9.8f), 0.6f)
        // 45° 斜看地面
        assertEquals(45f, ArGround.pitchDeg(0f, 6.93f, 6.93f), 0.6f)
    }

    @Test
    fun describe_is_readable() {
        val s = ArGround.describe(25f, 1.5f, fov, h, 2f)
        assertTrue(s.contains("pitch=25.0"))
        assertTrue(s.contains("脚y="))
    }
}
''')
print("✓ 写了 test/.../ArGroundTest.kt")

print()
print("=== gradlew test（不需要手机）===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "testReleaseUnitTest", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if l.startswith(("BUILD", "> Task :app:test", "e: ")) or "FAILED" in l or "tests completed" in l:
        print("   " + l.strip()[:160])
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(没有 BUILD 行)"))
if r.returncode != 0:
    for l in o.splitlines():
        if "ArGroundTest" in l or "expected" in l.lower() or "AssertionError" in l:
            print("   ! " + l.strip()[:170])
    sys.exit(1)

res = os.path.join(CHAT, "app/build/test-results/testReleaseUnitTest")
if os.path.isdir(res):
    print("   测试结果文件:")
    for f in sorted(os.listdir(res)):
        if f.endswith(".xml"):
            x = io.open(os.path.join(res, f), encoding="utf-8", errors="replace").read()
            import re as _re
            m = _re.search(r'tests="(\\d+)" skipped="(\\d+)" failures="(\\d+)" errors="(\\d+)"', x)
            if m:
                print("      %-46s tests=%s failures=%s errors=%s" % (f, m.group(1), m.group(3), m.group(4)))
