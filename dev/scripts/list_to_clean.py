# -*- coding: utf-8 -*-
"""清理前的完整清单（只读，不动任何东西）：
  ① 所有已入库的大文件（>2MB，按体积排）
  ② 手机端相关的已入库路径（把"文档"与"非文档"分开列，因为文档可以推）
  ③ 录屏/素材类
  ④ 现有 .gitignore 状况
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(args, timeout=600):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


# 已跟踪文件 + 体积
files = [l.strip() for l in sh(["git", "ls-files"]).split("\n") if l.strip()]
sizes = []
for f in files:
    p = os.path.join(ROOT, f.replace("/", os.sep))
    try:
        sizes.append((os.path.getsize(p), f))
    except OSError:
        pass
sizes.sort(reverse=True)

print("=== ① 已入库大文件 >2MB（共 %d 个）===" % sum(1 for s, _ in sizes if s > 2 * 1048576))
tot = 0
for s, f in sizes:
    if s > 2 * 1048576:
        tot += s
        print("   %8.1f MB  %s" % (s / 1048576, f[:96]))
print("   （这些合计 %.1f MB）" % (tot / 1048576))

print()
print("=== ② 手机端相关：非文档（按你的要求：**不推**）===")
PHONE = re.compile(r"android|apk|gradle|kotlin|\.kt$|\.java$|chatter|hand|mediapipe|vrm|ar/|"
                   r"arcore|adb|termux|安卓|手机", re.I)
DOC = re.compile(r"\.md$|\.txt$|docs?/", re.I)
non_doc, doc = [], []
for s, f in sizes:
    if PHONE.search(f):
        (doc if DOC.search(f) else non_doc).append((s, f))
print("   ✗ 非文档（建议清掉）：%d 个" % len(non_doc))
for s, f in non_doc[:30]:
    print("      %8.2f MB  %s" % (s / 1048576, f[:92]))
print("   ✓ 文档（可保留）：%d 个" % len(doc))
for s, f in doc[:14]:
    print("      %8.2f MB  %s" % (s / 1048576, f[:92]))

print()
print("=== ③ 素材类（录屏/视频/图片/模型缓存）===")
MEDIA = re.compile(r"\.(mp4|mkv|webm|avi|mov|wav|mp3|flac|tar\.bz2|zip|7z|gguf|safetensors|"
                   r"onnx|bin|pth|ckpt|dll|so|exe|apk|aab)$", re.I)
media = [(s, f) for s, f in sizes if MEDIA.search(f) and s > 1048576]
print("   共 %d 个 >1MB：" % len(media))
for s, f in media[:30]:
    print("      %8.2f MB  %s" % (s / 1048576, f[:92]))

print()
print("=== ④ dev/ 下的可疑目录（体积）===")
for sub in ("dev/shots", "dev/three-demo", "dev/tmp", "dev/tts_model_cache", "dev/screenshots"):
    d = os.path.join(ROOT, sub.replace("/", os.sep))
    if not os.path.isdir(d):
        continue
    tot2, n2 = 0, 0
    for dp, dn, fn in os.walk(d):
        for f in fn:
            try:
                tot2 += os.path.getsize(os.path.join(dp, f))
                n2 += 1
            except OSError:
                pass
    tracked = [l for l in sh(["git", "ls-files", sub]).split("\n") if l.strip()]
    print("   %-26s 工作区 %7.1f MB / %4d 文件   已入库 %4d 个"
          % (sub, tot2 / 1048576, n2, len(tracked)))

print()
print("=== ⑤ .gitignore 现有内容 ===")
gi = os.path.join(ROOT, ".gitignore")
if os.path.isfile(gi):
    for i, l in enumerate(io.open(gi, encoding="utf-8", errors="replace").read().split("\n"), 1):
        print("   %3d| %s" % (i, l.rstrip()[:100]))
