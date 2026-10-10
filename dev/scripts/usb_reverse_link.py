# -*- coding: utf-8 -*-
"""用 adb reverse 打通手机→电脑（绕开校园网隔离）：28565(Jev) + 9881(F5语音)；再用手机浏览器验证。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
TMP = r"E:\university\order\python\pet\_audit_fish9269"


def adb(*a, t=120):
    return subprocess.run([ADB, *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=t).stdout or ""


def sh(*a, t=120):
    return subprocess.run([ADB, "shell", *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=t).stdout or ""


print("=== ① 手机能否 ping 通电脑（确认是否被隔离）===")
p = sh("ping", "-c", "3", "-W", "2", "172.25.173.193")
print("   " + p.strip().replace("\n", "\n   ")[:400])

print()
print("=== ② 建反向端口转发（USB 通道）===")
for port in (28565, 9881):
    out = adb("reverse", "tcp:%d" % port, "tcp:%d" % port)
    print("   28565/9881 → tcp:%d  %s" % (port, out.strip() or "✓"))
print("   当前 reverse 列表:")
for l in adb("reverse", "--list").strip().splitlines():
    print("      " + l.strip())

print()
print("=== ③ 手机浏览器访问 http://127.0.0.1:28565/docs（走 USB）===")


def dump(tag):
    sh("uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=60)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "start", "-a", "android.intent.action.VIEW", "-d", "http://127.0.0.1:28565/docs")
time.sleep(12)
z = dump("i1")
texts = [t for t in re.findall(r'text="([^"]*)"', z) if t.strip()]
print("   页面文字（前 14 条）:", texts[:14])
joined = " ".join(texts)
ok = any(k in joined for k in ("Swagger", "FastAPI", "openapi", "/jev/choose", "Schemas"))
print("   ★ 判定:", "✓✓ 手机已能访问电脑服务（走 USB）" if ok else "✗ 仍不通")
with io.open(os.path.join(TMP, "phone_usb_conn.png"), "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", os.path.join(TMP, "phone_usb_conn.png"))
sh("input", "keyevent", "KEYCODE_BACK")

print()
print("=== ④ 结论与你要填的地址 ===")
print("""
   若上面显示 ✓：手机端两个地址请改成（走 USB，绕开校园网隔离）：
       Jev 电脑地址   →  http://127.0.0.1:28565
       语音服务地址   →  http://127.0.0.1:9881
   注意：adb reverse 在**拔线/重启手机后失效**，重连后需再跑一次：
       adb reverse tcp:28565 tcp:28565
       adb reverse tcp:9881  tcp:9881
   （我可以给你做一个 .bat 一键重连脚本）
""")
