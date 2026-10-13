# -*- coding: utf-8 -*-
"""真启动一次语音服务（经外壳），验证：
  ① 窗口标题 ② 控制台只剩横幅 ③ 日志里有 api.py 的输出 ④ /T 收掉后**不留孤儿**
"""
import io
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
GSV = os.path.join(ROOT, "GPT-SoVITS")
PY = os.path.join(GSV, "runtime", "python.exe")
WRAP = os.path.join(ROOT, "tool", "tts_console.py")
LOG = os.path.join(ROOT, "data", "tts_service.log")


def procs():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                        "ForEach-Object { $_.ProcessId.ToString() + '|' + $_.CommandLine }"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=180)
    out = []
    for l in (r.stdout or "").split("\n"):
        l = l.strip()
        if l and "|" in l:
            out.append(l)
    return out


print("=== ① 启动前：python 进程 ===")
for l in procs():
    print("   ", l[:110])

# 配置（与 run.py 会写的同构）
io.open(os.path.join(ROOT, "data", "tts_console.json"), "w", encoding="utf-8",
        newline="\n").write(json.dumps({
            "title": "AIpet 语音服务 · 丛雨（GPT-SoVITS 9880）",
            "log": LOG,
            "lines": [
                "AIpet 语音服务 · 丛雨",
                "GPT-SoVITS  ·  服务端口 9880  ·  模型：murasame-gpt.ckpt / murasame-sovits.pth",
                "详细日志写在 data\\tts_service.log（本窗口故意保持安静）",
                "关闭本窗口 = 停止语音服务；不需要语音时可在设置里关掉「短语音」。",
            ],
        }, ensure_ascii=False, indent=1))

if os.path.isfile(LOG):
    try:
        os.remove(LOG)
    except Exception:
        pass

print()
print("=== ② 经外壳启动真实 api.py（新控制台）===")
flags = 0x00000010 | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000)
p = subprocess.Popen([PY, WRAP, os.path.join(ROOT, "data", "tts_console.json"), "--",
                      "api.py",
                      "-s", "SoVITS_weights/murasame-sovits.pth",
                      "-g", "GPT_weights/murasame-gpt.ckpt"],
                     cwd=GSV, creationflags=flags)
print("   外壳 PID =", p.pid)

print("   等待 20 秒（api.py 在这期间往日志里刷启动信息）…")
time.sleep(20)

print()
print("=== ③ 进程树（外壳 + api.py）===")
for l in procs():
    print("   ", l[:118])

print()
print("=== ④ 日志文件（服务本体的输出应该都在这儿）===")
if os.path.isfile(LOG):
    txt = io.open(LOG, encoding="utf-8", errors="replace").read()
    ls = [x for x in txt.split("\n") if x.strip()]
    print("   共 %d 行 / %d 字节；头 3 行与末 3 行：" % (len(ls), os.path.getsize(LOG)))
    for x in ls[:3] + ["   …"] + ls[-3:]:
        print("   >", x[:112])
else:
    print("   ✗ 没有日志")

print()
print("=== ⑤ 截桌面（看那个窗口长什么样）===")
shot = subprocess.run(["powershell", "-NoProfile", "-Command",
                       "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
                       "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
                       "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
                       "$g=[System.Drawing.Graphics]::FromImage($bmp);"
                       "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
                       "$out=Join-Path $env:TEMP 'tts_console_shot.png';"
                       "$bmp.Save($out,[System.Drawing.Imaging.ImageFormat]::Png);"
                       "Write-Output $out"],
                      capture_output=True, text=True, encoding="utf-8", errors="replace",
                      timeout=300)
path = (shot.stdout or "").strip().split("\n")[-1].strip()
print("   截图:", path or "（失败）")

print()
print("=== ⑥ 收工：taskkill /T /F 外壳，再查残留 ===")
subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
time.sleep(4)
left = procs()
print("   残留 python 进程：%d 个" % len(left))
for l in left:
    print("   !", l[:118])
print("   ⇒", "干净 ✓（没有孤儿）" if not left else "仍有残留 ✗")

print()
print("=== ⑦ 9880 端口 ===")
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "(Get-NetTCPConnection -LocalPort 9880 -State Listen -ErrorAction "
                    "SilentlyContinue | Measure-Object).Count"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
print("   监听数:", (r.stdout or "").strip())
