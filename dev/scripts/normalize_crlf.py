# -*- coding: utf-8 -*-
"""按技能 §14.1：把我改过的代码文件行尾统一回 CRLF（工作区与仓库其余文件一致）。
   二进制读写，避免任何换行翻译；改完逐字节复核。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")


def repo_policy(repo):
    """读仓库行尾策略。桌面仓实测 core.autocrlf=false + core.eol=lf ⇒ 仓库本体就是 LF。"""
    def cfg(k):
        r = subprocess.run(["git", "-C", repo, "config", k], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return (r.stdout or "").strip()
    return cfg("core.autocrlf"), cfg("core.eol")


def safety_ok(repo, label):
    """SAFETY_GUARD：若仓库本体是 LF（autocrlf=false 且 eol=lf），把工作区转成 CRLF 会制造
    整文件翻动（实测桌面仓 1904 行差异）。所以这种仓库**拒绝转换**。"""
    ac, eol = repo_policy(repo)
    if ac.lower() in ("false", "") and eol.lower() == "lf":
        print("   [SKIP] %s：core.autocrlf=%s core.eol=%s ⇒ 仓库本体为 LF，"
              "转 CRLF 会造成整文件差异，已拒绝（这是实测教训）" % (label, ac or "(空)", eol))
        return False
    return True


def to_crlf(path):
    d = open(path, "rb").read()
    crlf0 = d.count(b"\r\n")
    lf0 = d.count(b"\n") - crlf0
    if lf0 == 0 and crlf0 > 0:
        return "已是 CRLF", 0
    new = d.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    open(path, "wb").write(new)
    return "已转换", 1


print("=== 桌面仓 ===")
if not safety_ok(MAIN, "桌面仓"):
    main_files = []
else:
main_files = [
    "api.py", "tool/vad.py", "tool/silero_vad.py", "tool/heavy_gate.py",
    "dev/scripts/accept_all.py", "dev/scripts/test_vad.py", "dev/scripts/test_heavy_gate.py",
    "dev/scripts/heavy_gate_e2e2.py", "dev/scripts/vrm_inspect.py",
]
changed = 0
for f in main_files:
    p = os.path.join(MAIN, f.replace("/", os.sep))
    if not os.path.isfile(p):
        print("   %-34s (不存在)" % f)
        continue
    msg, c = to_crlf(p)
    changed += c
    d = open(p, "rb").read()
    print("   %-34s %s  CRLF=%d LF=%d" % (f, msg, d.count(b"\r\n"),
                                          d.count(b"\n") - d.count(b"\r\n")))

print("=== 手机仓 ===")
chat_files = [
    "app/src/main/java/com/aipet/murasame/ui/WakeWord.kt",
    "app/src/main/java/com/aipet/murasame/ui/WakeWordSetting.kt",
    "app/src/main/java/com/aipet/murasame/ui/VadGate.kt",
    "app/src/main/java/com/aipet/murasame/ui/SileroVad.kt",
    "app/src/main/java/com/aipet/murasame/ui/HandTouch.kt",
    "app/src/main/java/com/aipet/murasame/ui/HandTracker.kt",
    "app/src/main/java/com/aipet/murasame/ui/VrmArScreen.kt",
    "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt",
    "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt",
    "app/src/test/java/com/aipet/murasame/WakeWordTest.kt",
]
for f in chat_files:
    p = os.path.join(CHAT, f.replace("/", os.sep))
    if not os.path.isfile(p):
        print("   %-52s (不存在)" % f.split("/")[-1])
        continue
    msg, c = to_crlf(p)
    changed += c
    d = open(p, "rb").read()
    print("   %-52s %s  CRLF=%d" % (f.split("/")[-1], msg, d.count(b"\r\n")))

print()
print("RESULT_CONVERTED: %d 个文件" % changed)
print()
print("=== git 是否因此产生差异（autocrlf=true 时预期无差异）===")
for nm, repo in (("桌面", MAIN), ("手机", CHAT)):
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8", errors="replace").stdout.strip()
    print("   %s仓：%s" % (nm, "工作区干净（行尾由 git 归一化，无需提交）" if not st
                          else "%d 项差异：%s" % (len(st.splitlines()), st.splitlines()[:3])))
