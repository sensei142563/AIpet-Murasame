# -*- coding: utf-8 -*-
"""最后一道门：加 network_security_config 允许 127.0.0.1/localhost 明文 → 装机 → 发消息 → 拉日志。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
MAN = os.path.join(CHAT, "app/src/main/AndroidManifest.xml")
XMLDIR = os.path.join(CHAT, "app/src/main/res/xml")
NSC = os.path.join(XMLDIR, "network_security_config.xml")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

os.makedirs(XMLDIR, exist_ok=True)
io.open(NSC, "w", encoding="utf-8", newline="\n").write(
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<!-- 允许到电脑的明文 HTTP：手机经 USB 反向转发访问 127.0.0.1:28565(api.py) 与 9881(F5-TTS)。\n'
    '     只在 localhost/回环与常见本机别名上放开，不整体关闭明文限制。 -->\n'
    '<network-security-config>\n'
    '    <domain-config cleartextTrafficPermitted="true">\n'
    '        <domain includeSubdomains="false">127.0.0.1</domain>\n'
    '        <domain includeSubdomains="false">localhost</domain>\n'
    '        <domain includeSubdomains="false">10.0.2.2</domain>\n'
    '    </domain-config>\n'
    '</network-security-config>\n')
print("✓ 写入 res/xml/network_security_config.xml")

s = io.open(MAN, encoding="utf-8", newline="").read()
if "networkSecurityConfig" not in s:
    m = re.search(r"<application\b[^>]*>", s)
    assert m, "✗ 找不到 <application>"
    tag = m.group(0)
    if tag.rstrip().endswith("/>"):
        new = tag.rstrip()[:-2] + '\n        android:networkSecurityConfig="@xml/network_security_config" />'
    else:
        new = tag[:-1] + '\n        android:networkSecurityConfig="@xml/network_security_config">'
    s = s[:m.start()] + new + s[m.end():]
    io.open(MAN, "w", encoding="utf-8", newline="").write(s)
    print("✓ manifest 已加 android:networkSecurityConfig")
else:
    print("（manifest 已有 networkSecurityConfig）")

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:140])
if r.returncode != 0:
    subprocess.run(["git", "-C", CHAT, "checkout", "--", "app/src/main/AndroidManifest.xml"],
                   capture_output=True)
    if os.path.isfile(NSC):
        os.remove(NSC)
    print("   ✗ 回滚")
    sys.exit(1)
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
print("   安装（--no-streaming）:", end=" ")
rr = subprocess.run([ADB, "install", "-r", "--no-streaming", APK], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=3600)
print((rr.stdout or rr.stderr or "").strip().splitlines()[-1][:60])
subprocess.run([ADB, "shell", "rm", "-f", "/sdcard/Android/data/com.aipet.murasame/files/jev.log"],
               capture_output=True)

MSG = """fix(net): 允许到本机回环的明文 HTTP（Jet 一直发不出去的最后一道门）

手机端日志（外部可读副本，adb pull 取得）已经打到最里面一层：
    chatOnce 进入: useSticker=true 候选=20 baseUrl='http://127.0.0.1:28565'
    请求 http://127.0.0.1:28565/jev/choose 候选=20 问：…
    异常：UnknownServiceException CLEARTEXT communication to 127.0.0.1 not permitted by network security policy

即：地址加载已修好、请求已发出，但被 Android 的网络安全策略拦下（明文 HTTP）。
修复：
  app/src/main/res/xml/network_security_config.xml —— 仅对 127.0.0.1 / localhost / 10.0.2.2
  放开 cleartextTrafficPermitted（不整体打开明文），并在 manifest 的 <application> 上引用。

配合既有的 USB 反向转发（adb reverse tcp:28565 → 手机用 127.0.0.1 访问电脑 api.py）。

验证：编译安装后真机发消息，确认手机日志出现"选中「…」置信度=…"、电脑端 api 日志出现
POST /jev/choose、NanoJev 日志出现 POST /api/evaluate。
"""
msg = os.path.join(MAP, "_msg_cleartext.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交: " + (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送: " + subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                    capture_output=True, text=True).stdout.strip() + " 条")
