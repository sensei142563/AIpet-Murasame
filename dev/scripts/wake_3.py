# -*- coding: utf-8 -*-
"""① 扩变体表（含同音误听）② 新增 WakeWordSetting（文件式，照抄 VoiceClient 模式）
   ③ ChatScreen 接分支（默认关，行为不变）④ SettingsPage 加开关行 → 全量回归 → 提交"""
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

# ① 变体表扩容
W = os.path.join(UI, "WakeWord.kt")
t = io.open(W, encoding="utf-8").read().replace("\r\n", "\n")
old = '''        "murasame" to listOf(
            "丛雨", "叢雨", "村雨", "ムラサメ", "むらさめ", "murasame", "村雨丸", "丛雨丸",
        ),'''
new = '''        "murasame" to listOf(
            "丛雨", "叢雨", "村雨", "ムラサメ", "むらさめ", "murasame", "村雨丸", "丛雨丸",
            // 同音/近音误听（**显式列出**，不做编辑距离模糊）：
            // 试过"编辑距离≤1"的模糊匹配，但两字名字下 大雨/下雨 距 丛雨 都只有 1 次替换
            // ⇒ 会把日常词误判成唤醒。所以宁愿把常见的几个显式写出来。
            "从雨", "丛宇", "从宇", "重雨", "勿雨",
        ),'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(W, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 变体表已扩容（含同音误听，并写明为何不做编辑距离模糊）")
else:
    print("· 变体表未命中（可能已改）")

# ② WakeWordSetting
io.open(os.path.join(UI, "WakeWordSetting.kt"), "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame.ui

import android.content.Context
import java.io.File

/**
 * "只回应呼唤"开关的持久化（文件式，照抄项目里 VoiceClient/JevClient 的既有做法）。
 *
 * 为什么用文件而不是把状态提到 MainActivity：这样 ChatScreen 与 SettingsPage 各自读写，
 * **不用改设置状态流**（只动两个文件），风险最小。
 * 默认 **关**：保持现有"按住说话就回应"的手感，不改变既有体验。
 */
object WakeWordSetting {

    private const val FILE = "wake_word.txt"

    fun load(ctx: Context): Boolean = runCatching {
        val f = File(ctx.filesDir, FILE)
        f.isFile && f.readText().trim() == "1"
    }.getOrDefault(false)

    fun save(ctx: Context, on: Boolean) = runCatching {
        File(ctx.filesDir, FILE).writeText(if (on) "1" else "0")
    }.let { }
}
''')
print("✓ 新增 ui/WakeWordSetting.kt")

# ③ ChatScreen 分支
CS = os.path.join(UI, "ChatScreen.kt")
t = io.open(CS, encoding="utf-8").read().replace("\r\n", "\n")
old = """                                        if (txt.isNotBlank()) { input = txt; notice = "离线识别：" + txt }
                                        else notice = "没听清，再说一次？\""""
new = """                                        if (txt.isNotBlank()) {
                                            // 「只回应呼唤」（默认关）：开了以后要先喊她名字才回应。
                                            // 唤醒判定是纯文本（见 WakeWord），零新模型；同音误听写成变体表。
                                            val wakeOn = WakeWordSetting.load(ctx)
                                            if (wakeOn && !WakeWord.isCalling(txt, petId)) {
                                                val hit = WakeWord.hit(txt, petId)
                                                notice = if (hit == null) "她没听见你叫她（试试先说「丛雨」）"
                                                else "唤醒了：$hit"
                                            } else {
                                                input = txt
                                                notice = "离线识别：" + txt
                                            }
                                        } else notice = "没听清，再说一次？\""""
if old in t:
    t = t.replace(old, new, 1)
    io.open(CS, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ ChatScreen 已接「只回应呼唤」分支")
else:
    print("✗ ChatScreen 锚点未命中")
    sys.exit(1)

# ④ SettingsPage 开关行
SP = os.path.join(UI, "SettingsPage.kt")
t = io.open(SP, encoding="utf-8").read().replace("\r\n", "\n")
old = """    Row2("朗读", if (ttsOn) "开" else "关", Icons.Default.VolumeUp, text, sub) { onToggleTts() }"""
new = """    Row2("朗读", if (ttsOn) "开" else "关", Icons.Default.VolumeUp, text, sub) { onToggleTts() }
    // 「只回应呼唤」：默认关（保持"按住说话就回应"的手感）；开=要先喊她名字才回应
    var wakeOn by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(WakeWordSetting.load(vctx)) }
    Row2("只回应呼唤", if (wakeOn) "开（先喊「丛雨」）" else "关", Icons.Default.Mic, text, sub) {
        wakeOn = !wakeOn
        WakeWordSetting.save(vctx, wakeOn)
    }"""
if old in t:
    t = t.replace(old, new, 1)
    io.open(SP, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ SettingsPage 已加「只回应呼唤」开关行")
else:
    print("✗ SettingsPage 锚点未命中")
    sys.exit(1)

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
        m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        if m:
            tot += int(m.group(1)); fail += int(m.group(2)) + int(m.group(3))
print("   合计 %d 个用例，失败 %d" % (tot, fail))
if fail:
    sys.exit(1)
r2 = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                    cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=ENV, timeout=7200)
o2 = (r2.stdout or "") + (r2.stderr or "")
print("   release: " + next((l for l in o2.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o2.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:220])
if r2.returncode != 0:
    print("✗ 未提交")
    sys.exit(1)

MSG = """feat(stt): 「只回应呼唤」接线（默认关）+ 变体表扩容；并记录"为何不做编辑距离模糊"

一、接线（只动两个文件，不碰设置状态流）：
    · 新增 ui/WakeWordSetting.kt：文件式持久化（照抄项目里 VoiceClient/JevClient 的既有做法），
      **默认关** —— 保持现有"按住说话就回应"的手感，不改既有体验；
    · ChatScreen 长按录音识别之后加一条分支：开着时先 WakeWord.isCalling() 判断，
      没喊名字就提示"她没听见你叫她（试试先说「丛雨」）"、不把文本填进输入框；
    · SettingsPage 加「只回应呼唤」开关行（自己读写设置，无需新增参数）。

二、变体表扩容 + 记录一个设计取舍：
    · 增加同音/近音误听：从雨、丛宇、从宇、重雨、勿雨（加上原有的 村雨、ムラサメ、むらさめ…）；
    · **不采用"编辑距离≤1"的模糊匹配**：两字名字下，"大雨""下雨"距"丛雨"都只有 1 次替换，
      会把日常词误判成唤醒。与其引入误唤醒，不如把常见误听显式列出（可审计、可回滚）。

三、诚实标注：真机未验证（唤醒命中率、提示文案手感需上机看）；开关默认关，
    所以即使有问题也不会影响现有语音流程。
"""
p = os.path.join(MAP, "_msg_wake2.txt")
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
