# -*- coding: utf-8 -*-
"""TTS 落地①：台词包优先。
   1) 把 App 固定会说的那句「你好，我是丛雨。」补进台词包；
   2) VoiceClient.speak 改为 台词包 → 缓存 → 电脑 F5 → 交回系统 TTS；
   3) 编译装机，点设置页「测试电脑语音」验证：日志命中预生成 + f5tts.log 不增长（= 没联网）。
"""
import io
import json
import os
import re
import struct
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
VC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt")
ASSETS = os.path.join(CHAT, "app/src/main/assets/voice")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = os.path.join(MAIN, "dev/shots")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


# ---------- ① 补台词：App 固定会说的那些 ----------
EXTRA = {"murasame": ["你好，我是丛雨。"]}
ip = os.path.join(ASSETS, "index.json")
idx = json.loads(io.open(ip, encoding="utf-8").read())
import hashlib


def synth(text, pet):
    body = json.dumps({"text": text, "pet": pet}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:9881/infer", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


for pet, lines in EXTRA.items():
    d = os.path.join(ASSETS, pet)
    os.makedirs(d, exist_ok=True)
    idx["index"].setdefault(pet, {})
    for text in lines:
        if idx["index"][pet].get(text):
            print("· 台词已存在:", text)
            continue
        name = hashlib.sha1((pet + "|" + text).encode("utf-8")).hexdigest()[:16] + ".wav"
        try:
            b = synth(text, pet)
            if b[:4] != b"RIFF":
                print("✗ 合成非 WAV:", text)
                continue
            io.open(os.path.join(d, name), "wb").write(b)
            idx["index"][pet][text] = name
            print("✓ 补台词: %s → %s (%.0f KB)" % (text, name, len(b) / 1024))
        except Exception as e:
            print("✗ 补台词失败:", text, e)
idx["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
io.open(ip, "w", encoding="utf-8", newline="\n").write(json.dumps(idx, ensure_ascii=False, indent=2))
note("索引已更新（含固定台词）", "你好，我是丛雨。" in io.open(ip, encoding="utf-8").read())

# ---------- ② VoiceClient：台词包优先 ----------
s = io.open(VC, encoding="utf-8").read().replace("\r\n", "\n")
if "playPacked" in s:
    note("VoiceClient 已接台词包", True)
else:
    add = '''
    // ===== 预生成台词包（assets/voice）：命中则直接播，不联网、不依赖电脑 =====
    @Volatile private var packedIndex: JSONObject? = null
    @Volatile private var packedTried = false

    private fun packed(ctx: Context, text: String, petId: String?): Boolean = runCatching {
        if (!packedTried) {
            packedTried = true
            packedIndex = runCatching {
                JSONObject(ctx.assets.open("voice/index.json").use { it.readBytes().toString(Charsets.UTF_8)) }
            }.getOrNull()
        }
        val root = packedIndex?.optJSONObject("index") ?: return false
        val pet = (petId ?: "").ifBlank { "murasame" }
        val name = root.optJSONObject(pet)?.optString(text)?.takeIf { it.isNotBlank() } ?: return false
        val f = File(ctx.cacheDir, "packed_" + name)
        if (!f.isFile || f.length() < 20000) {
            ctx.assets.open("voice/" + pet + "/" + name).use { ins ->
                f.outputStream().use { ins.copyTo(it) }
            }
        }
        if (f.length() < 20000) return false
        log("命中预生成台词 " + f.length() + " 字节（不联网）")
        play(ctx, f)
        true
    }.getOrElse { e ->
        log("台词包异常：" + e.javaClass.simpleName + " / " + e.message)
        false
    }

'''
    anchor = "    /** 播放（主线程调用）。 */"
    note("定位 play() 前锚点", anchor in s)
    s = s.replace(anchor, add + anchor, 1)
    old = """        val f = cacheFile(ctx, text)
        if (f.isFile && f.length() >= 2000) {"""
    new = """        // ① 预生成台词包（离线、秒出）
        if (packed(ctx, text, petId)) return true
        // ② 联网缓存
        val f = cacheFile(ctx, text)
        if (f.isFile && f.length() >= 2000) {"""
    note("定位 speak() 里的缓存分支", old in s)
    s = s.replace(old, new, 1)
    if "import java.io.File" not in s:
        s = s.replace("import org.json.JSONObject", "import org.json.JSONObject\nimport java.io.File", 1)
    io.open(VC, "w", encoding="utf-8", newline="\n").write(s)
    note("VoiceClient 已接台词包优先", "playPacked" not in s and "packed(ctx, text, petId)" in s)

print()
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
    t = subprocess.run([ADB, "shell", "dumpsys", "package", PKG], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300).stdout
    mm = re.search(r"lastUpdateTime=([^\n]+)", t)
    return mm.group(1).strip() if mm else "?"


before_t = itime()
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
for att in range(1, 4):
    rr = subprocess.run([ADB, "install", "-r", "--no-streaming", APK], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=3600)
    print("   装 %d:" % att, ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:44])
    time.sleep(3)
    now = itime()
    if now != before_t and now != "?":
        print("   ✓ 已装上:", now)
        break
