# -*- coding: utf-8 -*-
"""把离线 TTS 模型推到手机外部目录（Android/data/<pkg>/files/tts）。
   模型 190MB 不进 APK：OfflineTtsEngine.modelDir() 查的就是这个外部目录。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
SRC = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\tts_model_cache\extracted\kokoro-int8-multi-lang-v1_0"
DST = "/sdcard/Android/data/%s/files/tts" % PKG

print("可用设备:")
print(subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout)
if DEV not in subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout:
    print("✗ 手机不在线，先插线或开热点")
    sys.exit(1)
subprocess.run([ADB, "-s", DEV, "shell", "mkdir", "-p", DST], capture_output=True)
print("推送 %s → %s（约 190MB，慢的话等一会儿）" % (os.path.basename(SRC), DST))
r = subprocess.run([ADB, "-s", DEV, "push", SRC + "/.", DST], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=3600)
print((r.stdout or r.stderr or "").strip()[-300:])
print("校验:")
print(subprocess.run([ADB, "-s", DEV, "shell", "ls", "-l", DST + "/model.int8.onnx",
                      DST + "/voices.bin", DST + "/tokens.txt"], capture_output=True, text=True).stdout)
print(subprocess.run([ADB, "-s", DEV, "shell", "ls", DST + "/espeak-ng-data | wc -l"],
                     capture_output=True, text=True).stdout.strip(), "个 espeak 文件")
