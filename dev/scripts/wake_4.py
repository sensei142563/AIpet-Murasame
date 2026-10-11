# -*- coding: utf-8 -*-
"""用正则加 SettingsPage 的开关行，然后全量回归 + 提交（前三处补丁已落盘，需一并验证）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
UI = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

SP = os.path.join(UI, "SettingsPage.kt")
t = io.open(SP, encoding="utf-8").read().replace("\r\n", "\n")
if "只回应呼唤" in t:
    print("· 已有开关行")
else:
    pat = re.compile(r"^(?P<ind>[ \t]*)Row2\(\"朗读\".*$", re.M)
    m = pat.search(t)
    if not m:
        print("✗ 仍找不到 Row2(\"朗读\" ...)")
        # 打印含"朗读"的行，便于人工核对
        for i, l in enumerate(t.split("\n"), 1):
            if "朗读" in l:
                print("   %4d| %s" % (i, l.strip()[:130]))
        sys.exit(1)
    ind = m.group("ind")
    add = ("\n" + ind + "// 「只回应呼唤」：默认关（保持\"按住说话就回应\"的手感）；开=要先喊她名字才回应\n"
           + ind + "var wakeOn by androidx.compose.runtime.remember {\n"
           + ind + "    androidx.compose.runtime.mutableStateOf(WakeWordSetting.load(vctx))\n"
           + ind + "}\n"
           + ind + "Row2(\"只回应呼唤\", if (wakeOn) \"开（先喊「丛雨」）\" else \"关\", Icons.Default.Mic, text, sub) {\n"
           + ind + "    wakeOn = !wakeOn\n"
           + ind + "    WakeWordSetting.save(vctx, wakeOn)\n"
           + ind + "}")
    t = t[:m.end()] + add + t[m.end():]
    io.open(SP, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已用正则插入开关行（缩进 %d）" % len(ind))

print()
print("=== 关键行复核 ===")
for f, keys in ((SP, ["只回应呼唤", "WakeWordSetting.load", "WakeWordSetting.save"]),
                (os.path.join(UI, "ChatScreen.kt"), ["WakeWordSetting.load", "WakeWord.isCalling"]),
                (os.path.join(UI, "WakeWord.kt"), ["从雨", "编辑距离"]),
                (os.path.join(UI, "WakeWordSetting.kt"), ["wake_word.txt"])):
    tt = io.open(f, encoding="utf-8", errors="replace").read()
    print("   " + os.path.basename(f))
    for k in keys:
        print("      %-26s %s" % (k, "✓" if k in tt else "✗"))

print()
print("=== 全量单测 + release ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:175])
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
tot = fail = 0
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if f.endswith(".xml"):
        x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        m2 = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        if m2:
            tot += int(m2.group(1)); fail += int(m2.group(2)) + int(m2.group(3))
print("   合计 %d 个用例，失败 %d" % (tot, fail))
r2 = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                    cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=ENV, timeout=7200)
o2 = (r2.stdout or "") + (r2.stderr or "")
print("   release: " + next((l for l in o2.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o2.splitlines() if x.startswith("e: ")][:10]:
    print("   " + y[:225])
if r2.returncode != 0 or fail:
    print("✗ 未提交（保留改动待修）")
    sys.exit(1)

MSG = """feat(stt): 「只回应呼唤」接线（默认关）+ 变体表扩容；并记录"为何不做编辑距离模糊"

一、接线（只动两个文件，不碰设置状态流）：
    · 新增 ui/WakeWordSetting.kt：文件式持久化（照抄项目里 VoiceClient/JevClient 的既有做法），
      **默认关** —— 保持现有"按住说话就回应"的手感，不改既有体验；
    · ChatScreen 长按录音识别之后加一条分支：开着时先 WakeWord.isCalling() 判断，
      没喊名字就提示"她没听见你叫她（试试先说「丛雨」）"，不把文本填进输入框；
    · SettingsPage 加「只回应呼唤」开关行（自己读写设置，无需新增参数）。

二、变体表扩容 + 一个设计取舍：
    · 新增同音/近音误听：从雨、丛宇、从宇、重雨、勿雨（原有 村雨、ムラサメ、むらさめ、murasame…）；
    · **不采用"编辑距离≤1"的模糊匹配**：两字名字下，"大雨""下雨"距"丛雨"都只有 1 次替换，
      会把日常词误判成唤醒。与其引入误唤醒，不如把常见误听显式列出（可审计、可回滚）。

三、诚实标注：真机未验证（唤醒命中率与提示文案手感需上机看）；因开关默认关，
    即使这条链路有问题也不会影响现有语音流程。
"""
p = os.path.join(MAP, "_msg_wake3.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", CHAT, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
