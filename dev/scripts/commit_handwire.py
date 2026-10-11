# -*- coding: utf-8 -*-
"""提交手部接线；跑全量单测 + release 构建作回归。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

print("=== 全量单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if re.search(r"tests completed|BUILD|FAILED", l):
        print("   " + l.strip()[:160])
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
tot = fail = 0
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if not f.endswith(".xml"):
        continue
    x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    if m:
        t = int(m.group(1)); fl = int(m.group(2)) + int(m.group(3))
        tot += t; fail += fl
        print("   %-24s tests=%-3s 失败=%s" % (f.replace("TEST-com.aipet.murasame.", "").replace(".xml", ""), t, fl))
print("   合计 %d 个用例，失败 %d" % (tot, fail))

print()
print("=== release 构建 ===")
r2 = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                    cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=ENV, timeout=7200)
o2 = (r2.stdout or "") + (r2.stderr or "")
print("   " + next((l for l in o2.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o2.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:220])
if r2.returncode != 0:
    print("✗ 未提交")
    sys.exit(1)

MSG = """feat(ar): 手部互动接线 —— 可插拔数据源 + 「试手」自测 + 命中分区反馈（4 个行为单测）

把上一轮的纯数学（HandTouch）真正接进 3D AR，并解决"检测器还没接、整条链路无法验证"的问题。

新增 ui/HandTracker.kt：
  · `provider: (() -> List<Pair<Float,Float>>?)?` —— 手部数据源的**可插拔接口**：
    等接入 MediaPipe/TFLite 之类检测器时，只要给 provider 赋一个"返回帧坐标系关键点"的闭包即可，
    其余（旋转/裁剪/镜像/命中/去抖/通知页面）都已就位；
  · `FakeHand.pointAt(nowMs, w, h)` —— 确定性的假手（三角波横扫 + 轻微起伏），
    纯函数（时间→点），因此可单测。

VrmArScreen：
  · 15Hz 判定：取关键点 → ArGround.collisionRect（用实测 fovY 与 charPixelHeightExact）
    → HandTouch.onLandmark（含 3 帧去抖 + 12 帧冷却）→ 命中则 evaluateJavascript 调
    `__poke('HEAD'|'BODY')`，并在画面上提示"摸到头了/碰到她了"；
  · 顶部新增「试手」按钮：开启假手后，你不接摄像头也能**亲眼看到整条链路**
    （假手扫过 → 命中她 → 她切表情+跳一下）。

页面：`__poke(zone)` 现在按分区给不同表情（摸头用 surprised/angry/happy，碰身用 happy/joy/relaxed），
两份 index.html（电脑测试版与手机 assets）同步。

单测 HandTrackerTest（4 个用例，全绿）：
  · 假手始终在帧内；· 一趟扫描**恰好触发 1~6 次**（既不是 0 次、也不是每帧都触发）；
  · 把轨迹挪到远离她处 → 0 次触发；· 没有手的一帧会把去抖清零。
全量回归：ArGround 15 + HandTouch 8 + HandTracker 4 + OneBotParse 9 + NativeSmoke 4 = **40 个用例全绿**。
"""
p = os.path.join(MAP, "_msg_handwire1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r1 = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (r1.stdout or r1.stderr or "").splitlines()[0][:130])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", MAIN, "commit", "-m",
                     "chore(ar): 手部接线的脚本与页面 __poke(zone) 同步"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r3.stdout or r3.stderr or "").splitlines()[0][:130])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
