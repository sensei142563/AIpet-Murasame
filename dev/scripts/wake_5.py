# -*- coding: utf-8 -*-
"""把我插入的 8 行缩进对齐到 16 空格（与邻行一致），然后重建 + 提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SP = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(SP, encoding="utf-8").read().replace("\r\n", "\n")
old = '''Row2("朗读", if (ttsOn) "开" else "关", Icons.Default.VolumeUp, text, sub) { onToggleTts() }
// 「只回应呼唤」：默认关（保持"按住说话就回应"的手感）；开=要先喊她名字才回应
var wakeOn by androidx.compose.runtime.remember {
    androidx.compose.runtime.mutableStateOf(WakeWordSetting.load(vctx))
}
Row2("只回应呼唤", if (wakeOn) "开（先喊「丛雨」）" else "关", Icons.Default.Mic, text, sub) {
    wakeOn = !wakeOn
    WakeWordSetting.save(vctx, wakeOn)
}'''
IND = " " * 16
new = (IND + 'Row2("朗读", if (ttsOn) "开" else "关", Icons.Default.VolumeUp, text, sub) { onToggleTts() }\n'
       + IND + '// 「只回应呼唤」：默认关（保持"按住说话就回应"的手感）；开=要先喊她名字才回应\n'
       + IND + 'var wakeOn by androidx.compose.runtime.remember {\n'
       + IND + '    androidx.compose.runtime.mutableStateOf(WakeWordSetting.load(vctx))\n'
       + IND + '}\n'
       + IND + 'Row2("只回应呼唤", if (wakeOn) "开（先喊「丛雨」）" else "关", Icons.Default.Mic, text, sub) {\n'
       + IND + '    wakeOn = !wakeOn\n'
       + IND + '    WakeWordSetting.save(vctx, wakeOn)\n'
       + IND + '}')
if old in t:
    t = t.replace(old, new, 1)
    io.open(SP, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已把该段（含原有「朗读」行）缩进对齐到 16 空格")
else:
    print("· 未命中（可能已对齐）")

print()
print("=== 重建 + 单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "assembleRelease",
                    "--console=plain"], cwd=CHAT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:170])
if r.returncode != 0:
    sys.exit(1)

MSG = """style(settings): 把「只回应呼唤」那段缩进对齐（含其锚点「朗读」行）

修复自己上一提交留下的可读性问题：插入时锚点行 `Row2("朗读", …)` 本身是 0 缩进
（这一行在我改之前就是 0 缩进，与周围 16 空格不一致），导致我按锚点缩进插入后
新代码块整体贴到行首。已把这一整段统一到 16 空格（只改缩进，无行为变化）。

顺带记录核对方法：不只看"编译通过"，而是
  ① 打印含目标字符串的**原文**（带缩进）看清上下文；
  ② 数一遍从函数头到该行的**花括号嵌套深度**判断它落在哪个作用域。
本例确认它确实位于 SettingsPage 的「语音」卡片里（紧跟在原「朗读」行之后），
不是因为编译通过就当作没问题。
"""
p = os.path.join(MAP, "_msg_wake4.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", CHAT, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
