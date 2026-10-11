# -*- coding: utf-8 -*-
"""提交热点脚本修复（--gateway + 经验教训），并输出两仓状态。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """fix(hotspot): 热点脚本网关解析改用 helper --gateway（原实现被引号吃掉变成 +）

用户实测 dev\\热点连接.bat 第 3 步：
    set GW=+  →  adb connect +:5555  →  cannot resolve host '+'
原因：bat 里用 for /f 解析 PowerShell 的 (Get-NetRoute ...).NextHop，
      ^| 转义与引号在 cmd 里被吃掉，取回了一个 '+'。

改为给 hotspot_ready.py 增加 --gateway（只打印网关），bat 直接
    for /f "usebackq tokens=1" %%g in (`"%PY%" ... hotspot_ready.py --gateway`) do set GW=%%g
实测：取到 192.168.43.1（手机热点网关）→ adb connect 成功 → reverse 建立 ✓

顺带记录一条 adb 经验（本次踩到）：`adb reverse --remove-all` 是**设备级**的，
不是按 -s 通道隔离的；用 -s <USB序列号> 执行会连带清掉网络通道的转发，
表现为转发列表整片变空、手机请求到不了电脑。要按通道操作就只能逐条 add/remove。

实测结果（热点通道，USB 转发已清）：
  设备列表含 192.168.43.1:5555 device ✓
  reverse 列表 host-18 tcp:28565 / tcp:9881 ✓
  手机聊天页发消息 → 电脑 dev/logs/api.log 新增
  INFO: 127.0.0.1:55493 - "POST /jev/choose HTTP/1.1" 200 OK ✓
  ⇒ 手机 → 手机热点 → 无线 adb 反向 → 电脑 api.py，端到端打通。
"""
p = os.path.join(MAP, "_msg_hotspot2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("桌面仓:", (r.stdout or r.stderr or "").splitlines()[0][:120])
for name, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (name, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
print()
print("当前热点通道状态：")
print("  " + subprocess.run([r"E:\Android\SDK\platform-tools\adb.exe", "reverse", "--list"],
                           capture_output=True, text=True).stdout.replace("\n", " | ").strip())
print("  " + subprocess.run([r"E:\Android\SDK\platform-tools\adb.exe", "devices"],
                           capture_output=True, text=True).stdout.replace("\n", " ").strip()[:140])
