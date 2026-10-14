# -*- coding: utf-8 -*-
"""第一步（无风险：只从 git 摘掉，硬盘上一个文件都不删）：
  ① 确认工具（git filter-repo 有没有）与那个 293MB DLL 到底入库没有
  ② git rm -r --cached 摘掉：手机端相关（非文档）/ 录屏素材 / 主题视频 / 模型缓存 / 垃圾
  ③ 写 .gitignore
  ④ 提交（只影响索引，工作区文件保留）
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


print("=== ① 工具与那个 293MB DLL ===")
for tool in ("git-filter-repo", "filter-repo"):
    out, code = sh([tool, "--version"])
    print("   %-16s %s" % (tool, "可用 ✓" if code == 0 else "不可用 ✗"))
dll = "dev/tmp/venv_junk/~orch/lib/torch_cpu.dll"
out, code = sh(["git", "ls-files", "--error-unmatch", dll])
print("   293MB DLL 是否入库：%s" % ("是 ✗" if code == 0 else "否 ✓（不在 git 里，虚惊）"))
out, _ = sh(["git", "ls-files", "dev/tmp"])
tmpf = [l for l in out.split("\n") if l.strip()]
print("   dev/tmp 已入库文件数：%d" % len(tmpf))
for l in tmpf[:6]:
    print("      " + l[:100])

# ---------- 要从 git 摘掉的路径 ----------
PATHS = [
    "dev/shots",                 # 手机/AR 测试素材 + 录屏（你说的两类都在这）
    "dev/three-demo",            # 手机端 3D 试验
    "dev/vrm_probe",             # 真机拉的 VRM
    "dev/tts_model_cache",       # 模型缓存（我的错）
    "dev/tmp",                   # 临时垃圾（含那个 293MB 的 DLL）
    "dev/screenshots",
    "pcl_launcher/themes/senrenbanka_copy/assets/bg_custom.mp4",   # 主题视频：仅本地
    "AIpet-Murasame.exe.bak_1604",
]
# 手机端相关的一次性脚本（非文档）
out, _ = sh(["git", "ls-files", "dev/scripts"])
for f in out.split("\n"):
    f = f.strip()
    if not f:
        continue
    base = os.path.basename(f).lower()
    if any(k in base for k in ("vrm_", "hand_", "ar_", "phone", "make_handover")):
        if base.endswith(".py"):
            PATHS.append(f)

print()
print("=== ② 从 git 摘掉（--cached：硬盘文件保留）===")
for p in PATHS:
    out, code = sh(["git", "rm", "-r", "--cached", "--quiet", "--", p])
    n = 0
    if code != 0:
        print("   · %-58s （没入库或不存在，跳过）" % p[:58])
    else:
        print("   ✓ %-58s 已从 git 摘掉" % p[:58])

print()
print("=== ③ 写 .gitignore ===")
gi = os.path.join(ROOT, ".gitignore")
t = io.open(gi, encoding="utf-8", errors="replace").read() if os.path.isfile(gi) else ""
ADD = """
# ══════════════════════════════════════════════════════════════════
# 2026-10-14 清理：以下内容**仅本地**，绝不入库
#   主人要求：① 主题视频仅本地 ② 除文档外手机端相关一律不推 ③ 录屏素材不推
#   另外：模型缓存 / 临时目录 / 大二进制 都不进 git（曾因此被 GitHub 拒收）
# ══════════════════════════════════════════════════════════════════
dev/shots/
dev/three-demo/
dev/vrm_probe/
dev/tmp/
dev/screenshots/
dev/tts_model_cache/
pcl_launcher/themes/*/assets/bg_custom.mp4
*.exe.bak_*
*.tar.bz2
"""
if "2026-10-14 清理" not in t:
    if t and not t.endswith("\n"):
        t += "\n"
    io.open(gi, "w", encoding="utf-8", newline="\n").write(t + ADD)
    print("   ✓ 已追加 9 条规则")
else:
    print("   · 已存在")

print()
print("=== ④ 提交（只动索引；工作区文件仍在）===")
sh(["git", "add", "-A"])
MSG = """chore(repo): 把"仅本地/手机端素材/模型缓存"从 git 摘掉（文件保留在硬盘上）

## 主人要求
1. 主题视频（沫子的日常）**仅本地** ⇒ 不进 git；
2. **除文档外，一切手机端相关的东西都不推**；
3. 录屏素材不推（这一条是我的错，之前误提交了）。

## 起因
推送被 GitHub 拒收：
```
remote: error: File dev/tts_model_cache/kokoro-int8-multi-lang-v1_0.tar.bz2 is 126.17 MB;
        this exceeds GitHub's file size limit of 100 MB
! [remote rejected] (pre-receive hook declined)
```
查明：仓库里 >2MB 的已入库文件共 **71 个、合计 477.8 MB**，其中
`dev/tts_model_cache/**`（模型缓存，126MB tarball + 解压目录）、`dev/shots/**`（手机/AR 测试截图与录屏）、
`dev/three-demo/**`、`dev/vrm_probe/model_from_device.vrm`、主题视频 `bg_custom.mp4`（71MB）、
`AIpet-Murasame.exe.bak_1604` 等都不该入库。
⇒ 这也解释了"以前能推、现在不能"：126MB 那个是 **2026-10-11** 提交（111cf76）进来的，
   而最后一次成功推送是 10-10。

## 本步做了什么（**不删任何文件**）
`git rm -r --cached`（只从 git 索引摘掉）+ `.gitignore` 固化。
**硬盘上的文件原样保留** ⇒ 主题视频本地照常工作，只是不再进仓库（正是"仅本地"的意思）。

## 下一步（待做）
历史改写（filter-repo / filter-branch）把这些对象从历史里剔除 —— 否则 GitHub 仍会拒收；
之后推**新分支**（新分支 ⇒ 无需 force ⇒ main 一个字节不动）。
"""
p = os.path.join(ROOT, "dev", "merge-map", "_msg_dejunk.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
sh(["git", "add", "-A"])
out, code = sh(["git", "commit", "-F", p])
print("   " + (out.splitlines()[0] if out else "")[:140])
st, _ = sh(["git", "status", "--porcelain"])
print("   工作区改动 %d 项（应只剩未跟踪的排查脚本）" % len([l for l in st.split("\n") if l.strip()]))
# 关键验证：文件还在硬盘上吗
for probe in ("pcl_launcher/themes/senrenbanka_copy/assets/bg_custom.mp4",
              "dev/shots/ar_final_layout.png"):
    fp = os.path.join(ROOT, probe.replace("/", os.sep))
    print("   硬盘上仍在：%-58s %s" % (probe[:58], "✓" if os.path.isfile(fp) else "✗ 不见了吗"))
