# -*- coding: utf-8 -*-
"""修 ilink：CredentialStore 原子写+损坏隔离+明确告警；PendingInbox 用 SafeStore 读。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
D = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/ilink")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- 先打印 SecureStore 的加解密是否有 runCatching 兜底（决定测试可行性）----------
SS = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame/SecureStore.kt")
if os.path.isfile(SS):
    body = io.open(SS, encoding="utf-8", errors="replace").read()
    print("=== SecureStore 关键行 ===")
    for i, l in enumerate(body.split("\n"), 1):
        if re.search(r"fun (encrypt|decrypt)|runCatching|getOrElse|return ", l):
            print("   %4d| %s" % (i, l.strip()[:125]))
print()

# ---------- ① CredentialStore ----------
CS = os.path.join(D, "CredentialStore.kt")
t = io.open(CS, encoding="utf-8").read().replace("\r\n", "\n")
print("=== CredentialStore 需要改的行（原文）===")
for i, l in enumerate(t.split("\n"), 1):
    if re.search(r"writeText|readJson|fun credentials", l):
        print("   %4d| %s" % (i, l.rstrip()[:130]))
print()

changed = []
# a) readJson：损坏时隔离 + 告警（而不是静默 null）
old_read = '''    private fun readJson(file: File): JSONObject? =
        runCatching { JSONObject(file.readText()) }.getOrNull()'''
new_read = '''    private fun readJson(file: File): JSONObject? {
        if (!file.isFile) return null
        // 损坏时**隔离**（改名保留）并明确告警：凭据读不出来会让整个微信桥"静默失效"，
        // 用户只会觉得"发了消息没反应"，所以必须留下可查的痕迹，而不是静默 null。
        return SafeStore.readWithRecovery(file) { raw -> runCatching { JSONObject(raw) }.getOrNull() }
            ?: run {
                android.util.Log.w("CredentialStore", "凭据文件不可用，已隔离并改名保留: " + file.name)
                null
            }
    }'''
if old_read in t:
    t = t.replace(old_read, new_read, 1)
    changed.append("readJson 用 SafeStore.readWithRecovery + 告警")
else:
    print("⚠ readJson 锚点未命中")

# b) 三处 writeText 改原子写
t, n1 = re.subn(r'(?P<i>[ \t]*)credFile\.writeText\(', r'\g<i>SafeStore.writeAtomic(credFile, ', t)
if n1:
    changed.append("credFile 原子写")
t, n2 = re.subn(r'(?P<i>[ \t]*)syncBufFile\.writeText\(buf\)',
                r'\g<i>SafeStore.writeAtomic(syncBufFile, buf)', t)
if n2:
    changed.append("syncBufFile 原子写")
t, n3 = re.subn(r'(?P<i>[ \t]*)ctxFile\.writeText\(JSONObject\(all\)\.toString\(2\)\)',
                r'\g<i>SafeStore.writeAtomic(ctxFile, JSONObject(all).toString(2))', t)
if n3:
    changed.append("ctxFile 原子写")

# 修 credFile 那处因为 writeText( 被替换后，末尾多出的 ")" 需要匹配：检查括号配对
# 形如 SafeStore.writeAtomic(credFile, JSONObject()...toString(2)\n            )  —— 原来是 writeText(...)，括号数一致
if "SafeStore.writeAtomic(credFile" in t:
    changed.append("credFile 调用已替换")
if "SafeStore.writeAtomic(syncBufFile, buf)" in t:
    changed.append("syncBufFile 调用已替换")
if "SafeStore.writeAtomic(ctxFile" in t:
    changed.append("ctxFile 调用已替换")
if "import com.aipet.murasame.bot.chat.SafeStore" not in t:
    t = t.replace("import java.io.File", "import com.aipet.murasame.bot.chat.SafeStore\nimport java.io.File", 1)
    changed.append("补 import SafeStore")
io.open(CS, "w", encoding="utf-8", newline="\n").write(t)
print("CredentialStore 改动：%s" % ("; ".join(changed) or "无"))

# ---------- ② PendingInbox ----------
PI = os.path.join(D, "PendingInbox.kt")
t = io.open(PI, encoding="utf-8").read().replace("\r\n", "\n")
print()
print("=== PendingInbox.load 原文 ===")
i = t.find("fun load(")
print("\n".join("   " + l for l in t[i:i + 520].split("\n")[:16]))

old_load = '''        val arr = JSONObject(f.readText()).optJSONArray("items") ?: JSONArray()'''
new_load = '''        // 损坏时隔离主文件并尝试从 .bak 恢复：否则读到空列表、下一次 save 会把原文件
        // （含尚未回复的消息）直接覆盖掉 —— 与聊天记录那条路径同类。
        val root = SafeStore.readWithRecovery(f) { raw ->
            runCatching { JSONObject(raw) }.getOrNull()
        } ?: return emptyList()
        val arr = root.optJSONArray("items") ?: JSONArray()'''
if old_load in t:
    t = t.replace(old_load, new_load, 1)
    changed.append("PendingInbox.load 用 SafeStore")
else:
    print("⚠ PendingInbox.load 锚点未命中")
if "import com.aipet.murasame.bot.chat.SafeStore" not in t:
    t = t.replace("import java.io.File", "import com.aipet.murasame.bot.chat.SafeStore\nimport java.io.File", 1)
    changed.append("PendingInbox 补 import")
# save 也统一走 SafeStore（原来已原子，统一实现便于维护）
old_save = '''        tmp.writeText(JSONObject().put("items", arr).toString(2))
        Files.move(tmp.toPath(), f.toPath(), StandardCopyOption.REPLACE_EXISTING)'''
new_save = '''        // 统一走 SafeStore（语义相同：临时文件 + move；顺带保留 .bak 便于恢复）
        SafeStore.writeAtomicWithBackup(f, JSONObject().put("items", arr).toString(2))'''
if old_save in t:
    t = t.replace(old_save, new_save, 1)
    changed.append("PendingInbox.save 统一走 SafeStore")
io.open(PI, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 改动汇总 ===")
for c in changed:
    print("   ✓ " + c)

print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:compileDebugKotlin", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.strip().startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ") or "error:" in x][:12]:
    print("   " + y[:230])
