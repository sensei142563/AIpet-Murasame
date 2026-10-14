# -*- coding: utf-8 -*-
"""把本次被我改成 LF 的文件**改回 CRLF**（仓库是 core.autocrlf=true，其余文件都是 CRLF）。
   ⚠ 只处理文本文件；跳过二进制（png/pptx/pdf 等）。
   按技能 §14 的建议：读写都用二进制，避免 newline 再出岔子。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
TEXT_EXT = (".py", ".md", ".json", ".txt", ".toml", ".cfg", ".ini", ".yaml", ".yml",
            ".js", ".ts", ".html", ".css", ".bat", ".ps1", ".gitignore")

# 本次我动过的 + 我新建的
TARGETS = [
    "run.py",
    "pcl_launcher/silicon_window.py",
    "tool/chat.py",
    "tool/tts_console.py",
    "docs/本机环境约定-不用虚拟环境.md",
    "README.md",
]
for dp, dn, fn in os.walk(os.path.join(ROOT, "dev", "scripts")):
    for f in fn:
        if f.endswith(".py"):
            TARGETS.append(os.path.relpath(os.path.join(dp, f), ROOT))
for dp, dn, fn in os.walk(os.path.join(ROOT, "dev", "docs")):
    for f in fn:
        if f.endswith(".md"):
            TARGETS.append(os.path.relpath(os.path.join(dp, f), ROOT))
for dp, dn, fn in os.walk(os.path.join(ROOT, "dev", "merge-map")):
    for f in fn:
        if f.endswith(".txt"):
            TARGETS.append(os.path.relpath(os.path.join(dp, f), ROOT))

print("=== 逐个检查并修回 CRLF ===")
fixed, ok, skipped = [], 0, []
for rel in sorted(set(TARGETS)):
    fp = os.path.join(ROOT, rel)
    if not os.path.isfile(fp):
        continue
    if not rel.lower().endswith(TEXT_EXT):
        skipped.append(rel)
        continue
    d = open(fp, "rb").read()
    if b"\x00" in d[:4096]:
        skipped.append(rel + "（疑似二进制）")
        continue
    crlf = d.count(b"\r\n")
    lf = d.count(b"\n") - crlf
    if lf > 0:
        nd = d.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        with open(fp, "wb") as f:
            f.write(nd)
        fixed.append((rel, crlf, lf))
    else:
        ok += 1

for rel, crlf, lf in fixed:
    print("   ✓ 修回 CRLF：%-52s (原 CRLF=%d LF=%d)" % (rel[:52], crlf, lf))
print("   本来就没问题的：%d 个" % ok)
if skipped:
    print("   跳过 %d 个（非文本/二进制）" % len(skipped))

print()
print("=== 复查关键文件 ===")
for rel in ("run.py", "pcl_launcher/silicon_window.py", "docs/本机环境约定-不用虚拟环境.md"):
    fp = os.path.join(ROOT, rel)
    d = open(fp, "rb").read()
    crlf = d.count(b"\r\n")
    lf = d.count(b"\n") - crlf
    print("   %-44s CRLF=%-6d LF=%-5d %s" % (rel, crlf, lf,
                                            "✓" if crlf > 0 and lf == 0 else "⚠"))

print()
print("=== git 状态（行尾修回后应仍只有内容改动）===")
r = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
lines = [l for l in (r.stdout or "").split("\n") if l.strip()]
print("   %d 项改动" % len(lines))
for l in lines[:12]:
    print("   " + l[:110])
