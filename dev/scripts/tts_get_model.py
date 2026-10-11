# -*- coding: utf-8 -*-
"""下载并放置手机离线 TTS 模型（Kokoro int8 132MB）：
   ① 打印 OfflineTtsEngine.modelDir() 的候选根目录（决定放哪）② 下载 tar.bz2 ③ 解包 ④ 落到 assets/tts/ ⑤ 核对文件清单
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
ENG = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/OfflineTtsEngine.kt")
URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-int8-multi-lang-v1_0.tar.bz2"
CACHE = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\tts_model_cache"
UA = {"User-Agent": "Mozilla/5.0 (aipet-tts)"}

print("=== ① OfflineTtsEngine.modelDir() 的候选根 ===")
lines = io.open(ENG, encoding="utf-8", errors="replace").read().splitlines()
for i in range(34, 44):
    if i < len(lines):
        print("   %4d| %s" % (i + 1, lines[i].rstrip()[:130]))

print()
print("=== ② 下载（132 MB，走 github.com 直链）===")
os.makedirs(CACHE, exist_ok=True)
tar = os.path.join(CACHE, os.path.basename(URL))
if os.path.isfile(tar) and os.path.getsize(tar) > 100 * 1e6:
    print("   · 已存在 %.1f MB" % (os.path.getsize(tar) / 1e6))
else:
    t0, got = time.time(), 0
    with urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=600) as r, \
            open(tar + ".part", "wb") as out:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            out.write(b)
            got += len(b)
            if got % (20 << 20) < (1 << 20):
                print("      %.0f MB  (%.0fs)" % (got / 1e6, time.time() - t0), flush=True)
    os.replace(tar + ".part", tar)
    print("   ✓ 下载完成 %.1f MB  (%.0fs)" % (os.path.getsize(tar) / 1e6, time.time() - t0))

print()
print("=== ③ 解包 ===")
ex = os.path.join(CACHE, "extracted")
if not os.path.isdir(ex) or not os.listdir(ex):
    os.makedirs(ex, exist_ok=True)
    with tarfile.open(tar, "r:bz2") as t:
        t.extractall(ex)
    print("   ✓ 已解包")
else:
    print("   · 已解包过")
tops = os.listdir(ex)
print("   顶层:", tops)
root = os.path.join(ex, tops[0]) if len(tops) == 1 and os.path.isdir(os.path.join(ex, tops[0])) else ex
print("   模型根:", root)
print("   内容（前 20）:")
for n in sorted(os.listdir(root))[:20]:
    p = os.path.join(root, n)
    print("      %-24s %s" % (n, ("%.1f MB" % (os.path.getsize(p) / 1e6)) if os.path.isfile(p) else "(目录)"))

print()
print("=== ④ 落到 app/src/main/assets/tts/ ===")
dst = os.path.join(CHAT, "app/src/main/assets/tts")
if os.path.isdir(dst):
    shutil.rmtree(dst)
os.makedirs(dst, exist_ok=True)
for n in os.listdir(root):
    s = os.path.join(root, n)
    d = os.path.join(dst, n)
    if os.path.isdir(s):
        shutil.copytree(s, d)
    else:
        shutil.copy2(s, d)
print("   ✓ 已复制到", dst)
tot = sum(os.path.getsize(os.path.join(b, f)) for b, _, fs in os.walk(dst) for f in fs)
cnt = sum(len(fs) for _, _, fs in os.walk(dst))
print("   合计 %.1f MB / %d 个文件" % (tot / 1e6, cnt))

print()
print("=== ⑤ 关键文件核对（OfflineTtsEngine 要这四个）===")
for need in ("model.int8.onnx", "voices.bin", "tokens.txt"):
    f = os.path.join(dst, need)
    print("   %-20s %s" % (need, ("%.1f MB" % (os.path.getsize(f) / 1e6)) if os.path.isfile(f) else "✗ 缺失"))
es = os.path.join(dst, "espeak-ng-data")
print("   %-20s %s" % ("espeak-ng-data/", ("%d 个文件" % len(os.listdir(es))) if os.path.isdir(es) else "✗ 缺失（日语发音要用）"))
print()
print("   其它文件:", [n for n in sorted(os.listdir(dst)) if n not in
                     ("model.int8.onnx", "voices.bin", "tokens.txt", "espeak-ng-data")][:10])
