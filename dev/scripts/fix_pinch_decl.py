# -*- coding: utf-8 -*-
"""按真实缩进（8 空格）补上捏合去抖器的声明，然后编译 + 单测。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
AR = os.path.join(REPO, "app", "src", "main", "java", "com", "aipet", "murasame", "ui",
                  "VrmArScreen.kt")

t = io.open(AR, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = "        val latch = HandTouch.Latch(needFrames = 3, coolingFrames = 12)\n"
NEW = ("        val latch = HandTouch.Latch(needFrames = 3, coolingFrames = 12)\n"
       "        // 捏合（捏脸）独立一条判定线 + 独立去抖：不能和\"碰到她\"共用计数，\n"
       "        // 否则捏一下会被当成碰一次、两个动作互相顶掉。\n"
       "        val pinch = HandGesture.Latch(needFrames = 3, coolingFrames = 20)\n")

if "val pinch = HandGesture.Latch" in t:
    print("· 已声明")
elif OLD in t:
    t = t.replace(OLD, NEW, 1)
    io.open(AR, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已按 8 空格缩进补上 pinch 声明")
else:
    print("✗ 仍未命中")

print()
print("=== 相关行 ===")
for i, l in enumerate(io.open(AR, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if "val pinch" in l or "val latch" in l or "pinch.feed" in l or "hitPts" in l:
        print("   %4d| %s" % (i, l.strip()[:116]))

print()
print("=== 编译 + 单测 ===")
env = dict(os.environ, JAVA_HOME=r"E:\Android Studio\jbr")
for task in ("assembleDebug", "testDebugUnitTest"):
    r = subprocess.run([os.path.join(REPO, "gradlew.bat"), task, "--no-daemon", "--console=plain"],
                       cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=1800)
    out = (r.stdout or "") + (r.stderr or "")
    for l in out.split("\n"):
        s = l.strip()
        if s.startswith("e: ") or "BUILD" in s or "FAILED" in s:
            print("   [%s] %s" % (task, s[:150]))
