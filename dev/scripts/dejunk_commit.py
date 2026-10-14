# -*- coding: utf-8 -*-
"""① 把已暂存的 824 项"从 git 摘掉"提交掉
   ② 核对结果（提交数、剩余大文件、文件仍在硬盘）
   ③ 为历史改写做备份与准备（不改写，只准备）
"""
import io
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(args, timeout=900):
    try:
        r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode
    except Exception as e:
        return "ERR %s" % e, 1


print("=== ① 提交 ===")
out, _ = sh(["git", "status", "--porcelain"])
staged = [l for l in out.split("\n") if l.strip()]
print("   待提交 %d 项（绝大多数是 D = 从 git 摘掉）" % len(staged))
MSG = """chore(repo): 把"仅本地 / 手机端素材 / 模型缓存"从 git 摘掉（文件保留在硬盘上）

## 主人要求
1. 主题视频（沫子的日常）**仅本地** ⇒ 不进 git；
2. **除文档外，一切手机端相关的东西都不推**；
3. 录屏素材不推。
（第 2、3 条是我之前误提交的，认。）

## 起因：推送被 GitHub 拒收
```
remote: error: File dev/tts_model_cache/kokoro-int8-multi-lang-v1_0.tar.bz2 is 126.17 MB;
        this exceeds GitHub's file size limit of 100 MB
! [remote rejected] (pre-receive hook declined)
```
按体积排查：>2MB 的已入库文件共 71 个、合计 477.8 MB。其中
`dev/tts_model_cache/**`（模型缓存）、`dev/shots/**`（手机/AR 测试截图与录屏）、
`dev/three-demo/**`、`dev/vrm_probe/model_from_device.vrm`、
`AIpet-Murasame.exe.bak_1604` 都不该入库。
⇒ 也解释了"以前能推、现在不能"：126MB 那个是 **2026-10-11**（111cf76）进来的，
   而最后一次成功推送是 10-10。

（另核实：`dev/tmp/venv_junk` 那个 293MB DLL **从未入库**；
 主题视频 `bg_custom.mp4` 也**从未入库** —— 本来就是仅本地，主人说得对。
 我先前那份"已入库"清单里这两条是错的，已更正。）

## 本步（**不删任何文件**）
`git rm -r --cached`（只从 git 索引摘掉）+ `.gitignore` 固化。
**硬盘上的文件原样保留** ⇒ 主题视频本地照常工作，只是不再进仓库。

## 下一步
历史改写（filter-branch）把这些对象从历史里剔除 —— 否则 GitHub 仍会因 126MB 拒收；
之后推**新分支**（新分支 ⇒ 无需 force ⇒ main 一个字节不动）。
"""
p = os.path.join(ROOT, "dev", "merge-map", "_msg_dejunk3.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
sh(["git", "add", os.path.join("dev", "merge-map", "_msg_dejunk3.txt")])
out2, code2 = sh(["git", "commit", "-F", p])
print("   " + (out2.splitlines()[0] if out2 else "")[:140])
print("   退出码 = %d" % code2)

print()
print("=== ② 核对 ===")
out3, _ = sh(["git", "log", "--oneline", "-2"])
for l in out3.split("\n")[:2]:
    print("   " + l[:110])
out4, _ = sh(["git", "status", "--porcelain"])
left = [l for l in out4.split("\n") if l.strip()]
print("   工作区剩余 %d 项" % len(left))
for l in left[:8]:
    print("      " + l[:104])

print()
print("   已入库 >2MB 的文件（Python 统计，避免中文路径问题）：")
files, _ = sh(["git", "ls-files", "-z"])
big = []
for f in [x for x in files.split("\x00") if x.strip()]:
    fp = os.path.join(ROOT, f.replace("/", os.sep))
    try:
        s = os.path.getsize(fp)
    except OSError:
        continue
    if s > 2 * 1048576:
        big.append((s, f))
big.sort(reverse=True)
for s, f in big:
    print("      %8.1f MB  %s" % (s / 1048576, f[:90]))
print("      合计 %.1f MB（最多 %d MB，均在 GitHub 100MB 限制内 %s）"
      % (sum(s for s, _ in big) / 1048576, (big[0][0] / 1048576) if big else 0,
         "✓" if not big or big[0][0] < 100 * 1048576 else "✗"))

print()
print("=== ③ 文件仍在硬盘？ ===")
for probe in ("pcl_launcher/themes/senrenbanka_copy/assets/bg_custom.mp4",
              "dev/shots/ar_final_layout.png", "dev/three-demo",
              "dev/tts_model_cache/kokoro-int8-multi-lang-v1_0.tar.bz2"):
    fp = os.path.join(ROOT, probe.replace("/", os.sep))
    print("   %-64s %s" % (probe[:64], "✓ 在" if os.path.exists(fp) else "✗ 不在"))

print()
print("=== ④ 为历史改写做准备 ===")
v, _ = sh(["git", "versions"])
out5, _ = sh(["git", "filter-branch", "--version"])
print("   内置 filter-branch 可用：%s" % ("✓" if "filter-branch" in out5 else "?"))
print("   现有提交数（本分支）：%s" % sh(["git", "rev-list", "--count", "HEAD"])[0])
now = time.strftime("%Y%m%d-%H%M%S")
print("   建议先复制一份 .git 备份（0.91GB）→ 或依赖 tag preB-20261014 保底")
print("   安全标签 = %s" % sh(["git", "rev-list", "-n", "1", "preB-20261014"])[0][:12])
