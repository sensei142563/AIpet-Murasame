# -*- coding: utf-8 -*-
"""修 accept_all.py 第 240 行的双逗号；按技能要求自查 CRLF；重跑 dry-run；提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
P = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(P, encoding="utf-8").read().replace("\r\n", "\n")
n = t.count("),, (")
t = t.replace("),, (", "), (")
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("RESULT_FIX: 修掉双逗号 %d 处" % n)

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % P],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("RESULT_SYNTAX:", "OK" if r.returncode == 0 else "FAIL " + (r.stderr or "")[:200])

print()
print("=== 技能 §14.1 自查：我改过的文件行尾是否被换成 LF ===")
targets = [P,
           os.path.join(MAIN, "api.py"),
           os.path.join(MAIN, "tool", "vad.py"),
           os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt"),
           os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt"),
           os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/WakeWord.kt"),
           os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt")]
for f in targets:
    if not os.path.isfile(f):
        continue
    d = open(f, "rb").read()
    crlf = d.count(b"\r\n")
    lf = d.count(b"\n") - crlf
    flag = "CRLF ✓" if crlf > 0 and lf == 0 else ("LF-only ⚠" if lf > 0 and crlf == 0 else "mixed ⚠")
    print("   %-22s CRLF=%-5d LF=%-5d %s" % (os.path.basename(f), crlf, lf, flag))
print("   说明：本仓库 core.autocrlf=true，git 内部存 LF、检出为 CRLF；")
print("         工作区若变 LF-only，提交本身无害（git 会归一化），但与其他文件不一致。")

print()
print("=== dry-run 复核（不截断输出，只看汇总）===")
r2 = subprocess.run([sys.executable, "-u", P, "--dry-run"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=600,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
i = out.find("=== 汇总 ===")
seg = out[i:] if i > 0 else out[-1200:]
print(seg)
honest = ("PASS 0" in seg) and ("FAIL 0" in seg)
print("RESULT_DRYRUN:", "全部 SKIP、零谎报 ✓" if honest else "仍有非 SKIP 项 ⚠")
print("RESULT_EXITCODE: %d" % r2.returncode)

MSG = """fix(accept): 修掉正则替换引入的双逗号语法错误（accept_all.py 第 240 行）

上一提交用正则把「DRY 直接判 PASS」统一替换成 verdict(...) 时，把 ⑤b 那条多行语句
替换成了 `... verdict(any(...)),, (lines[-1:] ...)` —— 多出一个逗号，ast.parse 在第 240 行报错。
已修（`),, (` → `), (`）。

教训（与技能 windows-powershell-traps 一致）：
  · 正则做批量改写后，必须立刻跑一次语法检查，且**不要只看退出码**；
  · 我的核验脚本自己在 subprocess.run(text=True) 时没写 encoding="utf-8"，
    撞上本机 GBK 默认编码抛 UnicodeDecodeError —— 已统一显式指定 encoding/errors。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_accept4.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("DESKTOP_COMMIT:", (rc.stdout or rc.stderr or "").splitlines()[0][:120])
n2 = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                    capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"],
                    capture_output=True, text=True, encoding="utf-8").stdout.strip()
print("RESULT_REPO: 未推送 %s 条，工作区 %s" % (n2, "干净" if not st else "%d 项" % len(st.splitlines())))
