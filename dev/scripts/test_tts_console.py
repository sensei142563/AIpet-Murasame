# -*- coding: utf-8 -*-
"""测 tool/tts_console.py：
  ① 用**项目 venv 的 python** 跑一次（假命令）⇒ 看横幅、看日志、看退出码
  ② 用 **GPT-SoVITS 自带的 python** 跑一次 ⇐ **关键风险**：那个是便携 Python，能不能跑我的脚本
"""
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
WRAP = os.path.join(ROOT, "tool", "tts_console.py")
LOG = os.path.join(ROOT, "data", "tts_service.log")
CFG = os.path.join(ROOT, "data", "tts_console.json")

# 写一份测试用配置（内容与 run.py 会写的同构）
io.open(CFG, "w", encoding="utf-8", newline="\n").write(json.dumps({
    "title": "AIpet 语音服务 · 丛雨（GPT-SoVITS 9880）",
    "log": LOG,
    "lines": [
        "AIpet 语音服务 · 丛雨",
        "GPT-SoVITS  ·  服务端口 9880  ·  模型：murasame-gpt.ckpt / murasame-sovits.pth",
        "详细日志写在 data\\tts_service.log（本窗口故意保持安静）",
        "关闭本窗口 = 停止语音服务；不需要语音时可在设置里关掉「短语音」。",
    ],
}, ensure_ascii=False, indent=1))

FAKE = [sys.executable, "-c",
        "import sys;print('CHILD-OUT 这行应该只出现在日志里');"
        "sys.stderr.write('CHILD-ERR 这行也只该在日志里\\n')"]

PYS = [
    ("项目 venv 的 python", os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")),
    ("GPT-SoVITS 自带 python", os.path.join(ROOT, "GPT-SoVITS", "runtime", "python.exe")),
]

for tag, py in PYS:
    print("=" * 72)
    print("=== %s ===" % tag)
    print("   ", py)
    if not os.path.isfile(py):
        print("    ✗ 不存在，跳过")
        continue
    # 清掉日志，便于判断是不是这次写的
    try:
        if os.path.isfile(LOG):
            os.remove(LOG)
    except Exception as e:
        print("    ⚠ 删旧日志失败:", e)

    r = subprocess.run([py, WRAP, CFG, "--"] + FAKE,
                       cwd=os.path.join(ROOT, "GPT-SoVITS"),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=180)
    print("    退出码:", r.returncode)
    print("    ---- 控制台输出（这就是窗口里会看到的东西）----")
    for l in (r.stdout or "").split("\n"):
        if l.strip() or l == "":
            print("    | " + l[:104])
    if (r.stderr or "").strip():
        print("    ---- stderr ----")
        for l in (r.stderr or "").split("\n")[:6]:
            print("    ! " + l[:104])
    print("    ---- 日志文件 ----")
    if os.path.isfile(LOG):
        txt = io.open(LOG, encoding="utf-8", errors="replace").read()
        for l in txt.split("\n"):
            if l.strip():
                print("    > " + l[:104])
        print("    （%d 字节）" % os.path.getsize(LOG))
    else:
        print("    ✗ 日志没生成")
    print()
