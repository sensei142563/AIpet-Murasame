# -*- coding: utf-8 -*-
"""OneBotParse 的对抗测试：畸形 OneBot11 payload（重点：JSON null 被 org.json 变成 "null"）。"""
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

io.open(os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/OneBotAdversarialTest.kt"),
        "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import com.aipet.murasame.bot.chat.OneBotParse
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * OneBot11 协议解析的对抗测试：喂畸形/边界 payload。
 *
 * 重点假设（待验证）：org.json 的 optString() 在**值是 JSON null** 时返回字符串 "null"，
 * 而不是空串 —— 若成立，`user_id: null` 会造出 "private_null" 这种虚构会话，
 * `message: null` 会在聊天里显示一条内容为 "null" 的消息。
 */
class OneBotAdversarialTest {

    private fun msg(json: String, hint: String = "999") = OneBotParse.parseMessage(json, hint)

    @Test
    fun json_null_fields_must_not_become_the_string_null() {
        // user_id / group_id / message 都是 JSON null
        val m = msg("""{"post_type":"message","message_type":"private","user_id":null,
                        "message":null,"time":1700000000,"message_id":"1"}""")
        // 期望：user_id 为 null ⇒ 字段"缺失" ⇒ 解析失败返回 null（不能造出 private_null 会话）
        assertNull("user_id 为 JSON null 时应视为缺失，而不是变成 private_null。实际=$m", m)
    }

    @Test
    fun json_null_message_content_must_be_empty_not_null_string() {
        val j = JSONObject("""{"message":null,"raw_message":null}""")
        val t = OneBotParse.extractText(j)
        // 提示语里提到某个字符串时用中文引号：跨语言生成时要特别小心 ——
        // 我原先把 Kotlin 提示语写成 \"null\"，而 Python 三引号串里 \" 是**合法转义**，
        // 反斜杠被吃掉 ⇒ 生成出来的 Kotlin 变成裸 "null" ⇒ 编译失败。
        //（另注意：本测试文件由脚本生成，直接改生成物会被下次运行覆盖，要改脚本本身。）
        assertFalse("message/raw_message 为 JSON null 时不该得到字面量「null」。实际=$t", t == "null")
        assertEquals("应是空串", "", t)
    }

    @Test
    fun json_null_in_at_segment_must_not_be_literal_null() {
        val j = JSONObject("""{"message":[{"type":"at","data":{"qq":null}}]}""")
        val t = OneBotParse.extractText(j)
        assertFalse("at 段的 qq 为 JSON null 时不该出现 @null。实际=$t", t.contains("@null"))
    }

    @Test
    fun json_null_group_id_must_not_create_group_null() {
        val m = msg("""{"post_type":"message","message_type":"group","user_id":"5","group_id":null,
                        "message":"hi","time":1700000000,"message_id":"2"}""")
        assertNull("group_id 为 JSON null 时应视为缺失。实际=$m", m)
    }

    @Test
    fun login_info_with_null_fields() {
        val r = OneBotParse.parseLoginInfo("""{"status":"ok","retcode":0,
              "data":{"user_id":null,"nickname":null}}""")
        // 两个字段都是 JSON null ⇒ 视为都缺失 ⇒ 应返回 null
        assertNull("user_id/nickname 均为 JSON null 时应视为缺失。实际=$r", r)
    }

    @Test
    fun normal_payloads_still_work() {
        val m = msg("""{"post_type":"message","message_type":"private","user_id":"12345",
                        "message":[{"type":"text","data":{"text":"你好"}},{"type":"image","data":{}}],
                        "time":1700000000,"message_id":"9"}""")
        assertNotNull(m)
        assertEquals("private_12345", m!!.key)
        assertEquals("user", m.role)
        assertEquals("你好[图片]", m.content)
        assertEquals(1700000000000L, m.timestampMs)

        val sent = msg("""{"post_type":"message_sent","message_type":"private","user_id":"12345",
                           "message":"我发出的","time":1700000001,"message_id":"10"}""")
        assertEquals("assistant", sent!!.role)
    }

    @Test
    fun missing_time_falls_back_to_now() {
        val before = System.currentTimeMillis() - 5000
        val m = msg("""{"post_type":"message","message_type":"private","user_id":"1","message":"x"}""")
        assertNotNull(m)
        assertTrue("缺 time 时应回落到当前时间：${m!!.timestampMs}", m.timestampMs >= before)
    }

    @Test
    fun weird_post_and_message_types() {
        assertNull(msg("""{"post_type":"notice","message_type":"private","user_id":"1"}"""))
        assertNull(msg("""{"post_type":"message","user_id":"1","message":"x"}"""))          // 缺 message_type
        assertNull(msg("""{"post_type":"message","message_type":"group","user_id":"1"}"""))  // 缺 group_id
        assertNull(msg("not json at all"))
        assertNull(msg(""))
        assertNull(msg("[]"))
        // 有 user_id 但没 message ⇒ 仍会解析成"内容为空"的一条（实现如此，也合理：
        // "空消息"要不要展示应由调用方决定；这里把现状钉住，避免以后无意改变语义）
        val empty = msg("""{"post_type":"message","message_type":"private","user_id":"1"}""")
        assertNotNull(empty)
        assertEquals("", empty!!.content)
    }

    @Test
    fun huge_and_deep_payload_does_not_crash() {
        val big = "长".repeat(200000)
        val m = msg("""{"post_type":"message","message_type":"private","user_id":"7",
                        "message":[{"type":"text","data":{"text":"$big"}}],"time":1,"message_id":"3"}""")
        assertNotNull(m)
        assertEquals(200000, m!!.content.length)

        // 嵌套很深的 data（不崩溃即可）
        var nested = """{"a":1}"""
        repeat(40) { nested = """{"a":$nested}""" }
        val j = JSONObject("""{"message":[{"type":"text","data":$nested}]}""")
        OneBotParse.extractText(j)   // 不抛异常即通过
    }

    @Test
    fun emoji_and_cq_codes_in_string_message() {
        val j = JSONObject("""{"message":"😀[CQ:image,file=abc.jpg]你好"}""")
        val t = OneBotParse.extractText(j)
        assertTrue("emoji 应保留", t.contains("😀"))
        // 记录现状：字符串形态的 message 会原样带出 CQ 码（数组形态才会映射成 [图片]）
        println("字符串形态 message 的解析结果：$t")
        assertTrue("CQ 码应被映射成 [图片]（此前会原样带出 CQ 码，属 UX 缺口，本轮已修）",
            t.contains("[图片]") && !t.contains("[CQ:"))
        // 其余段的映射
        val j2 = JSONObject("""{"message":"[CQ:face,id=1][CQ:record,file=a.silk]@[CQ:at,qq=123]x"}""")
        assertEquals("[表情][语音]@123x", OneBotParse.extractText(j2))
    }

    @Test
    fun unknown_segment_types_are_skipped() {
        val j = JSONObject("""{"message":[{"type":"mystery","data":{"x":1}},
                                          {"type":"text","data":{"text":"A"}},
                                          {"type":"reply","data":{"id":"1"}},
                                          {"type":"face","data":{"id":"1"}}]}""")
        assertEquals("A[表情]", OneBotParse.extractText(j))
    }
}
''')
print("✓ 新增 OneBotAdversarialTest.kt")

print()
print("=== 跑对抗测试 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.OneBotAdversarialTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
for l in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:185])
p2 = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.OneBotAdversarialTest.xml")
if os.path.isfile(p2):
    x = io.open(p2, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   OneBotAdversarialTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,260})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:230]))
