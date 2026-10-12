# -*- coding: utf-8 -*-
"""盯 NapCat 安装进度：每 45 秒回读 Termux 侧日志，报告里程碑与尾部。"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tx import get, run_as  # noqa: E402

LOG = "napcat_install.log"
MILESTONES = [
    ("pull", "拉取 Debian 镜像"),
    ("Extracting", "解包镜像"),
    ("initializing", "初始化容器"),
    ("apt update", "容器内 apt update"),
    ("NapCat", "NapCat 安装"),
    ("QQ", "拉取 LinuxQQ"),
    ("NapCat 安装完成", "安装完成"),
    ("FAILED", "失败"),
    ("error", "报错"),
]

lastlen = 0
for i in range(40):                      # 最多 ~30 分钟
    body = get(LOG) or ""
    if len(body) != lastlen:
        lastlen = len(body)
        tail = [l.rstrip() for l in body.splitlines() if l.strip()][-5:]
        print("[%4ds] %s" % (i * 45, " ／ ".join(l.strip()[:70] for l in tail)))
    if "NapCat 安装完成" in body:
        print("⇒ 安装完成 ✓")
        break
    if "初始化失败" in body:
        print("⇒ 初始化失败（日志见下）")
        break
    time.sleep(45)
print()
print("=== 日志尾部 45 行 ===")
body = get(LOG) or ""
for l in body.splitlines()[-45:]:
    print("   " + l.rstrip()[:185])
print()
print("=== 容器是否建好 ===")
print(run_as("ls -l /data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/ 2>&1").strip()[:400])
