# -*- coding: utf-8 -*-
"""新增 bot/chat/SafeStore.kt（原子写 + 备份 + 损坏隔离/恢复）+ 单测（纯 JVM，可注入失败）。"""
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

io.open(os.path.join(SRC, "bot/chat/SafeStore.kt"), "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame.bot.chat

import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/**
 * 本地小文件的**安全读写**（纯 java.io，可 JVM 单测，无 Android 依赖）。
 *
 * 为什么需要它（实测出来的两条永久丢数据路径）：
 *   · ChatScreen.load 读坏 JSON 时被 runCatching 吞掉 ⇒ sessions 为空 ⇒ 新建空会话；
 *     而 save 每条消息都写 ⇒ **空会话立刻覆盖掉那个坏文件** ⇒ 旧对话永久消失。
 *   · MemoryStore 同理：readHistory 静默返回空，writeHistory 非原子 ⇒ 记忆同样会被覆盖。
 *
 * 所以本类提供三件事：
 *   ① writeAtomic —— 先写同目录临时文件再 move，避免写一半被杀留下半截文件
 *      （项目里 bot/ilink/PendingInbox 已有同样做法，这里抽出来复用）；
 *   ② writeAtomicWithBackup —— 替换前把旧文件留一份 `<name>.bak`；
 *   ③ readWithRecovery —— 主文件坏了就**隔离**它（改名而不是删/覆盖）并尝试从 .bak 恢复，
 *      保证"读不出来"绝不会演变成"被覆盖掉"。
 */
object SafeStore {

    fun bakOf(f: File): File = File(f.parentFile, f.name + ".bak")

    fun tmpOf(f: File): File = File(f.parentFile, f.name + ".tmp")

    /** 原子写：临时文件 + move(REPLACE_EXISTING)。失败时抛异常，且**不动**原文件。 */
    fun writeAtomic(f: File, content: String) {
        f.parentFile?.mkdirs()
        val tmp = tmpOf(f)
        tmp.writeText(content)                       // 这一步失败 ⇒ 抛异常，原文件完好
        Files.move(tmp.toPath(), f.toPath(), StandardCopyOption.REPLACE_EXISTING)
    }

    /** 原子写 + 备份旧内容（旧文件存在时）。返回是否创建了备份。 */
    fun writeAtomicWithBackup(f: File, content: String): Boolean {
        var backedUp = false
        if (f.isFile && f.length() > 0) {
            runCatching {
                f.copyTo(bakOf(f), overwrite = true)
                backedUp = true
            }
        }
        writeAtomic(f, content)
        return backedUp
    }

    /**
     * 读文件；内容交给 [parse] 校验（返回 null 表示不可用）。
     * 主文件不可用且存在 .bak 时：把主文件**隔离**成 `<name>.corrupt-<时间戳>`，改用备份内容。
     * @return 可用的内容，或 null（连备份也没有）
     */
    fun <T> readWithRecovery(f: File, parse: (String) -> T?): T? {
        if (!f.isFile) return null
        val raw = runCatching { f.readText() }.getOrNull()
        if (raw != null) parse(raw)?.let { return it }
        // 主文件坏了
        val bak = bakOf(f)
        val fromBak = if (bak.isFile) runCatching { bak.readText() }.getOrNull()?.let(parse) else null
        if (fromBak != null) {
            // 有可用备份：隔离坏文件（改名保留，绝不删除/覆盖），用备份顶上
            quarantine(f)
            return fromBak
        }
        // 没有可用备份：仍然隔离坏文件，让调用方拿到 null 去走"新建"逻辑，
        // 但**原始字节被保留**在 .corrupt-* 里，之后不会被新内容覆盖掉
        quarantine(f)
        return null
    }

    /** 把损坏文件改名保留（`<name>.corrupt-<yyyyMMddHHmmss>`）。返回隔离后的文件，失败返回 null。 */
    fun quarantine(f: File): File? = runCatching {
        if (!f.isFile) return null
        val stamp = java.text.SimpleDateFormat("yyyyMMddHHmmss", java.util.Locale.US)
            .format(java.util.Date())
        var dst = File(f.parentFile, f.name + ".corrupt-" + stamp)
        var n = 1
        while (dst.exists()) {
            dst = File(f.parentFile, f.name + ".corrupt-" + stamp + "-" + n)
            n++
        }
        if (f.renameTo(dst)) dst else null
    }.getOrNull()
}
''')
print("✓ 新增 bot/chat/SafeStore.kt")

io.open(os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/SafeStoreTest.kt"),
        "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import com.aipet.murasame.bot.chat.SafeStore
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.After
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * 本地文件安全读写的单测（纯 JVM：用临时目录 + java.io.File，可注入失败）。
 * 背景：实测存在"读坏 → 静默当空 → 被新内容覆盖"的永久丢数据路径。
 */
class SafeStoreTest {

    private lateinit var dir: File

    @Before
    fun setUp() {
        dir = Files.createTempDirectory("safestore").toFile()
    }

    @After
    fun tearDown() {
        dir.deleteRecursively()
    }

    @Test
    fun atomic_write_leaves_no_tmp_and_correct_content() {
        val f = File(dir, "a.json")
        SafeStore.writeAtomic(f, """{"v":1}""")
        assertEquals("""{"v":1}""", f.readText())
        assertFalse("不应留下 .tmp", SafeStore.tmpOf(f).exists())
    }

    @Test
    fun when_tmp_write_fails_the_original_is_untouched() {
        val f = File(dir, "b.json")
        SafeStore.writeAtomic(f, "原始内容")
        // 失败注入：把临时文件路径占成目录 ⇒ writeText 必失败
        assertTrue(SafeStore.tmpOf(f).mkdirs())
        var threw = false
        try {
            SafeStore.writeAtomic(f, "新内容")
        } catch (e: Exception) {
            threw = true
        }
        assertTrue("应当抛异常（而不是悄悄写坏）", threw)
        assertEquals("失败时原文件必须完好", "原始内容", f.readText())
    }

    @Test
    fun backup_keeps_previous_content() {
        val f = File(dir, "c.json")
        SafeStore.writeAtomic(f, "第一版")
        assertTrue("旧文件存在时应创建备份", SafeStore.writeAtomicWithBackup(f, "第二版"))
        assertEquals("第二版", f.readText())
        assertEquals("备份应是上一版", "第一版", SafeStore.bakOf(f).readText())
    }

    @Test
    fun recovery_uses_backup_and_quarantines_corrupt_file() {
        val f = File(dir, "d.json")
        SafeStore.writeAtomic(f, """{"history":["旧的一条"]}""")
        SafeStore.writeAtomicWithBackup(f, """{"history":["新的一条"]}""")
        // 模拟"写一半被杀"：主文件变成半截 JSON，备份还是好的
        f.writeText("""{"history":["新的一""")
        val parsed = SafeStore.readWithRecovery(f) { raw ->
            runCatching { JSONArray("[" + raw + "]") }.getOrNull()?.let { raw }   // 这里只要"能解析"
        }
        assertNotNull("坏主文件 + 好备份 ⇒ 应恢复出备份内容", parsed)
        // 备份保存的是**写入前**的版本：主文件是"写一半被杀"留下的一半，
        // 而 .bak 是上一版完整内容 ⇒ 恢复出来应该是它（这正是想要的语义）。
        // 我第一次把期望写成"写入后的内容"，是**测试**错了，不是实现错了。
        assertEquals("""{"history":["旧的一条"]}""", parsed)
        assertTrue("坏文件应被隔离保留（不能删、不能被覆盖）",
            dir.listFiles()!!.any { it.name.startsWith("d.json.corrupt-") })
        // 注意：这里刻意不写"带转义引号的字符串"。上一轮我在生成脚本的三引号串里写了 \\"，
        // 而 Python 里 \\" 是合法转义、反斜杠会被吃掉 ⇒ 生成出的 Kotlin 成了裸引号 ⇒ 编译失败。
        // 结论：生成 Kotlin 时，表达式里不要出现转义引号，换个等价写法（这里只比对前半段即可）。
        assertFalse("隔离后主文件位置不应再是坏内容", f.isFile && f.readText().contains("新的一"))
    }

    @Test
    fun corrupt_file_without_backup_is_still_preserved() {
        val f = File(dir, "e.json")
        f.writeText("半截 JSON {")
        val r = SafeStore.readWithRecovery(f) { raw -> runCatching { JSONArray(raw) }.getOrNull() }
        assertNull("没有备份时调用方会拿到 null（去走新建逻辑）", r)
        val quarantined = dir.listFiles()!!.filter { it.name.startsWith("e.json.corrupt-") }
        assertTrue("但原始字节必须被保留下来", quarantined.isNotEmpty())
        assertEquals("半截 JSON {", quarantined.first().readText())
        assertFalse("主文件已让位，后续写入不会再覆盖它", f.exists())
    }

    @Test
    fun missing_file_returns_null_without_creating_anything() {
        val f = File(dir, "nope.json")
        assertNull(SafeStore.readWithRecovery(f) { it })
        assertEquals(0, dir.listFiles()!!.size)
    }

    @Test
    fun valid_file_reads_without_touching_backup() {
        val f = File(dir, "g.json")
        SafeStore.writeAtomic(f, "好的")
        assertEquals("好的", SafeStore.readWithRecovery(f) { it })
        assertFalse(SafeStore.bakOf(f).exists())
        assertTrue(dir.listFiles()!!.none { it.name.contains("corrupt") })
    }
}
''')
print("✓ 新增 SafeStoreTest.kt")

print()
print("=== 编译 + 跑 SafeStore 测试 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.SafeStoreTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
for l in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:185])
p2 = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.SafeStoreTest.xml")
if os.path.isfile(p2):
    x = io.open(p2, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   SafeStoreTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,300})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:270]))
