# -*- coding: utf-8 -*-
"""去掉重复的 -u，并打印启动 bat 的三条完整命令行做最终确认。"""
import glob
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DEV = r"E:\university\order\python\pet\AIpet-Murasame-main\dev"
hits = [p for p in glob.glob(os.path.join(DEV, "*Jev*.bat")) if p.lower().endswith(".bat")]
if not hits:
    print("✗ 没找到启动 bat")
    sys.exit(1)
p = hits[0]
s = io.open(p, encoding="gbk").read()
n = s.count("%PY% -u -u ")
s = s.replace("%PY% -u -u ", "%PY% -u ")
io.open(p, "w", encoding="gbk", newline="").write(
    s.replace("\r\n", "\n").replace("\n", "\r\n"))
print("✓ 去掉重复 -u（%d 处）" % n)
print()
print("=== %s 的三条完整启动命令 ===" % os.path.basename(p))
raw = io.open(p, "rb").read()
for i, l in enumerate(raw.decode("gbk").split("\r\n"), 1):
    if l.strip().startswith("start "):
        print("  第 %d 行:" % i)
        print("     " + l.strip())
        print()
print("=== 其它关键行 ===")
for i, l in enumerate(raw.decode("gbk").split("\r\n"), 1):
    st = l.strip()
    if st.startswith(("chcp", "set REPO", "set NANOREPO", "set PY", "set ADB", "set LOGDIR", 'if not exist')):
        print("   %3d| %s" % (i, st[:150]))
print()
print("文件大小 %d B，双 CR = %s" % (len(raw), b"\r\r" in raw))
