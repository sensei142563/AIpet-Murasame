# -*- coding: utf-8 -*-
"""修「沫子的日常」：从 git 历史里把 senrenbanka_copy 的 theme.json 找回来，
   并把 name 设为「沫子的日常」（若本来就是这个名则原样保留）。
   同时查：代码怎么处理主题背景视频（bg_custom.mp4 是怎么被用上的）。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
THEME = os.path.join(ROOT, "pcl_launcher", "themes", "senrenbanka_copy")


def sh(args):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "") + (r.stderr or "")


print("=== ① 历史上 senrenbanka_copy 的 theme.json 出现在哪些提交 ===")
print(sh(["git", "log", "--all", "--oneline", "--", "pcl_launcher/themes/senrenbanka_copy/theme.json"])[:1200])

print("=== ② 用 git 全部历史找这份文件的内容 ===")
cand = None
r = subprocess.run(["git", "-C", ROOT, "log", "--all", "--format=%H", "--",
                    "pcl_launcher/themes/senrenbanka_copy/theme.json"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
hashes = [h for h in (r.stdout or "").split("\n") if h.strip()]
content = ""
for h in hashes[:6]:
    c = subprocess.run(["git", "-C", ROOT, "show", "%s:pcl_launcher/themes/senrenbanka_copy/theme.json" % h],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if c.returncode == 0 and (c.stdout or "").strip():
        content = c.stdout
        cand = h
        print("   ✓ 从 %s 取到内容（%d 字节）" % (h[:8], len(content)))
        break
if not content:
    print("   ✗ 历史里没有这份 theme.json")
    print("   → 改用 senrenbanka 的 theme.json 作为模板（同源主题，最接近）")

print()
print("=== ③ 参考：senrenbanka 的 theme.json（前 40 行）===")
ref = io.open(os.path.join(ROOT, "pcl_launcher", "themes", "senrenbanka", "theme.json"),
              encoding="utf-8", errors="replace").read()
for l in ref.split("\n")[:40]:
    print("   " + l.rstrip()[:112])

print()
print("=== ④ 代码里怎么用主题背景 / bg_custom ===")
for dp, dn, fn in os.walk(os.path.join(ROOT, "pcl_launcher")):
    if "__pycache__" in dp:
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().split("\n"), 1):
            if re.search(r"bg_custom|bg_video|\.mp4|QMediaPlayer|QVideoWidget|背景视频|video", l):
                print("   %-30s %5d| %s" % (os.path.basename(p), i, l.strip()[:100]))
