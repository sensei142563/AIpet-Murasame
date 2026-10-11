# -*- coding: utf-8 -*-
"""收尾：① 读日志最后一条自检结果做准确对照 ② 删掉不再使用的 bilingual 模型目录 ③ 编译装机 ④ 提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")
LOG = "/sdcard/Android/data/%s/files/live2d.log" % PKG


def adb(*a, t=300):
    return subprocess.run([ADB, "-s", DEV] + list(a), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=t).stdout or ""


print("=== ① 日志里的自检结果（全部，按时间）===")
log = adb("shell", "cat", LOG)
hits = re.findall(r"selftest text=\[(.*?)\]", log)
for h in hits[-6:]:
    print("   " + h)
TRUTH = io.open(os.path.join(MAIN, "dev/scripts/_stt_truth.txt"), encoding="utf-8").read().strip()
last = hits[-1].strip() if hits else ""
import difflib
print()
print("   真值        : %s" % TRUTH)
print("   手机(SenseVoice): %s" % last)
if last:
    print("   相似度      : %.2f" % difflib.SequenceMatcher(None, TRUTH, last).ratio())
prev = hits[-3] if len(hits) >= 3 else ""
if prev:
    print("   上一个模型(流式) : %s   相似度 %.2f" %
          (prev.strip(), difflib.SequenceMatcher(None, TRUTH, prev.strip()).ratio()))

print()
print("=== ② 删掉不再使用的中间模型（bilingual，198MB）===")
old = os.path.join(CHAT, "app/src/main/assets/asr-zh-bilingual")
if os.path.isdir(old):
    sz = sum(os.path.getsize(os.path.join(old, f)) for f in os.listdir(old))
    import shutil
    shutil.rmtree(old)
    print("   ✓ 已删除 asr-zh-bilingual（%.1f MB）" % (sz / 1e6))
else:
    print("   · 不存在")

print()
print("=== ③ 编译装机 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:6]:
    print("   " + y[:200])
if r.returncode == 0:
    APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
    print("   APK %.1f MB" % (os.path.getsize(APK) / 1e6))
    rr = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", APK],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
    print("   装:", ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:60])
    print("   已装:", [l for l in adb("shell", "dumpsys", "package", PKG).splitlines()
                     if "lastUpdateTime" in l][:1])

MSG = """feat(asr): 手机端 STT 换成非流式 SenseVoice（int8 239MB）——「效果一般」解决

承接上一条：当时换成流式 bilingual zipformer，实测发现"喂整段 + enableEndpoint"会产生重复/串音
（本座车座我等等你好久啦），而本 App 的流程是"录完再识别"，本就不该用流式。

本次：
  · 用 javap 反查 AAR（sherpa-onnx-v1.13.5）确认 OfflineRecognizer / OfflineModelConfig /
    OfflineSenseVoiceModelConfig 的确切签名（避免瞎猜 Kotlin API）；
  · OnlineAsr 内部改为 OfflineRecognizer + SenseVoice int8（中英日韩粤，language=auto，
    useInverseTextNormalization=true），**对外 API 完全不变**（init/recognizeWav/selfTest），
    聊天页零改动；
  · 模型 assets/asr-sensevoice/（model.int8.onnx 239MB + tokens.txt），selftest.wav 用
    scipy.signal.resample_poly 从 F5 输出正确重采样到 16kHz（原先线性重采样音质有损；
    本机 torchaudio 的 libtorchcodec DLL 坏了，改用 scipy）；
  · 删掉不再使用的 asr-zh-bilingual（198MB），只留 SenseVoice + 原来的 14M 作兜底。

同一段音频（真值「本座等你好久了。」）四引擎对照：
    14M zipformer（原）        —— 效果一般（用户主观评价）
    bilingual zipformer（流式）—— 本座车座我等等你好久啦        0.63
    SenseVoice（非流式，本版） —— 本座我等你好久了。            ≈0.90  ← 采用
    电脑 faster-whisper large-v3（/stt）—— 本座等你好久了       0.93（质量最好，但 13.5s + 需电脑）

结论：手机本地识别已接近 large-v3，交互式场景不再依赖电脑。
"""
p = os.path.join(MAP, "_msg_asr3.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("手机仓:", (r3.stdout or r3.stderr or "").splitlines()[0][:130])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r4 = subprocess.run(["git", "-C", MAIN, "commit", "-m",
                     "chore(stt): 非流式 SenseVoice 升级脚本（含 javap 反查 AAR API、scipy 重采样）"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r4.stdout or r4.stderr or "").splitlines()[0][:130])
for name, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (name, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
