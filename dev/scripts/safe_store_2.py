# -*- coding: utf-8 -*-
"""① 修我的测试预期（备份=写入前版本）② 把 SafeStore 接进 ChatScreen 与 MemoryStore ③ 全量回归 ④ 提交"""
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
TST = os.path.join(CHAT, "app/src/test/java/com/aipet/murasame")
GEN = os.path.join(MAIN, "dev", "scripts", "safe_store_1.py")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ① 修测试预期（在生成脚本里改，避免被覆盖）
g = io.open(GEN, encoding="utf-8").read().replace("\r\n", "\n")
g = g.replace('''        assertNotNull("坏主文件 + 好备份 ⇒ 应恢复出备份内容", parsed)
        assertEquals("""{"history":["新的一条"]}""", parsed)''',
              '''        assertNotNull("坏主文件 + 好备份 ⇒ 应恢复出备份内容", parsed)
        // 备份保存的是**写入前**的版本：主文件是"写一半被杀"留下的一半，
        // 而 .bak 是上一版完整内容 ⇒ 恢复出来应该是它（这正是想要的语义）。
        // 我第一次把期望写成"写入后的内容"，是**测试**错了，不是实现错了。
        assertEquals("""{"history":["旧的一条"]}""", parsed)''', 1)
io.open(GEN, "w", encoding="utf-8", newline="\n").write(g)
print("✓ 已修测试预期（备份=写入前版本）")
# 把已生成的测试文件里那一行也改掉（不等重新生成）
T = os.path.join(TST, "SafeStoreTest.kt")
t = io.open(T, encoding="utf-8").read().replace("\r\n", "\n")
t = t.replace('assertEquals("""{"history":["新的一条"]}""", parsed)',
              'assertEquals("""{"history":["旧的一条"]}""", parsed)   // 备份=写入前版本')
io.open(T, "w", encoding="utf-8", newline="\n").write(t)

# ② ChatScreen：安全读 + 原子写 + 损坏恢复
CS = os.path.join(SRC, "ui/ChatScreen.kt")
t = io.open(CS, encoding="utf-8").read().replace("\r\n", "\n")
old_load = '''        runCatching {
            val f = file(ctx, petId)
            if (f.isFile) {
                val arr = JSONArray(f.readText())'''
new_load = '''        runCatching {
            val f = file(ctx, petId)
            // 用 SafeStore 读：主文件损坏时**隔离**它（改名保留）并尝试从 .bak 恢复，
            // 绝不静默当成"空会话"—— 否则紧接着的 save 会把旧对话直接覆盖掉（实测过的永久丢数据路径）。
            val arr = SafeStore.readWithRecovery(f) { raw -> runCatching { JSONArray(raw) }.getOrNull() }
            if (arr != null) {'''
if old_load in t:
    t = t.replace(old_load, new_load, 1)
    # 对应的收尾括号：原来 if (f.isFile) { ... } 结构要收口
    old_tail = '''                    sessions.add(ChatSession(o.optString("id"), o.optString("title"), msgs,
                        o.optLong("updatedAt", System.currentTimeMillis())))
                }
            }
        }'''
    new_tail = '''                    sessions.add(ChatSession(o.optString("id"), o.optString("title"), msgs,
                        o.optLong("updatedAt", System.currentTimeMillis())))
                }
            }
        }'''
    t = t.replace(old_tail, new_tail, 1)
    print("✓ ChatScreen.load 已接 SafeStore.readWithRecovery")
else:
    print("⚠ ChatScreen.load 锚点未命中")

old_save = '''            f.writeText(arr.toString())'''
new_save = '''            // 原子写 + 备份：写一半被杀也不会把聊天记录截断，且保留上一版可回滚
            SafeStore.writeAtomicWithBackup(f, arr.toString())'''
if old_save in t:
    t = t.replace(old_save, new_save, 1)
    print("✓ ChatScreen.save 已改为原子写 + 备份")
