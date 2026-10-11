# -*- coding: utf-8 -*-
"""让两条不变量同时成立：collisionRect 始终良构；hit() 拒绝零面积/反向/NaN。"""
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

t = t.replace("""            // 返回**反向矩形**（右<左、下<上）而不是零面积矩形：
            // 零面积矩形 (x,y,x,y) 在闭区间判定下会让"恰好等于中心"的点命中 ——
            // 这就是我自己写的对抗测试抓到的"幽灵命中"。反向矩形则任何点都不满足。
            return floatArrayOf(centerX, feetY, centerX - 1f, feetY - 1f)""",
              """            // 两条不变量要同时成立：
            //   ① 本函数返回的矩形始终"良构"（左≤右、上≤下）；
            //   ② 退化情况（看不见/高度非正/NaN）不能让任何点命中。
            // 做法：这里返回零面积矩形；由 hit() 负责拒绝零面积（零面积本就是退化矩形）。
            // 起因：我第一次写成 (x,y,x,y) 就以为"空"了，但 hit() 用闭区间判定
            // （>= 与 <=），"恰好等于中心"的点仍会命中 —— 是我自己的对抗测试抓到的幽灵命中。
            return floatArrayOf(centerX, feetY, centerX, feetY)""", 1)
print("✓ collisionRect 恢复良构零面积矩形")

t = t.replace("""        if (rect.size < 4) return false
        if (rect.any { it.isNaN() }) return false
        if (rect[2] < rect[0] || rect[3] < rect[1]) return false""",
              """        if (rect.size < 4) return false
        if (rect.any { it.isNaN() }) return false
        // 反向（右<左、下<上）与**零面积**都视为不可命中。
        // 零面积必须排除：闭区间判定下 (x,y,x,y) 会让"恰好等于中心"的点命中（幽灵命中）。
        if (rect[2] <= rect[0] || rect[3] <= rect[1]) return false""", 1)
print("✓ hit() 拒绝零面积（<= 而非 <）")
io.open(A, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 关键行复核 ===")
src = io.open(A, encoding="utf-8", errors="replace").read()
for k in ("return floatArrayOf(centerX, feetY, centerX, feetY)",
          "if (rect[2] <= rect[0] || rect[3] <= rect[1]) return false",
          "两条不变量要同时成立"):
    print("   %-52s %s" % (k[:50], "✓" if k in src else "✗"))

print()
print("=== 全量单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
tot = fail = 0
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if f.endswith(".xml"):
        x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        if m:
            tt = int(m.group(1)); fl = int(m.group(2)) + int(m.group(3))
            tot += tt; fail += fl
            print("   %-20s tests=%-3d 失败=%d" % (f.replace("TEST-com.aipet.murasame.", "").replace(".xml", ""), tt, fl))
print("   合计 %d 用例，失败 %d" % (tot, fail))
if fail:
    for f in os.listdir(d):
        if f.endswith(".xml"):
            x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
            for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,200})', x):
                print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:180]))
    sys.exit(1)

print()
r2 = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                    cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=ENV, timeout=7200)
print("   release: " + next((l for l in ((r2.stdout or "") + (r2.stderr or "")).splitlines()
                              if l.startswith("BUILD")), "(无)"))
if r2.returncode != 0:
    sys.exit(1)

MSG = """fix(ar): 用"两者兼得"的方式同时满足两条不变量（竞争性断言的正解）

上一提交后，我自己写的两条对抗断言互相矛盾：
  · collision_rect_is_well_formed_for_absurd_heights 要求矩形**良构**（左≤右、上≤下）；
  · no_ghost_hits_when_she_is_not_projectable 要求退化情况**不命中任何点**。
我把退化矩形写成"反向矩形"（右<左）后，前者失败了。

正解不是二选一，而是把责任分开：
  · collisionRect **始终**返回良构矩形；退化时返回零面积 (x,y,x,y)；
  · hit() 负责把"反向"与"**零面积**"都判为不可命中 —— 注意必须是 `<=` 而不是 `<`：
    闭区间判定下 (x,y,x,y) 会让"恰好等于中心"的那个点命中（这正是幽灵命中的来源）。

顺带记录：这已是本轮第 3 次由**对抗测试**（而不是正常路径测试）抓到我自己的错：
  ① toScreen 视口 0 → NaN；② FakeHand 负时间越界；③ NaN 静默污染碰撞盒致"点她"失灵；
  ④ 退化矩形零面积仍可命中；加上我"直流会被能量法误判"的错误认知（实测不成立，已改正）。

验证：全量单测 69 个用例（含 13 个对抗用例）全绿；release 构建通过。
"""
p = os.path.join(MAP, "_msg_adversarial2.txt")
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
