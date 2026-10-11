# -*- coding: utf-8 -*-
"""装机窗口内做「拿走后做不了」的事：① 核实安装版本 ② 推 190MB 离线 TTS 模型到外部目录 ③ 校验。"""
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
SRC = os.path.join(MAIN, "dev", "tts_model_cache", "extracted", "kokoro-int8-multi-lang-v1_0")
DST = "/sdcard/Android/data/%s/files/tts" % PKG


def adb(*a, t=3600):
    return subprocess.run([ADB, "-s", DEV] + list(a), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=t).stdout or ""


devs = subprocess.run([ADB, "devices"], capture_output=True, text=True, timeout=60).stdout
if DEV not in devs:
    print("手机已不在线 ✗")
    sys.exit(0)

print("=== ① 核实安装 ===")
t = adb("shell", "dumpsys", "package", PKG, t=600)
m = re.search(r"lastUpdateTime=([^\n]+)", t)
print("   lastUpdateTime:", (m.group(1).strip() if m else "?"))
print("   versionName:", (re.search(r"versionName=([^\n]+)", t).group(1).strip()
                        if re.search(r"versionName=([^\n]+)", t) else "?"))
print("   现在时间:", time.strftime("%Y-%m-%d %H:%M:%S"))

print()
print("=== ② 推离线 TTS 模型（190MB / 377 文件）===")
print("   源:", SRC)
print("   目标:", DST)
if not os.path.isdir(SRC):
    print("   ✗ 源目录不存在")
    sys.exit(1)
adb("shell", "mkdir", "-p", DST, t=300)
t0 = time.time()
r = subprocess.run([ADB, "-s", DEV, "push", SRC + "/.", DST],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
out = (r.stdout or "") + (r.stderr or "")
print("   推送输出末尾: " + out.strip().splitlines()[-1][:120] if out.strip() else "   (无输出)")
print("   耗时 %.0f 秒" % (time.time() - t0))

print()
print("=== ③ 校验（OfflineTtsEngine 要的四个）===")
print(adb("shell", "ls", "-l", "%s/model.int8.onnx" % DST).strip()[:130])
print(adb("shell", "ls", "-l", "%s/voices.bin" % DST).strip()[:130])
print(adb("shell", "ls", "-l", "%s/tokens.txt" % DST).strip()[:130])
n = adb("shell", "ls", "%s/espeak-ng-data | wc -l" % DST).strip()
print("   espeak-ng-data 文件数:", n)
tot = adb("shell", "du", "-sm", DST).strip()
print("   目录合计:", tot)
print()
print("   判定:", "✓ 模型就位，手机的离线 TTS 具备运行条件（下次开机/重进页面即可用）"
      if "model.int8.onnx" in adb("shell", "ls", DST) else "✗ 似乎没推全")
