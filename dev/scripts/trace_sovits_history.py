# -*- coding: utf-8 -*-
"""翻日志与 bat，回答"以前的 GPT-SoVITS 终端为什么不一样"：
  ① data 下所有日志里关于"启动 TTS 服务 / api.py / api_v2.py / 新控制台 / 纯净"的记录
  ② 启动桌宠.bat / 启动启动器.bat 到底怎么起的（有没有设 quiet_mode / 传参）
  ③ config.json 的 tts_type / quiet_mode（决定短文本走 GPT-SoVITS 还是长文本走 F5-TTS）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

print("=== ① 日志里的 TTS 启动记录（按时间倒序，取最近 30 条）===")
pat = re.compile(r"api_v2\.py|api\.py|启动 TTS 服务|新控制台|纯净|quiet|9880|9881|F5-TTS")
rows = []
for dp, dn, fn in os.walk(os.path.join(ROOT, "data")):
    for f in fn:
        if not f.lower().endswith((".log", ".txt")):
            continue
        p = os.path.join(dp, f)
        try:
            for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace"), 1):
                if pat.search(l):
                    rows.append((os.path.getmtime(p), f, i, l.strip()[:120]))
        except Exception:
            pass
rows.sort(key=lambda r: r[0], reverse=True)
for _, f, i, l in rows[:30]:
    print("   %-22s %5d| %s" % (f, i, l))
if not rows:
    print("   （没有任何相关记录）")

print()
print("=== ② 两个 bat 的内容 ===")
for b in ("启动桌宠.bat", "启动启动器.bat"):
    p = os.path.join(ROOT, b)
    print("   --- %s ---" % b)
    if os.path.isfile(p):
        for l in io.open(p, encoding="utf-8", errors="replace").read().split("\n")[:14]:
            if l.strip():
                print("      " + l.rstrip()[:112])
    else:
        print("      ✗ 不存在")

print()
print("=== ③ config.json 关键项 ===")
import json  # noqa: E402
c = json.load(io.open(os.path.join(ROOT, "config.json"), encoding="utf-8", errors="replace"))
for k in ("tts_type", "longtext_tts_type", "longtext_enabled", "quiet_mode",
          "gpt_sovits_version", "sovits_version", "tts_version"):
    if k in c:
        print("   %-22s = %r" % (k, c[k]))
print("   （没有的键就是没配，走默认）")
