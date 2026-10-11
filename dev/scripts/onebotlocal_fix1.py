# -*- coding: utf-8 -*-
"""真去重：新增纯类 OneBotDedup（可单测）+ 接进 OneBotLocal + 原子缓存 + 按最近活跃淘汰。"""
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

io.open(os.path.join(SRC, "bot/chat/OneBotDedup.kt"), "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame.bot.chat

/**
 * OneBot 消息去重（**纯逻辑，可 JVM 单测**）。
 *
 * 背景（实测读出）：OneBotLocal.handle() 每收到一条消息就无条件 append，
 * 而 lastLine/lastAt 这两个字段**只被写入和从缓存恢复、从来没有被读过做比较** ——
 * 也就是说"去重"这件事看起来有、实际没有。后果是 WebSocket 断线重连后
 * NapCat 重投的同一条消息会被收两次，她很可能会**回两遍**。
 *
 * 设计要点：
 *   1) **优先按 messageId 判重**（协议里它就是唯一标识）；
 *   2) messageId 为空时才回落到"同一会话、与上一条内容相同"的启发式 ——
 *      此时 lastLine 才真正起作用；
 *   3) 只有 id 集合是有界的（按**条数**上限，不用时间窗）：
 *      重连后的重投可能隔很久才来，用时间窗会漏判；
 *      而"同一句话重复说两次"是正常的（不同 id ⇒ 不会误判）。
 */
class OneBotDedup(private val maxIds: Int = 800) {

    private val seenIds = LinkedHashSet<String>()
    private val lastContent = HashMap<String, String>()

    /** @return true 表示这是新消息（应当处理）；false 表示判定为重复（应当丢弃）。 */
    fun accept(key: String, messageId: String, content: String): Boolean {
        val id = messageId.trim()
        if (id.isNotEmpty()) {
            if (!seenIds.add(id)) return false          // 同一个 id 又来一次 ⇒ 重复
            while (seenIds.size > maxIds) {
                val first = seenIds.firstOrNull() ?: break
                seenIds.remove(first)
            }
            lastContent[key] = content
            return true
        }
        // 没有 id：只能靠"与上一条内容相同"判断（同一会话内）
        val prev = lastContent[key]
        lastContent[key] = content
        return prev == null || prev != content
    }

    /** 会话被淘汰时清理其状态，避免 hashmap 无限增长。 */
    fun forget(key: String) {
        lastContent.remove(key)
    }

    /** 从缓存恢复最后一条内容（保持重启前后的启发式连续）。 */
    fun seedLastContent(key: String, content: String) {
        lastContent[key] = content
    }

    fun idCount(): Int = seenIds.size

    fun reset() {
        seenIds.clear()
        lastContent.clear()
    }
}
''')
print("✓ 新增 bot/chat/OneBotDedup.kt")

# ---- 接进 OneBotLocal ----
OL = os.path.join(SRC, "bot/chat/OneBotLocal.kt")
t = io.open(OL, encoding="utf-8").read().replace("\r\n", "\n")
if "OneBotDedup" in t:
    print("· 已接")
else:
    t = t.replace('''    private val lastLine = HashMap<String, String>()''',
                  '''    /**
     * 去重器。注意：旧实现里 lastLine/lastAt 只写不读 —— "看起来有去重、实际没有"，
     * 断线重连后 NapCat 重投的消息会被收两次（她很可能会回两遍）。现在真正用起来了。
     */
    private val dedup = OneBotDedup()
    private val lastLine = HashMap<String, String>()''', 1)
    t = t.replace('''        val msg = OneBotParse.parseMessage(text, selfId) ?: return
        synchronized(lock) {''',
                  '''        val msg = OneBotParse.parseMessage(text, selfId) ?: return
        // 去重：同一 messageId 只处理一次；没有 id 时回落到"与上一条内容相同"
        if (!dedup.accept(msg.key, msg.messageId, msg.content)) {
            log("丢弃重复消息 [" + msg.key + "] id=" + msg.messageId + " 内容=" + msg.content.take(20))
            return
        }
        synchronized(lock) {''', 1)
    # 淘汰改为按最近活跃
    t = t.replace('''            while (sessions.size > MAX_SESSIONS) {
                val first = sessions.keys.firstOrNull() ?: break
                sessions.remove(first)
            }''',
                  '''            while (sessions.size > MAX_SESSIONS) {
                // 按**最近活跃**淘汰（原来按插入顺序，而 UI 是按 lastAt 排序的 ⇒ 两边不一致，
                // 可能把用户正在聊的会话挤掉，却留着很久没动的）
                val victim = sessions.keys.minByOrNull { lastAt[it] ?: 0L } ?: break
                sessions.remove(victim)
                dedup.forget(victim)
            }''', 1)
    # 原子缓存
    t = t.replace('''        cacheFile?.writeText(root.toString())''',
                  '''        // 原子写：缓存体积随会话数增长，写一半被杀的概率不低（缓存可重建，所以坏文件直接覆盖即可，
        // 不需要像聊天记录那样隔离保留）
        cacheFile?.let { SafeStore.writeAtomic(it, root.toString()) }''', 1)
    # 恢复时把最后一条内容喂给去重器
    t = t.replace('''                lastLine[k] = list.lastOrNull()?.optString("content")?.take(80) ?: ""''',
                  '''                val lastContent = list.lastOrNull()?.optString("content") ?: ""
                lastLine[k] = lastContent.take(80)
                dedup.seedLastContent(k, lastContent)''', 1)
    io.open(OL, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ OneBotLocal 已接真去重 + 原子缓存 + 按最近活跃淘汰")

# ---- 单测 ----
io.open(os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/OneBotDedupTest.kt"),
        "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import com.aipet.murasame.bot.chat.OneBotDedup
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** 去重逻辑单测：重点是"重投要挡住，正常的重复发言不能误杀"。 */
class OneBotDedupTest {

    @Test
    fun same_message_id_is_rejected() {
        val d = OneBotDedup()
        assertTrue("第一条应通过", d.accept("private_1", "1001", "在吗"))
        assertFalse("同一个 messageId 再来一次 ⇒ 重复（断线重投的现场）",
            d.accept("private_1", "1001", "在吗"))
    }

    @Test
    fun same_content_with_different_id_must_pass() {
        // "同一句话说两次"是正常的（比如连发两条"在吗"）—— 不能因为内容相同就吞掉
        val d = OneBotDedup()
        assertTrue(d.accept("private_1", "2001", "在吗"))
        assertTrue("不同 id、相同内容 ⇒ 必须通过", d.accept("private_1", "2002", "在吗"))
        assertTrue(d.accept("private_1", "2003", "在吗"))
    }

    @Test
    fun empty_id_falls_back_to_last_content() {
        val d = OneBotDedup()
        assertTrue("没有 id 时第一条通过", d.accept("g1", "", "你好"))
        assertFalse("没有 id 且与上一条内容相同 ⇒ 判为重复", d.accept("g1", "", "你好"))
        assertTrue("内容变了 ⇒ 通过", d.accept("g1", "", "在吗"))
    }

    @Test
    fun fallback_is_per_session() {
        val d = OneBotDedup()
        assertTrue(d.accept("a", "", "同样的话"))
        assertTrue("另一个会话里的相同内容不应被误判", d.accept("b", "", "同样的话"))
    }

    @Test
    fun long_delayed_redelivery_is_still_rejected() {
        // 重连后的重投可能隔很久才到：所以按**条数**上限而不是时间窗
        val d = OneBotDedup()
        assertTrue(d.accept("p", "9001", "很久以前的一条"))
        for (i in 0 until 50) d.accept("p", "id$i", "后来的消息$i")
        assertFalse("即便过了很多条，同一 id 仍应判重", d.accept("p", "9001", "很久以前的一条"))
    }

    @Test
    fun id_set_is_bounded() {
        val d = OneBotDedup(maxIds = 10)
        for (i in 0 until 100) d.accept("p", "id$i", "内容$i")
        assertTrue("id 集合必须有上界，实际 ${d.idCount()}", d.idCount() <= 10)
        // 被挤出去的旧 id 之后不再判重（这是有界性的代价，明确记录）
        assertTrue(d.accept("p", "id0", "内容0"))
    }

    @Test
    fun forget_clears_session_state() {
        val d = OneBotDedup()
        d.accept("k", "", "一句话")
        d.forget("k")
        assertTrue("forget 后同一内容应重新通过", d.accept("k", "", "一句话"))
    }

    @Test
    fun seed_then_same_content_is_rejected() {
        // 从缓存恢复：重启后立刻收到与缓存里最后一条相同的内容（无 id）应判重
        val d = OneBotDedup()
        d.seedLastContent("p", "缓存里的最后一句")
        assertFalse(d.accept("p", "", "缓存里的最后一句"))
        assertTrue(d.accept("p", "", "新的一句"))
    }

    @Test
    fun blank_and_whitespace_ids_use_fallback() {
        val d = OneBotDedup()
        assertTrue(d.accept("p", "   ", "内容A"))
        assertFalse("空白 id 视同没有 id", d.accept("p", "\\t", "内容A"))
        assertTrue(d.accept("p", "  ", "内容B"))
    }
}
''')
print("✓ 新增 OneBotDedupTest.kt")

print()
print("=== 编译 + 单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.OneBotDedupTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
for l in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:185])
p2 = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.OneBotDedupTest.xml")
if os.path.isfile(p2):
    x = io.open(p2, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   OneBotDedupTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,240})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:220]))
