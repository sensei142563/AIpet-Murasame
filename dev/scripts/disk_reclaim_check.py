# -*- coding: utf-8 -*-
"""回收清单前置核实：
  ① 代码到底用 F5-TTS 的哪一套权重（4 套里能不能只留 1 套）
  ② .venv（第二套 venv）有没有被任何代码/脚本引用
  ③ 明确是垃圾的：dev/tmp、build、__pycache__、_import_tmp、*.log 体积
  ④ .git 有多大、能不能安全 gc
  ⑤ 顺带把 deck 定稿（Deck_24.pptx → Deck.pptx），并重挂讲稿
"""
import io
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SKIP = re.compile(r"\\(runtime|\.venv|GPT-SoVITS|F5-TTS_Models|models|_internal|build|"
                  r"NapCat\.Shell\.Windows\.OneKey|\.git|_import_tmp|__pycache__)\\", re.I)


def gb(n):
    return n / (1024 ** 3)


print("=== ① F5-TTS 用的哪一套（代码里怎么找模型）===")
pat = re.compile(r"F5TTS_v1_Base|F5TTS_Base_bigvgan|F5TTS_Base|no_zero_init|F5-TTS_Models")
for dp, dn, fn in os.walk(ROOT):
    if SKIP.search(dp + "\\"):
        continue
    for f in fn:
        if not f.endswith((".py", ".json")):
            continue
        p = os.path.join(dp, f)
        try:
            ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        for i, l in enumerate(ls, 1):
            if pat.search(l):
                print("   %-40s %5d| %s" % (p.replace(ROOT + os.sep, "")[:40], i, l.strip()[:92]))

print()
print("=== ② 第二套 venv（.venv）有没有被引用 ===")
hits = 0
for dp, dn, fn in os.walk(ROOT):
    if SKIP.search(dp + "\\"):
        continue
    for f in fn:
        if not f.endswith((".py", ".bat", ".json", ".md", ".ps1")):
            continue
        p = os.path.join(dp, f)
        try:
            t = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for m in re.finditer(r"[^\n]{0,60}\.venv[^\n]{0,40}", t):
            s = m.group(0).strip()
            if "runtime\\.venv" in s or "runtime/.venv" in s:
                continue
            print("   %-38s | %s" % (p.replace(ROOT + os.sep, "")[:38], s[:96]))
            hits += 1
            if hits > 14:
                break
        if hits > 14:
            break
    if hits > 14:
        break
if not hits:
    print("   （项目代码里没有引用 .venv）")

print()
print("=== ③ 明确是垃圾/可重建的 ===")
JUNK = ["dev\\tmp", "build", "dist", "_import_tmp", ".pytest_cache", "tmp",
        "dev\\tts_model_cache"]
for rel in JUNK:
    p = os.path.join(ROOT, rel)
    if os.path.isdir(p):
        tot = 0
        for dp, dn, fn in os.walk(p):
            for f in fn:
                try:
                    tot += os.path.getsize(os.path.join(dp, f))
                except OSError:
                    pass
        print("   %-24s %8.2f GB" % (rel, gb(tot)))
pyc = 0
npcy = 0
for dp, dn, fn in os.walk(ROOT):
    if "__pycache__" in dp:
        npcy += 1
        for f in fn:
            try:
                pyc += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
print("   __pycache__              %8.2f GB （%d 个目录）" % (gb(pyc), npcy))

print()
print("=== ④ NapCat 里的安装包 / 大文件 ===")
nc = os.path.join(ROOT, "NapCat.Shell.Windows.OneKey")
if os.path.isdir(nc):
    for dp, dn, fn in os.walk(nc):
        for f in fn:
            p = os.path.join(dp, f)
            try:
                s = os.path.getsize(p)
            except OSError:
                continue
            if s > 80 * 1024 * 1024:
                print("   %8.2f GB  %s" % (gb(s), p.replace(ROOT + os.sep, "")[:100]))

print()
print("=== ⑤ .git 体积与可回收 ===")
g = os.path.join(ROOT, ".git")
if os.path.isdir(g):
    tot = 0
    for dp, dn, fn in os.walk(g):
        for f in fn:
            try:
                tot += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    print("   .git = %.2f GB" % gb(tot))
    r = subprocess.run(["git", "-C", ROOT, "count-objects", "-vH"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    for l in (r.stdout or "").split("\n"):
        if l.strip():
            print("      " + l.strip())

print()
print("=== ⑥ deck 定稿：Deck_24.pptx → Deck.pptx ===")
src = os.path.join(ROOT, "dev", "ppt", "out", "Deck_24.pptx")
dst = os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx")
if os.path.isfile(src):
    try:
        shutil.copy2(src, dst)          # 覆盖（WPS 已关）
        os.remove(src)
        print("   ✓ 已定稿：Deck.pptx（24 页）")
    except Exception as e:
        print("   ✗ 失败（可能 WPS 还开着？）：%s" % e)
else:
    print("   · 没有 Deck_24.pptx（可能已定稿过）")
