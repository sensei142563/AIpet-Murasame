# -*- coding: utf-8 -*-
"""修 deck 第 20 页：① 去掉幻灯片上的字面 ** （引擎不解析 markdown，会直接显示星号）
                     ② 缩短"已经有 人做了（二）"那条，避免换行
   并**全 deck 扫描**其它页有没有同样的字面 **。
"""
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
OUT = os.path.join(ROOT, "dev", "ppt", "outline.json")

o = json.loads(io.open(OUT, encoding="utf-8", errors="replace").read())
slides = o["slides"]

# ---------- ① 全 deck 扫描字面 ** ----------
print("=== 扫描：哪些页的字面文本里含 ** ===")
bad = []
for i, s in enumerate(slides, 1):
    def walk(v, path=""):
        if isinstance(v, str):
            if "**" in v:
                bad.append((i, path, v[:70]))
        elif isinstance(v, list):
            for k, x in enumerate(v):
                walk(x, "%s[%d]" % (path, k))
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, "%s.%s" % (path, k))
    walk({k: v for k, v in s.items() if k != "type"}, "")
for i, p, v in bad:
    print("   第 %2d 页 %-16s %s" % (i, p, v))
if not bad:
    print("   （无）")

# ---------- ② 清掉字面 **（仅幻灯片可见字段）----------
CLEAN_KEYS = {"title", "subtitle", "text", "by", "left_title", "right_title", "num"}
def clean(v):
    if isinstance(v, str):
        return v.replace("**", "")
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    return v

changed = 0
for s in slides:
    for k in list(s.keys()):
        if k in CLEAN_KEYS or k in ("bullets", "left", "right"):
            before = json.dumps(s[k], ensure_ascii=False)
            s[k] = clean(s[k])
            if json.dumps(s[k], ensure_ascii=False) != before:
                changed += 1
print()
print("=== 已清理 %d 处（去掉幻灯片上的字面 **）===" % changed)

# ---------- ③ 缩短第 20 页那条 ----------
for s in slides:
    if s.get("title", "").startswith("中期：另一条感知路线"):
        for b in s["bullets"]:
            if b.get("text", "").startswith("但已经有人做了（二）"):
                b["sub"] = "文心守护：60GHz 雷达 + 大模型，明说做「情感陪伴」与「存在即感知」，面向独居老人看护（开源）"
        print("✓ 第 20 页第 3 条已缩短")
        break

json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)

# ---------- ④ 重建 + 渲染 ----------
print()
print("=== 重建 + 渲染 ===")
env = dict(os.environ, PYTHONIOENCODING="utf-8")
r = subprocess.run([sys.executable, r"E:\Codex\workflows\ppt\scripts\build_deck.py",
                    "--outline", "dev\\ppt\\outline.json", "--out", "dev\\ppt\\out\\Deck.pptx",
                    "--theme", "dev\\ppt\\theme-murasame.json"],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env, timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "已生成" in l:
        print("   " + l.strip()[:90])
r = subprocess.run([sys.executable, os.path.join(ROOT, "dev", "scripts", "ppt_add_notes.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env, timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "缺备注" in l or "已写入备注" in l:
        print("   " + l.strip()[:90])
r = subprocess.run(["powershell", "-NoProfile", "-File",
                    r"E:\Codex\workflows\ppt\scripts\render_qc.ps1",
                    "-Deck", os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:90])
