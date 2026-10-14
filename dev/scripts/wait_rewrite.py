# -*- coding: utf-8 -*-
"""等历史改写结束，然后做核对（供后台运行）。"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
LOG = os.path.join(ROOT, "dev", "tmp_rewrite.log")


def sh(a, timeout=900):
    r = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip()


print("=== 等待 filter-branch 结束（最多 40 分钟）===")
t0 = time.time()
last_size = -1
while time.time() - t0 < 2400:
    # 进程还在吗
    alive = False
    try:
        out = subprocess.run(["tasklist", "/FI", "PID eq 33528"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=60).stdout
        alive = "33528" in out
    except Exception:
        pass
    try:
        sz = os.path.getsize(LOG)
    except OSError:
        sz = 0
    if not alive:
        print("   进程已结束（等待 %.1f 分钟）" % ((time.time() - t0) / 60))
        break
    if sz != last_size:
        last_size = sz
    time.sleep(15)
else:
    print("   ⚠ 等待超时，但它可能仍在跑")

time.sleep(3)
print()
print("=== 改写日志尾部 ===")
try:
    ls = io.open(LOG, encoding="utf-8", errors="replace").read().split("\n")
    for l in [x for x in ls if x.strip()][-12:]:
        print("   " + l.strip()[:130])
except Exception as e:
    print("   （读不到日志：%s）" % e)

print()
print("=== 核对 ===")
print("   HEAD = %s" % sh(["git", "log", "-1", "--format=%h %s"])[:110])
print("   提交数 = %s" % sh(["git", "rev-list", "--count", "HEAD"]))
print("   保底 refs/original：%s" % (sh(["git", "for-each-ref", "--format=%(refname)",
                                          "refs/original"]) or "（无）")[:140])
print("   安全标签 preB-20261014 = %s" % sh(["git", "rev-list", "-n", "1",
                                             "preB-20261014"])[:12])

print()
print("   历史里是否还有那些大路径（逐条查 HEAD 全历史）:")
for p in ("dev/tts_model_cache", "dev/shots", "dev/three-demo", "dev/vrm_probe"):
    o = sh(["git", "log", "--all", "--oneline", "--format=%h", "-1", "--", p])
    print("      %-24s %s" % (p, ("✗ 还有 %s" % o[:20]) if o else "✓ 已剔除"))

print()
print("   当前 HEAD 树上 >2MB 的文件:")
files = sh(["git", "ls-files"]).split("\n")
big = []
for f in files:
    f = f.strip()
    if not f:
        continue
    fp = os.path.join(ROOT, f.replace("/", os.sep))
    try:
        s = os.path.getsize(fp)
    except OSError:
        continue
    if s > 2 * 1048576:
        big.append((s, f))
big.sort(reverse=True)
print("      共 %d 个，最大 %.1f MB %s"
      % (len(big), (big[0][0] / 1048576) if big else 0,
         "✓ 在 GitHub 限制内" if not big or big[0][0] < 100 * 1048576 else "✗ 超限"))

print()
print("=== 结论 ===")
ok = (not sh(["git", "log", "--all", "--oneline", "--format=%h", "-1", "--",
              "dev/tts_model_cache"]))
print("   历史已清干净：%s" % ("✓ 可以推送" if ok else "✗ 还需处理"))
