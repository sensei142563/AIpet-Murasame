# -*- coding: utf-8 -*-
"""① 验诺瓦头像文件的真实格式（扩展名 vs magic，很可能是 .jpg 改名的 .png ⇒ Qt 解不出 = "乱码/没了"）
   ② 读代码里"沫子"的上下文，弄清"沫子的日常"到底是什么（主题？视频？）
   ③ 列 pcl_launcher/themes/ 现状 + git 历史里的主题目录
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def magic(p):
    try:
        with open(p, "rb") as f:
            b = f.read(16)
    except Exception as e:
        return "读不到: %s" % e
    sig = b[:8]
    kind = "?"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        kind = "PNG ✓"
    elif b[:3] == b"\xff\xd8\xff":
        kind = "JPEG"
    elif b[:6] in (b"GIF87a", b"GIF89a"):
        kind = "GIF"
    elif b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        kind = "WEBP"
    elif b[:2] == b"BM":
        kind = "BMP"
    return "%s   头字节=%r" % (kind, sig)


print("=== ① 诺瓦相关图片文件的真实格式（扩展名 vs 内容）===")
for rel in ("pets/noir/avatar.png", "pets/noir/avatar.jpg", "pets/noir/诺瓦.jpg",
            "pets/murasame/avatar.png", "pets/murasame/avatar.jpg"):
    p = os.path.join(ROOT, rel)
    if os.path.isfile(p):
        print("   %-30s %8d B   %s" % (rel, os.path.getsize(p), magic(p)))
    else:
        print("   %-30s （不存在）" % rel)
# 别的角色的头像作对照
print()
print("   其他角色头像作对照：")
pets = os.path.join(ROOT, "pets")
for d in sorted(os.listdir(pets)):
    pj = os.path.join(pets, d, "pet.json")
    if not os.path.isfile(pj):
        continue
    t = io.open(pj, encoding="utf-8", errors="replace").read()
    import re
    m = re.search(r'"avatar"\s*:\s*"([^"]+)"', t)
    av = m.group(1) if m else "(未指定)"
    fp = os.path.join(pets, d, av)
    print("      %-10s avatar=%-14s %s" % (d, av, magic(fp) if os.path.isfile(fp) else "（文件不存在 ✗）"))

print()
print("=== ② 代码里'沫子'的上下文 ===")
for rel in ("pcl_launcher/silicon_ui.py", "tests/test_bugfix_0930.py",
            "docs/handover/2026-09-24.md"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls, 1):
        if "沫子" in l:
            a = max(0, i - 4)
            b = min(len(ls), i + 3)
            print("   --- %s:%d ---" % (rel, i))
            for j in range(a, b):
                mark = ">>" if j == i - 1 else "  "
                print("   %s %5d| %s" % (mark, j + 1, ls[j].rstrip()[:108]))
            print()

print("=== ③ pcl_launcher/themes/ 现状 ===")
th = os.path.join(ROOT, "pcl_launcher", "themes")
if os.path.isdir(th):
    for d in sorted(os.listdir(th)):
        p = os.path.join(th, d)
        if os.path.isdir(p):
            n = sum(len(f) for _, _, f in os.walk(p))
            sz = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fn in os.walk(p)
                     for f in fn)
            print("   [dir] %-34s %3d 个文件  %6.1f MB" % (d[:34], n, sz / 1048576))
        else:
            print("   %-40s %6d B" % (d[:40], os.path.getsize(p)))
else:
    print("   ✗ 没有 themes 目录")

print()
print("=== ④ git 历史里出现过的主题目录名（含已删除）===")
r = subprocess.run(["git", "-C", ROOT, "log", "--all", "--diff-filter=A", "--name-only",
                    "--pretty=format:"], capture_output=True, text=True, encoding="utf-8",
                   errors="replace")
seen = set()
for l in (r.stdout or "").split("\n"):
    l = l.strip()
    if "themes/" in l:
        top = l.split("themes/", 1)[1].split("/")[0]
        if top and top not in seen:
            seen.add(top)
            print("   themes/%s" % top)
print("   （历史里共 %d 个主题目录）" % len(seen))

print()
print("=== ⑤ .gitignore 里与主题/副本相关的规则 ===")
g = os.path.join(ROOT, ".gitignore")
if os.path.isfile(g):
    for i, l in enumerate(io.open(g, encoding="utf-8", errors="replace").read().split("\n"), 1):
        if "theme" in l.lower() or "copy" in l.lower() or "视频" in l or "video" in l.lower():
            print("   %5d| %s" % (i, l.strip()[:100]))
