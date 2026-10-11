# -*- coding: utf-8 -*-
"""只看两件事：① silero_vad.onnx 能否下载（并下载到 assets）② VadModelConfig 的构造签名。"""
import io
import os
import subprocess
import sys
import urllib.request
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
DEST = os.path.join(CHAT, "app/src/main/assets/vad")
UA = {"User-Agent": "Mozilla/5.0 (aipet-vad)"}

print("=== ① 下载 silero_vad.onnx ===")
urls = [
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx",
    "https://cdn.jsdelivr.net/gh/k2-fsa/sherpa-onnx@master/silero_vad.onnx",
]
os.makedirs(DEST, exist_ok=True)
got = None
for u in urls:
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=180) as r:
            b = r.read()
        if len(b) > 100000:
            p = os.path.join(DEST, "silero_vad.onnx")
            io.open(p, "wb").write(b)
            print("   OK  %s" % u.split("/releases")[0][:60])
            print("       下载 %.2f MB → %s" % (len(b) / 1e6, p))
            got = p
            break
        else:
            print("   --  太小(%d B)：%s" % (len(b), u[:80]))
    except Exception as e:
        print("   --  %s … %s" % (u.split("/")[-1], str(e)[:60]))
if got:
    import hashlib
    h = hashlib.sha256(io.open(got, "rb").read()).hexdigest()[:16]
    print("   sha256(前16) = %s" % h)
else:
    print("   ✗ 两个地址都没拿到")

print()
print("=== ② VadModelConfig 构造签名（javap）===")
aar = None
root = os.path.join(os.path.expanduser("~"), ".gradle", "caches")
for base, dirs, files in os.walk(root) if os.path.isdir(root) else []:
    for f in files:
        if f.startswith("sherpa-onnx") and f.endswith(".aar"):
            aar = os.path.join(base, f); break
    if aar:
        break
if aar:
    out = os.path.join(os.environ.get("TEMP", "."), "aipet_aar2")
    os.makedirs(out, exist_ok=True)
    with zipfile.ZipFile(aar) as z:
        cj_name = next(n for n in z.namelist() if n.endswith("classes.jar"))
        z.extract(cj_name, out)
    cj = os.path.join(out, cj_name)
    javap = r"E:\Android Studio\jbr\bin\javap.exe"
    r = subprocess.run([javap, "-classpath", cj, "com.k2fsa.sherpa.onnx.VadModelConfig"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    for l in (r.stdout or r.stderr or "").splitlines()[:16]:
        print("   " + l.strip()[:140])
    # SpeechSegment 也要看（front 返回它）
    r2 = subprocess.run([javap, "-classpath", cj, "com.k2fsa.sherpa.onnx.SpeechSegment"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("   --- SpeechSegment ---")
    for l in (r2.stdout or r2.stderr or "").splitlines()[:12]:
        print("   " + l.strip()[:140])
else:
    print("   ✗ 没找到 AAR")
