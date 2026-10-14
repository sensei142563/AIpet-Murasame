# -*- coding: utf-8 -*-
"""核查：
  ① 手机端相关（非文档）在 git 里还剩什么
  ② main 与我们"真正不同的"是哪些文件、他们的版本是新的还是旧的（验证"都是旧代码"的说法）
  ③ 网易云音乐插件在不在、怎么用
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(a, timeout=900):
    r = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip()


print("=== ① 手机端相关（非文档）在 git 里还剩什么 ===")
PHONE = re.compile(r"android|apk|gradle|kotlin|\.kt$|\.java$|chatter|mediapipe|vrm|arcore|"
                   r"adb|termux|安卓|手机|hand_?landmark", re.I)
DOC = re.compile(r"\.md$|\.txt$|^docs?/|/docs?/|README", re.I)
files = [f for f in sh(["git", "ls-files"]).split("\n") if f.strip()]
left_nondoc, left_doc = [], []
for f in files:
    if PHONE.search(f):
        (left_doc if DOC.search(f) else left_nondoc).append(f)
print("   ✗ 非文档（按你的要求应当为 0）：%d 个" % len(left_nondoc))
for f in left_nondoc[:40]:
    sz = 0
    try:
        sz = os.path.getsize(os.path.join(ROOT, f.replace("/", os.sep)))
    except OSError:
        pass
    print("      %8.1f KB  %s" % (sz / 1024, f[:92]))
print("   ✓ 文档（允许保留）：%d 个" % len(left_doc))
for f in left_doc[:16]:
    print("      %s" % f[:96])

print()
print("   曾被摘掉的路径现在是否真的不在 git 里：")
for p in ("dev/shots", "dev/three-demo", "dev/vrm_probe", "dev/tts_model_cache",
          "AIpet-Murasame.exe.bak_1604"):
    n = len([x for x in sh(["git", "ls-files", p]).split("\n") if x.strip()])
    print("      %-34s 入库文件 %d 个 %s" % (p, n, "✓" if n == 0 else "✗ 还有"))

print()
print("=== ② main 与我们真正不同的文件（M=双方都改过）===")
ns = sh(["git", "diff", "--name-status", "origin/main", "HEAD"])
mods, adds, dels = [], [], []
for l in ns.split("\n"):
    if not l.strip():
        continue
    parts = l.split("\t")
    if len(parts) < 2:
        continue
    st, f = parts[0], parts[1]
    (mods if st.startswith("M") else adds if st.startswith("A") else dels).append(f)
print("   修改 %d / 新增 %d / 删除 %d" % (len(mods), len(adds), len(dels)))
print()
print("   ── 那 %d 个双方都动过的文件，看谁更新（他们最后一次改 / 我们最后一次改）──" % len(mods))
for f in mods[:22]:
    theirs = sh(["git", "log", "-1", "--format=%ad|%an|%s", "--date=short", "origin/main", "--", f])
    ours = sh(["git", "log", "-1", "--format=%ad|%an|%s", "--date=short", "HEAD", "--", f])
    tp = (theirs.split("|") + ["", "", ""])[:3]
    op = (ours.split("|") + ["", "", ""])[:3]
    print("      %-40s" % f[:40])
    print("         他们 %s %s  %s" % (tp[0], tp[1][:8], tp[2][:46]))
    print("         我们 %s %s  %s" % (op[0], op[1][:8], op[2][:46]))

print()
print("   ── 新增的 %d 个文件里，有多少是 dev/ 下的（我们的工作文档/脚本）──" % len(adds))
from collections import Counter
c = Counter(f.split("/")[0] for f in adds)
for k, v in c.most_common(10):
    print("      %-22s %d 个" % (k, v))

print()
print("=== ③ 网易云音乐插件 ===")
for dp, dn, fn in os.walk(os.path.join(ROOT, "plugins")):
    if "__pycache__" in dp:
        continue
    for f in fn:
        if f == "plugin.json":
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, ROOT)
            try:
                t = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                t = ""
            name = re.search(r'"name"\s*:\s*"([^"]*)"', t)
            en = re.search(r'"enabled"\s*:\s*(\w+)', t)
            print("   %-52s name=%s enabled=%s"
                  % (rel[:52], name.group(1) if name else "?", en.group(1) if en else "?"))
if not os.path.isdir(os.path.join(ROOT, "plugins")):
    print("   （没有 plugins/ 目录，换个位置找）")
    for dp, dn, fn in os.walk(ROOT):
        if any(s in dp for s in (".git", "runtime", "GPT-SoVITS", "dev\\tmp", ".venv",
                                 "__pycache__", "node_modules")):
            continue
        for f in fn:
            if f == "plugin.json":
                print("   " + os.path.relpath(os.path.join(dp, f), ROOT)[:100])
