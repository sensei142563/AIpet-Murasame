# -*- coding: utf-8 -*-
"""run-as 驱动 Termux（修正版）。

关键坑（实测）：`adb shell run-as … sh -c "cat > 路径"` 里的 `>` 会被**设备外层 shell** 解析，
于是变成 shell 用户在写 Termux 私有目录 ⇒ Permission denied。
必须把整条内层命令**用单引号包成一个参数**，让重定向发生在 run-as 之后的那个 shell 里。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.termux"
HOME = "/data/data/com.termux/files/home"
BASH = "/data/data/com.termux/files/usr/bin/bash"


def adb_raw(*args, timeout=1800, stdin=None, binary=False):
    r = subprocess.run([ADB, "-s", DEV, *args], capture_output=True, timeout=timeout, stdin=stdin)
    if binary:
        return r.stdout
    return ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", "replace")


def run_as(inner, timeout=1800, stdin=None):
    """把 inner 作为**单个参数**传给 run-as 后的 sh -c，使引号与重定向都在远端生效。"""
    return adb_raw("shell", "run-as", PKG, "sh", "-c", "'%s'" % inner.replace("'", "'\\''"),
                   timeout=timeout, stdin=stdin)


def put(local, name):
    with io.open(local, "rb") as fh:
        out = run_as("cat > %s/%s" % (HOME, name), stdin=fh)
    return out.strip()[:200]


def get(name):
    return run_as("cat %s/%s" % (HOME, name))


def ls(name):
    return run_as("ls -l %s/%s" % (HOME, name)).strip()


def run(local, timeout=2400):
    name = os.path.basename(local)
    log = name + ".log"
    e = put(local, name)
    if e:
        print("   写入提示:", e[:200])
    print("   远端:", ls(name)[:130])
    inner = ("cd %s && chmod 700 %s && export PATH=/data/data/com.termux/files/usr/bin:$PATH && "
             "%s %s > %s 2>&1; echo RC=$?") % (HOME, name, BASH, name, log)
    print("   执行:", run_as(inner, timeout=timeout).strip()[-120:])
    return get(log)


if __name__ == "__main__":
    local = sys.argv[1]
    tmo = int(sys.argv[2]) if len(sys.argv) > 2 else 2400
    print("=== %s ===" % os.path.basename(local))
    body = run(local, tmo)
    print()
    print("=== Termux 日志 ===")
    if body and body.strip():
        for l in body.splitlines()[-55:]:
            print("   " + l.rstrip()[:190])
    else:
        print("   （空）")
