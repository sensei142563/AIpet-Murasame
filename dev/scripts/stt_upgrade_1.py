# -*- coding: utf-8 -*-
"""STT 升级①：下载 sherpa-onnx streaming zipformer bilingual zh-en 2023-02-20（int8）进 assets，
   用已知台词的 F5 wav 重采样成 16k selftest.wav，OnlineAsr 换模型，并加「识别自检」按钮 → 编译装机。"""
import audioop
import io
import os
import re
import struct
import subprocess
import sys
import time
import urllib.request
import wave

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
API = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
NEWDIR = "asr-zh-bilingual"
ASSETS = os.path.join(CHAT, "app/src/main/assets")
ONLINE = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/OnlineAsr.kt")
SETTINGS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt")
REPO = "csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20"
FILES = ["encoder-epoch-99-avg-1.int8.onnx", "decoder-epoch-99-avg-1.int8.onnx",
         "joiner-epoch-99-avg-1.int8.onnx", "tokens.txt"]
UA = {"User-Agent": "Mozilla/5.0 (aipet-stt)"}
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① 下载模型 ----------
d = os.path.join(ASSETS, NEWDIR)
os.makedirs(d, exist_ok=True)
print("=== ① 下载模型（%s）===" % REPO.split("/")[-1])
for n in FILES:
    fp = os.path.join(d, n)
    if os.path.isfile(fp) and os.path.getsize(fp) > 10000:
        print("   · 已存在 %-42s %6.1f MB" % (n, os.path.getsize(fp) / 1e6))
        continue
    url = "https://hf-mirror.com/%s/resolve/main/%s" % (REPO, n)
    t0, got = time.time(), 0
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r, \
                open(fp + ".part", "wb") as out:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                out.write(b)
                got += len(b)
        os.replace(fp + ".part", fp)
        print("   ✓ %-42s %6.1f MB  (%.0fs)" % (n, got / 1e6, time.time() - t0))
    except Exception as e:
        print("   ✗ %s 失败: %s" % (n, e))
        sys.exit(1)

# ---------- ② 造 16k selftest.wav（用已知台词的 F5 输出）----------
print()
print("=== ② 造 16kHz 单声道 selftest.wav ===")
src = os.path.join(ASSETS, "voice", "murasame")
# 直接从索引里拿「本座等你好久了。」这条（识别过，相似度最高）
import json
idx = json.loads(io.open(os.path.join(ASSETS, "voice/index.json"), encoding="utf-8").read())
truth, name = None, None
for t, f in idx["index"]["murasame"].items():
    if "本座等你好久了" in t:
        truth, name = t, f
        break
if not name:
    print("   ✗ 找不到源音频")
    sys.exit(1)
srcp = os.path.join(src, name)
with wave.open(srcp, "rb") as w:
    ch, sw, fr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    pcm = w.readframes(n)
print("   源: %s  %d Hz  %d ch  %d bit  %.2fs" % (os.path.basename(srcp), fr, ch, sw * 8, n / fr))
if ch == 2:
    pcm = audioop.tomono(pcm, sw, 0.5, 0.5)
pcm16 = audioop.ratecv(pcm, sw, 1, fr, 16000, None)[0]
out = os.path.join(d, "selftest.wav")
with wave.open(out, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(16000)
    w.writeframes(pcm16)
print("   ✓ %s  %d B  %.2fs  台词=%s" % (out, os.path.getsize(out), len(pcm16) / 32000, truth))
io.open(os.path.join(API, "_stt_truth.txt"), "w", encoding="utf-8").write(truth)

# ---------- ③ OnlineAsr 换模型 ----------
print()
print("=== ③ OnlineAsr 换模型 ===")
s = io.open(ONLINE, encoding="utf-8").read().replace("\r\n", "\n")
if NEWDIR in s:
    print("   · 已切换")
else:
    s = s.replace('private const val DIR = "asr-zh-14M"', 'private const val DIR = "%s"' % NEWDIR, 1)
    s = s.replace("流式 zipformer（中文，14M 参数）",
                  "流式 zipformer（中英双语，int8 约 198MB；此前是 14M tiny，效果一般）", 1)
    for a, b in ((ENC_OLD := "encoder-epoch-99-avg-1.int8.onnx", "encoder-epoch-99-avg-1.int8.onnx"),
                 ("decoder-epoch-99-avg-1.int8.onnx", "decoder-epoch-99-avg-1.int8.onnx"),
                 ("joiner-epoch-99-avg-1.int8.onnx", "joiner-epoch-99-avg-1.int8.onnx")):
        pass
    io.open(ONLINE, "w", encoding="utf-8", newline="\n").write(s)
    print("   ✓ DIR → %s（文件名与旧模型相同，无需改其它常量）" % NEWDIR)

# ---------- ④ 加「识别自检」按钮 ----------
print()
print("=== ④ 设置页加识别自检按钮 ===")
t = io.open(SETTINGS, encoding="utf-8").read().replace("\r\n", "\n")
if "识别自检" in t:
    print("   · 已存在")
else:
    anchor = 'Row2("测试电脑语音"'
    ok = anchor in t
    print(("   ✓ " if ok else "   ✗ ") + "定位 测试电脑语音 行")
    if ok:
        block = '''Row2("识别自检", "离线识别内置样例，结果写入日志（验收用）",
Icons.Default.Mic, text, sub) {
runCatching { com.aipet.murasame.ui.OnlineAsr.selfTest(vctx) }
}
'''
        t = t.replace(anchor, block + anchor, 1)
        # 确保 Mic 图标可用
        if "Icons.Default.Mic" in t and "import androidx.compose.material.icons.filled.Mic" not in t:
            t = t.replace("import androidx.compose.material.icons.Icons",
                          "import androidx.compose.material.icons.Icons\nimport androidx.compose.material.icons.filled.Mic", 1)
        io.open(SETTINGS, "w", encoding="utf-8", newline="\n").write(t)
        print("   ✓ 已加（Icons.Default.Mic）")

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


b = itime()
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
print("   APK: %.1f MB" % (os.path.getsize(APK) / 1e6))
rr = subprocess.run([ADB, "-s", "4BD9K24C06021770", "install", "-r", "--no-streaming", APK],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
print("   装:", ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:60])
print("   已装:", itime())
