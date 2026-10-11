# -*- coding: utf-8 -*-
"""检查并清理 PendingInbox.save 的残骸 + 新增 PendingInboxTest（纯 JVM）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
PI = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/ilink/PendingInbox.kt")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(PI, encoding="utf-8").read().replace("\r\n", "\n")
i = t.find("private fun save(")
print("=== save() 现状 ===")
print("\n".join("   " + l for l in t[i:i + 700].split("\n")[:22]))

# 清理未使用的 tmp 行与 import
t2 = re.sub(r"^[ \t]*val tmp = File\([^\n]*\n", "", t, flags=re.M)
t2 = t2.replace("import java.nio.file.Files\n", "").replace("import java.nio.file.StandardCopyOption\n", "")
if t2 != t:
    io.open(PI, "w", encoding="utf-8", newline="\n").write(t2)
    print("✓ 已清理未使用的 tmp 行与 Files import")
    t = t2

# 新增纯 JVM 单测
io.open(os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/PendingInboxTest.kt"),
        "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import com.aipet.murasame.bot.ilink.PendingInbox
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * 待回复收件箱的单测（纯 JVM：它只依赖 java.io.File，不碰 Android）。
 * 重点：损坏时**不能**把尚未回复的消息悄悄覆盖掉；messageId 幂等；上限淘汰。
 */
class PendingInboxTest {

    private lateinit var base: File
    private lateinit var pending: File

    private fun item(id: Long, text: String = "内容$id") =
        PendingInbox.PendingItem(messageId = id, fromUserId = "u1", kind = "text",
            text = text, mediaPath = null, contextToken = null, receivedAt = 1700000000000L + id)

    @Before
    fun setUp() {
        base = Files.createTempDirectory("inbox").toFile()
        pending = File(File(base, "data"), "pending.json")
    }

    @After
    fun tearDown() {
        base.deleteRecursively()
    }

    @Test
    fun append_then_load_roundtrip() {
        PendingInbox.append(base, item(1))
        PendingInbox.append(base, item(2))
        val l = PendingInbox.load(base)
        assertEquals(2, l.size)
        assertEquals(listOf(1L, 2L), l.map { it.messageId })
        assertTrue("save 应留下备份（便于恢复）", File(pending.parentFile, "pending.json.bak").isFile)
    }

    @Test
    fun append_is_idempotent_by_message_id() {
        PendingInbox.append(base, item(7, "第一版"))
        PendingInbox.append(base, item(7, "第二版"))
        val l = PendingInbox.load(base)
        assertEquals("同一 messageId 只应有一条", 1, l.size)
        assertEquals("应以最后一次为准", "第二版", l.first().text)
    }

    @Test
    fun remove_deletes_matching_item() {
        PendingInbox.append(base, item(1))
        PendingInbox.append(base, item(2))
        PendingInbox.remove(base, 1)
        assertEquals(listOf(2L), PendingInbox.load(base).map { it.messageId })
        // 删不存在的 id 不应改变任何东西
        PendingInbox.remove(base, 999)
        assertEquals(listOf(2L), PendingInbox.load(base).map { it.messageId })
    }

    @Test
    fun corrupt_file_is_quarantined_and_not_silently_overwritten() {
        PendingInbox.append(base, item(1))
        // 模拟"写一半被杀"：把文件截断成半截 JSON
        pending.writeText("""{"items":[{"messageId":1,"fromUser""")
        val l = PendingInbox.load(base)
        assertTrue("损坏文件读不出内容（调用方会当空）", l.isEmpty())
        val quarantined = pending.parentFile!!.listFiles()!!.filter { it.name.startsWith("pending.json.corrupt-") }
        assertTrue("原始字节必须被隔离保留", quarantined.isNotEmpty())
        assertTrue("隔离文件里应能看到原内容片段",
            quarantined.first().readText().contains("messageId"))
        assertTrue("旧备份仍在", File(pending.parentFile, "pending.json.bak").isFile)
        // 之后继续追加：新数据可用，且坏文件没被覆盖
        PendingInbox.append(base, item(5))
        assertEquals(listOf(5L), PendingInbox.load(base).map { it.messageId })
        assertTrue("隔离文件仍然存在（未被覆盖）",
            pending.parentFile!!.listFiles()!!.any { it.name.startsWith("pending.json.corrupt-") })
    }

    @Test
    fun recover_from_backup_when_main_is_corrupt() {
        // 先有一份好数据（同时产生 .bak），再故意把主文件写坏
        PendingInbox.append(base, item(1))
        PendingInbox.append(base, item(2))
        assertEquals(2, PendingInbox.load(base).size)
        val bak = File(pending.parentFile, "pending.json.bak")
        assertTrue(bak.isFile)
        pending.writeText("{坏掉的")
        val l = PendingInbox.load(base)
        assertTrue("有可用备份时应恢复出内容（而不是当空）", l.isNotEmpty())
        assertTrue("恢复出的应是备份里的条目", l.all { it.messageId == 1L || it.messageId == 2L })
    }

    @Test
    fun missing_file_is_empty_and_creates_nothing() {
        assertTrue(PendingInbox.load(base).isEmpty())
        assertTrue(!pending.exists() || pending.length() == 0L)
    }
}
''')
print("✓ 新增 PendingInboxTest.kt")

print()
print("=== 跑新测试 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.PendingInboxTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
for l in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:185])
p2 = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.PendingInboxTest.xml")
if os.path.isfile(p2):
    x = io.open(p2, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   PendingInboxTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,280})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:260]))
