# -*- coding: utf-8 -*-
"""修对抗测试暴露的 4 个真 bug + 改正我对直流信号的错误判断。"""
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
TESTDIR = os.path.join(CHAT, "app/src/test/java/com/aipet/murasame")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① screenYOfPoint：深度近 0 时不要 NaN ----------
A = os.path.join(UI, "ArGround.kt")
t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
print("=== 现有 screenYOfPoint 实现 ===")
i = t.find("fun screenYOfPoint(")
print("\n".join("   " + l for l in t[i:i + 700].split("\n")[:20]))

old = """        val th = Math.toRadians(pitchDeg.toDouble())
        val dist = distanceM.coerceAtLeast(0.05f).toDouble()"""
if old in t and "EPS_DEPTH" not in t:
    t = t.replace(old, """        val th = Math.toRadians(pitchDeg.toDouble())
        val dist = distanceM.coerceAtLeast(0.05f).toDouble()
        val EPS_DEPTH = 1e-6""", 1)
    # 找到 depth 与后面除法所在行，做保护
    m = re.search(r"([ \t]*)val depth = ([^\n]+)\n", t)
    if m:
        ind = m.group(1)
        t = t.replace(m.group(0),
                      "%sval depthRaw = %s\n"
                      "%s// 视线与地面几乎平行时 depth→0，除下去会得到 ±Inf 甚至 NaN。\n"
                      "%s// 这里把深度夹住，保证返回**有限**值（画面外的大数），而不是 NaN。\n"
                      "%sval depth = if (kotlin.math.abs(depthRaw) < EPS_DEPTH)\n"
                      "%s    (if (depthRaw < 0) -EPS_DEPTH else EPS_DEPTH) else depthRaw\n"
                      % (ind, m.group(2), ind, ind, ind, ind), 1)
        print("✓ screenYOfPoint 已加深度保护")
    else:
        print("⚠ 找不到 depth 行")
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
else:
    print("· screenYOfPoint 未改（可能已改）")

# ---------- ③ HandTouch.toScreen：视口/帧为 0 时直接返回 0 ----------
H = os.path.join(UI, "HandTouch.kt")
t = io.open(H, encoding="utf-8").read().replace("\r\n", "\n")
old2 = """        val r = ((rotationDeg % 360) + 360) % 360"""
new2 = """        // 视口或帧为 0 时不能进算法：max(0/0, 0/0) = NaN（对抗测试抓到的真问题）
        if (viewW <= 0 || viewH <= 0 || frameW <= 0 || frameH <= 0) return 0f to 0f
        val r = ((rotationDeg % 360) + 360) % 360"""
if old2 in t and "viewW <= 0" not in t:
    t = t.replace(old2, new2, 1)
    io.open(H, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ HandTouch.toScreen 已加零尺寸保护")
else:
    print("· HandTouch 未改")

# ---------- ④ HandTracker/FakeHand：负时间要归一化 ----------
HT = os.path.join(UI, "HandTracker.kt")
t = io.open(HT, encoding="utf-8").read().replace("\r\n", "\n")
old3 = """        val phase = (nowMs % periodMs).toFloat() / periodMs.toFloat()      // 0..1"""
new3 = """        // Kotlin 的 % 对负数返回负数（-123456 % 4000 = -3456）⇒ 三角波会跑出帧外。
        // 先用"正模"归一化到 [0, period)，保证任何输入都落在帧内（对抗测试抓到）。
        val p = if (periodMs > 0) periodMs else 4000L
        val t0 = ((nowMs % p) + p) % p
        val phase = t0.toFloat() / p.toFloat()                              // 0..1"""
if old3 in t:
    t = t.replace(old3, new3, 1)
    io.open(HT, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ FakeHand.pointAt 已用正模归一化")
else:
    print("· FakeHand 未改")

# ---------- ⑤ 改正测试里对直流的错误说明 ----------
T = os.path.join(TESTDIR, "AdversarialTest.kt")
t = io.open(T, encoding="utf-8").read().replace("\r\n", "\n")
t = t.replace("""        // 恒定直流不是声音，只是偏移。能量法只看 RMS ⇒ 会把直流当成"很大声"，
        // 这正是本测试要暴露的问题（对照：Silero 模型能正确拒绝）。""",
              """        // 恒定直流不是声音，只是偏移。
        // 我原本以为"能量法会把直流当很大声" —— 实测**不成立**：恒定信号的噪声底等于自身，
        // gate = max(0.006, 0.3×3=0.9)，0.3 < 0.9 ⇒ 反而被正确拒绝。这里记为回归测试。""", 1)
io.open(T, "w", encoding="utf-8", newline="\n").write(t)
print("✓ 已改正测试里对直流信号的错误说明")

print()
print("=== 关键行复核 ===")
for f, keys in ((A, ["EPS_DEPTH", "depthRaw"]), (H, ["viewW <= 0"]),
                (HT, ["正模", "t0"]), (T, ["实测**不成立**"])):
    tt = io.open(f, encoding="utf-8", errors="replace").read()
    print("   %-18s %s" % (os.path.basename(f), " ".join("%s%s" % (k, "✓" if k in tt else "✗") for k in keys)))

print()
print("=== 跑对抗测试（应全绿）===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.AdversarialTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
for l in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:180])
p2 = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.AdversarialTest.xml")
if os.path.isfile(p2):
    x = io.open(p2, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   AdversarialTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,240})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:220]))
