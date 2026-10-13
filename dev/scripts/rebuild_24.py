# -*- coding: utf-8 -*-
"""① 清掉幻灯片可见字段里的字面 **（新页我写了 `**没有一类把…**`）
   ② 重建 + 挂讲稿 + 渲染（deck 现在 24 页）
"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
OUT = os.path.join(ROOT, "dev", "ppt", "outline.json")

o = json.loads(io.open(OUT, encoding="utf-8", errors="replace").read())
CLEAN = {"title", "subtitle", "text", "by", "left_title", "right_title", "num"}


def clean(v):
    if isinstance(v, str):
        return v.replace("**", "")
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    return v


found = 0
for i, s in enumerate(o["slides"], 1):
    for k in list(s.keys()):
        if k in CLEAN or k in ("bullets", "left", "right"):
            before = json.dumps(s[k], ensure_ascii=False)
            s[k] = clean(s[k])
            if json.dumps(s[k], ensure_ascii=False) != before:
                print("   第 %d 页 %s：清掉字面 **" % (i, k))
                found += 1
json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)
print("✓ ① 共清理 %d 处；deck 页数 %d" % (found, len(o["slides"])))

print()
print("=== ② 重建 + 挂讲稿 + 渲染 ===")
env = dict(os.environ, PYTHONIOENCODING="utf-8")
r = subprocess.run([sys.executable, r"E:\Codex\workflows\ppt\scripts\build_deck.py",
                    "--outline", "dev\\ppt\\outline.json", "--out", "dev\\ppt\\out\\Deck.pptx",
                    "--theme", "dev\\ppt\\theme-murasame.json"],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env, timeout=1200)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "已生成" in l:
        print("   " + l.strip()[:92])
r = subprocess.run([sys.executable, os.path.join(ROOT, "dev", "scripts", "ppt_add_notes.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env, timeout=1200)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "缺备注" in l or "已写入备注" in l:
        print("   " + l.strip()[:92])
r = subprocess.run(["powershell", "-NoProfile", "-File",
                    r"E:\Codex\workflows\ppt\scripts\render_qc.ps1",
                    "-Deck", os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=2400)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:92])

print()
print("=== ③ 复核：pptx 里还有没有字面 ** ===")
check = subprocess.run([sys.executable, "-c",
                        "from pptx import Presentation\n"
                        "p=Presentation(r'dev/ppt/out/Deck.pptx')\n"
                        "bad=[]\n"
                        "for i,s in enumerate(p.slides,1):\n"
                        "    for sh in s.shapes:\n"
                        "        if sh.has_text_frame and '**' in sh.text_frame.text:\n"
                        "            bad.append(i)\n"
                        "print('   含 ** 的页:', bad or '无 ✓')\n"
                        "print('   总页数:', len(p.slides.__iter__.__self__._sldIdLst))\n"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=600)
print((check.stdout or "") + (check.stderr or ""))
