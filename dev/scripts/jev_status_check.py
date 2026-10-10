# -*- coding: utf-8 -*-
"""查 Jev 全链路各环现状：api.py 日志、NanoJev 日志、端口、转发、以及手机端有没有发过请求。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TMP = r"E:\university\order\python\pet\_audit_fish9269"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"

print("=== ① api.py 日志全文（28565 的请求记录）===")
p = os.path.join(TMP, "_api_serve.log")
txt = io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
print("   大小 %d 字节" % len(txt))
for l in txt.splitlines()[-25:]:
    print("   " + l.rstrip()[:130])
print("   ★ 出现过 /jev/choose 请求:", "有 ✓" if "/jev/choose" in txt else "没有 ✗")

print()
print("=== ② NanoJev 服务日志（8765，若被调用会有 evaluate 记录）===")
p2 = os.path.join(TMP, "repros", "NanoJev", "_serve.log")
t2 = io.open(p2, encoding="utf-8", errors="replace").read() if os.path.isfile(p2) else ""
print("   大小 %d 字节" % len(t2))
for l in t2.splitlines()[-12:]:
    print("   " + l.rstrip()[:130])
print("   ★ 出现过 /api/evaluate:", t2.count("/api/evaluate"), "次")
for m in re.finditer(r"POST /api/evaluate[^\n]*", t2):
    print("      " + m.group(0)[:110])

print()
print("=== ③ 端口与转发 ===")
r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, encoding="utf-8", errors="replace")
for l in (r.stdout or "").splitlines():
    if re.search(r":(28565|8765|9881)\s", l) and "LISTEN" in l.upper():
        print("   " + l.strip()[:100])
print("   reverse:", subprocess.run([ADB, "reverse", "--list"], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace").stdout.strip().replace("\n", " | ") or "(空)")

print()
print("=== ④ 手机端：直接打一发（走 USB 的 127.0.0.1）===")
# 用手机浏览器打 /health（GET），再看 api 日志是否新增
before = len(txt)
subprocess.run([ADB, "shell", "am", "start", "-a", "android.intent.action.VIEW",
                "-d", "http://127.0.0.1:28565/docs"], capture_output=True, timeout=120)
import time
time.sleep(8)
txt2 = io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
new = txt2[before:]
print("   新增日志行:")
for l in new.splitlines()[-8:]:
    print("      " + l.rstrip()[:120])
print("   ★ 手机请求已到达电脑:", "是 ✓" if new.strip() else "否 ✗")
subprocess.run([ADB, "shell", "input", "keyevent", "KEYCODE_BACK"], capture_output=True)

print()
print("=== ⑤ 结论 ===")
print("""
   传输层：手机(USB) → 127.0.0.1:28565 → api.py ✓ 已证实（浏览器可打开 Swagger，含 POST /jev/choose）
   PC 端：/jev/choose → tool/jev.py → 本地 NanoJev ✓ 已证实（curl 返回 {"name":"你认真的？"} 0.3s）
   应用层：手机 App 是否触发过 /jev/choose —— 见上面第 ① 项
   未触发的可能原因（按概率）：
     1) 聊天**没拿到回复**（手机端大模型需要 key/网络）→ 我的 Jev 调用在**回复之后**才执行
     2) 消息没真正发出（自动化的发送键点错）
     3) 表情包候选为空（murasame 有 20 个，理论上不是这条）
""")
