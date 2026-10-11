# -*- coding: utf-8 -*-
"""修正 hotspot_ready.py：无线 adb 的示例地址用默认网关（热点下=手机），并提交桌面仓。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
HELPER = os.path.join(MAIN, "dev/scripts/hotspot_ready.py")
MAP = os.path.join(MAIN, "dev", "merge-map")
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"

s = io.open(HELPER, encoding="utf-8").read()
old = '''    if good:
        ip = good[0][0]
        print("手机 App 设置里这样填（把地址改成电脑的局域网 IP，端口不变）：")
        for port, name in PORTS:
            if port in (28565, 9881):
                print("   %-16s → http://%s:%d" % (name, ip, port))
        print()
        print("或者更省事：不用改 App —— 走无线 adb 也能保留 127.0.0.1：")
        print("   1) 电脑: adb connect %s:5555   （手机需已开无线调试 / 之前执行过 adb tcpip 5555）" % ip)
        print("   2) 电脑: adb -s %s:5555 reverse tcp:28565 tcp:28565" % ip)
        print("   3) 电脑: adb -s %s:5555 reverse tcp:9881 tcp:9881" % ip)
        print("   这样 App 里的 127.0.0.1 地址完全不用动 ✓")'''
new = '''    gw = default_gateway()
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
        print("   这样 App 里的 127.0.0.1 地址完全不用动 ✓")'''
assert old in s, "✗ 锚点1"
s = s.replace(old, new, 1)

# 加 default_gateway()
if "def default_gateway(" not in s:
    anchor = "def main():"
    fn = '''def default_gateway():
    """默认网关：热点环境下它就是手机的地址（安卓热点常见 192.168.43.1）。"""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | "
                            "Select-Object -First 1).NextHop"], capture_output=True, text=True, timeout=120)
        gw = (r.stdout or "").strip().splitlines()
        return gw[0].strip() if gw else None
    except Exception:
        return None


'''
    s = s.replace(anchor, fn + anchor, 1)

# 底部路由打印改用该函数，避免重复
s = s.replace('''    print("路由表里的默认网关（热点时网关就是手机）：")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
                            "Select-Object -First 3 NextHop,InterfaceAlias | ConvertTo-Csv -NoTypeInformation)"],
                           capture_output=True, text=True, timeout=120)
        for line in (r.stdout or "").splitlines()[1:]:
            print("   " + line.replace('"', ""))
    except Exception:
        pass''',
                  '''    print("默认网关（热点时它就是手机）：%s" % (gw or "未识别"))''', 1)

io.open(HELPER, "w", encoding="utf-8", newline="\n").write(s)
print("✓ hotspot_ready.py 已修正（无线 adb 用默认网关）")

print()
print("=== 复核输出 ===")
r = subprocess.run([PY, "-u", HELPER], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=MAIN, timeout=600)
for l in (r.stdout or r.stderr).splitlines():
    print("   " + l)

MSG = """feat(hotspot): 打通手机热点链路（F5 绑 0.0.0.0 + 一键热点脚本 + 就绪探测）

背景：校园网做了客户端隔离，手机与电脑互相 ping 不通，现有链路依赖 USB adb reverse。
本提交补上"手机开热点 → 电脑连热点"这条路，作为 USB 之外的备用通道。

· longtext/f5tts_server.py：uvicorn 从 host="127.0.0.1" 改为 F5TTS_HOST 环境变量（默认 0.0.0.0）。
  原来只有本机能连，热点下手机连不上 9881；改后实测局域网 IP 172.25.195.72:9881 可连 ✓
  （api.py 本来就是 0.0.0.0:28565 ✓；NanoJev 8765 故意只留 127.0.0.1——它只被本机 api.py 调用，不对外更安全）
· dev/scripts/hotspot_ready.py：列出本机局域网 IP → 逐端口 TCP 探测（127.0.0.1 与各局域网 IP）
  → 打印手机 App 该填的地址 → 打印默认网关（热点下即手机地址）与无线 adb 三条命令。
· dev/热点连接.bat：一键做四件事——放行防火墙 28565/9881（UAC）、跑就绪探测、
  自动用默认网关 adb connect + reverse（这条路 App 设置完全不用改）、打印直连方式兜底。
  编码 GBK + CRLF，无括号块（吸取之前 bat 秒退的教训）。

实测（本机）：三服务 127.0.0.1 全通；9881/28565 在 172.25.195.72 上也可连；
adb tcpip 5555 已开、USB 转发已重建。等你开热点后再跑 dev\\热点连接.bat 即可。
"""
p = os.path.join(MAP, "_msg_hotspot.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:120])
print("未推送:", subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                                capture_output=True, text=True).stdout.strip(), "条")
