# -*- coding: utf-8 -*-
"""把 OneBot11 事件解析抽成纯函数（OneBotParse）并写单测；OneBotLocal 改为调用它。
   —— 让手机端 QQ 通路在真机之前就先被离线验证。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
OB = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/OneBotLocal.kt")
TEST = os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/OneBotParseTest.kt")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① 纯解析层 ----------
io.open(os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/OneBotParse.kt"),
        "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame.bot.chat

import org.json.JSONArray
import org.json.JSONObject

/** 解析出来的一条消息（纯数据，便于单测）。 */
data class OneBotMsg(
    val key: String,        // private_<uid> / group_<gid>
    val role: String,       // user / assistant
    val content: String,
    val timestampMs: Long,
    val messageId: String,
)

/**
 * OneBot11 事件解析（**纯函数，无 Android 依赖**，因此可用 JVM 单测覆盖）。
 *
 * 为什么单独抽出来：手机端"直连本机 NapCat"这条路，真机联调成本高，
 * 而协议解析恰恰是最容易出错、又最适合离线验证的部分 —— 抽成纯函数后
 * 可以用真实 payload 断言（见 OneBotParseTest）。
 */
object OneBotParse {

    /** OneBot11 的 message 可能是 string，也可能是 [{type,data}] 数组。 */
    fun extractText(j: JSONObject): String {
        val msg = j.opt("message")
        if (msg is String) return msg
        if (msg is JSONArray) {
            val sb = StringBuilder()
            for (i in 0 until msg.length()) {
                val seg = msg.optJSONObject(i) ?: continue
                when (seg.optString("type")) {
                    "text" -> sb.append(seg.optJSONObject("data")?.optString("text").orEmpty())
                    "image" -> sb.append("[图片]")
                    "face" -> sb.append("[表情]")
                    "record" -> sb.append("[语音]")
                    "at" -> sb.append("@" + (seg.optJSONObject("data")?.optString("qq") ?: ""))
                    "reply" -> {}
                    else -> {}
                }
            }
            return sb.toString()
        }
        return j.optString("raw_message")
    }

    /**
     * 解析一条 message / message_sent 事件；不是消息事件（或字段不全）返回 null。
     * @param selfIdHint 已知的自身 QQ 号（用于判断是不是自己发的）；为空则回落到事件里的 self_id
     */
    fun parseMessage(text: String, selfIdHint: String = ""): OneBotMsg? = runCatching {
        val j = JSONObject(text)
        val post = j.optString("post_type")
        if (post != "message" && post != "message_sent") return null
        val type = j.optString("message_type")
        val uid = j.optString("user_id")
        val gid = j.optString("group_id")
        if (type.isEmpty()) return null
        if (type == "group" && gid.isEmpty()) return null
        if (type == "private" && uid.isEmpty()) return null
        val key = if (type == "group") "group_$gid" else "private_$uid"
        val myId = selfIdHint.ifBlank { j.optString("self_id") }
        val fromMe = post == "message_sent" || (myId.isNotBlank() && uid == myId)
        OneBotMsg(
            key = key,
            role = if (fromMe) "assistant" else "user",
            content = extractText(j),
            timestampMs = j.optLong("time", System.currentTimeMillis() / 1000) * 1000,
            messageId = j.optString("message_id"),
        )
    }.getOrNull()

    /** 解析 get_login_info 的回包（{"status":"ok","retcode":0,"data":{"user_id":…,"nickname":…}}）。 */
    fun parseLoginInfo(text: String): Pair<String, String>? = runCatching {
        val j = JSONObject(text)
        if (!j.has("status")) return null
        val d = j.optJSONObject("data") ?: return null
        val id = d.optString("user_id")
        val nick = d.optString("nickname")
        if (id.isEmpty() && nick.isEmpty()) return null
        id to nick
    }.getOrNull()
}
''')
print("✓ 新增 OneBotParse.kt（纯函数解析层）")

# ---------- ② OneBotLocal 改为调用纯函数（去掉重复实现） ----------
t = io.open(OB, encoding="utf-8").read().replace("\r\n", "\n")
before = t
# handle(): 用 OneBotParse.parseLoginInfo / parseMessage
t = re.sub(r"        if \(j\.has\(\"echo\"\) && j\.has\(\"status\"\)\) \{.*?\n            return\n        \}\n",
           """        if (j.has("echo") && j.has("status")) {
            if (j.optString("echo").startsWith("get_login_info")) {
                OneBotParse.parseLoginInfo(text)?.let { (id, nick) ->
                    selfId = id
                    nickname = nick
                    log("登录信息：$nick($id)")
                }
            }
            return
        }
""", t, count=1, flags=re.S)
# 用 parseMessage 替换原来的手工解析（保留落盘/日志）
t = re.sub(r"        if \(post != \"message\" && post != \"message_sent\"\) return\n.*?\n        saveCache\(\)\n",
           """        if (post != "message" && post != "message_sent") return
        val msg = OneBotParse.parseMessage(text, selfId) ?: return
        synchronized(lock) {
            val list = sessions.getOrPut(msg.key) { mutableListOf() }
            list.add(JSONObject().apply {
                put("role", msg.role)
                put("content", msg.content)
                put("timestamp", msg.timestampMs)
            })
            while (list.size > MAX_PER_SESSION) list.removeAt(0)
            lastLine[msg.key] = msg.content.take(80)
            lastAt[msg.key] = System.currentTimeMillis()
            while (sessions.size > MAX_SESSIONS) {
                val first = sessions.keys.firstOrNull() ?: break
                sessions.remove(first)
            }
        }
        lastEventAt = System.currentTimeMillis()
        log("收到 [" + msg.key + "] " + msg.content.take(40))
        saveCache()
