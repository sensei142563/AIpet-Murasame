# -*- coding: utf-8 -*-
"""给两个 bat 开头加 chcp 936（匹配 GBK 内容），然后重跑重连 bat 并用 GBK 解码验证中文。"""
import glob
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DEV = r"E:\university\order\python\pet\AIpet-Murasame-main\dev"

bats = []
for pat in ("*重连*.bat", "*连电脑*.bat", "*Jev*.bat", "*启动*.bat"):
    bats += [p for p in glob.glob(os.path.join(DEV, pat)) if p.lower().endswith(".bat")]
bats = sorted(set(bats))
print("=== 要处理的 bat ===")
for b in bats:
    print("   ", os.path.basename(b))

for b in bats:
    s = io.open(b, encoding="gbk").read()
    if "chcp 936" in s:
        print("   %-24s 已有 chcp 936，跳过" % os.path.basename(b))
        continue
    lines = s.replace("\r\n", "\n").split("\n")
    # 在 @echo off 之后插入 setlocal + chcp 936（保持顺序整洁）
    out = []
    for i, l in enumerate(lines):
        out.append(l)
        if l.strip().lower() == "@echo off":
            out.append("setlocal")
            out.append("chcp 936 >nul")
    # 若原本紧跟 setlocal，去掉重复
    cleaned = []
    seen_setlocal = 0
    for l in out:
        if l.strip().lower() == "setlocal":
            seen_setlocal += 1
            if seen_setlocal > 1:
                continue
        cleaned.append(l)
    io.open(b, "w", encoding="gbk", newline="").write(
        "\n".join(cleaned).replace("\r\n", "\n").replace("\n", "\r\n"))
    print("   %-24s ✓ 已加 chcp 936" % os.path.basename(b))

print()
print("=== 再跑一次重连 bat（用 GBK 解码，看中文是否正确）===")
rb = [p for p in bats if "重连" in p or "连电脑" in p]
if not rb:
    print("   ✗ 没找到重连 bat")
    sys.exit(1)
r = subprocess.run(["cmd", "/c", rb[0]], stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
out = (r.stdout or b"")
err = (r.stderr or b"")
for enc in ("gbk", "utf-8"):
    try:
        t = (out + err).decode(enc)
        print("   （下面按 %s 解码）" % enc)
        for l in t.splitlines():
            if l.strip():
                print("   | " + l[:150])
        break
    except Exception as e:
        print("   按 %s 解码失败：%s" % (enc, e))
print("   rc =", r.returncode)
print()
print("=== 两个 bat 的前 6 行 ===")
for b in bats:
    print("   " + os.path.basename(b) + ":")
    for l in io.open(b, "rb").read().decode("gbk", errors="replace").split("\r\n")[:6]:
        print("      " + l)
