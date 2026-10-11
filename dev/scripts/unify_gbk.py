# -*- coding: utf-8 -*-
"""统一为 GBK(936)：① 启动 bat 的子窗口去掉 chcp 65001 / PYTHONIOENCODING
   ② 看日志 bat 用默认(ANSI=GBK)读取  ③ 清空旧的 UTF-8 日志，避免混着两种编码。"""
import glob
import io
import os
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


bat_start = find("*Jev*.bat", "*启动*.bat")
bat_logs = find("*看日志*.bat", "*日志*.bat")
print("=== 处理启动 bat:", os.path.basename(bat_start) if bat_start else "✗ 没找到")

if bat_start:
    s = io.open(bat_start, encoding="gbk").read()
    print("   改前子窗口行示例：")
    for l in s.split("\r\n"):
        if l.strip().startswith("start "):
            print("      " + l[:160])
    n1 = s.count("chcp 65001 >nul && ")
    s = s.replace("chcp 65001 >nul && ", "")
    n2 = s.count("set PYTHONIOENCODING=utf-8 && ")
    s = s.replace("set PYTHONIOENCODING=utf-8 && ", "")
    io.open(bat_start, "w", encoding="gbk", newline="").write(
        s.replace("\r\n", "\n").replace("\n", "\r\n"))
    print("   ✓ 去掉 chcp 65001（%d 处）与 PYTHONIOENCODING=utf-8（%d 处）→ 服务按系统默认 936 输出" % (n1, n2))
    print("   改后子窗口行：")
    for l in io.open(bat_start, encoding="gbk").read().split("\r\n"):
        if l.strip().startswith("start "):
            print("      " + l[:160])

if bat_logs:
    t = io.open(bat_logs, encoding="gbk").read()
    print()
    print("=== 处理看日志 bat:", os.path.basename(bat_logs))
    n = t.count("Get-Content -Wait -Tail 30 ")
    t = t.replace("Get-Content -Wait -Tail 30 ", "Get-Content -Wait -Tail 30 -Encoding Default ")
    io.open(bat_logs, "w", encoding="gbk", newline="").write(
        t.replace("\r\n", "\n").replace("\n", "\r\n"))
    print("   ✓ 加了 -Encoding Default（%d 处）→ PowerShell 按 ANSI/GBK 读，中文正常" % n)
    for l in io.open(bat_logs, encoding="gbk").read().split("\r\n"):
        if "Get-Content" in l:
            print("      " + l.strip()[:170])

print()
print("=== 清空旧日志（它们是 UTF-8 写的，留着会和新内容混编码）===")
if os.path.isdir(LOGDIR):
    for n in sorted(os.listdir(LOGDIR)):
        p = os.path.join(LOGDIR, n)
        sz = os.path.getsize(p)
        io.open(p, "wb").write(b"")
        print("   %-14s %d B → 已清空" % (n, sz))
else:
    os.makedirs(LOGDIR, exist_ok=True)
    print("   （新建了 logs 目录）")

print()
print("✓ 完成。请重新双击「%s」；三个服务窗口里的中文应当正常了。" %
      (os.path.basename(bat_start) if bat_start else "启动 bat"))
print("  跑完后再双击「重连」bat，然后双击「看日志」bat 就能实时看三行日志。")
