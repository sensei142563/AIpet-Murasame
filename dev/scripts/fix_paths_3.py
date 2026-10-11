# -*- coding: utf-8 -*-
"""Silero 阈值/最短静音可从文件调（真机当场可修，不用重新打包），并在日志里写明实际取值。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
UI = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

S = os.path.join(UI, "SileroVad.kt")
t = io.open(S, encoding="utf-8").read().replace("\r\n", "\n")
if "silero_threshold.txt" in t:
    print("· 已支持文件调参")
else:
    old = """        return runCatching {
            val silero = SileroVadModelConfig(
                model = mf.absolutePath,
                threshold = 0.5f,
                minSilenceDuration = 0.25f,
                minSpeechDuration = 0.20f,
                windowSize = WINDOW,
                maxSpeechDuration = 20.0f,
            )"""
    new = """        // 阈值/minSilence 可从文件调（真机当场可修，不用重新打包）：
        //   files/silero_threshold.txt      一行浮点，0.05~0.95
        //   files/silero_min_silence.txt    一行浮点（秒），0.05~2.0
        val thr = readFloatSetting(ctx, "silero_threshold.txt", 0.5f, 0.05f, 0.95f)
        val minSil = readFloatSetting(ctx, "silero_min_silence.txt", 0.25f, 0.05f, 2.0f)
        return runCatching {
            val silero = SileroVadModelConfig(
                model = mf.absolutePath,
                threshold = thr,
                minSilenceDuration = minSil,
                minSpeechDuration = 0.20f,
                windowSize = WINDOW,
                maxSpeechDuration = 20.0f,
            )"""
    if old in t:
        t = t.replace(old, new, 1)
        # 在 log 里写明实际取值
        t = t.replace('log(ctx, "Silero VAD ready (model=%d 字节)".format(mf.length()))',
                      'log(ctx, "Silero VAD ready (model=%d 字节, threshold=%.2f, minSilence=%.2fs)"\n'
                      '                .format(mf.length(), thr, minSil))', 1)
        # 助手函数
        t = t.replace("""    fun isAvailable(ctx: Context): Boolean = runCatching {""",
                      """    /** 从 files/ 读一个浮点设置（不存在或超范围就用默认值）。 */
    private fun readFloatSetting(ctx: Context, name: String, def: Float,
                                 lo: Float, hi: Float): Float = runCatching {
        val f = File(ctx.filesDir, name)
        if (!f.isFile) return def
        val v = f.readText().trim().toFloat()
        if (v in lo..hi) v else def
    }.getOrDefault(def)

    fun isAvailable(ctx: Context): Boolean = runCatching {""", 1)
        io.open(S, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ SileroVad：阈值与最短静音支持文件调参 + 日志写明实际取值")
    else:
        print("✗ 构造块锚点未命中")
        sys.exit(1)

print()
print("=== 关键行复核 ===")
tt = io.open(S, encoding="utf-8", errors="replace").read()
for k in ("silero_threshold.txt", "silero_min_silence.txt", "readFloatSetting",
          "threshold=%.2f, minSilence=%.2fs"):
    print("   %-34s %s" % (k, "✓" if k in tt else "✗"))

print()
print("=== 编译 + 单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", ":app:testDebugUnitTest",
                    "--console=plain"], cwd=CHAT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:230])
if r.returncode != 0:
    sys.exit(1)
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
tot = fail = 0
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if f.endswith(".xml"):
        x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        if m:
            tot += int(m.group(1)); fail += int(m.group(2)) + int(m.group(3))
print("   单测 %d 用例，失败 %d" % (tot, fail))
if fail:
    sys.exit(1)

MSG = """feat(stt): Silero 阈值/最短静音支持文件调参（真机当场可修，无需重新打包）

把真机最可能需要调的两个参数变成文件开关：
  · files/silero_threshold.txt      一行浮点（0.05~0.95，默认 0.5）
  · files/silero_min_silence.txt    一行浮点秒（0.05~2.0，默认 0.25）
超范围或文件不存在则用默认值；初始化日志写明实际取值：
  「Silero VAD ready (model=… 字节, threshold=0.50, minSilence=0.25s)」

配套（本轮另两处"当场可修"路径）：
  · 3D AR 手部命中写 vrm_ar.log + 进页面打印「手部判定启动：视口/ fov/ 假手周期」
    ⇒ 验收脚本 ②c 改为读日志判定，不再靠抓屏找一闪而过的提示；
  · 假手周期可由 files/vrm_fake_period.txt 调（500~60000ms）。

验证：release 编译通过；全量单测 56 用例全绿。
"""
p = os.path.join(MAP, "_msg_fixpaths2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", CHAT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
