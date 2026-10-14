# -*- coding: utf-8 -*-
"""历史改写：把"仅本地/手机端素材/模型缓存"从**所有历史提交**里剔除。
   保底：① filter-branch 自动保留 refs/original/* ✓ ② 已打标签 preB-20261014 ✓
   只改写当前分支（HEAD），不动其它分支与远端。
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

PATHS = [
    "dev/shots", "dev/three-demo", "dev/vrm_probe", "dev/screenshots",
    "dev/tts_model_cache", "dev/tmp",
    "AIpet-Murasame.exe.bak_1604",
]
# 手机端一次性脚本（ar_* / vrm_* / hand_* / phone* / make_handover）
out = subprocess.run(["git", "ls-files", "dev/scripts"], cwd=ROOT, capture_output=True,
                     text=True, encoding="utf-8", errors="replace").stdout
for f in out.split("\n"):
    f = f.strip()
    if f and os.path.basename(f).lower().endswith(".py") and re.search(
            r"(ar_|vrm_|hand_|phone|make_handover)", os.path.basename(f).lower()):
        PATHS.append(f)

flt = "git rm -r --cached --ignore-unmatch " + " ".join("'%s'" % p for p in PATHS)
print("=== 将要从历史里剔除的路径（%d 条）===" % len(PATHS))
for p in PATHS[:12]:
    print("   " + p)
print("   …（共 %d 条）" % len(PATHS))
print()
print("=== 开跑 filter-branch（只改 HEAD 这条线）===")
env = dict(os.environ, FILTER_BRANCH_SQUELCH_WARNING="1")
t0 = __import__("time").time()
r = subprocess.run(["git", "filter-branch", "-f", "--index-filter", flt, "--", "HEAD"],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env, timeout=7200)
dt = __import__("time").time() - t0
print("   耗时 %.1f 分钟，退出码 %d" % (dt / 60, r.returncode))
tail = ((r.stderr or "") + (r.stdout or "")).strip().split("\n")[-8:]
for l in tail:
    if l.strip():
        print("   " + l.strip()[:130])
print()
print("=== 改写后核对 ===")
def sh(a):
    x = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return ((x.stdout or "") + (x.stderr or "")).strip()
print("   HEAD = %s" % sh(["git", "log", "-1", "--format=%h %s"])[:110])
print("   提交数 = %s" % sh(["git", "rev-list", "--count", "HEAD"]))
print("   保底 refs/original = %s" % (sh(["git", "for-each-ref", "--format=%(refname)",
                                            "refs/original"]) or "（无）")[:120])
print("   安全标签 preB-20261014 仍在 = %s" % sh(["git", "rev-list", "-n", "1",
                                                 "preB-20261014"])[:12])
print("   历史里还有那个 126MB 文件吗：%s"
      % ("✗ 还有" if "tts_model_cache" in sh(["git", "log", "--all", "--name-only",
                                              "--format=", "-1", "HEAD"]) else "✓ 已从 HEAD 历史剔除"))
