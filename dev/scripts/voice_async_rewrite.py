# -*- coding: utf-8 -*-
"""重写 VoiceClient 为真正异步（IO 协程合成 + 主线程播放）→ 编译装机核实 → 点测试行 → pull voice.log。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
VC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"
VL = "/sdcard/Android/data/%s/files/voice.log" % PKG
F5LOG = r"E:\university\order\python\pet\_audit_fish9269\_f5serve.log"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

SRC = '''package com.aipet.murasame.bot.chat

import android.content.Context
import android.media.MediaPlayer
import android.net.Uri
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * 语音合成客户端 —— 手机端不自己合成，把文本发给电脑端 F5-TTS（可复用角色范例音色）。
 *
 * 设计要点（每一条都是踩过坑之后定下来的）：
 *   1) **绝不在主线程联网**：建连与读响应体都必须在线程外，否则抛 NetworkOnMainThreadException
 *      （这正是此前"朗读一直是系统语音"的真因）。
 *   2) **不阻塞调用方**：命中缓存直接播；否则丢到 IO 协程合成，完成后回主线程播放。
 *   3) 日志写到 files/voice.log、外部目录（adb 可 pull）、logcat 与 App 的 LogBus。
 */
object VoiceClient {

    @Volatile var baseUrl: String = ""

    @Volatile var appCtx: Context? = null

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(2500, TimeUnit.MILLISECONDS)
        .readTimeout(60000, TimeUnit.MILLISECONDS)
        .writeTimeout(5000, TimeUnit.MILLISECONDS)
        .build()

    private val JSON = "application/json; charset=utf-8".toMediaType()

    private const val FILE = "voice_service.txt"

    private var player: MediaPlayer? = null

    /** 语音链路日志：外部可读文件 + logcat + App 的 LogBus。 */
    fun log(msg: String) {
        val line = java.text.SimpleDateFormat("MM-dd HH:mm:ss", java.util.Locale.US)
            .format(java.util.Date()) + "  [voice] " + msg
        runCatching { android.util.Log.i("VoiceClient", line) }
        runCatching { com.aipet.murasame.bot.LogBus.log(line) }
        val c = appCtx ?: return
        runCatching {
            File(c.filesDir, "voice.log").appendText(line + "\\n")
            val ext = File(c.getExternalFilesDir(null) ?: return@runCatching, "voice.log")
            ext.appendText(line + "\\n")
        }
    }

    /** 读地址并**写回** baseUrl（只返回不写回是此前的 bug：界面有值、运行期却是空串）。 */
    fun load(ctx: Context): String = runCatching {
        appCtx = ctx.applicationContext
        val f = File(ctx.filesDir, FILE)
        val v = if (f.isFile) f.readText().trim() else ""
        baseUrl = v
        v
    }.getOrDefault("")

    fun save(ctx: Context, value: String) {
        runCatching {
            File(ctx.filesDir, FILE).writeText((value ?: "").trim())
            baseUrl = (value ?: "").trim()
        }
    }

    private fun cacheFile(ctx: Context, text: String): File =
        File(ctx.cacheDir, "tts_" + Integer.toHexString(text.hashCode()) + ".wav")

    /** 阻塞式合成（只在 IO 线程调用）：请求电脑 F5 → 校验 WAV → 写缓存。 */
    private fun synth(ctx: Context, f: File, base: String, text: String,
                      petId: String?, refAudio: String?, refText: String?): Boolean {
        log("开始合成 base=" + base + " pet=" + petId + " 文本长=" + text.length)
        return runCatching {
            val body = JSONObject().apply {
                put("text", text)
                if (!petId.isNullOrBlank()) put("pet", petId)
                if (!refAudio.isNullOrBlank()) put("ref_audio", refAudio)
                if (!refText.isNullOrBlank()) put("ref_text", refText)
            }.toString().toRequestBody(JSON)
            val req = Request.Builder().url(base + "/infer").post(body).build()
            http.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) {
                    log("HTTP 失败 code=" + resp.code)
                    return@use false
                }
                val bytes = resp.body?.bytes()
                if (bytes == null || bytes.isEmpty()) {
                    log("响应体为空")
                    return@use false
                }
                if (bytes.size < 2000) {
                    log("响应太小 size=" + bytes.size + " 内容=" + String(bytes).take(120))
                    return@use false
                }
                val isRiff = bytes.size > 12 && bytes[0] == 'R'.code.toByte() &&
                    bytes[1] == 'I'.code.toByte() && bytes[2] == 'F'.code.toByte() &&
                    bytes[3] == 'F'.code.toByte()
                if (!isRiff) {
                    log("不是 RIFF size=" + bytes.size + " 头=" + String(bytes).take(16))
                    return@use false
                }
                f.writeBytes(bytes)
                true
            }
        }.getOrElse { e ->
            log("合成异常：" + e.javaClass.simpleName + " / " + e.message)
            false
        }
    }

    /** 播放（主线程调用）。 */
    private fun play(ctx: Context, f: File): Boolean = runCatching {
        runCatching { player?.stop() }
        runCatching { player?.release() }
        player = MediaPlayer().apply {
            setDataSource(ctx, Uri.fromFile(f))
            setOnCompletionListener { runCatching { it.release() } }
            prepare()
            start()
        }
        log("成功播放 " + f.length() + " 字节（电脑 F5-TTS）")
        true
    }.getOrElse { e ->
        log("播放异常：" + e.javaClass.simpleName + " / " + e.message)
        false
    }

    /**
     * 请求电脑 F5-TTS 合成并播放。**不阻塞调用线程**。
     * @return true 表示已接手（调用方不必再回退系统 TTS）；false 表示未配置或文本为空。
     */
    fun speak(ctx: Context, text: String, refAudio: String? = null, refText: String? = null,
              petId: String? = null): Boolean {
        appCtx = ctx.applicationContext
        val base = (baseUrl.ifEmpty { load(ctx) }).trim().trimEnd('/')
        if (base.isEmpty() || text.isBlank()) {
            log("未配置地址或文本为空，交回系统 TTS")
            return false
        }
        val f = cacheFile(ctx, text)
        if (f.isFile && f.length() >= 2000) {
            log("命中缓存 " + f.length() + " 字节")
            play(ctx, f)
            return true
        }
        scope.launch {
            val ok = synth(ctx, f, base, text, petId, refAudio, refText)
            if (ok) withContext(Dispatchers.Main) { play(ctx, f) }
            else log("合成失败：本次不出声（请确认电脑 F5 是否在跑）")
        }
        return true
    }
}
'''
io.open(VC, "w", encoding="utf-8", newline="\n").write(SRC)
print("✓ VoiceClient.kt 已重写为异步版（%d 行）" % SRC.count("\n"))

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:140])
if r.returncode != 0:
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt"], capture_output=True)
    print("   ✗ 回滚")
    sys.exit(1)


def itime():
    t = subprocess.run([ADB, "shell", "dumpsys", "package", PKG], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300).stdout
    m = re.search(r"lastUpdateTime=([^\n]+)", t)
    return m.group(1).strip() if m else "?"


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


def sh(*a, t=300):
    return subprocess.run([ADB, "shell", *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=t).stdout or ""


def dump(tag):
    sh("uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=60)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def box(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return None if not m else (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


subprocess.run([ADB, "reverse", "tcp:28565", "tcp:28565"], capture_output=True)
subprocess.run([ADB, "reverse", "tcp:9881", "tcp:9881"], capture_output=True)
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(box("聊天", dump("a0")))
time.sleep(5)
tap(box("☰", dump("a1")))
time.sleep(3)
z = dump("a2")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z))
time.sleep(3)
z = dump("a3")
row = box("测试电脑语音", z)
print("   行:", row)
sh("rm", "-f", VL)
f50 = os.path.getsize(F5LOG) if os.path.isfile(F5LOG) else 0
tap(row)
for k in range(7):
    time.sleep(8)
    if os.path.isfile(F5LOG) and os.path.getsize(F5LOG) > f50:
        if "/infer" in io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]:
            print("   ✓ F5 收到 /infer（%ds）" % ((k + 1) * 8))
            break
    print("   %ds …" % ((k + 1) * 8))
print()
print("=== ★ voice.log ===")
dst = os.path.join(TMP, "phone_voice12.log")
subprocess.run([ADB, "pull", VL, dst], capture_output=True, timeout=120)
content = io.open(dst, encoding="utf-8", errors="replace").read() if os.path.isfile(dst) else ""
print(content or "   （没有 ✗）")
print("=== 判定 ===")
print("   ✅✅✅✅✅ TTS 端到端成功！" if "成功播放" in content else
      ("   ⚠ 异常 → " + str([l for l in content.splitlines() if ("异常" in l or "失败" in l)][:2]) if content.strip() else "   ✗ 无日志"))

MSG = """refactor(voice): VoiceClient 重写为不阻塞的异步实现（真因修复）

真因（voice.log 实证）：speak() 在主线程建连/读响应体 → NetworkOnMainThreadException，
于是每次都静默失败并回退系统 TTS —— 这就是"朗读一直是系统语音"的根因。

本次整文件重写：
  - 拆出 synth()（阻塞式合成，只在 IO 线程调用）与 play()（主线程播放）；
  - speak() 不阻塞：命中缓存直接播；否则 scope.launch(Dispatchers.IO) 合成，
    成功后 withContext(Dispatchers.Main) 播放；
  - 全部日志（开始/HTTP 码/响应太小/非 RIFF/异常/成功播放字节数）写 files/voice.log、
    外部目录（adb pull）、logcat 与 LogBus；
  - 不再使用 runBlocking（那会把主线程一起堵住）。
注意：speak() 现在返回"是否接手"；合成失败时不发声（后续可再加系统 TTS 兜底）。
"""
msg = os.path.join(MAP, "_msg_voiceasync.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:100])
print("未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                capture_output=True, text=True).stdout.strip(), "条")
