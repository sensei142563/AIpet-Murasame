# -*- coding: utf-8 -*-
"""只改 parseStickers 的那一行行为代码（锚点不再依赖整段），并简化测试里那行绕的写法。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
CC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/ChatCore.kt")
TE = os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/ChatSseTest.kt")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(CC, encoding="utf-8").read().replace("\r\n", "\n")
old = '''        val cleaned = if (found.isEmpty()) reply else regex.replace(reply, "").trim()'''
new = '''        // 修正：原来只在"至少命中一个候选"时才剥标记 ⇒ 模型编出来的名字会**原样显示在聊天里**
        //（用户看到 [表情:不存在]）。现在无论是否命中都剥掉，未命中的只记日志。
        if (found.isEmpty() && regex.containsMatchIn(reply)) {
            JevClient.log("表情标记未命中候选，已剥除：" + reply.take(60))
        }
        val cleaned = if (regex.containsMatchIn(reply)) regex.replace(reply, "").trim() else reply'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(CC, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ parseStickers 行为行已改（总是剥标记）")
else:
    print("⚠ 仍未命中那一行")
    for i, l in enumerate(t.split("\n"), 1):
        if "cleaned" in l:
            print("   %d| %s" % (i, l.strip()[:120]))

# 简化测试里那行绕的写法
te = io.open(TE, encoding="utf-8").read().replace("\r\n", "\n")
bad = [l for l in te.split("\n") if "replace(" in l and "data:" in l]
if bad:
    te = te.replace(bad[0], '        assertEquals("x", ChatSse.parseLine("data:   x"))')
    io.open(TE, "w", encoding="utf-8", newline="\n").write(te)
    print("✓ 已简化测试里那行绕的转义写法")

print()
print("=== 编译 + 跑 ChatSseTest ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.ChatSseTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
for l in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:185])
p2 = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.ChatSseTest.xml")
if os.path.isfile(p2):
    x = io.open(p2, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   ChatSseTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,260})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:240]))
