# -*- coding: utf-8 -*-
"""修 bat 的 CRLF（去掉多出来的一个 CR）：按 GBK 读入、统一成 CR CR? → 只留一个 CRLF。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DEV = r"E:\university\order\python\pet\AIpet-Murasame-main\dev"
names = ["一键启动-本地Jev与语音.bat", "手机连电脑-一键重连.bat", "看日志-开三个窗口.bat"]
for n in names:
    p = os.path.join(DEV, n)
    raw = io.open(p, "rb").read()
    # 统一：\r\n 与 \r\r\n 都压成单个 \r\n；单独的 \n 也补成 \r\n
    t = raw.replace(b"\r\r\n", b"\r\n").replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    t = t.replace(b"\n", b"\r\n")
    io.open(p, "wb").write(t)
    head = t[:14]
    print("✓ %-26s %6d B  首字节 %s" % (n, len(t), " ".join("%02X" % x for x in head)))
    # 校验：不允许出现 \r\r 或单独的 \n
    bad = (b"\r\r" in t) or (t.replace(b"\r\n", b"") .count(b"\n") > 0)
    print("   行尾校验:", "✓ 全是单个 CRLF" if not bad else "✗ 仍有问题")
    txt = t.decode("gbk", errors="replace").split("\r\n")
    print("   前 3 行 GBK 解码：", [x[:40] for x in txt[:3]])
print()
print("✓ 三个 bat 行尾已修正为单个 CRLF（GBK 编码不变）")
