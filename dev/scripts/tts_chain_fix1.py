# -*- coding: utf-8 -*-
"""修 TTS 链路的两个"静默无声"问题，并把层序抽成可单测的纯函数 TtsPlan。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SRC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① 新增纯函数 TtsPlan ----------
io.open(os.path.join(SRC, "bot/chat/TtsPlan.kt"), "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame.bot.chat

/**
 * 语音链路（五层）的**纯逻辑**：给定可用性，算出按顺序该试哪些层。
 *
 * 为什么要把这段单独抽出来：链路里最容易出错、也最难在真机上复现的，
 * 正是"某一层失败之后到底有没有下一层"—— 实测就踩过两次"静默无声"：
 *   ① 电脑合成是异步的，speak() 却在启动协程后立刻 return true，
 *      于是"电脑失败 + 离线未就绪"时只写一行日志，调用方以为已接手 ⇒ 一声不响；
 *   ② 缓存/台词包路径忽略了 play() 的返回值，坏缓存还会永久留在磁盘上。
 * 抽成纯函数后，"每一层都有下一层、SYSTEM 永远在最后"这条不变量可以被单测钉死。
 */
object TtsPlan {

    enum class Step {
        /** ① 预生成台词包（离线、秒出，与有没有电脑无关） */
        PACKED,
        /** ② 联网缓存（电脑之前合成过的结果） */
        CACHE,
        /** ③ 电脑 F5-TTS（她真正的音色） */
        PC,
        /** ④ 本机离线 TTS（Kokoro int8） */
        OFFLINE,
        /** ⑤ 系统 TTS（由调用方执行；本对象只负责把它排在最后并保证一定存在） */
        SYSTEM,
    }

    /**
     * 按可用性给出尝试顺序。
     * **不变量**：① 顺序固定为 PACKED < CACHE < PC < OFFLINE < SYSTEM；
     *            ② SYSTEM 一定存在且一定在最后（调用方永远有兜底）。
     */
    fun steps(hasPacked: Boolean, pcConfigured: Boolean, offlineReady: Boolean): List<Step> {
        val l = ArrayList<Step>(5)
        if (hasPacked) l.add(Step.PACKED)
        if (pcConfigured) {
            l.add(Step.CACHE)
            l.add(Step.PC)
        }
        if (offlineReady) l.add(Step.OFFLINE)
        l.add(Step.SYSTEM)
        return l
    }

    /** 某一层失败后，接下来该走哪一层（异步路径回报时用）。永远返回一个有效的下一步。 */
    fun after(step: Step, pcConfigured: Boolean, offlineReady: Boolean): Step {
        val l = steps(hasPacked = false, pcConfigured = pcConfigured, offlineReady = offlineReady)
        val i = l.indexOf(step)
        return if (i >= 0 && i + 1 < l.size) l[i + 1] else Step.SYSTEM
    }

    /** 这个顺序是否满足不变量（供自检/日志用）。 */
    fun isSane(l: List<Step>): Boolean =
        l.isNotEmpty() && l.last() == Step.SYSTEM &&
            l.toSet().size == l.size &&
            l.zipWithNext().all { (a, b) -> a.ordinal < b.ordinal }
}
''')
print("✓ 新增 bot/chat/TtsPlan.kt")

# ---------- ② 改 VoiceClient ----------
V = os.path.join(SRC, "bot/chat/VoiceClient.kt")
t = io.open(V, encoding="utf-8").read().replace("\r\n", "\n")

# ②-a 台词包：play 的结果要返回；失败要删掉损坏的副本以便下次重新解出
t = t.replace('''        if (f.length() < 20000) return false
        log("命中预生成台词 " + f.length() + " 字节（不联网）")
        play(ctx, f)
        true''',
              '''        if (f.length() < 20000) return false
        log("命中预生成台词 " + f.length() + " 字节（不联网）")
        val ok = play(ctx, f)
        if (!ok) {
            // 解出来的副本可能损坏：删掉，下次重新从 assets 解一份，
            // 否则这句话会**每次**都放不出声（实测过的坑：坏文件永远不删）
            runCatching { f.delete() }
            log("台词包播放失败，已删除损坏副本，交给下一层")
        }
        return ok''', 1)

# ②-b 缓存：play 结果要返回；失败删缓存
t = t.replace('''            if (f.isFile && f.length() >= 2000) {
                log("命中缓存 " + f.length() + " 字节")
                play(ctx, f)
                return true
            }''',
              '''            if (f.isFile && f.length() >= 2000) {
                log("命中缓存 " + f.length() + " 字节")
                if (play(ctx, f)) return true
                // 缓存损坏（例如写到一半被杀）：删掉后继续往下走，
                // 否则这条文本每次都会命中同一个坏文件、永远不出声
                runCatching { f.delete() }
                log("缓存播放失败，已删除并继续降级")
            }''', 1)

# ②-c 异步失败路径：用 TtsPlan 决定下一步；到 SYSTEM 时回调，让调用方走系统 TTS
t = t.replace('''            // ③ 电脑合成；失败则落 ④ 离线 TTS
            scope.launch {
                val okSynth = synth(ctx, f, base, text, petId, refAudio, refText)
                if (okSynth) {
                    withContext(Dispatchers.Main) { play(ctx, f) }
                } else if (offlineReady) {
                    log("电脑合成失败 → 改用离线 TTS")
                    withContext(Dispatchers.IO) { speakOffline(ctx, text) }
                } else {
                    log("电脑合成失败且离线 TTS 未就绪：本次不出声")
                }
            }
            return true''',
              '''            // ③ 电脑合成；失败后按 TtsPlan 决定下一步（实测坑：原来这里只写日志就结束了，
            //    于是"电脑失败 + 离线未就绪"会**静默无声**，调用方还以为已接手）
            scope.launch {
                val okSynth = synth(ctx, f, base, text, petId, refAudio, refText)
                if (okSynth) {
                    val played = withContext(Dispatchers.Main) { play(ctx, f) }
                    if (played) return@launch
                    runCatching { f.delete() }        // 合成结果损坏，别留成坏缓存
                    log("合成结果播放失败，已删除，按降级继续")
                }
                when (TtsPlan.after(TtsPlan.Step.PC, pcConfigured = true, offlineReady = offlineReady)) {
                    TtsPlan.Step.OFFLINE -> {
                        log("电脑合成失败 → 改用离线 TTS")
                        val ms = withContext(Dispatchers.IO) { speakOffline(ctx, text) }
                        if (!ms) giveUp(ctx, onGiveUp, "离线 TTS 也失败")
                    }
                    else -> giveUp(ctx, onGiveUp, "电脑合成失败且离线 TTS 未就绪")
                }
            }
            return true''', 1)

# ②-d speak 增加 onGiveUp 参数 + 空地址分支的兜底回调
t = t.replace('''    fun speak(ctx: Context, text: String, refAudio: String? = null, refText: String? = null,
              petId: String? = null): Boolean {
        appCtx = ctx.applicationContext
        if (text.isBlank()) {
            log("文本为空，交回系统 TTS")
            return false
        }''',
              '''    fun speak(ctx: Context, text: String, refAudio: String? = null, refText: String? = null,
              petId: String? = null, onGiveUp: (() -> Unit)? = null): Boolean {
        appCtx = ctx.applicationContext
        if (text.isBlank()) {
            log("文本为空，交回系统 TTS")
            return false
        }
        // 自检链路顺序（不变量：SYSTEM 永远在最后，调用方永远有兜底）
        runCatching {
            val plan = TtsPlan.steps(false, baseUrl.isNotBlank(), OfflineTtsEngine.isReady(ctx))
            if (!TtsPlan.isSane(plan)) log("⚠ 链路顺序异常：$plan")
        }''', 1)

t = t.replace('''        log("未配置电脑地址且离线 TTS 未就绪（缺 files/tts/model.int8.onnx）→ 交回系统 TTS")
        return false
    }''',
              '''        log("未配置电脑地址且离线 TTS 未就绪（缺 files/tts/model.int8.onnx）→ 交回系统 TTS")
        onGiveUp?.invoke()
        return false
    }

    /** 彻底没辙时回头通知调用方（让它去用系统 TTS），避免"静默无声"。 */
    private fun giveUp(ctx: Context, onGiveUp: (() -> Unit)?, why: String) {
        log(why + " → 通知调用方回退系统 TTS")
        if (onGiveUp == null) {
            log("⚠ 调用方未提供 onGiveUp，本次可能无声（请在该调用点传入系统 TTS 兜底）")
            return
        }
        runCatching { android.os.Handler(android.os.Looper.getMainLooper()).post { onGiveUp() } }
            .onFailure { log("onGiveUp 投递失败：" + it.javaClass.simpleName) }
    }''', 1)
io.open(V, "w", encoding="utf-8", newline="\n").write(t)
print("✓ VoiceClient 已修两处静默无声 + 接 TtsPlan + onGiveUp 回调")

# ---------- ③ 单测 ----------
io.open(os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/TtsPlanTest.kt"),
        "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import com.aipet.murasame.bot.chat.TtsPlan
import com.aipet.murasame.bot.chat.TtsPlan.Step
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 语音链路顺序的纯逻辑单测。核心不变量：**每一层失败都有下一层，SYSTEM 永远兜底**。
 * （真机上踩过两次"静默无声"，这两个不变量就是从那两次来的。）
 */
class TtsPlanTest {

    @Test
    fun system_is_always_last_and_present() {
        for (packed in listOf(true, false)) {
            for (pc in listOf(true, false)) {
                for (off in listOf(true, false)) {
                    val l = TtsPlan.steps(packed, pc, off)
                    assertEquals("SYSTEM 必须在最后：$l", Step.SYSTEM, l.last())
                    assertTrue("顺序应满足不变量：$l", TtsPlan.isSane(l))
                }
            }
        }
    }

    @Test
    fun full_availability_yields_the_documented_order() {
        assertEquals(listOf(Step.PACKED, Step.CACHE, Step.PC, Step.OFFLINE, Step.SYSTEM),
            TtsPlan.steps(true, true, true))
    }

    @Test
    fun no_network_still_has_two_offline_layers() {
        assertEquals(listOf(Step.PACKED, Step.OFFLINE, Step.SYSTEM),
            TtsPlan.steps(true, false, true))
        assertEquals(listOf(Step.PACKED, Step.SYSTEM), TtsPlan.steps(true, false, false))
    }

    @Test
    fun pc_failure_without_offline_must_land_on_system() {
        // 这正是此前"静默无声"的现场：电脑失败 + 离线未就绪
        assertEquals(Step.SYSTEM, TtsPlan.after(Step.PC, pcConfigured = true, offlineReady = false))
    }

    @Test
    fun pc_failure_with_offline_lands_on_offline() {
        assertEquals(Step.OFFLINE, TtsPlan.after(Step.PC, pcConfigured = true, offlineReady = true))
    }

    @Test
    fun every_step_has_a_successor() {
        // 对任意可用性组合、任意层，after() 都必须给出一个有效结果（不返回 null、不越界）
        for (pc in listOf(true, false)) {
            for (off in listOf(true, false)) {
                for (s in Step.values()) {
                    val n = TtsPlan.after(s, pc, off)
                    assertTrue("after($s) 应返回有效层，实际 $n", n in Step.values())
                }
            }
        }
        assertEquals("SYSTEM 之后仍是 SYSTEM（不能再降级）",
            Step.SYSTEM, TtsPlan.after(Step.SYSTEM, true, true))
    }

    @Test
    fun sanity_check_rejects_bad_orders() {
        assertFalse(TtsPlan.isSane(emptyList()))
        assertFalse("缺 SYSTEM 兜底", TtsPlan.isSane(listOf(Step.PACKED, Step.OFFLINE)))
        assertFalse("顺序颠倒", TtsPlan.isSane(listOf(Step.PC, Step.CACHE, Step.SYSTEM)))
        assertFalse("重复层", TtsPlan.isSane(listOf(Step.PC, Step.PC, Step.SYSTEM)))
    }
}
''')
print("✓ 新增 TtsPlanTest.kt")

print()
print("=== 编译 + 单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "assembleRelease",
                    "--console=plain"], cwd=CHAT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:12]:
    print("   " + y[:230])
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
tot = fail = 0
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if f.endswith(".xml"):
        x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        if m:
            tt = int(m.group(1)); fl = int(m.group(2)) + int(m.group(3))
            tot += tt; fail += fl
            print("   %-22s tests=%-3d 失败=%d" % (f.replace("TEST-com.aipet.murasame.", "").replace(".xml", ""), tt, fl))
print("   合计 %d 用例，失败 %d" % (tot, fail))
if r.returncode != 0 or fail:
    for f in os.listdir(d) if os.path.isdir(d) else []:
        if f.endswith(".xml"):
            x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
            for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,200})', x):
                print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:180]))
    sys.exit(1)
