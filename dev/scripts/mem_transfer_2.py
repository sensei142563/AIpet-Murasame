# -*- coding: utf-8 -*-
"""修正接线：MemoryStore 只留纯逻辑（exportBundle/importBundle）；文件读写放 MainActivity，
   用 getExternalFilesDir(null) 下的 memory_io/{export,import,imported}（可 adb pull 取证）。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
MS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/MemoryStore.kt")
ACT = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


# ① MemoryStore：删掉三个用错目录的辅助函数
s = io.open(MS, encoding="utf-8").read().replace("\r\n", "\n")
start = s.find("    /** 外部目录（可 adb pull / 用户手动拷贝）")
end = s.find("    private fun now(): String =")
note("定位要删的辅助函数段", start > 0 and end > start)
if start > 0 and end > start:
    s = s[:start] + s[end:]
    io.open(MS, "w", encoding="utf-8", newline="\n").write(s)
    note("已删除 externalIoDir/exportSnapshot/autoImport（改由 MainActivity 用外部目录做）",
         "externalIoDir" not in s)

# ② MainActivity：把两行接线换成完整内联块
a = io.open(ACT, encoding="utf-8").read().replace("\r\n", "\n")
old = """                // ④ 记忆互通：冷启动写一份导出快照，并合并 memory_io/import/ 里等待导入的文件
                runCatching { BotRepo.memoryStore.exportSnapshot() }
                runCatching { BotRepo.memoryStore.autoImport() }"""
new = """                // ④ 记忆互通：冷启动 ① 写一份导出快照（可 adb pull / 手动拷贝给桌面）
                // ② 合并 memory_io/import/ 下等待导入的文件（桌面导出丢进来即可，处理完归档）
                runCatching {
                    val store = com.aipet.murasame.bot.chat.MemoryStore(app.filesDir) { Store.activePetId() }
                    val ext = app.getExternalFilesDir(null) ?: app.filesDir
                    val pet = Store.activePetId().ifBlank { "murasame" }
                    val stamp = java.text.SimpleDateFormat("yyyyMMdd_HHmmss", java.util.Locale.CHINA)
                        .format(java.util.Date())
                    val outDir = File(ext, "memory_io/export").apply { mkdirs() }
                    File(outDir, "memory_" + pet + "_" + stamp + ".json")
                        .writeText(store.exportBundle(pet))
                    val inDir = File(ext, "memory_io/import")
                    val files = inDir.listFiles { f -> f.isFile && f.name.endsWith(".json") }
                    if (files != null && files.isNotEmpty()) {
                        val done = File(ext, "memory_io/imported").apply { mkdirs() }
                        files.forEach { f ->
                            val r = runCatching { store.importBundle(f.readText()) }.getOrNull()
                            if (r != null) {
                                android.util.Log.i("MemoryIO",
                                    "导入 " + f.name + " 新增 " + r.added + " 重复 " + r.dup +
                                        " 现有 " + r.total + " 角色 " + r.pet)
                                runCatching { f.renameTo(File(done, f.name)) }
                            }
                        }
                    }
                }"""
note("定位 MainActivity 旧接线", old in a)
if old in a:
    a = a.replace(old, new, 1)
    if "import java.io.File" not in a:
        a = a.replace("import android.os.Bundle", "import android.os.Bundle\nimport java.io.File", 1)
    io.open(ACT, "w", encoding="utf-8", newline="\n").write(a)
    note("MainActivity 接线完成（外部目录 + 归档）", "memory_io/import" in a)

print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:10]:
    print("   " + y[:230])
if r.returncode != 0:
    sys.exit(1)


def itime():
    t = subprocess.run([ADB, "shell", "dumpsys", "package", PKG], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300).stdout
    mm = re.search(r"lastUpdateTime=([^\n]+)", t)
    return mm.group(1).strip() if mm else "?"


before = itime()
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
for att in range(1, 4):
    rr = subprocess.run([ADB, "install", "-r", "--no-streaming", APK], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=3600)
    print("   装 %d:" % att, ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:44])
    time.sleep(3)
    now = itime()
    if now != before and now != "?":
        print("   ✓ 已装上:", now)
        break
