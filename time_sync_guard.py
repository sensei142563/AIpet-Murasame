# -*- coding: utf-8 -*-
"""
时间同步守护 — 自动修复 QQ "网络连接异常"(1006514) 与 NapCat [ServerTime] 警告。

原理：本地主板时钟会漂移，QQ 发送消息带时间戳校验，偏差过大即被腾讯服务器拒绝。
本守护每 3 分钟用网络时间校准本地偏差，超过阈值(4 秒)自动执行 w32tm /resync。
（以 SYSTEM 权限的计划任务运行，无需用户干预；NapCat 检测偏差约 7 秒会报警，
  我们提前到 4 秒就同步，警告根本不会出现。）

日志：data/time_sync_guard.log
"""
import os
import time
import socket
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(BASE, "data", "time_sync_guard.log")
LOCK_PORT = 29123  # 单实例端口锁
PIDFILE = os.path.join(BASE, "data", "time_sync_guard.pid")   # 心跳文件（启动器靠它判断守护在不在跑）

DRIFT_THRESHOLD = 4.0   # 偏差超过 4 秒即同步（NapCat 约 7 秒报警，提前处理）
CHECK_INTERVAL = 180    # 每 3 分钟检测一次


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


def net_timestamp():
    """通过 HTTPS Date 头获取网络时间戳（多个源轮流尝试）"""
    import urllib.request
    from email.utils import parsedate_to_datetime
    for url in ("https://www.baidu.com", "https://cn.bing.com", "https://www.qq.com"):
        try:
            req = urllib.request.Request(url, method="HEAD")
            resp = urllib.request.urlopen(req, timeout=6)
            d = resp.headers.get("Date", "")
            if d:
                return parsedate_to_datetime(d).timestamp()
        except Exception:
            continue
    return None


def resync():
    """执行 Windows 时间同步（需要 SYSTEM/管理员权限，计划任务已提供）"""
    try:
        r = subprocess.run(["w32tm", "/resync", "/nowait"],
                           capture_output=True, timeout=25)
        return r.returncode == 0
    except Exception:
        return False


def already_running():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(1)
        # 绑定成功 → 本进程持有锁；把 socket 存全局保持存活
        return s
    except OSError:
        return None


def heartbeat():
    """写心跳文件（PID + 时间戳），每个检测周期刷新一次。

    用途：启动器的插件页要显示「守护在不在跑」。以前那边是起 PowerShell 扫进程
    （一次 500ms+，还每张卡片都调），现在只要读这个文件的一次 stat。
    """
    try:
        os.makedirs(os.path.dirname(PIDFILE), exist_ok=True)
        with open(PIDFILE, "w", encoding="utf-8") as f:
            f.write("%d %d\n" % (os.getpid(), int(time.time())))
    except Exception:
        pass


def main():
    # 启动即先同步一次（清掉历史漂移）
    ok = resync()
    log(f"守护启动（resync={'OK' if ok else '失败(稍后重试)'}）")

    s = already_running()
    if s is None:
        log("检测到已有守护实例在运行，本实例退出")
        return
    heartbeat()
    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            heartbeat()
            n = net_timestamp()
            if n is None:
                log("无法获取网络时间（网络异常？）跳过本轮")
                continue
            drift = time.time() - n
            if abs(drift) > DRIFT_THRESHOLD:
                log(f"检测到时间偏差 {drift:+.1f}s，正在自动同步...")
                if resync():
                    time.sleep(5)
                    n2 = net_timestamp()
                    if n2 is not None:
                        d2 = time.time() - n2
                        log(f"同步完成，当前偏差 {d2:+.1f}s")
                else:
                    log("同步失败（权限或网络问题），下轮重试")
    finally:
        try:
            s.close()
        except Exception:
            pass
        # 正常退出时清掉心跳文件（只清自己的，避免误删新实例的）
        try:
            with open(PIDFILE, "r", encoding="utf-8") as f:
                if int(f.read().split()[0]) == os.getpid():
                    os.remove(PIDFILE)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"守护异常退出: {e}")
