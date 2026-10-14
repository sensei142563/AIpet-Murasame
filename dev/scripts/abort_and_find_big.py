# -*- coding: utf-8 -*-
"""① 立刻放弃合并、回到干净状态（并核对安全标签）
   ② 查清 126MB 大文件的来历：什么时候进的、还有没有别的超大文件、.git 多大
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(args, timeout=900):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode


print("=== ① 放弃合并、回到干净状态 ===")
print("   " + (sh(["git", "merge", "--abort"])[0] or "(已放弃合并)")[:100])
cur, _ = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])
print("   当前分支 = %s" % cur)
head, _ = sh(["git", "log", "-1", "--format=%h %s"])
print("   HEAD = %s" % head[:100])
print("   合并残留 = %s" % ("有 ✗" if os.path.exists(os.path.join(ROOT, ".git", "MERGE_HEAD"))
                            else "无 ✓"))
tagc, _ = sh(["git", "rev-list", "-n", "1", "preB-20261014"])
print("   安全标签 preB-20261014 → %s（应等于 HEAD）" % tagc[:12])
st, _ = sh(["git", "status", "--porcelain"])
print("   工作区改动 %d 项" % len([l for l in st.split("\n") if l.strip()]))

print()
print("=== ② 那个 126MB 文件什么时候进的仓库 ===")
BIG = "dev/tts_model_cache/kokoro-int8-multi-lang-v1_0.tar.bz2"
out, _ = sh(["git", "log", "--oneline", "--diff-filter=A", "--date=short",
             "--format=%h %ad %an %s", "--", BIG])
for l in out.split("\n")[:6]:
    if l.strip():
        print("   首次加入：" + l.strip()[:120])
if not out.strip():
    print("   （该路径没有被 add 过？再查整个目录）")
    out2, _ = sh(["git", "log", "--oneline", "--diff-filter=A", "--date=short",
                  "--format=%h %ad %an %s", "--", "dev/tts_model_cache"])
    for l in out2.split("\n")[:6]:
        if l.strip():
            print("   dev/tts_model_cache 首次加入：" + l.strip()[:120])

print()
print("   该路径现在的提交历史（最近 5 条）：")
out3, _ = sh(["git", "log", "--oneline", "-5", "--format=%h %ad %an %s", "--date=short",
              "--", "dev/tts_model_cache"])
for l in out3.split("\n")[:6]:
    if l.strip():
        print("      " + l.strip()[:118])

print()
print("=== ③ 工作区里还有哪些超大文件（>40MB）===")
BIGDIRS = (".git", "GPT-SoVITS", "F5-TTS_Models", "runtime", ".venv", "models",
           "_internal", "NapCat", "three-demo")
n = 0
for dp, dn, fn in os.walk(ROOT):
    if any(os.sep + s in dp + os.sep for s in BIGDIRS):
        continue
    for f in fn:
        p = os.path.join(dp, f)
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        if sz > 40 * 1048576:
            rel = os.path.relpath(p, ROOT)
            tracked, _ = sh(["git", "ls-files", "--error-unmatch", rel])
            print("   %7.1f MB  %-58s %s" % (sz / 1048576, rel[:58],
                                             "已入库 ✗" if tracked else "未入库 ✓"))
            n += 1
            if n > 20:
                break
    if n > 20:
        break
if n == 0:
    print("   （没有）")

print()
print("=== ④ 仓库体积 ===")
for name, cmd in ((".git 目录", None),):
    d = os.path.join(ROOT, ".git")
    tot = 0
    for dp, dn, fn in os.walk(d):
        for f in fn:
            try:
                tot += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    print("   .git = %.2f GB" % (tot / 1073741824))
