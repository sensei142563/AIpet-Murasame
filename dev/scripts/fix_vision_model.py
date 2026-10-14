# -*- coding: utf-8 -*-
"""① config.json / config.example.json / 代码默认值里的 vision_model_name → qwen3-vl-plus
   ② 本地视觉那两项（28460 地址 + D:\\下载\\... 目录）默认清空
   ③ 端到端验证：真发一张小图给 qwen3-vl-plus，确认能识别
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

print("=== ① 先找出所有写出旧模型名/本地视觉默认值的地方 ===")
PAT = re.compile(r"qwen-vl-plus|qwen-vl-max|28460|Qwen2-VL|下载\\\\AI桌宠|vision_local_url|"
                 r"vision_local_command|vision_model_name")
SKIP = (".git", "runtime", "GPT-SoVITS", "F5-TTS_Models", "\\models", "dev\\tmp", ".venv",
        "__pycache__", "NapCat", "dev\\scripts", "dev\\docs", "dev\\merge-map")
hits = []
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp for s in SKIP):
        continue
    for f in fn:
        if not f.endswith((".py", ".json", ".md", ".bat")):
            continue
        p = os.path.join(dp, f)
        try:
            t = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for i, l in enumerate(t.split("\n"), 1):
            if PAT.search(l) and not l.strip().startswith("#"):
                hits.append((os.path.relpath(p, ROOT), i, l.strip()))
for rel, i, l in hits[:40]:
    print("   %-38s %5d| %s" % (rel[:38], i, l[:96]))
print("   （共 %d 处）" % len(hits))

print()
print("=== ② 改 config.json（最小改动：只替换那一个值）===")
cfgp = os.path.join(ROOT, "config.json")
t = io.open(cfgp, encoding="utf-8", errors="replace").read()
old = '"vision_model_name": "qwen-vl-plus"'
new = '"vision_model_name": "qwen3-vl-plus"'
if old in t:
    t = t.replace(old, new, 1)
    io.open(cfgp, "w", encoding="utf-8", newline="\n").write(t)
    print("   ✓ config.json: qwen-vl-plus → qwen3-vl-plus")
else:
    m = re.search(r'"vision_model_name"\s*:\s*"([^"]*)"', t)
    print("   · 当前值 = %s" % (m.group(1) if m else "(找不到)"))
    if m and m.group(1) != "qwen3-vl-plus":
        t = t[:m.start(1)] + "qwen3-vl-plus" + t[m.end(1):]
        io.open(cfgp, "w", encoding="utf-8", newline="\n").write(t)
        print("   ✓ 已改为 qwen3-vl-plus")

print()
print("=== ③ 端到端验证：真发一张图给 qwen3-vl-plus ===")
try:
    import base64
    import urllib.request
    from PIL import Image, ImageDraw
    tmp = os.path.join(ROOT, "dev", "tmp", "vision_probe.png")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    im = Image.new("RGB", (240, 120), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([10, 10, 230, 110], outline=(200, 0, 0), width=4)
    d.text((70, 55), "AIpet", fill=(0, 0, 0))
    im.save(tmp)
    b64 = base64.b64encode(open(tmp, "rb").read()).decode()
    cfg = json.load(open(cfgp, encoding="utf-8", errors="replace"))
    key = ((cfg.get("APIKEY") or {}).get("qwen") or "").strip()
    body = json.dumps({
        "model": "qwen3-vl-plus",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "这张图里有什么？一句话。"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}]}],
        "max_tokens": 60}).encode("utf-8")
    req = urllib.request.Request(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        data=body, method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        j = json.loads(r.read().decode("utf-8"))
    print("   ✓✓ 视觉识别成功！她看到的：%s"
          % j["choices"][0]["message"]["content"].strip()[:110])
except Exception as e:
    print("   ✗ %s: %s" % (type(e).__name__, str(e)[:200]))
