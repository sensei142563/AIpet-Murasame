# -*- coding: utf-8 -*-
"""① 修 classes/murasame_class.py 的 `[:_14]` 打字错误（应为 [:14]）
   ② 用主人的 key 实测哪些视觉模型名能用（只发最小请求；key 打码）
   ③ 给"看屏幕"加每轮硬上限（治无限刷屏）
"""
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

print("=== ① 修 _14 打字错误 ===")
p = os.path.join(ROOT, "classes", "murasame_class.py")
t = io.open(p, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD1 = "                    _kind = _t[:_14]"
NEW1 = "                    _kind = _t[:14]          # ★ 2026-10-14 修：原为 [:_14]（打字错误，\n                    #   Python 把 _14 当变量名 → NameError → 整段队列去重被 except 吞掉）"
OLD2 = "                            if str(_q[_i][0])[:_14] == _kind:"
NEW2 = "                            if str(_q[_i][0])[:14] == _kind:      # ★ 同上：[:14]"
n1 = 0
if OLD1 in t:
    t = t.replace(OLD1, NEW1, 1)
    n1 += 1
if OLD2 in t:
    t = t.replace(OLD2, NEW2, 1)
    n1 += 1
if n1:
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("   ✓ 修了 %d 处" % n1)
else:
    print("   （没匹配到，可能已改）")
import py_compile  # noqa: E402
try:
    py_compile.compile(p, doraise=True)
    print("   ✓ py_compile OK")
except Exception as e:
    print("   ✗ py_compile: %s" % e)
    sys.exit(1)

print()
print("=== ② 实测视觉模型名（用配置里的 key）===")
cfg = json.load(io.open(os.path.join(ROOT, "config.json"), encoding="utf-8",
                        errors="replace"))
key = ((cfg.get("APIKEY") or {}).get("qwen") or "").strip()
print("   key: %s…%s（长度 %d）" % (key[:6], key[-4:], len(key)))
URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
CANDS = ["qwen-vl-plus", "qwen-vl-max", "qwen-vl-plus-latest", "qwen-vl-max-latest",
         "qwen2.5-vl-7b-instruct", "qwen2.5-vl-72b-instruct", "qwen-vl-chat-v1",
         "qwen-plus"]
for m in CANDS:
    body = json.dumps({"model": m, "messages": [{"role": "user", "content": "hi"}],
                       "max_tokens": 1}).encode("utf-8")
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            print("   ✓ %-26s HTTP %s" % (m, r.status))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:150]
        except Exception:
            pass
        short = re.search(r'"message":"([^"]{0,80})', detail)
        print("   ✗ %-26s HTTP %s  %s" % (m, e.code, (short.group(1) if short else detail[:80])))
    except Exception as e:
        print("   ? %-26s %s: %s" % (m, type(e).__name__, str(e)[:80]))
