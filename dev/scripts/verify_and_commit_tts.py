# -*- coding: utf-8 -*-
"""验证两个开关行可见 → 提交 ⑤b/离线 TTS 的修复与结论。"""
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
SD = os.path.join(MAIN, "dev", "shots")
MAP = os.path.join(MAIN, "dev", "merge-map")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"


def adb(*a, timeout=300):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def tap(x, needle, wait=3.0, scroll=3):
    for _ in range(scroll):
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
                    c = ns[j]
                    if c["c"] and c["x1"] <= tx <= c["x2"] and c["y1"] <= ty <= c["y2"]:
                        tgt = c
                        break
                tgt = tgt or nd
                cx, cy = (tgt["x1"] + tgt["x2"]) // 2, (tgt["y1"] + tgt["y2"]) // 2
                adb("shell", "input", "tap", str(cx), str(cy))
                time.sleep(wait)
                return (cx, cy)
        adb("shell", "input", "swipe", "612", "1900", "612", "1000", "250")
        time.sleep(1.2)
        x = dump("sc2")
    return None


adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(10)
tap(dump("e1"), "聊天", 4.0)
tap(dump("e2"), "☰", 3.0)
tap(dump("e3"), "设置", 4.0)
x = dump("e4")
vals = []
for m in re.finditer(r'text="([^"]{1,44})"', x):
    if m.group(1) and m.group(1) not in vals:
        vals.append(m.group(1))
print("设置页文本（前 20）：")
for v in vals[:20]:
    print("   " + v)
p = os.path.join(SD, "settings_two_switches.png")
with io.open(p, "wb") as fh:
    subprocess.run([ADB, "-s", DEV, "exec-out", "screencap", "-p"], stdout=fh,
                   stderr=subprocess.DEVNULL, timeout=240)
print("截图:", p)
print("离线识别开关：", "离线识别（实验）" in x)
print("离线音色开关：", "离线音色（实验）" in x)

MSG = """fix(tts): 定位到离线合成卡死的真因并默认停用；清掉会卡死主线程的遗留诊断

一、真因（真机 MIS-AL00 / Android 12，按"自己加日志找"的做法一步步量出来的）
  · live2d.log 里只有 "[tts] main：准备构造"，后面什么都没有 —— 而这一行来自
    **我早先留下的诊断函数** diagEmptyConfigOnMain（用空配置在主线程构造 OfflineTts）。
    也就是说：⑤b 这条检查读到的是诊断的日志，不是真实合成路径。
  · 把该诊断调用从 ChatScreen 移除后，走**真实路径**（设置页「离线音色（本地合成）→ 点一下测试」）：
        [tts] speak() 被调用 text=[你好，我是丛雨。] lang=zh
        [tts] init() 进入 lang=zh modelDir=/storage/.../files/tts
    然后**没有下文**：既没有 "ready lang=…"，也没有 "init failed"。
  · 判决性实验：触发后逐段等待到 **90 秒**，日志始终停在 init 进入；
    同时界面**响应正常**（uiautomator dump 2.4s）⇒ 不是 ANR，是**原生构造函数无限卡住**。
    连异常都不抛 ⇒ runCatching 兜不住。

二、结论（与之前离线识别那条串起来）
  这台机器上 sherpa-onnx 的**两个原生组件都不可用**：
    · SenseVoice（离线识别）：初始化即让进程被内核收走（Java 侧全无痕迹）
    · Kokoro（离线合成）：初始化即无限卡住（不抛异常、界面还正常）
  ⇒ 所以架构上必须默认绕开它们：离线识别走系统识别；离线合成走系统 TTS / 电脑 F5。
    （电脑 F5 那条路是好的：voice.log 里有「成功播放 …（电脑 F5-TTS）」的记录。）

三、改动
  ① OfflineTtsEngine 增加总开关 offlineEnabled(ctx)：**默认停用**，停用时 init() 直接返回 false、
     **根本不构造原生对象**。要试验时在设备上创建 files/tts_offline_enabled.txt 写 1。
  ② 删除遗留诊断函数 diagEmptyConfigOnMain，并从 ChatScreen 移除它的调用
     （它会在进聊天页/点设置时用空配置构造原生对象 ⇒ 卡死主线程）。
  ③ 设置页新增「离线音色（实验）」开关行，明确写出：
       已停用（推荐）—— 本机原生库会卡死；请用系统语音或电脑 F5
  ④ ⑤b 检查项改为走真实路径（选离线音色 + 点一下测试），并按 ready/samples/failed 细分判定。
"""
p = os.path.join(MAP, "_msg_tts_gate.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print()
print("手机仓:", (r.stdout or r.stderr or "").splitlines()[0][:150])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m", "chore(scripts): 离线 TTS 卡死定位脚本"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
