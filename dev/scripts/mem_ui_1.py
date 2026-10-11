# -*- coding: utf-8 -*-
"""④ 补上界面：记忆页加「导出互通包 / 导入互通包」（SAF），并写 MemoryIO 日志便于验收。编译装机。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
MS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/MemoryScreen.kt")
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


s = io.open(MS, encoding="utf-8").read().replace("\r\n", "\n")

if "exportBundleLauncher" in s:
    note("界面已加过互通按钮", True)
else:
    # ① 在 exportLauncher 之后插入 state + 两个 launcher
    anchor = """        exportTarget = null
        exportZip = false
    }
"""
    note("定位 exportLauncher 结尾", anchor in s)
    add = """        exportTarget = null
        exportZip = false
    }

    // ④ 记忆互通：导出 aipet.memory/1 互通包 / 从文件导入（SAF，可在文件管理器里选任意位置）
    var ioBusy by remember { mutableStateOf(false) }
    val memoryStore = remember(viewPetId) {
        com.aipet.murasame.bot.chat.MemoryStore(ctx.filesDir) { viewPetId }
    }
    val exportBundleLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/json")
    ) { uri ->
        if (uri != null) {
            scope.launch(Dispatchers.IO) {
                ioBusy = true
                val r = runCatching {
                    ctx.contentResolver.openOutputStream(uri)?.use { out ->
                        out.write(memoryStore.exportBundle(viewPetId).toByteArray(Charsets.UTF_8))
                    }
                }
                ioBusy = false
                val msg = if (r.isSuccess) "已导出互通包（$viewPetId）" else "导出失败：${r.exceptionOrNull()?.message}"
                android.util.Log.i("MemoryIO", "UI导出 $viewPetId 成功=${r.isSuccess}")
                scope.launch { android.widget.Toast.makeText(ctx, msg, android.widget.Toast.LENGTH_LONG).show() }
            }
        }
    }
    val importBundleLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri != null) {
            scope.launch(Dispatchers.IO) {
                ioBusy = true
                val r = runCatching {
                    val text = ctx.contentResolver.openInputStream(uri)?.use { ins ->
                        ins.readBytes().toString(Charsets.UTF_8)
                    } ?: error("读不到文件")
                    memoryStore.importBundle(text)
                }
                ioBusy = false
                val res = r.getOrNull()
                if (res != null) {
                    android.util.Log.i("MemoryIO",
                        "UI导入 新增 ${res.added} 重复 ${res.dup} 现有 ${res.total} 角色 ${res.pet}")
                }
                val msg = if (res != null) "导入完成：新增 ${res.added}，重复 ${res.dup}，现有 ${res.total}"
                else "导入失败：${r.exceptionOrNull()?.message}"
                scope.launch {
                    android.widget.Toast.makeText(ctx, msg, android.widget.Toast.LENGTH_LONG).show()
                    version++   // 刷新列表
                }
            }
        }
    }
"""
    s = s.replace(anchor, add, 1)

    # ② trailing 里加两个按钮
    old_trailing = """            trailing = {
                TextButton(onClick = {
                    exportZip = true
                    exportLauncher.launch("chatter_记忆备份_$viewPetId.zip")
                }) { Text("整包备份") }
            }"""
    new_trailing = """            trailing = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = {
                        exportZip = true
                        exportLauncher.launch("chatter_记忆备份_$viewPetId.zip")
                    }) { Text("整包备份") }
                    TextButton(enabled = !ioBusy, onClick = {
                        exportBundleLauncher.launch("aipet_记忆互通_$viewPetId.json")
                    }) { Text("导出互通包") }
                    TextButton(enabled = !ioBusy, onClick = {
                        importBundleLauncher.launch(arrayOf("application/json", "text/plain", "*/*"))
                    }) { Text("导入互通包") }
                }
            }"""
    note("定位记忆文件卡的 trailing", old_trailing in s)
    if old_trailing in s:
        s = s.replace(old_trailing, new_trailing, 1)
        note("已加两个按钮", "导出互通包" in s and "导入互通包" in s)
    io.open(MS, "w", encoding="utf-8", newline="\n").write(s)

if not ok:
    print("✗ 有步骤失败 —— 回滚 MemoryScreen")
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/ui/MemoryScreen.kt"], capture_output=True)
    sys.exit(1)

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:10]:
    print("   " + y[:230])
if r.returncode != 0:
    print("   ✗ 编译失败（保留改动）")
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
