# -*- coding: utf-8 -*-
"""定位 TTS 五层链路的实现：文件、函数签名、层序。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")

print("=== 与 TTS/朗读 相关的文件 ===")
cands = []
for base, dirs, files in os.walk(SRC):
    for f in files:
        if not f.endswith(".kt"):
            continue
        fp = os.path.join(base, f)
        body = io.open(fp, encoding="utf-8", errors="replace").read()
        if re.search(r"Tts|TTS|speak|朗读|合成|voice", body):
            cands.append((os.path.relpath(fp, SRC), len(body), body.count("fun ")))
for c, n, nf in sorted(cands, key=lambda x: -x[1])[:12]:
    print("   %-52s %6d B  %d 个 fun" % (c, n, nf))

print()
print("=== OfflineTtsEngine：对外函数与层序线索 ===")
p = os.path.join(SRC, "ui/OfflineTtsEngine.kt")
if os.path.isfile(p):
    for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().split("\n"), 1):
        if re.search(r"fun |object |//|层|fallback|回退|ready|log\(", l):
            s = l.strip()
            if s and not s.startswith("import"):
                print("   %4d| %s" % (i, s[:135]))
else:
    print("   ✗ 不存在")

print()
print("=== 朗读入口（谁在调用 TTS）===")
for base, dirs, files in os.walk(SRC):
    for f in files:
        if not f.endswith(".kt"):
            continue
        fp = os.path.join(base, f)
        body = io.open(fp, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"^\s*(?:suspend )?fun (\w*[Ss]peak\w*|\w*[Tt]ts\w*)\(([^)]*)\)", body, re.M):
            print("   %-42s fun %s(%s)" % (os.path.relpath(fp, SRC), m.group(1), m.group(2)[:60]))
