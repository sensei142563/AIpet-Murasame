# -*- coding: utf-8 -*-
"""按实测结果统一到 UTF-8：
   ① 看日志 bat：-Encoding Default → -Encoding UTF8（并给窗口 chcp 65001）
   ② 启动 bat：子窗口补回 chcp 65001 + PYTHONIOENCODING=utf-8（与 UTF-8 日志一致）
   ③ 实测：用同样的 powershell 读法验证中文正常。"""
import glob
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DEV = r"E:\university\order\python\pet\AIpet-Murasame-main\dev"
LOGDIR = os.path.join(DEV, "logs")


def find(*pats):
    for pat in pats:
        hits = [p for p in glob.glob(os.path.join(DEV, pat)) if p.lower().endswith(".bat")]
        if hits:
            return hits[0]
    return None


bat_logs = find("*看日志*.bat", "*日志*.bat")
bat_start = find("*Jev*.bat", "*启动*.bat")
print("=== 看日志 bat:", os.path.basename(bat_logs) if bat_logs else "✗")
if bat_logs:
    s = io.open(bat_logs, encoding="gbk").read()
    n = s.count("-Encoding Default")
    s = s.replace("-Encoding Default", "-Encoding UTF8")
    if "chcp 65001" not in s:
        s = s.replace("@echo off\r\nsetlocal", "@echo off\r\nsetlocal\r\nchcp 65001 >nul")
        s = s.replace("@echo off\nsetlocal", "@echo off\nsetlocal\nchcp 65001 >nul")
    io.open(bat_logs, "w", encoding="gbk", newline="").write(
        s.replace("\r\n", "\n").replace("\n", "\r\n"))
    print("   ✓ -Encoding Default → UTF8（%d 处）；已加 chcp 65001 到窗口" % n)

print("=== 启动 bat:", os.path.basename(bat_start) if bat_start else "✗")
if bat_start:
    s = io.open(bat_start, encoding="gbk").read()
    n1 = s.count('cmd /c "cd /d ')
    s = s.replace('cmd /c "cd /d ', 'cmd /c "chcp 65001 >nul && cd /d ')
    n2 = s.count("&& %PY%")
    s = s.replace("&& %PY%", "&& set PYTHONIOENCODING=utf-8 && %PY%")
    io.open(bat_start, "w", encoding="gbk", newline="").write(
        s.replace("\r\n", "\n").replace("\n", "\r\n"))
    print("   ✓ 子窗口补回 chcp 65001（%d 处）+ PYTHONIOENCODING=utf-8（%d 处）→ 与 UTF-8 日志一致" % (n1, n2))

print()
print("=== 验证：用看日志窗口相同的读法读 f5tts.log ===")
logp = os.path.join(LOGDIR, "f5tts.log")
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Content -Encoding UTF8 -TotalCount 6 '%s'" % logp],
                   capture_output=True, timeout=180)
raw = r.stdout or b""
for enc in ("utf-8", "gbk"):
    try:
        print("   （按 %s 解 PS 输出）" % enc)
        for l in raw.decode(enc).splitlines()[:6]:
            print("   | " + l[:150])
        break
    except Exception:
        pass

print()
print("=== 最后三行（确认有合成记录）===")
r2 = subprocess.run(["powershell", "-NoProfile", "-Command",
                     "Get-Content -Encoding UTF8 '%s' | Select-Object -Last 3" % logp],
                    capture_output=True, timeout=180)
print("   " + (r2.stdout or b"").decode("gbk", errors="replace").replace("\r\n", "\n   ")[:600])
