# -*- coding: utf-8 -*-
"""让工作区变干净（filter-branch 的前置条件），然后重新启动历史改写（后台）。"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(args, timeout=900):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode


print("=== ① 脏在哪（只列已跟踪的）===")
out, _ = sh(["git", "status", "--porcelain"])
tracked, untracked = [], []
for l in out.split("\n"):
    if not l.strip():
        continue
    (untracked if l.startswith("??") else tracked).append(l)
print("   已跟踪但被改动：%d 项" % len(tracked))
for l in tracked[:14]:
    print("      " + l[:110])
print("   未跟踪（不影响改写）：%d 项" % len(untracked))

print()
print("=== ② 看 Deck.pptx 到底改了什么 ===")
d, _ = sh(["git", "diff", "--stat", "--", "dev/ppt/out/Deck.pptx"])
print("   " + (d.replace("\n", "\n   ") if d else "（无差异？）")[:300])

print()
print("=== ③ 提交这些改动，让工作区干净 ===")
sh(["git", "add", "-A"])
MSG = """chore(ppt): 保存 Deck.pptx / Deck.pdf 的最新渲染（PowerPoint 渲染后元数据变化）

渲染脚本用 PowerPoint COM 打开过 Deck.pptx，退出时会改动文件元数据 ⇒ 工作区变脏。
filter-branch（历史改写）要求工作区干净，故先提交。
"""
p = os.path.join(ROOT, "dev", "merge-map", "_msg_render.txt")
import io
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
o, c = sh(["git", "commit", "-F", p])
print("   " + ((o.splitlines()[0] if o else "")[:130]))
print("   退出码 = %d" % c)
out2, _ = sh(["git", "status", "--porcelain"])
tr = [l for l in out2.split("\n") if l.strip() and not l.startswith("??")]
print("   现在已跟踪的脏项：%d 个 %s" % (len(tr), "✓ 干净，可以改写" if not tr else "✗ 还有"))
for l in tr[:6]:
    print("      " + l[:110])

print()
print("=== ④ 重新启动历史改写（后台）===")
PATHS = ["dev/shots", "dev/three-demo", "dev/vrm_probe", "dev/screenshots",
         "dev/tts_model_cache", "dev/tmp", "AIpet-Murasame.exe.bak_1604"]
o2, _ = sh(["git", "ls-files", "dev/scripts"])
for f in o2.split("\n"):
    f = f.strip()
    if f and f.lower().endswith(".py") and re.search(
            r"(ar_|vrm_|hand_|phone|make_handover)", os.path.basename(f).lower()):
        PATHS.append(f)
flt = "git rm -r --cached --ignore-unmatch " + " ".join("'%s'" % x for x in PATHS)
print("   要剔除 %d 条路径" % len(PATHS))
env = dict(os.environ, FILTER_BRANCH_SQUELCH_WARNING="1")
print("   启动 filter-branch（后台，预计几分钟）…")
proc = subprocess.Popen(
    ["git", "filter-branch", "-f", "--index-filter", flt, "--", "HEAD"],
    cwd=ROOT, env=env,
    stdout=open(os.path.join(ROOT, "dev", "tmp_rewrite.log"), "w", encoding="utf-8"),
    stderr=subprocess.STDOUT)
print("   已启动，PID = %d" % proc.pid)
print("   日志：dev/tmp_rewrite.log")
print("   （它是独立进程，不受本次命令结束影响 ✓）")
