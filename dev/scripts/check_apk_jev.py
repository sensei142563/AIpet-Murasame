# -*- coding: utf-8 -*-
"""决定性核对：APK 的 dex 里到底有没有 JevClient / jev/choose / LogBus 这些字符串。"""
import io
import os
import re
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
print("APK:", APK, os.path.getsize(APK) if os.path.isfile(APK) else "不存在")

NEEDLES = [b"jev/choose", b"JevClient", b"VoiceClient", b"/infer", b"motionHintOf", b"App",
           b"Jev \xe9\x80\x89\xe4\xb8\xad".decode("utf-8").encode("utf-8")]

with zipfile.ZipFile(APK) as z:
    dexes = [n for n in z.namelist() if re.match(r"classes\d*\.dex", n)]
    print("dex 文件:", dexes)
    blob = b""
    for n in dexes:
        blob += z.read(n)
    print("dex 总字节:", len(blob))
    print()
    print("=== 关键字符串是否存在 ===")
    for s in [b"jev/choose", b"JevClient", b"/jev/choose", b"infer", b"motionHintOf",
              b"skip", b"StateTracker"]:
        print("   %-16s %s" % (s.decode("utf-8", "replace"), "✓ 有" if s in blob else "✗ 没有"))
    # 中文串（UTF-8 编码在 dex 里就是原样字节）
    for s in ["跳过：base=", "选中「", "这条回复最该配哪个表情包"]:
        b = s.encode("utf-8")
        print("   %-16s %s" % (s, "✓ 有" if b in blob else "✗ 没有"))
    print()
    print("=== 顺带确认别的功能在不在（对照）===")
    for s in ["VoiceClient", "Live2DView", "motionHint", "朗读", "拍摄"]:
        b = s.encode("utf-8")
        print("   %-16s %s" % (s, "✓ 有" if b in blob else "✗ 没有"))
    print()
    print("=== APK 时间戳 ===")
    st = os.path.getmtime(APK)
    import datetime
    print("   ", datetime.datetime.fromtimestamp(st).strftime("%Y-%m-%d %H:%M:%S"))

print()
print("=== 源码里确认这几处确实存在 ===")
CS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/ChatCore.kt")
s = io.open(CS, encoding="utf-8", errors="replace").read()
for k in ("JevClient.choose", "baseUrl = JevClient.baseUrl", "jevPick"):
    print("   ChatCore.kt 含 %-28s %s" % (k, "✓" if k in s else "✗"))
JC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/JevClient.kt")
sj = io.open(JC, encoding="utf-8", errors="replace").read()
for k in ("/jev/choose", "appCtx", "LogBus.log", "fun log("):
    print("   JevClient.kt 含 %-28s %s" % (k, "✓" if k in sj else "✗"))
AP = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/App.kt")
sa = io.open(AP, encoding="utf-8", errors="replace").read()
print("   App.kt 含 JevClient.load        %s" % ("✓" if "JevClient.load" in sa else "✗"))
print("   App.kt 含 VoiceClient.load      %s" % ("✓" if "VoiceClient.load" in sa else "✗"))
