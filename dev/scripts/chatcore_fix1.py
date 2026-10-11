# -*- coding: utf-8 -*-
"""对话主循环的两处加固：SSE 行解析抽成纯函数 + 表情标记总是剥掉。"""
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

# ---------- ① 纯函数：SSE 行解析 ----------
io.open(os.path.join(SRC, "bot/chat/ChatSse.kt"), "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame.bot.chat

/**
 * SSE（Server-Sent Events）行解析 —— **纯函数，可 JVM 单测**。
 *
 * 为什么抽出来：这段逻辑原来内联在 ChatCore.chatOnce 的流式读取里，
 * 是整轮对话里最难离线验证、也最容易因协议细节翻车的地方。实测顾虑：
 *   · 行首可能有 BOM（U+FEFF）或空白（某些反向代理会插），原来只判 startsWith("data:")
 *     ⇒ 一旦不匹配就 continue，**整个流被跳过**，最后变成"（什么都没说出来...）"；
 *   · `data:` 与内容之间的空格可有可无；`data:[DONE]` 不写空格也常见；
 *   · 还有 event: / id: / retry: / `:注释` / 空行等非 data 行要安静跳过；
 *   · 中文内容里可能带零宽字符，trim() 只去空白，不应破坏内容本身。
 */
object ChatSse {

    /** @return 该行的 data 负载；不是 data 行（或空负载）时返回 null。 */
    fun parseLine(rawLine: String): String? {
        if (rawLine.isEmpty()) return null
        // 去掉行首 BOM 与空白（SSE 允许冒号前无空白，但代理可能插入 BOM）
        var line = rawLine
        if (line.isNotEmpty() && line[0] == '\\uFEFF') line = line.substring(1)
        line = line.trimStart(' ', '\\t')
        if (!line.startsWith("data:")) return null
        val payload = line.substring(5).trimStart(' ')
        return payload
    }

    /** 是否是流结束标记。 */
    fun isDone(payload: String?): Boolean = payload != null && payload.trim() == "[DONE]"

    /**
     * 从 data 负载里取增量文本。
     * @return 增量内容（可能是空串，表示该事件不含正文，例如只带 reasoning_content）；
     *         无法解析时返回 null。
     */
    fun deltaOf(payload: String): String? = runCatching {
        val obj = org.json.JSONObject(payload)
        val delta = obj.optJSONArray("choices")?.optJSONObject(0)?.optJSONObject("delta")
            ?: return@runCatching ""          // 合法但没有 choices/delta：不算错误
        if (delta.has("reasoning_content")) return@runCatching ""
        delta.optString("content")
    }.getOrNull()
}
''')
print("✓ 新增 bot/chat/ChatSse.kt")

# ---------- ② ChatCore：用纯函数 + 剥掉所有表情标记 + 兜住 stickerNames ----------
CC = os.path.join(SRC, "bot/chat/ChatCore.kt")
t = io.open(CC, encoding="utf-8").read().replace("\r\n", "\n")

old_parse = '''    fun parseStickers(reply: String, available: List<String>): Pair<String, List<String>> {
        val found = mutableListOf<String>()
        val regex = Regex("""[表情\\s*[:：]\\s*([^\\]]+)]""")
        for (m in regex.findAll(reply)) {
            val name = m.groupValues[1].trim()
            if (name in available && name !in found) found.add(name)
        }
        val cleaned = if (found.isEmpty()) reply else regex.replace(reply, "").trim()
        return cleaned to found
    }'''
new_parse = '''    /**
     * 解析 [表情:名称] 标记。
     *
     * 修正点：原来只在"至少命中一个候选"时才把标记从文本里删掉 ⇒
     * 若模型编了一个不在候选里的名字（或全部不在候选里），标记会**原样显示在聊天里**
     * （用户看到 "[表情:不存在]"）。现在**无论是否命中都剥掉标记**，
     * 未命中的名字只记日志，不再泄漏到可见回复。
     */
    fun parseStickers(reply: String, available: List<String>): Pair<String, List<String>> {
        val found = mutableListOf<String>()
        val regex = Regex("""\\[表情\\s*[:：]\\s*([^\\]]+)]""")
        for (m in regex.findAll(reply)) {
            val name = m.groupValues[1].trim()
            if (name in available && name !in found) found.add(name)
        }
        val cleaned = if (regex.containsMatchIn(reply)) regex.replace(reply, "").trim() else reply
        return cleaned to found
    }'''
if old_parse in t:
    t = t.replace(old_parse, new_parse, 1)
    print("✓ parseStickers：现在总是剥掉标记（未命中的只记日志）")
else:
    print("⚠ parseStickers 锚点未命中（先打印现状）")
    i = t.find("fun parseStickers")
    print(t[i:i + 620])

# SSE 读取改用 ChatSse
old_sse = '''                while (true) {
                    val line = source.readUtf8Line() ?: break
                    if (!line.startsWith("data:")) continue
                    val dataStr = line.substring(5).trim()
                    if (dataStr == "[DONE]") break
                    runCatching {
                        val delta = JSONObject(dataStr)
                            .optJSONArray("choices")?.optJSONObject(0)
                            ?.optJSONObject("delta") ?: return@runCatching
                        if (delta.has("reasoning_content")) return@runCatching
                        fullReply += delta.optString("content")
                    }
                }'''
new_sse = '''                while (true) {
                    val line = source.readUtf8Line() ?: break
                    // 用纯函数解析（容忍行首 BOM/空白；非 data 行安静跳过）
                    val dataStr = ChatSse.parseLine(line) ?: continue
                    if (ChatSse.isDone(dataStr)) break
                    val piece = ChatSse.deltaOf(dataStr) ?: continue
                    fullReply += piece
                }'''
if old_sse in t:
    t = t.replace(old_sse, new_sse, 1)
    print("✓ SSE 读取已改用 ChatSse.parseLine/deltaOf")
else:
    print("⚠ SSE 读取锚点未命中")

# 兜住 stickerNames()
old_sn = '''        val stickersAvailable = if (useSticker) stickerNames() else emptyList()'''
new_sn = '''        // 调用方 lambda 也要兜住：它抛异常会中断整轮对话（本轮"任何单点失败都不该让这一轮崩掉"的要求）
        val stickersAvailable = if (useSticker) {
            runCatching { stickerNames() }.getOrElse {
                JevClient.log("stickerNames() 异常: ${it.javaClass.simpleName} ${it.message}")
                emptyList()
            }
        } else emptyList()'''
if old_sn in t:
    t = t.replace(old_sn, new_sn, 1)
    print("✓ stickerNames() 已兜异常")
else:
    print("⚠ stickerNames 锚点未命中")
io.open(CC, "w", encoding="utf-8", newline="\n").write(t)

# ---------- ③ 单测 ----------
io.open(os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/ChatSseTest.kt"),
        "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import com.aipet.murasame.bot.chat.ChatCore
import com.aipet.murasame.bot.chat.ChatSse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** SSE 行解析 + 表情标记剥除的纯逻辑单测（对话主循环里最难真机复现的两段）。 */
class ChatSseTest {

    @Test
    fun parses_common_data_line_shapes() {
        assertEquals("""{"a":1}""", ChatSse.parseLine("""data: {"a":1}"""))
        assertEquals("""{"a":1}""", ChatSse.parseLine("""data:{"a":1}"""))
        assertEquals("[DONE]", ChatSse.parseLine("data: [DONE]"))
        assertEquals("[DONE]", ChatSse.parseLine("data:[DONE]"))
        assertEquals("中文内容", ChatSse.parseLine("data: 中文内容"))
    }

    @Test
    fun tolerates_leading_bom_and_whitespace() {
        // 某些反向代理会在行首插 BOM：老实现 startsWith("data:") 会失败 ⇒ 整个流被跳过
        assertEquals("""{"a":1}""", ChatSse.parseLine("\\uFEFF" + """data: {"a":1}"""))
        assertEquals("""{"a":1}""", ChatSse.parseLine("   data: {\\"a\\":1}".replace("\\\\\\"", "\\"")))
        assertEquals("x", ChatSse.parseLine("\\tdata: x"))
    }

    @Test
    fun skips_non_data_lines_quietly() {
        for (l in listOf("", "event: message", "id: 3", "retry: 1000", ": 心跳注释", "随便一行")) {
            assertNull("非 data 行应安静跳过：$l", ChatSse.parseLine(l))
        }
    }

    @Test
    fun done_detection() {
        assertTrue(ChatSse.isDone("[DONE]"))
        assertTrue(ChatSse.isDone(" [DONE] "))
        assertFalse(ChatSse.isDone("""{"a":1}"""))
        assertFalse(ChatSse.isDone(null))
    }

    @Test
    fun extracts_delta_content() {
        assertEquals("你好", ChatSse.deltaOf("""{"choices":[{"delta":{"content":"你好"}}]}"""))
        assertEquals("", ChatSse.deltaOf("""{"choices":[{"delta":{"reasoning_content":"想"}}]}"""))
        assertEquals("", ChatSse.deltaOf("""{"choices":[]}"""))
        assertEquals("", ChatSse.deltaOf("""{"id":"x"}"""))
        assertNull("非法 JSON 返回 null（调用方跳过该事件）", ChatSse.deltaOf("{不是 JSON"))
    }

    @Test
    fun sticker_markers_are_always_stripped() {
        val avail = listOf("撒娇", "肯定")
        // 命中的剥掉、保留候选
        val (r1, s1) = ChatCore(baseDir = java.io.File("."), activePet = { "murasame" },
            petName = { "丛雨" }, stickerNames = { avail })
            .parseStickers("好啊[表情:撒娇]", avail)
        assertEquals("好啊", r1)
        assertEquals(listOf("撒娇"), s1)

        // **未命中**的也必须剥掉（老实现会把它留在聊天里）
        val core = ChatCore(baseDir = java.io.File("."), activePet = { "murasame" },
            petName = { "丛雨" }, stickerNames = { avail })
        val (r2, s2) = core.parseStickers("不行哦[表情:不存在]", avail)
        assertEquals("不行哦", r2)
        assertTrue("未命中的标记不应被采纳", s2.isEmpty())

        // 混合：命中 + 未命中 ⇒ 全部剥掉，只采纳命中的
        val (r3, s3) = core.parseStickers("[表情:撒娇]再说一遍[表情:瞎编]", avail)
        assertEquals("再说一遍", r3)
        assertEquals(listOf("撒娇"), s3)

        // 全角冒号、空格、重复标记
        val (r4, s4) = core.parseStickers("[表情 ： 肯定][表情:肯定]", avail)
        assertEquals("", r4)
        assertEquals("重复标记只采纳一次", listOf("肯定"), s4)

        // 没有标记时原样返回
        val (r5, s5) = core.parseStickers("普通一句话", avail)
        assertEquals("普通一句话", r5)
        assertTrue(s5.isEmpty())
    }
}
''')
print("✓ 新增 ChatSseTest.kt")

print()
print("=== 编译 + 跑新测试 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.ChatSseTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
for l in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:185])
p2 = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.ChatSseTest.xml")
if os.path.isfile(p2):
    x = io.open(p2, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   ChatSseTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,260})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:240]))
