# -*- coding: utf-8 -*-
"""第一步（无风险：只从 git 摘掉，硬盘上一个文件都不删）"""
import io
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(args, timeout=900):
    try:
        r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode
    except FileNotFoundError:
        return "", 127
    except Exception as e:
        return "ERR %s" % e, 1


print("=== ① 工具与那个 293MB DLL ===")
print("   git-filter-repo：%s" % (shutil.which("git-filter-repo") or "不可用 ✗（改用内置 filter-branch）"))
dll = "dev/tmp/venv_junk/~orch/lib/torch_cpu.dll"
out, code = sh(["git", "ls-files", "--error-unmatch", dll])
print("   293MB DLL 入库了吗：%s" % ("是 ✗" if code == 0 else "否 ✓（虚惊一场）"))
out, _ = sh(["git", "ls-files", "dev/tmp"])
tmpf = [l for l in out.split("\n") if l.strip()]
print("   dev/tmp 已入库 %d 个文件" % len(tmpf))
for l in tmpf[:5]:
    print("      " + l[:100])

PATHS = [
    "dev/shots", "dev/three-demo", "dev/vrm_probe", "dev/tts_model_cache", "dev/tmp",
    "dev/screenshots",
    "pcl_launcher/themes/senrenbanka_copy/assets/bg_custom.mp4",
    "AIpet-Murasame.exe.bak_1604",
]
out, _ = sh(["git", "ls-files", "dev/scripts"])
for f in out.split("\n"):
    f = f.strip()
    if not f:
        continue
    base = os.path.basename(f).lower()
    if base.endswith(".py") and any(k in base for k in ("vrm_", "hand_", "ar_", "phone",
                                                       "make_handover")):
        PATHS.append(f)

print()
print("=== ② 从 git 摘掉（--cached，硬盘文件保留）===")
removed = 0
for p in PATHS:
    out, code = sh(["git", "rm", "-r", "--cached", "--quiet", "--", p])
    if code == 0:
        print("   ✓ %s" % p[:96])
        removed += 1
    else:
        print("   · %s（未入库/不存在，跳过）" % p[:90])
print("   实际摘掉 %d 个路径" % removed)

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
    print("   ✓ 已追加规则")
else:
    print("   · 已存在")

print()
print("=== ④ 提交 ===")
MSG = """chore(repo): 把"仅本地 / 手机端素材 / 模型缓存"从 git 摘掉（文件保留在硬盘上）

## 主人要求
1. 主题视频（沫子的日常）**仅本地** ⇒ 不进 git；
2. **除文档外，一切手机端相关的东西都不推**；
3. 录屏素材不推（这两条是我之前误提交，认）。

## 起因：推送被 GitHub 拒收
```
remote: error: File dev/tts_model_cache/kokoro-int8-multi-lang-v1_0.tar.bz2 is 126.17 MB;
        this exceeds GitHub's file size limit of 100 MB
! [remote rejected] (pre-receive hook declined)
```
按体积排查：>2MB 的已入库文件共 71 个、合计 **477.8 MB**，
其中 dev/tts_model_cache/**（模型缓存）、dev/shots/**（手机/AR 测试截图与录屏）、
dev/three-demo/**、dev/vrm_probe/model_from_device.vrm、主题视频 bg_custom.mp4（71MB）、
AIpet-Murasame.exe.bak_1604 都不该入库。
⇒ 也解释了"以前能推、现在不能"：126MB 那个是 **2026-10-11**（111cf76）进来的，最后一次成功推送是 10-10。

## 本步（**不删任何文件**）
`git rm -r --cached`（只从索引摘掉）+ `.gitignore` 固化。
**硬盘上的文件原样保留** ⇒ 主题视频本地照常工作，只是不再进仓库（正是"仅本地"）。

## 下一步
历史改写剔除这些对象（filter-branch / filter-repo），否则 GitHub 仍拒收；
然后推**新分支**（新分支 ⇒ 无需 force ⇒ main 一个字节不动）。
"""
p = os.path.join(ROOT, "dev", "merge-map", "_msg_dejunk2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
sh(["git", "add", "-A"])
out, code = sh(["git", "commit", "-F", p])
print("   " + ((out.splitlines()[0] if out else "")[:140]))
print("   退出码 = %d" % code)
st, _ = sh(["git", "status", "--porcelain"])
print("   工作区剩余 %d 项" % len([l for l in st.split("\n") if l.strip()]))

print()
print("=== ⑤ 关键验证：文件还在硬盘上吗 ===")
for probe in ("pcl_launcher/themes/senrenbanka_copy/assets/bg_custom.mp4",
              "dev/shots/ar_final_layout.png",
              "dev/tts_model_cache/kokoro-int8-multi-lang-v1_0.tar.bz2"):
    fp = os.path.join(ROOT, probe.replace("/", os.sep))
    print("   %-62s %s" % (probe[:62], "✓ 仍在" if os.path.isfile(fp) else "✗ 不见了"))
