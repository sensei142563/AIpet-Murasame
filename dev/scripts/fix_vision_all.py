# -*- coding: utf-8 -*-
"""① 确认 config.json 已是 qwen3-vl-plus
   ② config.example.json：vision_model_name → qwen3-vl-plus；本地视觉两项 → 空
   ③ 设置页那两个默认值（widgets.py）→ 空；下拉框去掉已下线的两个
   ④ 端到端：真发一张图给 qwen3-vl-plus 与 qwen3-vl-flash，看能不能识别
"""
import base64
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image, ImageDraw

ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def rd(p):
    return io.open(p, encoding="utf-8", errors="replace").read()


def wr(p, t):
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)


def patch(rel, pairs, label):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        print("   ✗ 缺 %s" % rel)
        return
    t = rd(p)
    n = 0
    for old, new in pairs:
        if old in t:
            t = t.replace(old, new, 1)
            n += 1
    if n:
        wr(p, t)
        print("   ✓ %s：改了 %d 处（%s）" % (rel, n, label))
    else:
        print("   · %s：无需改或已改（%s）" % (rel, label))


print("=== ① config.json ===")
cfgp = os.path.join(ROOT, "config.json")
t = rd(cfgp)
m = re.search(r'"vision_model_name"\s*:\s*"([^"]*)"', t)
print("   当前 vision_model_name = %s" % (m.group(1) if m else "?"))
if m and m.group(1) != "qwen3-vl-plus":
    t = t[:m.start(1)] + "qwen3-vl-plus" + t[m.end(1):]
    wr(cfgp, t)
    print("   ✓ 已改为 qwen3-vl-plus")
else:
    print("   ✓ 已是 qwen3-vl-plus（上一脚本已改）")

print()
print("=== ② config.example.json ===")
patch("config.example.json", [
    ('"vision_model_name": "deepseek-flash"', '"vision_model_name": "qwen3-vl-plus"'),
    ('"vision": "http://127.0.0.1:28460/describe"', '"vision": ""'),
    ('"vision_local_model_dir": "D:\\\\下载\\\\AI桌宠\\\\vision\\\\Qwen2-VL-2B-Instruct"',
     '"vision_local_model_dir": ""'),
], "模型名 + 本地视觉清空")

print()
print("=== ③ 设置页默认值（widgets.py）===")
patch("pcl_launcher/widgets.py", [
    ('"http://127.0.0.1:28460/describe")', '")'),
    ('r"D:\\下载\\AI桌宠\\vision\\Qwen2-VL-2B-Instruct")', '")'),
    ('"qwen3-vl-plus", "qwen3-vl-flash", "qwen-vl-max", "qwen-vl-plus"],',
     '"qwen3-vl-plus", "qwen3-vl-flash"],'),
], "本地视觉默认清空 + 去掉已下线的模型名")
import py_compile  # noqa: E402
try:
    py_compile.compile(os.path.join(ROOT, "pcl_launcher", "widgets.py"), doraise=True)
    print("   ✓ py_compile OK")
except Exception as e:
    print("   ✗ py_compile: %s" % e)

print()
print("=== ④ 端到端：真发一张图 ===")
tmp = os.path.join(ROOT, "dev", "tmp", "vision_probe.png")
os.makedirs(os.path.dirname(tmp), exist_ok=True)
im = Image.new("RGB", (260, 120), (255, 255, 255))
d = ImageDraw.Draw(im)
d.rectangle([8, 8, 250, 110], outline=(200, 0, 0), width=5)
d.text((100, 52), "AIpet", fill=(0, 0, 0))
im.save(tmp)
b64 = base64.b64encode(open(tmp, "rb").read()).decode()
key = ((json.load(open(cfgp, encoding="utf-8", errors="replace")).get("APIKEY") or {})
       .get("qwen") or "").strip()
for model in ("qwen3-vl-plus", "qwen3-vl-flash"):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "图里有什么？一句话。"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}]}],
        "max_tokens": 60}).encode("utf-8")
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            j = json.loads(r.read().decode("utf-8"))
        print("   ✓✓ %-16s 识别成功：%s"
              % (model, j["choices"][0]["message"]["content"].strip()[:90]))
    except urllib.error.HTTPError as e:
        det = ""
        try:
            det = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        mm = re.search(r'"message":"([^"]{0,70})', det)
        print("   ✗ %-16s HTTP %s %s" % (model, e.code, mm.group(1) if mm else ""))
    except Exception as e:
        print("   ✗ %-16s %s: %s" % (model, type(e).__name__, str(e)[:80]))
