# -*- coding: utf-8 -*-
"""重新生成交接文档（含新的第 ⑧ 节）+ 提交桌面仓。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")

print("=== 重新生成交接文档 ===")
r = subprocess.run([sys.executable, "-u", os.path.join(MAIN, "dev", "scripts", "make_handover.py")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                   env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    if re.search(r"已生成|单测：|验收项|未验证项检索", l):
        print("   " + l.strip()[:150])

DOC = os.path.join(MAIN, "dev", "docs", "交接清单-2026-10.md")
txt = io.open(DOC, encoding="utf-8").read()
i = txt.find("## 二、")
j = txt.find("## 三、")
print()
print("=== 文档第二节（验收项已含第 ⑧ 节）===")
print(txt[i:j][:1800] if i > 0 and j > i else "(未找到)")

print("=== 提交 ===")
MSG = """test(accept): 把 5 条「只能真机验证」的项做成精确判据，接进一键验收（第 ⑧ 节）

上一轮交接文档里列了 5 条"从设计上无法在 JVM 单测覆盖"的项。本轮把它们改写成
**真机上可执行、判据明确**的检查，接进 accept_all.py，让验收报告直接给出结论。

判据字符串全部来自**读源码**（不是凭记忆）：
  · ⑧1 Keystore 加解密：files/wechat_credentials.json 里的凭据必须含前缀 `enc:v1:`
        （SecureStore 的存储格式；看不到前缀即可能存了明文或加密失败）。
        文件不存在时 SKIP（该功能未配置）。
  · ⑧2 资产种子完整性：files/pets/pet_list.json 在、每个角色 pet.json 非空、
        且**没有任何 *.part 残留**（原子复制的临时文件不该留下）。
  · ⑧3 Silero 真机阈值：读 files/vad.log 的 `Silero VAD ready (model=… 字节, threshold=…, minSilence=…s)`
        —— 该行本身就是实际生效的阈值证据。
  · ⑧4 onGiveUp 已接线：files/voice.log **不应**出现 `未提供 onGiveUp`
        （出现即说明调用点没接上、可能静默无声）；同时统计 `通知调用方回退系统 TTS` 的次数。
  · ⑧5 重投去重生效：files/onebot_local.log 里出现 `丢弃重复消息` 即为去重生效的确证；
        没观察到重投则 SKIP（去重逻辑本身已有 9 个单测覆盖），不谎报 PASS。

dry-run 自检：第 ⑧ 节 5 项与原有 10 项一起输出，合计 PASS 0 / FAIL 0 / SKIP 15 —— 仍未谎报。
交接文档已用 make_handover.py 重新生成，第二节的检查项清单自动包含新的 ⑧ 节。
"""
p = os.path.join(MAP, "_msg_accept8.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:140])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
