# -*- coding: utf-8 -*-
"""把误放在 sys.exit(0) 之后的守卫挪到退出之前 —— 否则它们是**死代码**（本轮差点漏过去）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
TF = os.path.join(ROOT, "tests", "test_config_contracts.py")

t = io.open(TF, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
lines = t.split("\n")

# 找到那段守卫（从注释开头到文件末尾）
start = next((i for i, l in enumerate(lines) if l.startswith("# ── 语音服务记录")), None)
if start is None:
    print("· 没找到守卫段（可能已挪过）")
else:
    guard = "\n".join(lines[start:]).strip("\n")
    # 从原处删掉
    lines = lines[:start]
    while lines and lines[-1].strip() == "":
        lines.pop()
    # 插到 "print()\nif FAILS:" 之前
    anchor = next((i for i, l in enumerate(lines) if l.strip() == "print()"
                   and i + 1 < len(lines) and lines[i + 1].startswith("if FAILS")), None)
    if anchor is None:
        print("✗ 没找到插入锚点")
    else:
        lines = lines[:anchor] + guard.split("\n") + ["", ""] + lines[anchor:]
        io.open(TF, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
        print("✓ 已把守卫从第 %d 行之后挪到 sys.exit 之前" % (start + 1))

print()
print("=== 复核：exit 与守卫的相对位置 ===")
for i, l in enumerate(io.open(TF, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if "sys.exit" in l or "语音服务记录" in l or "_flag_arg(_extra" in l:
        print("   %5d| %s" % (i, l.strip()[:104]))

print()
print("=== 单跑该文件（看检查项数是否变化）===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    TF], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=900)
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n")[-8:]:
    print("   " + l.strip()[:130])
