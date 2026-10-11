# -*- coding: utf-8 -*-
"""热点/局域网就绪检查：列出本机所有局域网 IPv4 → 逐个探测三个服务端口 → 打印手机 App 该填的地址。

用法：python dev/scripts/hotspot_ready.py
说明：手机开热点后，电脑连上该热点，再跑本脚本（也可在 USB 状态下先跑，验证服务是否绑到 0.0.0.0）。
"""
import socket
import subprocess
import sys

PORTS = ((8765, "NanoJev 本地判断"), (9881, "F5-TTS 语音"), (28565, "api.py 总入口"))
# 热点环境下电脑拿到的地址通常长这样（安卓热点多为 192.168.43.x，Windows 热点为 192.168.137.x）
HOTSPOT_HINT = ("192.168.43.", "192.168.137.", "192.168.42.", "172.20.10.")


def ips():
    out = []
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-NetIPAddress -AddressFamily IPv4 | "
                            "Select-Object IPAddress,InterfaceAlias,PrefixOrigin | ConvertTo-Csv -NoTypeInformation"],
                           capture_output=True, text=True, timeout=120)
        for line in (r.stdout or "").splitlines()[1:]:
            p = [x.strip().strip('"') for x in line.split(",")]
            if len(p) >= 2 and p[0] and not p[0].startswith(("127.", "169.254.")):
                out.append((p[0], p[1]))
    except Exception as e:
        print("取网卡失败:", e)
    if not out:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            out.append((s.getsockname()[0], "默认路由"))
            s.close()
        except Exception:
            pass
    return out


def probe(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=1.5):
            return True
    except Exception:
        return False


def default_gateway():
    """默认网关：热点环境下它就是手机的地址（安卓热点常见 192.168.43.1）。"""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | "
                            "Select-Object -First 1).NextHop"], capture_output=True, text=True, timeout=120)
        gw = (r.stdout or "").strip().splitlines()
        return gw[0].strip() if gw else None
    except Exception:
        return None


def main():
    cand = ips()
    print("=" * 62)
    print(" AIpet 热点/局域网 就绪检查")
    print("=" * 62)
    print("本机局域网地址：")
    for ip, alias in cand:
        tag = " ← 看起来是手机热点的网段" if ip.startswith(HOTSPOT_HINT) else ""
        print("   %-16s [%s]%s" % (ip, alias, tag))
    print()
    print("三个服务（127.0.0.1 = USB 反向转发 / 局域网 IP = 热点直连）：")
    good = []
    for port, name in PORTS:
        loop = probe("127.0.0.1", port)
        row = []
        for ip, _ in cand:
            row.append((ip, probe(ip, port)))
        lan_ok = [ip for ip, okk in row if okk]
        print("   %-6d %-16s 本机127.0.0.1: %s   局域网: %s" % (
            port, name, "✓" if loop else "✗", ("、".join(lan_ok) if lan_ok else "✗ 都不通")))
        if lan_ok:
            good.append((lan_ok[0], port))
    print()
    gw = default_gateway()
    if good:
        ip = good[0][0]
        print("手机 App 设置里这样填（把地址改成电脑的局域网 IP，端口不变）：")
        for port, name in PORTS:
            if port in (28565, 9881):
                print("   %-16s → http://%s:%d" % (name, ip, port))
        print()
        print("或者更省事：不用改 App —— 走无线 adb 也能保留 127.0.0.1：")
        if gw:
            print("   1) 电脑: adb connect %s:5555      ← %s 是默认网关，热点下就是手机的地址" % (gw, gw))
            print("   2) 电脑: adb -s %s:5555 reverse tcp:28565 tcp:28565" % gw)
            print("   3) 电脑: adb -s %s:5555 reverse tcp:9881 tcp:9881" % gw)
        else:
            print("   1) 电脑: adb connect <手机的WiFi地址>:5555   （先看下面默认网关）")
            print("   2) 电脑: adb -s <同上>:5555 reverse tcp:28565 tcp:28565")
            print("   3) 电脑: adb -s <同上>:5555 reverse tcp:9881 tcp:9881")
        print("   这样 App 里的 127.0.0.1 地址完全不用动 ✓")
    else:
        print("局域网 IP 上都不通 → 多半是：服务没起 / 只绑了 127.0.0.1 / 防火墙拦了")
        print("   F5 请确认是 0.0.0.0（本仓库已默认）；api.py 应是 0.0.0.0:28565")
        print("   防火墙可双击 dev\\热点连接.bat 走一次放行（需要同意 UAC）")
    print()
    print("默认网关（热点时它就是手机）：%s" % (gw or "未识别"))


if __name__ == "__main__":
    if "--gateway" in sys.argv:
        print(default_gateway() or "")
    else:
        main()
