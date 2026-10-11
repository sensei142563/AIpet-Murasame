# -*- coding: utf-8 -*-
"""跑 NetDiagTest（纯 JVM 单测）—— 热点链接那条线的第一块逻辑。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.NetDiagTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:190])

p = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.NetDiagTest.xml")
if os.path.isfile(p):
    x = io.open(p, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   NetDiagTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,300})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:260]))
else:
    print("   （没有测试结果 XML —— 可能编译失败）")
    for l in o.splitlines():
        if l.startswith("e: "):
            print("   " + l[:200])
