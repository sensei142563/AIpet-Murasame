# -*- coding: utf-8 -*-
"""在 ChatScreen 的调用点传入 onGiveUp（系统 TTS 兜底，含语气），再编译提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
CS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(CS, encoding="utf-8").read().replace("\r\n", "\n")
i = t.find("VoiceClient.speak(")
print("=== 调用点原文（前后各几行）===")
print("\n".join("   " + l for l in t[max(0, i - 260):i + 260].split("\n")))

pat = re.compile(
    r'(?P<ind>[ \t]*)if \(!VoiceClient\.speak\(ctx, p, petId = petId\)\) \{\s*\n'
    r'[ \t]*tts\?\.speak\(p, TextToSpeech\.QUEUE_ADD, null, "murasame"\)\s*\n'
    r'[ \t]*\}', re.M)
m = pat.search(t)
if not m:
    print("\n✗ 未命中调用点")
    sys.exit(1)
ind = m.group("ind")
new = (ind + '// 异步路径（电脑合成失败 + 离线未就绪）回来时，用 onGiveUp 通知我们走系统 TTS。\n'
       + ind + '// 没有这个回调的话，speak() 早已 return true，下面的 if 分支永远不会执行 ⇒ **静默无声**\n'
       + ind + '// （实测坑：对着"电脑失败 + 手机离线模型缺失"的场景，一句话都不出声）。\n'
       + ind + 'if (!VoiceClient.speak(ctx, p, petId = petId, onGiveUp = {\n'
       + ind + '        tts?.setPitch(pitch); tts?.setSpeechRate(rate)\n'
       + ind + '        tts?.speak(p, TextToSpeech.QUEUE_ADD, null, "murasame")\n'
       + ind + '    })) {\n'
       + ind + '    tts?.speak(p, TextToSpeech.QUEUE_ADD, null, "murasame")\n'
       + ind + '}')
t = t[:m.start()] + new + t[m.end():]
io.open(CS, "w", encoding="utf-8", newline="\n").write(t)
print("\n✓ 已在 ChatScreen 调用点传入 onGiveUp")

print()
print("=== 编译 + 全量单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "assembleRelease",
                    "--console=plain"], cwd=CHAT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: ") or "FAILED" in l:
        print("   " + l.strip()[:200])
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
tot = fail = 0
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if f.endswith(".xml"):
        x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        m2 = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        if m2:
            tot += int(m2.group(1)); fail += int(m2.group(2)) + int(m2.group(3))
print("   合计 %d 用例，失败 %d；退出码 %d" % (tot, fail, r.returncode))
if r.returncode != 0 or fail:
    sys.exit(1)

MSG = """fix(tts): 修掉两处"静默无声"，并把五层链路的不变量变成可单测的纯函数

对抗/故障注入式审查 TTS 五层降级链（① 台词包 → ② 缓存 → ③ 电脑 F5 → ④ 本机离线 → ⑤ 系统 TTS），
直接读出两个真问题：

① **异步路径永远不触发兜底**（最严重）
   VoiceClient.speak() 里，电脑合成是在 IO 协程里做的，但函数**立刻 return true**；
   于是"电脑合成失败 + 离线 TTS 未就绪"时只写一行日志「本次不出声」，
   而 ChatScreen 里那句 `if (!speak(...)) { 系统TTS }` 永远不会执行 ⇒ **一声不响**（静默无声）。
   这正是链路设计承诺（"任何情况下都要落到系统 TTS"）被违反的地方。
   ⇒ 新增 onGiveUp 回调：彻底没辙时在主线程回调，调用方接系统 TTS；
     并在 ChatScreen 的调用点传入（连语气 pitch/rate 一起设好）。
     若调用方没传，会明确日志告警「本次可能无声」，不再默默失败。

② **缓存/台词包忽略播放结果，坏文件永久留盘**
   两条路径都是 `play(...)` 后无条件 return true。缓存文件损坏（例如写到一半被杀）时：
   本次静默无声，而且该文件**永远不会被删** ⇒ 这句文本以后**每次都放不出声**。
   ⇒ 播放失败即删除该文件并继续降级（台词包副本会重新从 assets 解出）。

顺带把"层序"抽成纯函数 bot/chat/TtsPlan.kt，使不变量可以被单测钉住：
  · steps(hasPacked, pcConfigured, offlineReady) 给出固定顺序 PACKED<CACHE<PC<OFFLINE<SYSTEM；
  · **SYSTEM 永远存在且永远在最后**（调用方永远有兜底）；
  · after(step, …) 保证"每一层失败都有下一层"，到 SYSTEM 为止不再降级；
  · isSane() 自检顺序（缺兜底/顺序颠倒/重复层都会被判否）。
  speak() 在入口做一次 isSane 自检并记日志。

单测 TtsPlanTest（7 个用例）：任意可用性组合下 SYSTEM 都在最后且顺序合法；
全可用时的顺序；无网时仍有两条离线层；**电脑失败且离线未就绪必须落到 SYSTEM**（就是此前无声的现场）；
每一层都有后继；SYSTEM 之后仍是 SYSTEM；isSane 会拒绝坏顺序（空/缺兜底/颠倒/重复）。

验证：全量单测 **87 个用例失败 0**（新增 TtsPlanTest 7）；release 构建通过。
诚实标注：onGiveUp 的真机行为（主线程回调与系统 TTS 接通）需上机确认；
本次改动均在纯逻辑与编排层，未触碰合成/播放实现。
"""
p = os.path.join(MAP, "_msg_tts_chain.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
