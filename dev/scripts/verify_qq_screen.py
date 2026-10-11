# -*- coding: utf-8 -*-
"""验收手机 QQ 页：核实装机 → 聊天→☰→QQ 通道 → 断言显示电脑真实数据 → 投递一条到队列 → 查 /qq/outbox。"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
TMP = os.path.join(MAIN, "dev", "shots")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


def adb(*a, t=300):
    return subprocess.run([ADB, "-s", DEV] + list(a), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=t).stdout or ""


def dump(tag):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "-s", DEV, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=90)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def box(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))) if m else None


def tap(b, tag=""):
    if not b:
        print("   ✗ 没找到 %s" % tag)
        return False
    adb("shell", "input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
    print("   tap %s" % tag)
    time.sleep(2.5)
    return True


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


def find(labels, tries=6, wait=4):
    for i in range(tries):
        z = dump("q%d_%d" % (int(time.time()) % 10000, i))
        for lb in labels:
            b = box(lb, z)
            if b:
                return lb, b, z
        time.sleep(wait)
    return None, None, z


print("=== ① 核实装机 ===")
t = adb("shell", "dumpsys", "package", PKG)
m = re.search(r"lastUpdateTime=([^\n]+)", t)
print("   lastUpdateTime:", (m.group(1).strip() if m else "?"))
if not m:
    print("   ✗ 包信息读不到")
    sys.exit(1)

print("=== ② 打开 QQ 通道页 ===")
adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
adb("shell", "am", "force-stop", PKG)
time.sleep(3)
adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(16)
lb, b, z = find(["聊天"])
tap(b, "聊天")
time.sleep(5)
lb, b, z = find(["☰"])
tap(b, "☰ 抽屉")
time.sleep(3)
lb, b, z = find(["💬 QQ 通道", "QQ 通道"])
note("抽屉里有「QQ 通道」入口", lb is not None)
if not lb:
    print("   抽屉文字:", [x for x in texts(z) if len(x) < 22][:14])
    sys.exit(1)
tap(b, lb)
time.sleep(8)
z = dump("qq1")
tx = texts(z)
print("   QQ 页文字:")
for x in tx[:18]:
    print("      " + x[:110])
note("页面标题出现", any("QQ 通道" in x for x in tx))
note("显示出 NapCat 状态（离线也算正常数据）", any("NapCat" in x for x in tx))
note("显示出会话数或会话目录", any("会话数" in x or "会话目录" in x for x in tx))
note("没有报「连不上电脑端 api.py」", not any("连不上电脑端" in x for x in tx))

print()
print("=== ③ 投递一条到队列 ===")
before = json.loads(urllib.request.urlopen("http://127.0.0.1:28565/qq/outbox", timeout=30).read())
print("   投递前 pending_bytes =", before.get("pending_bytes"))
# 目标号输入框（第一个 OutlinedTextField）
allb = re.findall(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
print("   找到输入框 %d 个" % len(allb))
if len(allb) >= 2:
    b1 = tuple(int(x) for x in allb[0])
    b2 = tuple(int(x) for x in allb[1])
    tap(b1, "目标号输入框")
    adb("shell", "input", "text", "1234567")
    time.sleep(1)
    tap(b2, "内容输入框")
    adb("shell", "input", "text", "hello-from-phone-ui")
    time.sleep(1)
    z = dump("qq2")
    sent = tap(box("发送到队列", z), "发送到队列")
    time.sleep(8)
    z = dump("qq3")
    print("   页面提示:", [x for x in texts(z) if "投递" in x or "队" in x][:3])
    after = json.loads(urllib.request.urlopen("http://127.0.0.1:28565/qq/outbox", timeout=30).read())
    print("   投递后 pending_bytes =", after.get("pending_bytes"), " 已发送记录 =", len(after.get("acked") or []))
    note("队列里多出待发送内容（pending 增大）", after.get("pending_bytes", 0) > before.get("pending_bytes", 0))
    q = (after.get("queued") or [])[-1] if after.get("queued") else {}
    print("   队尾条目:", json.dumps(q, ensure_ascii=False)[:160])
    note("队尾就是手机发的这条", "hello-from-phone-ui" in json.dumps(q, ensure_ascii=False))
else:
    note("找到两个输入框（目标号 + 内容）", False)

print()
print("总结:", "手机 QQ 页通路验证通过 ✓（真机端到端仍等 NapCat 起来）" if ok else "有失败项 ✗")
