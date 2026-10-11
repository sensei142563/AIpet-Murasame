# -*- coding: utf-8 -*-
"""唤醒词判定（纯文本、可单测）：ui/WakeWord.kt + WakeWordTest.kt。"""
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
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

io.open(os.path.join(UI, "WakeWord.kt"), "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame.ui

/**
 * 唤醒词判定：**"叫她名字才回应"**（纯文本，可 JVM 单测）。
 *
 * 为什么这么做而不上关键词识别（KWS）模型：手机端已经有**本地 STT**（SenseVoice，实测 0.94），
 * 我们对"VAD 判定有语音"的那一小段做一次识别，再在**文本**上判断有没有喊她名字 ——
 * 零新模型、零新依赖，而且**误听纠正可以直接写成变体表**（见下）。
 *
 * 设计要点：
 *   1) **归一化**：全角→半角、去空白、去标点、转小写，再匹配；
 *   2) **变体表**：把 STT 常见误听直接列出来 —— 例如"丛雨"极易被听成"村雨"，
 *      日文名又可能被识别成「ムラサメ / むらさめ」或罗马字 murasame；
 *   3) **只匹配完整名字**（"村里下雨"不应唤醒，因为它不含"村雨"这个连续子串）；
 *   4) **冷却**：一次唤醒后若干秒内不再重复唤醒（避免一句话里出现两次名字就回两次）。
 *
 * 用法（由调用方决定何时启用）：先 VAD 确认有人说话 → STT 出文本 → wake(text, petId) 判断是否该回应。
 */
object WakeWord {

    /** 每个角色的唤醒变体（全部按"归一化后的形式"书写：无空格、无标点、小写）。 */
    private val VARIANTS: Map<String, List<String>> = mapOf(
        "murasame" to listOf(
            "丛雨", "叢雨", "村雨", "ムラサメ", "むらさめ", "murasame", "村雨丸", "丛雨丸",
        ),
        "noir" to listOf(
            "诺瓦", "諾瓦", "ノワール", "のわーる", "noir",
        ),
    )

    /** 通用唤醒（不点名也行，但需要明显的呼叫语气）。 */
    private val GENERIC_CALLS = listOf("在吗", "你在吗", "醒醒")

    /** 归一化：全角→半角、去空白、去标点、转小写。 */
    fun normalize(text: String): String {
        if (text.isBlank()) return ""
        val sb = StringBuilder(text.length)
        for (ch in text) {
            var c = ch
            // 全角 ASCII（！-～）与全角空格 → 半角
            if (c.code in 0xFF01..0xFF5E) c = (c.code - 0xFEE0).toChar()
            else if (c.code == 0x3000) c = ' '
            if (c.isWhitespace()) continue
            if (c.isLetterOrDigit()) sb.append(c.lowercaseChar())
        }
        return sb.toString()
    }

    /** 该角色的所有变体（归一化后）。未知角色回退到 murasame。 */
    fun variantsOf(petId: String?): List<String> =
        VARIANTS[petId?.lowercase()] ?: VARIANTS.getValue("murasame")

    /**
     * 这段文本是否在喊她。
     * @param petId 角色 id（murasame / noir）
     * @param allowGeneric 是否允许"在吗"这类不点名的呼叫也算唤醒（默认 true）
     */
    fun isCalling(text: String, petId: String? = "murasame", allowGeneric: Boolean = true): Boolean {
        val n = normalize(text)
        if (n.isEmpty()) return false
        for (v in variantsOf(petId)) {
            if (n.contains(normalize(v))) return true
        }
        if (allowGeneric) {
            for (g in GENERIC_CALLS) {
                if (n.contains(normalize(g))) return true
            }
        }
        return false
    }

    /** 命中的那个变体（便于日志/调试）；没命中返回 null。 */
    fun hit(text: String, petId: String? = "murasame"): String? {
        val n = normalize(text)
        if (n.isEmpty()) return null
        return variantsOf(petId).firstOrNull { n.contains(normalize(it)) }
    }

    /**
     * 唤醒冷却器：一次唤醒后 cooldownMs 内不再放行（默认 6 秒）。
     */
    class Cooldown(private val cooldownMs: Long = 6000L) {
        private var last = 0L
        fun allow(nowMs: Long, hit: Boolean): Boolean {
            if (!hit) return false
            if (nowMs - last < cooldownMs) return false
            last = nowMs
            return true
        }
        fun reset() { last = 0L }
    }
}
''')
print("✓ 新增 ui/WakeWord.kt")

io.open(os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/WakeWordTest.kt"),
        "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import com.aipet.murasame.ui.WakeWord
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** 唤醒词判定的单测（纯文本）。重点覆盖：STT 误听变体、标点/空格/全角、以及**不该唤醒**的反例。 */
class WakeWordTest {

    @Test
    fun normalize_handles_fullwidth_space_and_punct() {
        assertEquals("丛雨在吗", WakeWord.normalize("丛雨，在吗？"))
        assertEquals("murasame", WakeWord.normalize("Ｍｕｒａｓａｍｅ"))
        assertEquals("abc123", WakeWord.normalize(" a b c 1 2 3 "))
        assertEquals("", WakeWord.normalize("　！？。"))
    }

    @Test
    fun direct_name_variants_wake() {
        for (t in listOf("丛雨", "丛雨，你在吗", "在吗丛雨", "叢雨", "ムラサメ", "むらさめ",
                         "MURASAME", "murasame 在吗", "村雨")) {
            assertTrue("应唤醒：$t", WakeWord.isCalling(t, "murasame"))
        }
    }

    @Test
    fun homophone_misrecognition_is_tolerated_by_design() {
        // 实测 STT 很容易把「丛雨」听成「村雨」——这是**有意的**容错，不是 bug
        assertEquals("村雨", WakeWord.hit("村雨", "murasame"))
        assertEquals("丛雨丸", WakeWord.hit("丛雨丸，醒醒", "murasame"))
    }

    @Test
    fun sentences_without_the_name_do_not_wake() {
        for (t in listOf("今天下雨了", "村里下雨了", "我在看一本书", "你好", "这是什么")) {
            assertFalse("不应唤醒：$t", WakeWord.isCalling(t, "murasame"))
        }
        assertNull(WakeWord.hit("今天下雨了", "murasame"))
    }

    @Test
    fun generic_call_wakes_but_can_be_disabled() {
        assertTrue(WakeWord.isCalling("在吗", "murasame"))
        assertFalse(WakeWord.isCalling("在吗", "murasame", allowGeneric = false))
    }

    @Test
    fun other_pet_names_do_not_wake_this_pet() {
        assertFalse("诺瓦 不该唤醒丛雨", WakeWord.isCalling("诺瓦", "murasame"))
        assertTrue("诺瓦 应唤醒诺瓦", WakeWord.isCalling("诺瓦，在吗？", "noir"))
        assertTrue("ノワール 应唤醒诺瓦", WakeWord.isCalling("ノワール", "noir"))
    }

    @Test
    fun unknown_pet_falls_back_to_murasame() {
        assertTrue(WakeWord.isCalling("丛雨", "someUnknownPet"))
    }

    @Test
    fun cooldown_blocks_repeat_within_window() {
        val cd = WakeWord.Cooldown(cooldownMs = 6000)
        assertTrue("第一次应放行", cd.allow(1000, true))
        assertFalse("1 秒后应被冷却挡住", cd.allow(2000, true))
        assertFalse("5.9 秒后仍挡住", cd.allow(6900, true))
        assertTrue("6 秒后可再放行", cd.allow(7001, true))
        assertFalse("没命中永远不放行", cd.allow(20000, false))
    }

    @Test
    fun empty_and_blank_are_safe() {
        assertFalse(WakeWord.isCalling("", "murasame"))
        assertFalse(WakeWord.isCalling("   ", "murasame"))
        assertNull(WakeWord.hit("", "murasame"))
    }
}
''')
print("✓ 新增 test/.../WakeWordTest.kt")

print()
print("=== 跑单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.WakeWordTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
for l in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: |AssertionError|expected", l):
        print("   " + l.strip()[:180])
p2 = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.WakeWordTest.xml")
if os.path.isfile(p2):
    x = io.open(p2, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   WakeWordTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    if m.group(2) != "0" or m.group(3) != "0":
        for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<failure[^>]*>([^<]{0,200})', x):
            print("      失败 %s → %s" % (mm.group(1), mm.group(2).replace("\n", " ")[:170]))
        sys.exit(1)
