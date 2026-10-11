# -*- coding: utf-8 -*-
"""查 sherpa-onnx 官方 Release 里的离线 TTS 模型资产（找 Kokoro int8 打包：含 espeak-ng-data 的那种）。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (aipet-tts)"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


print("=== sherpa-onnx releases（找 tts-models）===")
try:
    rels = get("https://api.github.com/repos/k2-fsa/sherpa-onnx/releases?per_page=30")
    for r in rels[:12]:
        print("   %-28s assets=%d" % (r.get("tag_name"), len(r.get("assets") or [])))
except Exception as e:
    print("   ✗ releases 查询失败:", str(e)[:120])

print()
print("=== tts-models release 里的 Kokoro / VITS 资产 ===")
for tag in ("tts-models", "asr-models"):
    try:
        rel = get("https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/tags/%s" % tag)
    except Exception as e:
        print("   %s ✗ %s" % (tag, str(e)[:80]))
        continue
    assets = rel.get("assets") or []
    print("   [%s] 共 %d 个资产" % (tag, len(assets)))
    hit = [a for a in assets if any(k in a["name"].lower() for k in
                                    ("kokoro", "vits-zh", "aishell", "espeak"))]
    for a in hit[:25]:
        print("      %-58s %7.1f MB" % (a["name"], (a.get("size") or 0) / 1e6))
    if not hit:
        print("      （无匹配，列前 10 个看看）")
        for a in assets[:10]:
            print("      %-58s %7.1f MB" % (a["name"], (a.get("size") or 0) / 1e6))
