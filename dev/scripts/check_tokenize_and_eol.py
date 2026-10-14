# -*- coding: utf-8 -*-
"""① 参考项目的 tokenize（中文怎么切，没分词器怎么办）
   ② 行尾自查：我改过的文件 CRLF 有没有被我换成 LF
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

print("=== ① 参考项目 jixia-kernel 的 tokenize ===")
p = r"E:\111\--main\jixia-kernel\crates\stdio\src\tools.rs"
if os.path.isfile(p):
    t = io.open(p, encoding="utf-8", errors="replace").read()
    m = re.search(r"fn tokenize[\s\S]{0,2500}?\n\}\n", t)
    if m:
        for l in m.group(0).split("\n"):
            print("   " + l.rstrip()[:118])
    else:
        print("   （没找到 fn tokenize，找找别的切词函数）")
        for i, l in enumerate(t.split("\n"), 1):
            if re.search(r"fn .*(token|split|segment|chunk|norm)", l, re.I):
                print("   %5d| %s" % (i, l.strip()[:112]))
else:
    print("   文件不存在")

print()
print("=== ② 行尾自查（本次我改过的文件）===")
for rel in ("run.py", "pcl_launcher/silicon_window.py", "docs/本机环境约定-不用虚拟环境.md"):
    fp = os.path.join(ROOT, rel)
    if not os.path.isfile(fp):
        print("   %-40s （不存在）" % rel)
        continue
    d = open(fp, "rb").read()
    crlf = d.count(b"\r\n")
    lf = d.count(b"\n") - crlf
    verdict = "✗ 行尾被换成 LF" if crlf == 0 and lf > 0 else "✓ 仍是 CRLF"
    print("   %-40s CRLF=%-6d LF=%-6d %s" % (rel, crlf, lf, verdict))

print()
print("=== ③ 仓库整体：有多少文件是纯 LF（对照）===")
r = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print("   工作区 %s" % ("干净 ✓" if not (r.stdout or "").strip() else "有改动"))