""", t, count=1, flags=re.S)
# 删掉旧的私有 extractText（已由纯函数取代）
t = re.sub(r"    /\*\* OneBot11 的 message 可能是 string.*?\n    \}\n\n", "", t, count=1, flags=re.S)
io.open(OB, "w", encoding="utf-8", newline="\n").write(t)
print("✓ OneBotLocal 改为调用 OneBotParse（%s）" % ("有变化" if t != before else "无变化 ⚠"))

# ---------- ③ 单测：真实 payload ----------
io.open(TEST, "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import com.aipet.murasame.bot.chat.OneBotParse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/** OneBot11 解析的 JVM 单测：用真实形态的 payload（不需要手机/NapCat）。 */
class OneBotParseTest {

    @Test
    fun private_text_message() {
        val raw = """{"post_type":"message","message_type":"private","sub_type":"friend",
            "message_id":123,"user_id":10086,"self_id":3559307823,"time":1791712800,
            "raw_message":"你好呀","message":"你好呀"}"""
        val m = OneBotParse.parseMessage(raw, "3559307823")
        assertNotNull(m)
        assertEquals("private_10086", m!!.key)
        assertEquals("user", m.role)
        assertEquals("你好呀", m.content)
        assertEquals(1791712800000L, m.timestampMs)
    }

    @Test
    fun group_text_message_key_and_role() {
        val raw = """{"post_type":"message","message_type":"group","group_id":987654,
            "user_id":10086,"self_id":3559307823,"time":1791712801,
            "message":[{"type":"text","data":{"text":"在吗"}}]}"""
        val m = OneBotParse.parseMessage(raw, "3559307823")
        assertEquals("group_987654", m!!.key)
        assertEquals("user", m.role)
        assertEquals("在吗", m.content)
    }

    @Test
    fun message_sent_counts_as_assistant() {
        val raw = """{"post_type":"message_sent","message_type":"private","user_id":10086,
            "self_id":3559307823,"time":1791712802,"message":"我在"}"""
        val m = OneBotParse.parseMessage(raw, "3559307823")
        assertEquals("assistant", m!!.role)
    }

    @Test
    fun own_user_id_is_treated_as_assistant_even_for_plain_message() {
        val raw = """{"post_type":"message","message_type":"private","user_id":3559307823,
            "self_id":3559307823,"time":1791712803,"message":"自言自语"}"""
        assertEquals("assistant", OneBotParse.parseMessage(raw, "3559307823")!!.role)
    }

    @Test
    fun array_message_keeps_placeholders() {
        val raw = """{"post_type":"message","message_type":"private","user_id":7,"self_id":1,
            "time":1791712804,"message":[{"type":"text","data":{"text":"看这个"}},
            {"type":"image","data":{"file":"a.jpg"}},{"type":"face","data":{"id":"1"}},
            {"type":"at","data":{"qq":"10086"}},{"type":"reply","data":{"id":"9"}}]}"""
        val m = OneBotParse.parseMessage(raw, "1")
        assertEquals("看这个[图片][表情]@10086", m!!.content)
    }

    @Test
    fun non_message_events_are_ignored() {
        assertNull(OneBotParse.parseMessage("""{"post_type":"meta_event","meta_event_type":"heartbeat"}"""))
        assertNull(OneBotParse.parseMessage("""{"post_type":"notice","notice_type":"group_recall"}"""))
        assertNull(OneBotParse.parseMessage("not json at all"))
    }

    @Test
    fun missing_ids_are_rejected() {
        assertNull(OneBotParse.parseMessage("""{"post_type":"message","message_type":"group","message":"hi"}"""))
        assertNull(OneBotParse.parseMessage("""{"post_type":"message","message_type":"private","message":"hi"}"""))
    }

    @Test
    fun login_info_reply() {
        val raw = """{"status":"ok","retcode":0,"data":{"user_id":3559307823,"nickname":"丛雨"}}"""
        val p = OneBotParse.parseLoginInfo(raw)
        assertEquals("3559307823" to "丛雨", p)
        assertNull(OneBotParse.parseLoginInfo("""{"status":"failed","retcode":1}"""))
    }

    @Test
    fun timestamp_falls_back_to_now_when_absent() {
        val raw = """{"post_type":"message","message_type":"private","user_id":5,"self_id":1,"message":"hi"}"""
        val m = OneBotParse.parseMessage(raw, "1")!!
        assertEquals(true, m.timestampMs > 1_600_000_000_000L)
    }
}
''')
print("✓ 新增 OneBotParseTest.kt（9 个用例，含真实 payload）")

print()
print("=== 跑单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.OneBotParseTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:170])
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
if os.path.isdir(d):
    p2 = os.path.join(d, "TEST-com.aipet.murasame.OneBotParseTest.xml")
    if os.path.isfile(p2):
        x = io.open(p2, encoding="utf-8", errors="replace").read()
        m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        print("   OneBotParseTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
