# -*- coding: utf-8 -*-
"""我自己来：通过 run-as 在 Termux 里跑安装前置步骤（修 apt/curl + 装 screen/proot-distro +
由手机自己下载 NapCat 官方安装脚本），后台执行、日志落在 Termux 私有目录，我再回读。

用法：python dev/scripts/tx.py <本地脚本> [超时秒]      # 上传并前台执行
      python dev/scripts/tx.py log <日志文件名>        # 读日志
"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.termux"
HOME = "/data/data/com.termux/files/home"
BASH = "/data/data/com.termux/files/usr/bin/bash"


def adb(*args, timeout=1800, stdin=None):
    r = subprocess.run([ADB, "-s", DEV, *args], capture_output=True, timeout=timeout, stdin=stdin)
    return ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", "replace")


def run_as(inner, timeout=1800, stdin=None):
    """注意：内层命令整体用单引号包住，让重定向/管道在 run-as 之后的 shell 里生效。"""
    q = "'" + inner.replace("'", "'\\''") + "'"
    return adb("shell", "run-as", PKG, "sh", "-c", q, timeout=timeout, stdin=stdin)


def put(local, name):
    with io.open(local, "rb") as fh:
        return run_as("cat > %s/%s" % (HOME, name), stdin=fh).strip()[:200]


def get(name):
    return run_as("cat %s/%s" % (HOME, name))


def main():
    if sys.argv[1] == "log":
        print(get(sys.argv[2]))
        return
    local = sys.argv[1]
    tmo = int(sys.argv[2]) if len(sys.argv) > 2 else 2400
    name = os.path.basename(local)
    print("上传:", put(local, name) or "ok")
    print("远端:", run_as("ls -l %s/%s" % (HOME, name)).strip()[:120])
    inner = ("cd %s && chmod 700 %s && export PATH=/data/data/com.termux/files/usr/bin:$PATH && "
             "%s %s > %s.log 2>&1; echo RC=$?") % (HOME, name, BASH, name, name)
    print("执行:", run_as(inner, timeout=tmo).strip()[-120:])
    body = get(name + ".log")
    print()
    print("=== 日志 ===")
    for l in (body or "").splitlines()[-60:]:
        print("   " + l.rstrip()[:190])


if __name__ == "__main__":
    main()
