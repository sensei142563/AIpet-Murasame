# -*- coding: utf-8 -*-
"""Store 加固：资产复制原子化 + 长度校验（纯函数可单测）+ listPets 过滤空壳条目。"""
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

# ---------- ① 纯函数：资产是否需要（重新）复制 ----------
io.open(os.path.join(SRC, "AssetSeed.kt"), "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

/**
 * 资产种子复制的**纯判定逻辑**（可 JVM 单测）。
 *
 * 背景（读 Store.kt 得来）：copyAssetDir 已经有"目录级"自愈 —— 每次启动递归，
 * 缺失文件会补齐（注释里写着"修复历史半截种子"）。但**文件级**没有：
 * `if (childDst.exists()) continue` 意味着一个被复制到一半就被杀的文件**永远存在**，
 * 于是永远被跳过 ⇒ 那个文件**永久截断**（用户看到的是"角色装好了但某个资源坏了"）。
 *
 * 所以判定要同时看：是否存在、长度是否等于资产长度（能拿到时）、以及**是否为半截临时文件**。
 * 复制本身改为"写临时文件 + 改名"后，半截文件根本不会以正式名字出现，
 * 这里的长度校验是第二道保险（针对历史遗留的坏文件）。
 */
object AssetSeed {

    private const val TMP_SUFFIX = ".part"

    fun partOf(dst: java.io.File): java.io.File = java.io.File(dst.parentFile, dst.name + TMP_SUFFIX)

    /**
     * 是否需要（重新）复制这个资产文件。
     * @param dstExists 目标正式文件是否已存在
     * @param dstLen    目标正式文件长度（不存在时为 0）
     * @param assetLen  资产长度；拿不到时为 null（压缩资产可能无法取长度）
     */
    fun needsCopy(dstExists: Boolean, dstLen: Long, assetLen: Long?): Boolean {
        if (!dstExists) return true
        if (assetLen == null) return false          // 拿不到长度：沿用"存在即跳过"，避免每次启动重拷
        return dstLen != assetLen                   // 长度不符（含被截断）⇒ 重拷
    }

    /** 清理遗留的半截临时文件（启动时调用一次即可）。 */
    fun cleanupParts(dir: java.io.File): Int {
        var n = 0
        dir.listFiles()?.forEach { f ->
            if (f.isFile && f.name.endsWith(TMP_SUFFIX)) {
                if (f.delete()) n++
            }
        }
        return n
    }
}
''')
print("✓ 新增 AssetSeed.kt")

# ---------- ② Store：原子复制 + 长度校验 + listPets 过滤 ----------
SP = os.path.join(SRC, "Store.kt")
t = io.open(SP, encoding="utf-8").read().replace("\r\n", "\n")

old_copy = '''            if ((am.list(childAsset) ?: emptyArray()).isEmpty() && name.contains('.')) {
                // 跳过已存在文件：保护用户记忆/编辑；补齐缺失文件（修复历史半截种子）
                if (childDst.exists()) continue
                runCatching {
                    am.open(childAsset).use { input -> childDst.outputStream().use { input.copyTo(it) } }
                }.onFailure { android.util.Log.w("Store", "种子文件复制失败: $childAsset -> $it") }'''
new_copy = '''            if ((am.list(childAsset) ?: emptyArray()).isEmpty() && name.contains('.')) {
                // 跳过已存在且**长度正确**的文件：保护用户记忆/编辑；补齐缺失或半截的文件。
                // 关键改动：原来只判 exists ⇒ 被复制到一半就被杀的文件会永远存在、永远被跳过 ⇒
                // 那个资源**永久截断**（用户看到"角色装好了但某个文件坏了"）。
                val assetLen = runCatching {
                    am.openFd(childAsset).use { it.length }
                }.getOrNull()
                if (!AssetSeed.needsCopy(childDst.exists(), childDst.length(), assetLen)) continue
                // 原子复制：写临时文件再改名 ⇒ 正式文件名下永远不会出现半截内容
                val part = AssetSeed.partOf(childDst)
                runCatching {
                    am.open(childAsset).use { input ->
                        part.outputStream().use { input.copyTo(it) }
                    }
                    if (!part.renameTo(childDst)) {
                        part.copyTo(childDst, overwrite = true)
                        part.delete()
                    }
                }.onFailure {
                    runCatching { part.delete() }
                    android.util.Log.w("Store", "种子文件复制失败: $childAsset -> $it")
                }'''
if old_copy in t:
    t = t.replace(old_copy, new_copy, 1)
    print("✓ copyAssetDir 改为原子复制 + 长度校验")
else:
    print("⚠ copyAssetDir 锚点未命中")

# cleanup 半截文件（放在 seedPetsIfNeeded 开头）
old_seed = '''    private fun seedPetsIfNeeded(context: Context) {
        val am = context.assets'''
new_seed = '''    private fun seedPetsIfNeeded(context: Context) {
        val am = context.assets
        // 清掉历史遗留的半截临时文件（正常流程不会留下，属于兜底）
        runCatching { AssetSeed.cleanupParts(petsDir) }.getOrNull()?.let {
            if (it > 0) android.util.Log.i("Store", "清理了 $it 个半截种子临时文件")
        }'''
if old_seed in t:
    t = t.replace(old_seed, new_seed, 1)
    print("✓ 启动时清理半截临时文件")

# listPets：跳过磁盘上不存在的条目（避免"空壳角色"）
old_list = '''                val id = entry.optString("id")
                if (id.isBlank()) return@runCatching
                val petJson = readJson(safeSub(petsDir, "$id/pet.json")) ?: JSONObject()'''
new_list = '''                val id = entry.optString("id")
                if (id.isBlank()) return@runCatching
                // 注册表有条目但磁盘上没有这个角色包（例如种子中断/被手动删掉）⇒
                // 不再产出一个"空壳角色"混进列表（名字回退成 id、头像为空，用户会一头雾水）
                val packDir = safeSub(petsDir, id)
                val petJsonFile = File(packDir, "pet.json")
                if (!packDir.isDirectory || !petJsonFile.isFile) {
                    android.util.Log.w("Store", "注册表里的角色在磁盘上不存在，已跳过: $id")
                    return@runCatching
                }
                val petJson = readJson(petJsonFile) ?: JSONObject()'''
if old_list in t:
    t = t.replace(old_list, new_list, 1)
    print("✓ listPets 过滤磁盘上不存在的空壳条目")
else:
    print("⚠ listPets 锚点未命中")
io.open(SP, "w", encoding="utf-8", newline="\n").write(t)

# ---------- ③ 单测 ----------
io.open(os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/AssetSeedTest.kt"),
        "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** 资产种子复制的判定逻辑单测：重点是"半截文件必须被重新复制"。 */
class AssetSeedTest {

    private lateinit var dir: File

    @Before
    fun setUp() {
        dir = Files.createTempDirectory("assetseed").toFile()
    }

    @After
    fun tearDown() {
        dir.deleteRecursively()
    }

    @Test
    fun missing_file_needs_copy() {
        assertTrue(AssetSeed.needsCopy(dstExists = false, dstLen = 0, assetLen = 100))
        assertTrue(AssetSeed.needsCopy(dstExists = false, dstLen = 0, assetLen = null))
    }

    @Test
    fun existing_file_with_unknown_asset_length_is_kept() {
        // 压缩资产拿不到长度：沿用"存在即跳过"，否则每次启动都要重拷
        assertFalse(AssetSeed.needsCopy(dstExists = true, dstLen = 123, assetLen = null))
    }

    @Test
    fun truncated_file_must_be_recopied() {
        // 这正是实测那条路径：复制到一半被杀 ⇒ 文件存在但长度不对 ⇒ 永远被跳过
        assertTrue("半截文件必须重拷", AssetSeed.needsCopy(dstExists = true, dstLen = 40, assetLen = 100))
        assertTrue(AssetSeed.needsCopy(dstExists = true, dstLen = 0, assetLen = 100))
    }

    @Test
    fun complete_file_is_kept() {
        assertFalse(AssetSeed.needsCopy(dstExists = true, dstLen = 100, assetLen = 100))
    }

    @Test
    fun oversized_file_also_recopied() {
        // 长度不符（无论大小）都重拷：可能是旧版本残留或用户误改
        assertTrue(AssetSeed.needsCopy(dstExists = true, dstLen = 200, assetLen = 100))
    }

    @Test
    fun part_file_path_is_sibling_with_suffix() {
        val dst = File(dir, "model.bin")
        val part = AssetSeed.partOf(dst)
        assertEquals(dir, part.parentFile)
        assertEquals("model.bin.part", part.name)
    }

    @Test
    fun cleanup_removes_only_part_files() {
        File(dir, "a.part").writeText("半截")
        File(dir, "b.part").writeText("半截")
        File(dir, "keep.bin").writeText("正式文件")
        File(dir, "sub").mkdirs()                       // 目录不该被删
        assertEquals(2, AssetSeed.cleanupParts(dir))
        assertFalse(File(dir, "a.part").exists())
        assertFalse(File(dir, "b.part").exists())
        assertTrue("正式文件必须保留", File(dir, "keep.bin").exists())
        assertTrue("目录必须保留", File(dir, "sub").isDirectory)
    }
}
''')
print("✓ 新增 AssetSeedTest.kt")

print()
print("=== 编译 + 跑新测试 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.AssetSeedTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
for l in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:185])
p2 = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.AssetSeedTest.xml")
if os.path.isfile(p2):
    x = io.open(p2, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   AssetSeedTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,260})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:240]))
