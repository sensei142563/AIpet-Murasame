# -*- coding: utf-8 -*-
"""从日志里找证据：run.py 启动时到底有没有把自己切到 runtime\\venv。
   然后提交本次的注释+文档+对比脚本。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

print("=== ① 日志里找「切换解释器」的痕迹 ===")
pats = re.compile(r"不是项目自带的|改用|runtime\\venv|venv\\Scripts|AIPET_REEXEC")
for rel in ("data/pet_run.log", "data/launcher.log", "data/self_learn.log"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        print("   %-22s （没有）" % rel)
        continue
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    hits = [(i, l) for i, l in enumerate(ls, 1) if pats.search(l)]
    print("   %-22s %d 行命中（共 %d 行）" % (rel, len(hits), len(ls)))
    for i, l in hits[-8:]:
        print("      %5d| %s" % (i, l.strip()[:120]))

print()
print("=== ② 当前跑着的桌宠用的是哪个解释器（若在跑）===")
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
                    "ForEach-Object { $_.ProcessId.ToString() + '|' + $_.CommandLine }"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
n = 0
for l in (r.stdout or "").split("\n"):
    l = l.strip()
    if not l or "|" not in l:
        continue
    pid, cmd = l.split("|", 1)
    tag = ""
    if "runtime\\venv" in cmd:
        tag = "  ← **venv**"
    elif "Python310" in cmd:
        tag = "  ← 全局 Python310"
    print("   PID %-7s %s%s" % (pid, cmd[:104], tag))
    n += 1
if n == 0:
    print("   （没有 python 在跑）")

MSG = """docs(env): 重点注释「本机不用虚拟环境」+ 环境对比脚本（查出 venv 缺 273 个包）

## 主人要求
"把那个每次你都搞混的虚拟环境重点注释，咱本地不用虚拟环境"

## 做了什么
1. **run.py 顶部**加一大段「本机虚拟环境约定」重点注释（⚠⚠⚠ 框起来），写明：
   - 本机跑项目用**全局 Python 3.10**，依赖都在全局 site-packages；
   - `runtime\\venv` 是**历史遗留、包不全**，默认不要用；
   - **如实记录矛盾**：下面三个函数的注释说的恰好相反（"必须用 venv 否则会崩"），
     那是历史情况，现在反了；保留原行为（改了有崩的风险），但调用处不要重复写死 venv。
2. 三个函数各加一行指针（`_ensure_project_python` / `_project_python` / `_f5tts_venv_python`）。
3. 新增 `docs/本机环境约定-不用虚拟环境.md`：结论、矛盾说明、**排查三步走**、
   历次"装错环境"事故对照表、以及"装包前先 --dry-run"的教训。
4. README 加指针。
5. 新增 `dev/scripts/compare_envs.py`：对比两个解释器的包，列出"全局有、venv 没有"。

## 对比结果（关键）
```
全局包数 = 390      venv 包数 = 126
「全局有、venv 没有」= **273 个**，含 f5-tts / cn2an / edge-tts / budoux /
fast-langdetect / datasets / bigvgan / encodec / auraloss / aliyun-* / boto3 …
⇒ 项目默认跑在 venv 上时，任何用到这些的功能都会炸（F5-TTS 就是其中之一，已修）
```
⇒ 数据完全支持主人的说法：**本机就是全局 Python 环境，venv 不该用**。

## 待主人拍板（未擅自改）
要不要把默认行为也翻过来？三个方案：
  A. 加配置开关 `use_venv`（默认 false）⇒ 三个函数都尊重它（可逆、最稳）
  B. 让 `_ensure_project_python` 在"全局能 import 项目核心依赖"时不切换
  C. 什么都不改（只保留注释与文档）
主人说"重点注释"，所以我**只做了注释与文档**，行为未动 —— 等一句话。
"""
p = os.path.join(MAP, "_msg_env.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("=== ③ 提交 ===")
print("   ", (rc.stdout or rc.stderr or "").splitlines()[0][:150])
n2 = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                    capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("   未推送 %s 条，工作区 %s" % (n2, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
