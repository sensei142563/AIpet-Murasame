# -*- coding: utf-8 -*-
"""整段替换 MainActivity 的记忆IO块：改为「先导入、后导出」→ 编译装机 → 重跑双向验收。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
ACT = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
VERIFY = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts\verify_memory_roundtrip2.py"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

NEW = '''                // ④ 记忆互通：冷启动 ① 先合并 memory_io/import/ 下等待导入的文件（桌面导出丢进来即可）
                // ② 再写一份导出快照到 memory_io/export/（顺序必须如此，否则快照是导入前的旧状态）
                runCatching {
                    val store = com.aipet.murasame.bot.chat.MemoryStore(app.filesDir) { Store.activePetId() }
                    val ext = app.getExternalFilesDir(null) ?: app.filesDir
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
                    val pet = Store.activePetId().ifBlank { "murasame" }
                    val stamp = java.text.SimpleDateFormat("yyyyMMdd_HHmmss", java.util.Locale.CHINA)
                        .format(java.util.Date())
                    val outDir = File(ext, "memory_io/export").apply { mkdirs() }
                    File(outDir, "memory_" + pet + "_" + stamp + ".json")
                        .writeText(store.exportBundle(pet))
                }'''

a = io.open(ACT, encoding="utf-8").read().replace("\r\n", "\n")
i0 = a.find("                // ④ 记忆互通：冷启动")
if i0 < 0:
    print("✗ 找不到记忆IO段")
    sys.exit(1)
# 段尾：其后第一个行内容恰为 "                }" 的行
i1 = None
pos = i0
for l in a[i0:].split("\n"):
    pos += len(l) + 1
    if l == "                }":
        i1 = pos - 1
        break
if i1 is None:
    print("✗ 找不到段尾")
    sys.exit(1)
a2 = a[:i0] + NEW + a[i1:]
io.open(ACT, "w", encoding="utf-8", newline="\n").write(a2)
print("✓ 已改为「先导入、后导出」（段长 %d → %d 字符）" % (i1 - i0, len(NEW)))

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
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

print()
print("=== 重跑双向验收 ===")
rv = subprocess.run([sys.executable, "-u", VERIFY], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=1800)
print(rv.stdout or rv.stderr)
print("验收 rc =", rv.returncode)
