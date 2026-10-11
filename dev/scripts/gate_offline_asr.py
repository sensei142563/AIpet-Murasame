# -*- coding: utf-8 -*-
"""离线识别总开关（默认停用）+ 长按说话改用系统识别。编译（不装机，等用户确认安装）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SRC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")
OA = os.path.join(SRC, "ui/OnlineAsr.kt")
CS = os.path.join(SRC, "ui/ChatScreen.kt")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① OnlineAsr 总开关 ----------
oa = io.open(OA, encoding="utf-8").read().replace("\r\n", "\n")
if "offlineEnabled" in oa:
    print("· OnlineAsr 已有开关")
else:
    # 在 object OnlineAsr 的内部常量之后插入 helper
    m = re.search(r"(object OnlineAsr \{\n(?:.*\n)*?)(\n)", oa)
    helper = '''
    /**
     * 离线识别总开关：**默认停用**。
     *
     * 原因（真机实测，MIS-AL00 / Android 12）：这个 SenseVoice 原生库一旦初始化，
     * 进程就会被内核直接收走（appDiedLocked fromBinderDied=true，Java 异常处理器、
     * crash buffer、dropbox 里全都没有记录，onDestroy 也不执行）—— 表现就是"一进聊天页就闪退"。
     * 默认停用可以保证 App 可用；需要实验时在设备上创建
     *   files/asr_offline_enabled.txt  内容写 1
     * 重新进入聊天页即生效。
     */
    fun offlineEnabled(ctx: Context): Boolean = runCatching {
        val f = File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "asr_offline_enabled.txt")
        f.isFile && f.readText().trim() == "1"
    }.getOrDefault(false)
'''
    m2 = re.search(r"@Volatile private var failed = false\n", oa)
    if m2:
        oa = oa[:m2.end()] + helper + oa[m2.end():]
    else:
        oa = oa.replace("object OnlineAsr {", "object OnlineAsr {" + helper, 1)
    # init 开头加判断
    oa = oa.replace("""    fun init(ctx: Context): Boolean {
        recognizer?.let { return true }
        if (failed) return false""",
                    """    fun init(ctx: Context): Boolean {
        // 停用时**根本不加载原生库**（加载即崩，见 offlineEnabled 的说明）
        if (!offlineEnabled(ctx)) return false
        recognizer?.let { return true }
        if (failed) return false""", 1)
    # selfTest 开头加判断
    oa = oa.replace("""    fun selfTest(ctx: Context) {
        runCatching {""",
                    """    fun selfTest(ctx: Context) {
        if (!offlineEnabled(ctx)) {
            log(ctx, "自检跳过：离线识别已停用（要试请先创建 files/asr_offline_enabled.txt 写 1）")
            return
        }
        runCatching {""", 1)
    io.open(OA, "w", encoding="utf-8", newline="\n").write(oa)
    print("✓ OnlineAsr 已加 offlineEnabled + init/selfTest 守卫")

# ---------- ② 长按说话：停用时改用系统识别 ----------
cs = io.open(CS, encoding="utf-8").read().replace("\r\n", "\n")
old = '''                                if (AsrRecorder.isRecording()) {
                                    val f = AsrRecorder.stop(ctx)
                                    scope.launch {'''
new = '''                                if (AsrRecorder.isRecording()) {
                                    val f = AsrRecorder.stop(ctx)
                                    if (!com.aipet.murasame.ui.OnlineAsr.offlineEnabled(ctx)) {
                                        // 离线识别已停用（其原生库在该机型初始化即崩）→ 改用系统识别
                                        val i = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                                            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                                                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                                            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
                                        }
                                        val ok = runCatching { stt.launch(i) }.isSuccess
                                        notice = if (ok) "用系统识别（离线识别已停用）"
                                                 else "系统识别不可用；离线识别已停用，暂不能语音输入"
                                        return@detectTapGestures
                                    }
                                    scope.launch {'''
if old in cs:
    cs = cs.replace(old, new, 1)
    io.open(CS, "w", encoding="utf-8", newline="\n").write(cs)
    print("✓ ChatScreen 长按说话已加系统识别回退")
else:
    print("✗ ChatScreen 锚点未命中")

print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:190])
print("   退出码:", r.returncode)
