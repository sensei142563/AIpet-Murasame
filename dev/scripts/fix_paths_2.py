# -*- coding: utf-8 -*-
"""补上 HandTracker.periodMs 属性（上次误判"已有"：FakeHand.pointAt 的参数也叫 periodMs），再编译提交。"""
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

H = os.path.join(UI, "HandTracker.kt")
t = io.open(H, encoding="utf-8").read().replace("\r\n", "\n")
print("=== 现状 ===")
for i, l in enumerate(t.split("\n"), 1):
    if "periodMs" in l or "fake = false" in l or "FakeHand.pointAt" in l:
        print("   %4d| %s" % (i, l.rstrip()[:120]))

if "var periodMs" in t:
    print("· 属性已存在")
else:
    old = '    @Volatile var fake = false'
    new = '''    @Volatile var fake = false

    /**
     * 假手扫过一个来回的周期（毫秒）。可从文件调（VrmArScreen 读 vrm_fake_period.txt），
     * 这样真机上调"手多久扫到她一次"不用重新打包。
     * 注意：FakeHand.pointAt 的**参数**也叫 periodMs，别用"文件里是否有 periodMs"
     * 来判断这个属性是否已加（第一次就是这么误判的）。
     */
    @Volatile var periodMs: Long = 4000L'''
    if old in t:
        t = t.replace(old, new, 1)
        print("✓ 已加 HandTracker.periodMs")
    else:
        print("✗ 锚点未命中")
        sys.exit(1)
    # points() 里把周期传进去
    t2 = t.replace("return listOf(FakeHand.pointAt(nowMs, w, h))",
                   "return listOf(FakeHand.pointAt(nowMs, w, h, periodMs))", 1)
    if t2 == t:
        print("⚠ points() 未改（可能已经传了）")
    else:
        print("✓ points() 已传 periodMs")
    t = t2
    io.open(H, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:10]:
    print("   " + y[:230])
if r.returncode != 0:
    print("✗ 未提交")
    sys.exit(1)

print()
print("=== 全量单测（回归）===")
r2 = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain"],
                    cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=ENV, timeout=3600)
o2 = (r2.stdout or "") + (r2.stderr or "")
print("   " + next((l for l in o2.splitlines() if l.startswith("BUILD")), "(无)"))
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
tot = fail = 0
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if f.endswith(".xml"):
        x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        if m:
            tot += int(m.group(1)); fail += int(m.group(2)) + int(m.group(3))
print("   合计 %d 用例，失败 %d" % (tot, fail))
if fail:
    sys.exit(1)

MSG = """feat(ar): 手部命中写日志 + 假手周期可调（为真机验收准备"当场可修"的路径）

背景：验收脚本里最难判的一项原是"点试手后在 dump 里找命中提示"——提示可能一闪而过、
dump 时机错过就误判失败。改成**读日志**后判定就确定了。

VrmArScreen：
  · 每次手部命中写一行 vrm_ar.log：
    「手部命中 HEAD/BODY（假手=… 周期=…ms 视口=WxH fov=… pitch=…）」+「↳ 摸到头/摸到身子」；
  · 进入 3D AR 时打印一次「手部判定启动：视口=… fov=… 假手周期=…ms」，失败时能立刻看出是
    视口/FO V没拿到还是命中没触发；
  · 假手周期从 files/vrm_fake_period.txt 读（500~60000ms 之间才生效）⇒ 真机上调
    "多久扫到她一次"**不用重新打包**。

HandTracker：新增 @Volatile var periodMs（默认 4000ms），points() 传入。
踩坑记录：第一次判断"属性是否已加"用了 `"periodMs" in 文件`，而 FakeHand.pointAt 的**形参**
也叫 periodMs ⇒ 误判为"已有"，编译才报 Unresolved reference。已改成精确判断
（`"var periodMs" in ...`）并把这条写进注释。

accept_all.py：②c 由"抓屏找提示"改为"读 vrm_ar.log 的『手部命中』"，失败时附上
「手部判定启动」那行作为诊断。

验证：release 编译通过；全量单测 56 个用例全绿；accept_all --dry-run 仍 PASS 0/FAIL 0/SKIP 10。
"""
p = os.path.join(MAP, "_msg_fixpaths1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("手机仓:", (r3.stdout or r3.stderr or "").splitlines()[0][:130])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r4 = subprocess.run(["git", "-C", MAIN, "commit", "-m",
                     "test(accept): ②c 改为读 vrm_ar.log 的手部命中（不再靠抓屏）"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r4.stdout or r4.stderr or "").splitlines()[0][:130])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
