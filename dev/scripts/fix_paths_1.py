# -*- coding: utf-8 -*-
"""① VrmArScreen：手部命中写日志 + 假手周期可从文件调 + 启动时打印诊断
   ② accept_all.py：②c 改为读 vrm_ar.log 的「手部命中」
   ③ 编译 + dry-run + 提交"""
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

# ---------- ① HandTracker：假手周期可调 ----------
H = os.path.join(UI, "HandTracker.kt")
t = io.open(H, encoding="utf-8").read().replace("\r\n", "\n")
if "periodMs" not in t:
    t = t.replace('''    /** 本帧是否启用了假手（自测模式）。 */
    @Volatile var fake = false''',
                  '''    /** 本帧是否启用了假手（自测模式）。 */
    @Volatile var fake = false

    /**
     * 假手扫过一个来回的周期（毫秒）。可以从文件调（见 VrmArScreen 里的 vrm_fake_period.txt），
     * 这样真机上调"手多久扫到她一次"不用重新打包。
     */
    @Volatile var periodMs: Long = 4000L''', 1)
    t = t.replace('''            return listOf(FakeHand.pointAt(nowMs, w, h))''',
                  '''            return listOf(FakeHand.pointAt(nowMs, w, h, periodMs))''', 1)
    io.open(H, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ HandTracker：新增 periodMs（默认 4000ms）")
else:
    print("· HandTracker 已有 periodMs")

# ---------- ① VrmArScreen ----------
V = os.path.join(UI, "VrmArScreen.kt")
t = io.open(V, encoding="utf-8").read().replace("\r\n", "\n")
if "手部命中" in t:
    print("· VrmArScreen 已有命中日志")
else:
    # 命中日志
    old = """                    triggered?.let { z ->
                        touchHint = if (z == HandTouch.Zone.HEAD) "摸到头了" else "碰到她了\""""
    new = """                    triggered?.let { z ->
                        touchHint = if (z == HandTouch.Zone.HEAD) "摸到头了" else "碰到她了"
                        // 写日志 ⇒ 验收脚本可以直接读日志，不必去 dump 里抓可能一闪而过的提示
                        log("手部命中 %s（假手=%s 周期=%dms 视口=%dx%d fov=%.1f pitch=%.2f）"
                            .format(z.name, fakeHand, HandTracker.periodMs, vw, vh, fovY, pitchDeg))
                        if (z == HandTouch.Zone.HEAD) log("  ↳ 摸到头")
                        else log("  ↳ 摸到身子")"""
    if old in t:
        t = t.replace(old, new, 1)
        print("✓ VrmArScreen：命中写日志")
    else:
        print("✗ 未命中命中块锚点")
        sys.exit(1)
    # 启动一次性诊断 + 读假手周期
    old2 = """        val latch = HandTouch.Latch(needFrames = 3, coolingFrames = 12)"""
    new2 = """        val latch = HandTouch.Latch(needFrames = 3, coolingFrames = 12)
        // 假手周期可从文件调（不用重新打包就能改"多久扫到她一次"）
        runCatching {
            val f = File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "vrm_fake_period.txt")
            if (f.isFile) f.readText().trim().toLongOrNull()?.let {
                if (it in 500L..60000L) HandTracker.periodMs = it
            }
        }
        log("手部判定启动：视口=%dx%d fov=%.1f 假手周期=%dms".format(vw, vh, fovY, HandTracker.periodMs))"""
    if old2 in t:
        t = t.replace(old2, new2, 1)
        print("✓ VrmArScreen：启动打印诊断 + 读假手周期文件")
    else:
        print("⚠ 未命中 latch 锚点（诊断行未加）")
    io.open(V, "w", encoding="utf-8", newline="\n").write(t)

# ---------- ② accept_all.py：②c 改读日志 ----------
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")
s = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
old3 = """        # 试手 → 命中提示
        tap_text_any(dump("a8"), ["试手"])
        time.sleep(8)
        x = dump("a9")
        hit = ("碰到她了" in x) or ("摸到头了" in x) or ("试手：" in x)
        record("②c 手部试手", verdict(hit),
               "命中提示出现" if hit else "未见命中提示（假手可能还没扫到）")"""
new3 = """        # 试手 → 命中（读日志，比抓屏可靠）
        tap_text_any(dump("a8"), ["试手"])
        time.sleep(10)
        lg = read_log("vrm_ar.log")
        hits = [l for l in (lg or "").splitlines() if "手部命中" in l]
        x = dump("a9")
        record("②c 手部试手", verdict(bool(hits)),
               (hits[-1:] or ["(vrm_ar.log 里没有『手部命中』) 试手诊断=" +
                              str([l for l in (lg or "").splitlines() if "手部判定启动" in l][-1:])])[0].strip()[:120])"""
if old3 in s:
    s = s.replace(old3, new3, 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ accept_all.py：②c 改为读 vrm_ar.log 的「手部命中」")
else:
    print("⚠ accept_all.py ②c 锚点未命中（可能已改）")

# ---------- ③ 语法 + 编译 + dry-run ----------
print()
for f in (H, V, A):
    r = subprocess.run([sys.executable, "-c",
                        "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % f],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if f.endswith(".py"):
        print("   语法 %-16s %s" % (os.path.basename(f), "OK" if r.returncode == 0 else
                                    "FAIL " + (r.stderr or "")[:200]))
print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
errs = [x for x in o.splitlines() if x.startswith("e: ")]
for y in errs[:10]:
    print("   " + y[:230])
if r.returncode != 0:
    print("✗ 未提交")
    sys.exit(1)

print()
print("=== accept_all dry-run（确认没被我改坏）===")
r2 = subprocess.run([sys.executable, "-u", A, "--dry-run"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=600,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
i = out.find("=== 汇总 ===")
print(out[i:] if i > 0 else out[-900:])
print("   EXIT:", r2.returncode)

print()
print("=== 关键行复核 ===")
for f, keys in ((V, ["手部命中", "vrm_fake_period.txt", "手部判定启动"]),
                (H, ["periodMs"]), (A, ["手部命中"])):
    tt = io.open(f, encoding="utf-8", errors="replace").read()
    print("   " + os.path.basename(f) + ": " +
          " ".join("%s%s" % (k, "✓" if k in tt else "✗") for k in keys))
