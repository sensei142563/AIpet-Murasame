# -*- coding: utf-8 -*-
"""正确核对：只看**从 HEAD 可达**的对象（那才是要推送的东西）。
   干净就推新分支（A）；不干净就停下报告。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(a, timeout=3600):
    r = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode


print("=== ① 正确判据：从 HEAD 可达的历史里还有没有这些路径 ===")
BAD = ("dev/tts_model_cache", "dev/shots", "dev/three-demo", "dev/vrm_probe",
       "AIpet-Murasame.exe.bak_1604")
dirty = []
for p in BAD:
    o, _ = sh(["git", "log", "--oneline", "--format=%h %s", "-3", "HEAD", "--", p])
    if o:
        dirty.append(p)
        print("   ✗ %-26s 还有：" % p)
        for l in o.split("\n")[:2]:
            print("        " + l[:100])
    else:
        print("   ✓ %-26s 已从 HEAD 历史剔除" % p)
print("   ⇒ 结论：%s" % ("干净 ✓ 可以推送" if not dirty else "仍有 %d 条 ✗ 先别推" % len(dirty)))

print()
print("=== ② 要推送的对象里最大的几个（这才是 GitHub 会检查的）===")
out, _ = sh(["git", "rev-list", "--objects", "HEAD"], timeout=1800)
objs = []
for l in out.split("\n"):
    parts = l.split(" ", 1)
    if len(parts) == 2:
        objs.append((parts[0], parts[1]))
print("   从 HEAD 可达对象 %d 个" % len(objs))
# 用 cat-file --batch-check 批量取大小（只查前 4000 个，够看大头）
sha_list = "\n".join(s for s, _ in objs[:4000])
r = subprocess.run(["git", "cat-file", "--batch-check=%(objectsize) %(rest)"],
                   cwd=ROOT, input=sha_list, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
sizes = []
for line in (r.stdout or "").split("\n"):
    parts = line.split(" ", 1)
    if len(parts) == 2 and parts[0].isdigit():
        sizes.append((int(parts[0]), parts[1].strip()))
sizes.sort(reverse=True)
for s, f in sizes[:10]:
    print("      %8.2f MB  %s" % (s / 1048576, f[:88]))
biggest = sizes[0][0] if sizes else 0
print("   最大 %.2f MB %s" % (biggest / 1048576,
                              "✓ 低于 100MB 限制" if biggest < 100 * 1048576 else "✗ 超限"))

if dirty or biggest >= 100 * 1048576:
    print()
    print("=== 停下：历史还没清干净，不推送 ===")
    sys.exit(0)

print()
print("=== ③ 推送到 origin/readme-on-their-main（不动 main）===")
out2, code = sh(["git", "push", "origin", "readme-on-their-main:readme-on-their-main"],
                timeout=3600)
for l in out2.split("\n")[-8:]:
    if l.strip():
        print("   " + l.strip()[:130])
print("   退出码 = %d" % code)
out3, _ = sh(["git", "ls-remote", "--heads", "origin"])
if "readme-on-their-main" in out3:
    print("   ✓✓ 推送成功！远端已有该分支")
    for l in out3.split("\n"):
        if "readme-on-their-main" in l:
            print("      " + l.strip())
    print("   ⇒ https://github.com/sensei142563/AIpet-Murasame/tree/readme-on-their-main")
else:
    print("   ✗ 仍未推上去（远端没有该分支）")
