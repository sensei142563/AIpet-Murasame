# -*- coding: utf-8 -*-
"""修两处实现 bug：变体按长度降序匹配；冷却初值用哨兵（否则第一次就被挡）。再跑全量 + 提交。"""
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

W = os.path.join(UI, "WakeWord.kt")
t = io.open(W, encoding="utf-8").read().replace("\r\n", "\n")

# ① 变体按长度降序（更具体的优先命中）
old1 = """    fun variantsOf(petId: String?): List<String> =
        VARIANTS[petId?.lowercase()] ?: VARIANTS.getValue("murasame")"""
new1 = """    fun variantsOf(petId: String?): List<String> =
        (VARIANTS[petId?.lowercase()] ?: VARIANTS.getValue("murasame"))
            // 按【归一化后的长度降序】排：更具体的变体先命中
            //（否则"丛雨丸"会先匹配到"丛雨"，hit() 报出来的就是较短那个）
            .sortedByDescending { normalize(it).length }"""
if old1 in t:
    t = t.replace(old1, new1, 1)
    print("✓ variantsOf 改为按长度降序")

# ② 冷却初值哨兵
old2 = """    class Cooldown(private val cooldownMs: Long = 6000L) {
        private var last = 0L
        fun allow(nowMs: Long, hit: Boolean): Boolean {
            if (!hit) return false
            if (nowMs - last < cooldownMs) return false
            last = nowMs
            return true
        }
        fun reset() { last = 0L }
    }"""
new2 = """    class Cooldown(private val cooldownMs: Long = 6000L) {
        // 初值必须是哨兵，不能用 0：否则"开机后 6 秒内的第一次唤醒"会被自己的冷却挡掉
        //（这是单测抓出来的真 bug —— 这一次是**实现**错，不是测试预期错）
        private var last = Long.MIN_VALUE / 2

        fun allow(nowMs: Long, hit: Boolean): Boolean {
            if (!hit) return false
            if (nowMs - last < cooldownMs) return false
            last = nowMs
            return true
        }

        fun reset() { last = Long.MIN_VALUE / 2 }
    }"""
if old2 in t:
    t = t.replace(old2, new2, 1)
    print("✓ Cooldown 初值改为哨兵")
io.open(W, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 全量单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:170])
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
tot = fail = 0
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if not f.endswith(".xml"):
        continue
    x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    if m:
        tt = int(m.group(1)); fl = int(m.group(2)) + int(m.group(3))
        tot += tt; fail += fl
        print("   %-22s tests=%-3s 失败=%s" % (f.replace("TEST-com.aipet.murasame.", "").replace(".xml", ""), tt, fl))
print("   合计 %d 个用例，失败 %d" % (tot, fail))
if fail:
    sys.exit(1)

r2 = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                    cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=ENV, timeout=7200)
print("   release: " + next((l for l in ((r2.stdout or "") + (r2.stderr or "")).splitlines()
                              if l.startswith("BUILD")), "(无)"))
if r2.returncode != 0:
    sys.exit(1)

MSG = """feat(stt): 唤醒词判定（"叫她名字才回应"）—— 纯文本 + 9 个单测，零新模型

思路：手机已有本地 STT（SenseVoice 0.94）。对"VAD 判定有语音"的那段做一次识别，
再在**文本**上判断有没有喊她 —— 零新模型、零新依赖，而且 STT 误听可以直接写成变体表。

新增 ui/WakeWord.kt：
  · normalize()：全角→半角、去空白、去标点、转小写；
  · 变体表：丛雨/叢雨/**村雨**（实测最易被听成这个）/ムラサメ/むらさめ/murasame/丛雨丸…
    诺瓦/諾瓦/ノワール/noir；
  · isCalling()/hit()：匹配**完整名字子串**（"村里下雨"不含"村雨"⇒不唤醒）；
    变体按归一化长度**降序**匹配，让 hit() 报出最具体的那个；
  · 通用呼叫（"在吗/你在吗/醒醒"）可开关；
  · Cooldown：一次唤醒后若干秒不再放行。

单测 WakeWordTest（9 个用例）—— 这一轮**两个失败都是实现 bug，不是测试预期错**（少见，记录一下）：
  ① hit("丛雨丸…") 原本返回"丛雨"（变体表里短的在前面）⇒ 改成按长度降序，更具体的先命中；
  ② Cooldown 初值 last=0 ⇒ "开机后 6 秒内的第一次唤醒"会被自己的冷却挡掉
     ⇒ 初值改为哨兵 Long.MIN_VALUE/2。这两处都是单测抓出来的真问题。
覆盖：归一化（全角/空格/标点）/ 各种变体唤醒 / **误听容错（村雨→丛雨，有意为之）** /
不含名字的句子不唤醒 / 通用呼叫可关 / 跨角色不误唤醒 / 未知角色回退 / 冷却窗口 / 空输入安全。

未接线（下一步）：把"VAD 有语音 → STT → WakeWord → 才回应"接进语音输入流程，
并给它一个设置开关（默认关，避免改变现有"按住说话就回应"的手感）。
"""
p = os.path.join(MAP, "_msg_wake1.txt")
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
