# -*- coding: utf-8 -*-
"""提交 OneBot 解析层与单测；再出一次 release APK 确认整包仍能编。"""
import io
import os
import re
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

print("=== release APK ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:220])
if r.returncode != 0:
    print("✗ 失败，不提交")
    sys.exit(1)
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
print("   APK %.1f MB" % (os.path.getsize(APK) / 1e6))
with zipfile.ZipFile(APK) as z:
    names = z.namelist()
    for n in ("assets/vrm/index.html", "assets/vrm/vendor/three.js", "assets/voice/index.json"):
        print("   含 %-34s %s" % (n, "✓" if n in names else "✗"))
    print("   不含 .vrm 测试模型: %s" % ("✓" if not any(x.endswith(".vrm") for x in names) else "✗"))
    print("   不含 assets/tts（190MB 走外部目录）: %s"
          % ("✓" if not any(x.startswith("assets/tts/") for x in names) else "✗"))

MSG = """test(qq): 抽出 OneBot11 纯解析层并加 9 个 JVM 单测（真机联调前先离线验证）

方案 A（NapCat 跑在手机 Termux 里）里，App 侧最容易出错、又最适合离线验证的就是**协议解析**。
本次把它从 OneBotLocal 里抽成**无 Android 依赖的纯函数** OneBotParse，并让 OneBotLocal 调用它
（即"跑的代码 = 被测的代码"）。

新增 bot/chat/OneBotParse.kt：
  · extractText()：message 既可能是字符串也可能是 [{type,data}] 数组；文本拼接时把
    image/face/record/at 转成 [图片]/[表情]/[语音]/@qq 占位，reply 忽略；
  · parseMessage()：只认 post_type=message/message_sent，产出 key(private_<uid>/group_<gid>)、
    role(自己发的=assistant)、content、timestampMs、messageId；缺 id 返回 null；
  · parseLoginInfo()：解析 get_login_info 回包。
新增 app/src/test/.../OneBotParseTest.kt：9 个用例，全部用**真实形态的 payload**：
  私聊文本 / 群聊文本(键与角色) / message_sent→assistant / user_id==self_id→assistant /
  数组消息占位符拼接 / 非消息事件与坏 JSON 一律 null / 缺 id 拒绝 / login_info 回包 /
  无 time 字段时时间戳回落到当前时间。
结果：gradlew :app:testDebugUnitTest --tests …OneBotParseTest → **tests=9 failures=0 errors=0**；
      assembleRelease 通过，APK 316MB，仍含 assets/vrm 与 assets/voice、不含任何 .vrm、不含 assets/tts。
"""
p = os.path.join(MAP, "_msg_parse1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", CHAT, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
