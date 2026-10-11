# -*- coding: utf-8 -*-
"""收尾：跑全量 JVM 单测（回归）+ 提交透明模式与全部脚本。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

print("=== 回归：JVM 单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if re.search(r"tests completed|BUILD|FAILED", l):
        print("   " + l.strip()[:150])
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
if os.path.isdir(d):
    tot = fail = 0
    for f in sorted(os.listdir(d)):
        if f.endswith(".xml"):
            x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
            m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
            if m:
                tot += int(m.group(1)); fail += int(m.group(2)) + int(m.group(3))
                print("   %-46s tests=%s failures+errors=%s" % (f, m.group(1),
                      int(m.group(2)) + int(m.group(3))))
    print("   合计 %d 个用例，失败 %d" % (tot, fail))

print()
print("=== 提交 ===")
MSG = """feat(3d): VRM 页面支持透明背景（?bg=transparent）—— 3D AR 叠加的前置件（含像素级验证）

目标：把 VRM 叠到相机画面上做成真正的 3D AR。第一步是让页面**真正透明**（否则会盖住相机）。

改动（dev/three-demo/index.html 与 app/src/main/assets/vrm/index.html 两份同步）：
· 新增 `transparentBg`（`?bg=transparent` 查询参数），声明放在 module 脚本**最前面** ——
  踩坑：第一次插在 `const scene` 那行，而 renderer 在更前面就用到它，触发 TDZ
  （Cannot access 'transparentBg' before initialization），页面白屏，靠自诊断的
  document.title=E:err=... 才发现；
· 透明模式下：renderer 用 alpha:true + premultipliedAlpha:false，setClearColor(0,0) 且
  每帧 setClearAlpha(0)，scene.background 不设色，**不加地面与网格**（AR 里地板由相机画面提供），
  html/body 背景置 transparent。

验证（不靠截图 —— CDP 截图会把透明压平成白/黑，第一次就误判了）：
· 改为在页面里直接 `gl.readPixels` 读 WebGL 缓冲：
    不透明（默认）      corner=[32,36,44,255]（深色背景）
    透明（?bg=transparent）corner=[0,0,0,0] ← **alpha=0**，且 window.__bgTransparent=true
  两种模式下 center=[102,69,53,255]（角色头发像素）都在 ⇒ 角色正常渲染、背景正确透明。
· 工具：dev/scripts/vrm_transparent_px.py（可复跑）。

顺带：补上子页面 BackHandler 的自我纠错已在 f9a862d 完成；本轮回归 JVM 单测仍全绿。
"""
p = os.path.join(MAP, "_msg_3dar1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r1 = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (r1.stdout or r1.stderr or "").splitlines()[0][:130])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m",
                     "chore(3d): 透明背景模式的验证脚本（CDP 读 WebGL 像素 alpha）"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:130])
for name, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (name, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
