# -*- coding: utf-8 -*-
"""用主人的 key 实测一批（含新名字 qwen3-vl-plus 等），找出真正可用的视觉模型名。"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8", errors="replace"))
key = ((cfg.get("APIKEY") or {}).get("qwen") or "").strip()
URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

CANDS = [
    "qwen3-vl-plus",            # ← 公告里提到的新名字
    "qwen3-vl-max",
    "qwen3-vl-235b-a22b-instruct",
    "qwen3-vl-30b-a3b-instruct",
    "qwen-vl-plus",
    "qwen-vl-max",
    "qwen2.5-vl-7b-instruct",
    "qwen2.5-vl-32b-instruct",
    "qwen-plus",                 # 对照：已知可用
]
print("=== 实测视觉模型名（key %s…%s）===" % (key[:6], key[-4:]))
good = []
for m in CANDS:
    body = json.dumps({"model": m, "messages": [{"role": "user", "content": "hi"}],
                       "max_tokens": 1}).encode("utf-8")
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            print("   ✓ %-34s HTTP %s" % (m, r.status))
            good.append(m)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        mm = re.search(r'"message":"([^"]{0,90})', detail)
        print("   ✗ %-34s HTTP %s  %s" % (m, e.code, mm.group(1) if mm else detail[:70]))
    except Exception as e:
        print("   ? %-34s %s: %s" % (m, type(e).__name__, str(e)[:70]))

print()
print("=== 可用的 ===")
for m in good:
    print("   " + m)
if not good:
    print("   ✗ 一个都没通 —— 那就确实是账号/开通问题")
