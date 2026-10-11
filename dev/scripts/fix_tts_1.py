# -*- coding: utf-8 -*-
"""① 查设备 live2d.log 里的 [tts] 真实路径日志
   ② 从 ChatScreen 移除遗留诊断 diagEmptyConfigOnMain（它会卡死主线程）
   ③ ⑤b 检查改为走真实路径（设置页「点一下测试」）
   ④ 编译装机 + 真机触发一次并读日志"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
CS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt")
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
EXT = "/sdcard/Android/data/%s/files" % PKG
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")


def adb(*a, timeout=240):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


print("=== ① 设备 live2d.log 里的 [tts] 行（真实路径有没有成功过）===")
log = adb("shell", "cat", EXT + "/live2d.log")
tts = [l for l in (log or "").splitlines() if "[tts]" in l]
for l in tts[-18:]:
    print("   " + l.strip()[:170])
if not tts:
    print("   （没有 [tts] 行）")

print()
print("=== ② 移除 ChatScreen 里的遗留诊断 ===")
t = io.open(CS, encoding="utf-8").read().replace("\r\n", "\n")
m = re.search(r'\n[ \t]*//[^\n]*\n?[ \t]*OfflineTtsEngine\.diagEmptyConfigOnMain\(ctx\)\n', t)
if m:
    t = t[:m.start()] + "\n" + t[m.end():]
    io.open(CS, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已移除 diagEmptyConfigOnMain 调用（它用空配置在主线程构造 OfflineTts，卡死主线程）")
else:
    m2 = re.search(r'\n[ \t]*OfflineTtsEngine\.diagEmptyConfigOnMain\(ctx\)\n', t)
    if m2:
        t = t[:m2.start()] + "\n" + t[m2.end():]
        io.open(CS, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ 已移除（无注释版）")
    else:
        print("· 没找到该调用（可能已移除）")

print()
print("=== ③ ⑤b 检查改为走真实路径 ===")
a = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
i = a.find("⑤b 离线 TTS 合成")
print("   现状片段：")
print("\n".join("      " + l.rstrip()[:150] for l in a[max(0, i - 500):i + 400].split("\n")[-22:]))
