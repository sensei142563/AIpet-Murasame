# -*- coding: utf-8 -*-
"""① 把设备上的 model.vrm 拉下来体检（如实回答：这是哪个模型、什么衣服、有哪些表情）
   ② 给 3D 页加"canvas 到底在不在、被谁盖住"的定位日志，重新装机。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
IDX = os.path.join(CHAT, "app/src/main/assets/vrm/index.html")
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
EXT = "/sdcard/Android/data/%s/files" % PKG
LOCAL_VRM = os.path.join(MAIN, "dev", "vrm_probe", "model_from_device.vrm")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① 拉模型 + 体检 ----------
os.makedirs(os.path.dirname(LOCAL_VRM), exist_ok=True)
r0 = subprocess.run([ADB, "-s", DEV, "pull", EXT + "/vrm/model.vrm", LOCAL_VRM],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
print("=== 拉取设备上的模型 ===")
print("   " + ((r0.stdout or r0.stderr or "").strip().splitlines() or ["?"])[-1][:140])
print("   本地大小:", os.path.getsize(LOCAL_VRM) if os.path.isfile(LOCAL_VRM) else "无")

print()
print("=== 用 vrm_inspect.py 体检（这是判定依据，不是我猜的）===")
ins = os.path.join(MAIN, "dev", "scripts", "vrm_inspect.py")
if os.path.isfile(ins) and os.path.isfile(LOCAL_VRM):
    r1 = subprocess.run([sys.executable, "-u", ins, LOCAL_VRM], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=600,
                        env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    print("\n".join("   " + l for l in ((r1.stdout or "") + (r1.stderr or "")).splitlines()[:70]))
else:
    print("   (缺 vrm_inspect.py 或模型)")

# ---------- ② canvas 定位日志 ----------
print()
print("=== 给 3D 页加 canvas 定位日志 ===")
h = io.open(IDX, encoding="utf-8").read().replace("\r\n", "\n")
if "__canvasProbe" not in h:
    probe = '''
// 【定位用】canvas 到底在不在布局里、中心点最上层是谁 —— 一次把话问清楚。
window.__canvasProbe = function () {
  const c = renderer.domElement;
  const r = c.getBoundingClientRect();
  const cx = Math.max(1, (innerWidth / 2) | 0), cy = Math.max(1, (innerHeight / 2) | 0);
  const top = document.elementFromPoint(cx, cy);
  return 'canvasRect=' + [r.left | 0, r.top | 0, r.width | 0, r.height | 0].join(',')
       + ' style=' + c.style.width + 'x' + c.style.height
       + ' buf=' + c.width + 'x' + c.height
       + ' body=' + document.body.clientWidth + 'x' + document.body.clientHeight
       + ' topAtCenter=' + (top ? (top.id || top.tagName) : 'null');
};
setTimeout(function () { document.title = 'P:' + window.__canvasProbe(); }, 3000);
'''
    h = h.replace("// 每秒把运行状况写进标题", probe + "\n// 每秒把运行状况写进标题", 1)
    io.open(IDX, "w", encoding="utf-8", newline="\n").write(h)
    print("✓ 已加 __canvasProbe（3 秒后把布局事实写进标题）")
else:
    print("· 已有 probe")

print()
print("=== 编译 + 装机 ===")
rr = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                    cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=ENV, timeout=7200)
for l in ((rr.stdout or "") + (rr.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:180])
if rr.returncode != 0:
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
o2 = (r2.stdout or "") + (r2.stderr or "")
print("   装机:", [l for l in o2.splitlines() if "Success" in l or "Failure" in l][:1] or "?")


def adb(*a, timeout=240):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def tap_text(x, needle, wait=3.0):
    ns = []
    for m in re.finditer(r'<node(?P<a1>[^>]*?)bounds="\[(?P<x1>\d+),(?P<y1>\d+)\]\[(?P<x2>\d+),(?P<y2>\d+)\]"(?P<a2>[^>]*?)/?>', x):
        at = (m.group("a1") or "") + (m.group("a2") or "")
        tm = re.search(r'text="([^"]*)"', at)
        ns.append({"t": tm.group(1) if tm else "", "c": 'clickable="true"' in at,
                   "x1": int(m.group("x1")), "y1": int(m.group("y1")),
                   "x2": int(m.group("x2")), "y2": int(m.group("y2"))})
    for i, nd in enumerate(ns):
        if needle in nd["t"]:
            tx, ty = (nd["x1"] + nd["x2"]) // 2, (nd["y1"] + nd["y2"]) // 2
            tgt = None
            for j in range(i - 1, -1, -1):
                cc = ns[j]
                if cc["c"] and cc["x1"] <= tx <= cc["x2"] and cc["y1"] <= ty <= cc["y2"]:
                    tgt = cc
                    break
            tgt = tgt or nd
            cx, cy = (tgt["x1"] + tgt["x2"]) // 2, (tgt["y1"] + tgt["y2"]) // 2
            adb("shell", "input", "tap", str(cx), str(cy))
            time.sleep(wait)
            return (cx, cy)
    return None


adb("shell", "rm", "-f", EXT + "/vrm.log")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(9)
tap_text(dump("x1"), "聊天", 4.0)
tap_text(dump("x2"), "☰", 3.0)
tap_text(dump("x3"), "VRM 演示", 16.0)
print("\n=== vrm.log 里的 P: 行（canvas 布局事实）===")
log = adb("shell", "cat", EXT + "/vrm.log")
for l in (log or "").splitlines():
    if "title=P:" in l:
        print("   " + l.strip()[:230])
        break
else:
    print("   （没有 P: 行）")
print("\n=== log 最后 4 行 ===")
print("\n".join("   " + l.strip()[:170] for l in (log or "").splitlines()[-4:]))
