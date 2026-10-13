# -*- coding: utf-8 -*-
"""① 全仓找"文件名本身是乱码"的文件（UTF-8 被当 GBK/Latin1 解释的典型形态）
   ② 细看 themes/senrenbanka_copy（"沫子的日常"）里那 1 个 71MB 文件到底是什么
   ③ 看启动器怎么枚举主题、它需要哪些文件（判断主题为什么"看不见"）
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SKIP = ("\\.git", "\\runtime", "\\GPT-SoVITS", "\\_internal", "\\build", "\\.venv",
        "\\NapCat", "\\__pycache__", "\\F5-TTS_Models", "\\models")

print("=== ① 文件名像乱码的（UTF-8 被误解）===")
# 典型乱码字符：Ã Â Ä Å Æ Ç È É Ê Ë Ì Í Î Ï Ð Ñ Ò Ó Ô Õ Ö Ø Ù Ú Û Ü Ý Þ ß
# 以及中文 UTF-8 被 GBK 解释后出现的 锟斤拷 / 烫烫 / 屯屯 等
BAD = re.compile(r"[ÃÂÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞß]|锟斤拷|烫烫|屯屯|ï¿½|\ufffd")
CN_MOJI = re.compile(r"^(?:[\u00c0-\u00ff\u0100-\u017f]{2,}|[\u4e00-\u9fff]{0,2}"
                     r"[\u00c0-\u00ff]{2,})")
n = 0
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp for s in SKIP):
        continue
    for f in fn + dn:
        if BAD.search(f):
            print("   %s" % os.path.join(dp, f).replace(ROOT + os.sep, "")[:120])
            n += 1
            if n > 40:
                break
    if n > 40:
        break
print("   （命中 %d 个）" % n)

print()
print("=== ② themes/senrenbanka_copy 里到底是什么 ===")
d = os.path.join(ROOT, "pcl_launcher", "themes", "senrenbanka_copy")
if os.path.isdir(d):
    for dp, dn, fn in os.walk(d):
        for f in fn:
            p = os.path.join(dp, f)
            sz = os.path.getsize(p)
            with open(p, "rb") as fh:
                head = fh.read(16)
            kind = "?"
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                kind = "PNG"
            elif head[:3] == b"\xff\xd8\xff":
                kind = "JPEG"
            elif head[4:12] in (b"ftypisom", b"ftypmp42", b"ftypMSNV", b"ftypavc1"):
                kind = "MP4/视频"
            elif head[:4] == b"RIFF":
                kind = "RIFF(avi/wav)"
            elif head[:4] == b"\x1a\x45\xdf\xa3":
                kind = "MKV/WebM"
            print("   %-44s %10.1f MB  %s  头=%r" % (
                p.replace(d + os.sep, "")[:44], sz / 1048576, kind, head[:8]))
    t = os.path.join(d, "theme.json")
    if os.path.isfile(t):
        print("   theme.json 内容：")
        for l in io.open(t, encoding="utf-8", errors="replace").read().split("\n")[:40]:
            print("      " + l.rstrip()[:110])

print()
print("=== ③ 启动器怎么枚举主题（它需要哪些文件）===")
for rel in ("pcl_launcher/silicon_ui.py", "pcl_launcher/silicon_window.py",
            "pcl_launcher/themes/__init__.py"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().split("\n"), 1):
        if re.search(r"themes[/\\]|_THEMES|listdir.*theme|theme\.json|_ACTIVE_THEME|available_themes", l):
            print("   %-34s %5d| %s" % (rel[:34], i, l.strip()[:100]))

print()
print("=== ④ 四个主题各自的 theme.json（名字与文件数）===")
th = os.path.join(ROOT, "pcl_launcher", "themes")
for sub in sorted(os.listdir(th)):
    p = os.path.join(th, sub)
    if not os.path.isdir(p):
        continue
    tj = os.path.join(p, "theme.json")
    nm = ""
    if os.path.isfile(tj):
        txt = io.open(tj, encoding="utf-8", errors="replace").read()
        m = re.search(r'"name"\s*:\s*"([^"]*)"', txt)
        nm = m.group(1) if m else "?"
    files = [(os.path.join(dp, f), os.path.getsize(os.path.join(dp, f)))
             for dp, dn, fn in os.walk(p) for f in fn]
    big = sorted(files, key=lambda x: -x[1])[:3]
    print("   %-20s name=%-14s %2d 文件" % (sub, nm, len(files)))
    for fp, sz in big:
        print("        %-46s %8.1f MB" % (fp.replace(p + os.sep, "")[:46], sz / 1048576))