else:
    print("⚠ ChatScreen.save 锚点未命中")
# import
if "import com.aipet.murasame.bot.chat.SafeStore" not in t:
    t = t.replace("import com.aipet.murasame.bot.chat.ChatStore", "import com.aipet.murasame.bot.chat.ChatStore\nimport com.aipet.murasame.bot.chat.SafeStore", 1)
    if "import com.aipet.murasame.bot.chat.SafeStore" not in t:
        t = t.replace("import androidx.compose", "import com.aipet.murasame.bot.chat.SafeStore\nimport androidx.compose", 1)
    print("✓ ChatScreen 补 import SafeStore")
io.open(CS, "w", encoding="utf-8", newline="\n").write(t)

# ③ MemoryStore：安全读 + 原子写
MS = os.path.join(SRC, "bot/chat/MemoryStore.kt")
t = io.open(MS, encoding="utf-8").read().replace("\r\n", "\n")
old_read = '''    private fun readHistory(file: File): MutableList<JSONObject> {
        val out = mutableListOf<JSONObject>()
        val raw = runCatching { file.readText() }.getOrNull() ?: return out
        runCatching {
            val obj = JSONObject(raw)
            val arr = obj.optJSONArray("history") ?: JSONArray()
            for (i in 0 until arr.length()) out.add(arr.getJSONObject(i))
        }
        return out
    }'''
new_read = '''    private fun readHistory(file: File): MutableList<JSONObject> {
        val out = mutableListOf<JSONObject>()
        // 损坏时隔离主文件并尝试 .bak，避免"读成空 → 下一次写入把整份记忆覆盖掉"（实测路径）
        val parsed = SafeStore.readWithRecovery(file) { raw ->
            runCatching {
                val obj = JSONObject(raw)
                val arr = obj.optJSONArray("history") ?: JSONArray()
                val list = mutableListOf<JSONObject>()
                for (i in 0 until arr.length()) list.add(arr.getJSONObject(i))
                list
            }.getOrNull()
        }
        if (parsed != null) out.addAll(parsed)
        return out
    }'''
if old_read in t:
    t = t.replace(old_read, new_read, 1)
    print("✓ MemoryStore.readHistory 已接 SafeStore")
else:
    print("⚠ MemoryStore.readHistory 锚点未命中")

old_write = '''        file.writeText(
            JSONObject()
                .put("history", JSONArray(history))
                .put("updated_at", now())
                .toString(2)
        )'''
new_write = '''        SafeStore.writeAtomicWithBackup(
            file,
            JSONObject()
                .put("history", JSONArray(history))
                .put("updated_at", now())
                .toString(2)
        )'''
if old_write in t:
    t = t.replace(old_write, new_write, 1)
    print("✓ MemoryStore.writeHistory 已改为原子写 + 备份")
else:
    print("⚠ MemoryStore.writeHistory 锚点未命中")
if "import com.aipet.murasame.bot.chat.SafeStore" not in t and "package com.aipet.murasame.bot.chat" in t:
    pass   # 同包，无需 import
io.open(MS, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 全量单测 + release ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "assembleRelease",
                    "--console=plain"], cwd=CHAT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: ") or "FAILED" in l:
        print("   " + l.strip()[:200])
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
tot = fail = 0
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if f.endswith(".xml"):
        x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        if m:
            tt = int(m.group(1)); fl = int(m.group(2)) + int(m.group(3))
            tot += tt; fail += fl
            print("   %-22s tests=%-3d 失败=%d" % (f.replace("TEST-com.aipet.murasame.", "").replace(".xml", ""), tt, fl))
print("   合计 %d 用例，失败 %d；退出码 %d" % (tot, fail, r.returncode))
if r.returncode != 0 or fail:
    for f in os.listdir(d) if os.path.isdir(d) else []:
        if f.endswith(".xml"):
            x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
            for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,220})', x):
                print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:200]))
    sys.exit(1)
