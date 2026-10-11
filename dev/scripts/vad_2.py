# -*- coding: utf-8 -*-
"""修 percentile 的测试预期（nearest-rank 定义）+ 在代码里写明该选择，再跑全量单测 + 提交。"""
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

# ① 代码注释写明百分位定义
g = os.path.join(UI, "VadGate.kt")
t = io.open(g, encoding="utf-8").read().replace("\r\n", "\n")
old = "    /** 百分位（p 取 0..1）。 */"
new = """    /**
     * 百分位（p 取 0..1）。用 **nearest-rank**（不做线性插值）：
     * 噪声底宁可偏低（宁可多放几帧过去），安全由 absFloor 兜底 ——
     * 若用插值把噪声底抬高，安静环境下的轻声反而会被门限切掉。
     * （写这条时踩过：我按插值定义写了测试，5 个值的 20 分位期望 0.02，
     *   而 nearest-rank 给出第 1 个值 0.01 —— 是**测试的预期**错了，不是实现。）
     */"""
if old in t and "nearest-rank" not in t:
    t = t.replace(old, new, 1)
    io.open(g, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ VadGate.percentile 注释写明 nearest-rank 定义")

# ② 修测试预期
ts = os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/VadGateTest.kt")
x = io.open(ts, encoding="utf-8").read().replace("\r\n", "\n")
old2 = """        assertEquals(0.02f, VadGate.percentile(v, 0.20f), 0.005f)"""
new2 = """        // nearest-rank：5 个值取 20 分位 → 索引 (5-1)*0.2=0.8 → 取整 0 → 第 1 个值 0.01
        // （这里曾被我按"线性插值"写成 0.02，是实现与预期之争，最终以实现为准并把定义写进注释）
        assertEquals(0.01f, VadGate.percentile(v, 0.20f), 0.001f)
        assertEquals(0.03f, VadGate.percentile(v, 0.50f), 0.001f)"""
if old2 in x:
    x = x.replace(old2, new2, 1)
    io.open(ts, "w", encoding="utf-8", newline="\n").write(x)
    print("✓ 已修测试预期")
else:
    print("· 未命中测试预期行")

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
    xx = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', xx)
    if m:
        tt = int(m.group(1)); fl = int(m.group(2)) + int(m.group(3))
        tot += tt; fail += fl
        print("   %-22s tests=%-3s 失败=%s" % (f.replace("TEST-com.aipet.murasame.", "").replace(".xml", ""), tt, fl))
print("   合计 %d 个用例，失败 %d" % (tot, fail))
if fail:
    sys.exit(1)

print()
print("=== release 构建 ===")
r2 = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                    cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=ENV, timeout=7200)
print("   " + next((l for l in ((r2.stdout or "") + (r2.stderr or "")).splitlines()
                    if l.startswith("BUILD")), "(无)"))
if r2.returncode != 0:
    for y in [z for z in ((r2.stdout or "") + (r2.stderr or "")).splitlines() if z.startswith("e: ")][:8]:
        print("   " + y[:220])
    sys.exit(1)

MSG = """feat(stt): VAD/静音剔除 —— 噪声不再被"编"成一句话（7 个纯计算单测）

上一轮做闸门取证时发现：我那段合成嗡嗡声被 whisper 识别成 "Teksting av Nicolai Winther"。
噪声幻觉对"没说话也发识别请求"的场景很致命（手机语音输入、连续识别都受影响），本次补上。

新增 ui/VadGate.kt（纯计算，可 JVM 单测）：
  · frameRms()：按 20ms 分帧算 RMS；
  · percentile()：**nearest-rank**（不插值）—— 噪声底宁可偏低，安全由 absFloor 兜底；
    若用插值把噪声底抬高，安静环境里的轻声反而会被门限切掉；
  · analyze()：噪声底取各帧 RMS 的 20 百分位；某帧算有声当且仅当
    rms > max(absFloor, noiseRms × relThreshold)；累计语音时长 ≥ minSpeechMs 才算说了话；
    返回裁剪区间（含 150ms padding）；
  · trim()/describe()：裁出语音段、给出一行日志摘要。

接进 OnlineAsr.recognizeWav：读 WAV 后**先过 VAD**，没检测到人声就直接返回空
（于是不会把噪声送去识别，也不会把幻觉出的文字发进对话），日志里留下 VAD 摘要。
识别时只送裁剪后的语音段，顺带省算力、减少边缘幻觉。

单测 VadGateTest（7 个用例）：
  纯静音不算说话 / 静音中的 600ms 突发算说话且被裁短（含 padding）/
  60ms 咔哒因小于 200ms 被拒 / **持续大声噪声不误判**（自适应噪声底的意义）/
  底噪上的语音被检出且主要覆盖语音段 / 百分位 nearest-rank 取值 / 空输入安全。
踩坑（第三次"我的测试预期错了"）：我按线性插值写了 20 分位=0.02，实现给 0.01 ——
以实现为准，并把 nearest-rank 的定义与理由写进代码注释。
"""
p = os.path.join(MAP, "_msg_vad1.txt")
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
