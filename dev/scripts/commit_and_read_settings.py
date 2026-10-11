# -*- coding: utf-8 -*-
"""① 提交验收的"已是最新则跳过安装"加固
   ② 设置页：把「离线识别」做成可见开关（读写 files/asr_offline_enabled.txt）
      并在离线识别停用时，自检按钮给出明确提示（而不是什么都不发生）"""
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
SP = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt")

MSG1 = """test(accept): 设备上已是当前这版就跳过安装（安装动作会弹系统窗口抢前台）

实测两轮 UI 检查全被 SKIP，原因是**安装动作本身**会弹出：
  · 华为应用市场的"安装完成/建议开启增强防护"页
  · com.huawei.coauthservice 的「统一身份验证」对话框
它们把前台抢走，于是 ①~⑤⑥/⑩1/⑩2 这些需要点击的检查一律被前台守卫跳过。
这些系统弹窗（尤其身份验证）不该由自动化去点。

改为：进第 1 步先比对设备 lastUpdateTime 与本地 APK 构建时间，
       已经是当前这版 ⇒ **跳过安装**（并打印跳过原因），从源头避免弹窗。
需要真正重装时，删掉 app/build/outputs/apk/release/app-release.apk 或改一行代码重新构建即可。

实测：跳过安装后同一轮 PASS 10 / FAIL 0 / SKIP 10，退出码 0；
⑨3 聊天页守门测试再次通过（pid 29108→29108，前台仍是本应用）。
"""
p = os.path.join(MAP, "_msg_skip_install.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG1)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("桌面仓:", (r.stdout or r.stderr or "").splitlines()[0][:140])

# ---------- ② 设置页：离线识别开关 ----------
print()
print("=== SettingsPage.kt 里自检按钮与开关的现状 ===")
src = io.open(SP, encoding="utf-8", errors="replace").read()
lines = src.split("\n")
for i, l in enumerate(lines, 1):
    if re.search(r"selfTest|识别|自检|Switch|Checkbox|SettingRow|Row\(|Text\(", l):
        print("   %4d| %s" % (i, l.strip()[:130]))
