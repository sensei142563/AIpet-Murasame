# -*- coding: utf-8 -*-
"""提交 selftest_rules + 诊断包自检；打印两仓状态。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """test(accept): 自检改为语义判断 + 自证（第三次踩"朴素子串检查"）

起因：上一提交后我加的自查报「screenrecord 存在 ⇒ ⚠ 与技能要求不符」。
实际查证：`screenrecord` **只出现在一行注释里**（引用技能名），脚本根本没有调用它。
⇒ 是我的检查器错了，不是脚本违规。

这类错误本轮第三次（前两次：用 "periodMs" 子串误判属性已存在；更早用 "PASS" 文本判断）。
共同点：**用"文件里有没有某个词"代替"代码有没有做某件事"**。

修法：
  · 新增 selftest_rules()，按语义检查截图技能的四条要求：
      ① 截图调用必须同时含 exec-out 与 -p；② 不允许真的调用 screenrecord（正则匹配 adb 调用，
         注释里出现不算）；③ 不允许 kill -9；④ 必须校验 PNG 魔数；
  · **检查器自证**（技能 §10 的要求）：注入一段"只在注释里提 screenrecord"的假文本，
    断言检查器仍判为合规 ⇒ 证明它检查的是语义而不是词。实测输出：
      [selftest-rules] 全部符合截图技能要求 ✓
      [selftest-rules] 注释里出现 screenrecord 时判为合规：True（应为 True）
"""
p = os.path.join(MAP, "_msg_selftest_rules.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("DESKTOP_COMMIT:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
for nm, repo in (("桌面", MAIN), ("手机", CHAT)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("%s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
