# -*- coding: utf-8 -*-
"""电脑侧网络自检（配合手机端「网络自检（找电脑）」）。

用法：
    python tool/net_selfcheck.py                 # 只看电脑自己的网络状况
    python tool/net_selfcheck.py 192.168.43.7    # 顺便测能不能连到手机

它回答三件事：
  ① 电脑有哪些可用 IPv4（哪些是虚拟网卡/没连上的，一并说明）
  ② 电脑看起来在什么网络里；**像不像"手机热点"网段**（192.168.43.x / 42 / 44 / 172.20.10）
  ③ 关键端口是不是监听在 0.0.0.0（只听 127.0.0.1 的话手机永远连不上 —— 这是最常见的坑）
"""
import io
import os
import socket
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOTSPOT = ("192.168.43.", "192.168.42.", "192.168.44.", "172.20.10.")
PORTS = (28565, 9881, 3001)


def ipv4s():
    out = []
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-NetIPAddress -AddressFamily IPv4 | "
                            "Select-Object -Property IPAddress,InterfaceAlias,AddressState,PrefixLength | "
                            "ConvertTo-Csv -NoTypeInformation"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        for line in (r.stdout or "").splitlines()[1:]:
            f = [x.strip('"') for x in line.split('","')]
            if len(f) >= 4:
                out.append({"ip": f[0], "iface": f[1], "state": f[2], "prefix": f[3]})
    except Exception as e:
        print("   （取 IP 失败：%s）" % e)
    return out


def listening():
    res = {}
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-NetTCPConnection -State Listen | "
                            "Select-Object -Property LocalAddress,LocalPort | ConvertTo-Csv -NoTypeInformation"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        for line in (r.stdout or "").splitlines()[1:]:
            f = [x.strip('"') for x in line.split('","')]
            if len(f) >= 2 and f[1].isdigit():
                res.setdefault(int(f[1]), set()).add(f[0])
    except Exception:
        pass
    return res


def can_reach(host, port, timeout=2.5):
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except Exception:
        return False


print("=" * 70)
print("电脑侧网络自检")
print("=" * 70)

addrs = ipv4s()
print("\n① 本机 IPv4")
good = []
for a in addrs:
    tag = ""
    if a["ip"].startswith("127."):
        tag = "回环"
    elif a["ip"].startswith("169.254."):
        tag = "链路本地（这根网线/Wi-Fi 没连上）"
    elif a["state"].lower() != "preferred":
        tag = a["state"]
    else:
        good.append(a)
        tag = "可用"
    print("   %-16s %-26s %-8s %s" % (a["ip"], a["iface"][:26], "/" + a["prefix"], tag))

print("\n② 网络判断")
hot = [a for a in good if any(a["ip"].startswith(p) for p in HOTSPOT)]
if not good:
    print("   ✗ 没有可用的局域网地址（电脑没连任何网络？）")
elif hot:
    print("   ✓ 看起来电脑**连在手机热点上**：%s（%s）" % (hot[0]["ip"], hot[0]["iface"]))
    print("     ⇒ 手机上点「网络自检（找电脑）」应当能扫到本机；或直接手填本机地址")
else:
    print("   · 电脑在：%s（%s）" % (good[0]["ip"], good[0]["iface"]))
    print("     不是手机热点网段。若手机显示的是别的网段（例如 10.x 或 192.168.x），")
    print("     说明两台不在同一网络 —— 这类校园/企业网还常常**客户端互相隔离**，")
    print("     ⇒ 推荐走「手机开热点、电脑连手机」这条路。")

print("\n③ 关键端口监听情况（手机要连的）")
ls = listening()
for p in PORTS:
    if p not in ls:
        print("   %-6d ✗ 没有进程监听" % p)
        continue
    addrs_s = ls[p]
    if "0.0.0.0" in addrs_s or "::" in addrs_s:
        print("   %-6d ✓ 监听在 0.0.0.0（局域网可达）%s" % (p, sorted(addrs_s)))
    else:
        print("   %-6d ✗ 只监听在 %s ⇒ **手机连不上**（服务要绑 0.0.0.0）" % (p, sorted(addrs_s)))

if len(sys.argv) > 1:
    phone = sys.argv[1]
    print("\n④ 从电脑连手机 %s" % phone)
    if can_reach(phone, 5555):
        print("   · 5555（adb 无线调试）可达")
    for p in PORTS:
        print("   · %-6d %s" % (p, "可达" if can_reach(phone, p) else "不可达"))
    if not can_reach(phone, PORTS[0]):
        print("   （手机端本来就不监听这些端口，连不上是正常的；这里只是确认链路通不通）")
print()
