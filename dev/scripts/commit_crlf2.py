# -*- coding: utf-8 -*-
"""提交 normalize_crlf.py 的缩进修复。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """fix(env): normalize_crlf.py 缩进错误（插 else: 时未重排文件列表）

上一提交给该脚本加 SAFETY_GUARD 时写成：
    if not safety_ok(...):
        main_files = []
    else:
    main_files = [ ... ]     ← 原块缩进没动 ⇒ IndentationError（line 48/49）
已改为早退（打印 RESULT 后 sys.exit(0)），并**不过滤输出**地复核：
  · 语法检查 EXIT=0；
  · 实跑：`[SKIP] 桌面仓：core.autocrlf=false core.eol=lf ⇒ 仓库本体为 LF，转 CRLF
    会造成整文件差异，已拒绝` + `RESULT_CONVERTED: 0`；
  · git status 只有本脚本自身改动，无意外文件变动。

教训（连续两次同类）：
  ① 用正则/文本替换做批量改写后，**必须立刻语法检查**（本轮已犯两次：,, 与 else:）；
  ② 检查时**不要过滤输出**（§11.3）—— 第一次复核我把输出过滤了，
     结果把 IndentationError 一起滤掉，误以为"保险验证通过"。
"""
p = os.path.join(MAP, "_msg_crlf2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("DESKTOP_COMMIT:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("桌面仓: 未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))

PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
n2 = subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                    capture_output=True, text=True, encoding="utf-8").stdout.strip()
st2 = subprocess.run(["git", "-C", CHAT, "status", "--porcelain"], capture_output=True,
                     text=True, encoding="utf-8").stdout.strip()
print("手机仓: 未推送 %s 条，工作区 %s" % (n2, "干净 ✓" if not st2 else "%d 项" % len(st2.splitlines())))
