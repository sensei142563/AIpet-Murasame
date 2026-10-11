# -*- coding: utf-8 -*-
"""① 空矩形改成"反向矩形"（右<左、下<上）② hit() 增加形状合法性判断（双保险）
   ③ 用正则补 screenYOfPoint 的 NaN 契约注释 ④ 跑全量单测 ⑤ 提交"""
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

A = os.path.join(UI, "ArGround.kt")
t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")

# ① 空矩形：右<左、下<上 ⇒ 闭区间判定也不可能命中
t = t.replace("""        if (pixelHeight.isNaN() || pixelHeight <= 0f) {
            val x = centerX
            val y = feetY
            return floatArrayOf(x, y, x, y)
        }""",
              """        if (pixelHeight.isNaN() || pixelHeight <= 0f) {
            // 返回**反向矩形**（右<左、下<上）而不是零面积矩形：
            // 零面积矩形 (x,y,x,y) 在闭区间判定下会让"恰好等于中心"的点命中 ——
            // 这就是我自己写的对抗测试抓到的"幽灵命中"。反向矩形则任何点都不满足。
            return floatArrayOf(centerX, feetY, centerX - 1f, feetY - 1f)
        }""", 1)
print("✓ collisionRect 空矩形改为反向矩形")

# ② hit() 增加形状合法性（双保险，防御任何来源的畸形矩形）
t = t.replace("""    fun hit(rect: FloatArray, x: Float, y: Float): Boolean =
        x >= rect[0] && x <= rect[2] && y >= rect[1] && y <= rect[3]""",
              """    fun hit(rect: FloatArray, x: Float, y: Float): Boolean {
        // 先判形状：右<左或下<上（含 NaN）一律视为"不可命中"。
        // 这样即使别处传来畸形/NaN 矩形，也不会出现幽灵命中。
        if (rect.size < 4) return false
        if (rect.any { it.isNaN() }) return false
        if (rect[2] < rect[0] || rect[3] < rect[1]) return false
        return x >= rect[0] && x <= rect[2] && y >= rect[1] && y <= rect[3]
    }""", 1)
print("✓ hit() 已加形状合法性判断")

# ③ 契约注释（正则，容忍缩进/空白差异）
if "不可投影" not in t:
    t2 = re.sub(r"^([ \t]*)if \(depth <= 1e-4\) return Float\.NaN[ \t]*$",
                r"\1// **契约**：depth ≤ 0（点跑到相机后面 / 视线与地面平行）时返回 NaN，\n"
                r"\1// 表示\u201c此点不可投影\u201d。调用方必须处理 NaN —— 见 charPixelHeightExact\n"
                r"\1// 与 collisionRect 里的显式处理（否则 NaN 会让碰撞盒静默失效）。\n"
                r"\1if (depth <= 1e-4) return Float.NaN", t, count=1, flags=re.M)
    if t2 != t:
        t = t2
        print("✓ 已补 NaN 契约注释")
    else:
        print("· 契约注释锚点仍不匹配（不影响功能）")
io.open(A, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 复核 ===")
src = io.open(A, encoding="utf-8", errors="replace").read()
for k in ("反向矩形", "rect[2] < rect[0]", "不可投影", "return 0f"):
    print("   %-26s %s" % (k, "✓" if k in src else "✗"))

print()
print("=== 全量单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for l in o.splitlines():
    if re.search(r"FAILED|^e: ", l):
        print("   " + l.strip()[:180])
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
tot = fail = 0
rows = []
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if f.endswith(".xml"):
        x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        if m:
            tt = int(m.group(1)); fl = int(m.group(2)) + int(m.group(3))
            tot += tt; fail += fl
            rows.append((f.replace("TEST-com.aipet.murasame.", "").replace(".xml", ""), tt, fl))
for n, tt, fl in rows:
    print("   %-20s tests=%-3d 失败=%d" % (n, tt, fl))
print("   合计 %d 用例，失败 %d" % (tot, fail))
if fail:
    for f in os.listdir(d):
        if f.endswith(".xml"):
            x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
            for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,200})', x):
                print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:180]))
    sys.exit(1)

print()
print("=== release 构建 ===")
r2 = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                    cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=ENV, timeout=7200)
print("   " + next((l for l in ((r2.stdout or "") + (r2.stderr or "")).splitlines()
                    if l.startswith("BUILD")), "(无)"))
if r2.returncode != 0:
    sys.exit(1)

MSG = """fix(ar): 对抗测试抓到的 4 个真问题 + 1 处我自己的错误认知

用极端输入（pitch ±90、视口 0、负时间、畸形矩形）审查自己写的数学件，结果：

真问题（已修）：
  ① HandTouch.toScreen(视口或帧为 0) → (NaN, NaN)
     原因：max(0/0, 0/0) = NaN。⇒ 零尺寸直接返回 (0,0)。
  ② FakeHand.pointAt(负时间) → x=-2211（跑出帧外）
     原因：Kotlin 的 % 对负数返回负数（-123456 % 4000 = -3456），三角波越界。
     ⇒ 改用正模 ((t % p) + p) % p 归一化到 [0,p)。
  ③ NaN 会一路传下去，导致碰撞盒**静默失效**：
     screenYOfPoint 在"不可投影"时有意返回 NaN（这是契约），但
     charPixelHeightExact 直接 feet-head ⇒ NaN；collisionRect 的 coerceAtLeast(1f)
     **对 NaN 无效**（NaN<1f 为 false）⇒ 整个矩形变 NaN ⇒ hit() 永远 false
     ⇒ 抬头/低头到极限时"点她"会静默失灵（真机上就是对着天/地的时候）。
     ⇒ charPixelHeightExact 遇 NaN 返回 0（看不见）；collisionRect 返回空矩形。
  ④ 我修的"空矩形"本身又差点是 bug：写成 (x,y,x,y) 的零面积矩形，在闭区间判定
     （>= 与 <=）下"恰好等于中心"的点仍会命中 ⇒ 幽灵命中。是**新加的对抗测试**当场抓到的。
     ⇒ 改为反向矩形（右<左、下<上），并给 hit() 加形状合法性判断（含 NaN / size<4）双保险。

我自己的错误认知（已改正）：
  · 我原以为"能量法会把恒定直流当成很大声"。实测**不成立**：恒定信号的噪声底等于自身，
    gate = max(0.006, 0.3×3=0.9)，0.3 < 0.9 ⇒ 反而正确拒绝。测试注释已改为事实描述。
  · 我写对抗测试时**没读签名**就写调用（ArGround 全用 Float，screenYOfPoint 参数顺序也不同），
    编译报 10 个错误 ⇒ 全部按 ArGround.kt 的真实签名重写。

契约说明（写进代码注释）：screenYOfPoint 返回 NaN 表示"此点不可投影"，调用方必须处理。

验证：全量单测（含新增 13 个对抗用例）全绿；release 构建通过。
"""
p = os.path.join(MAP, "_msg_adversarial.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", CHAT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
