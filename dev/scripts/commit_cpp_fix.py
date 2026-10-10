# -*- coding: utf-8 -*-
"""确认 cpp 改动是否被忽略 → 强制加入并提交（保住 AR 黑底修复）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
CPP = "app/src/main/cpp/LApp/LAppDelegate.cpp"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts"

print("=== 该文件是否被忽略 ===")
r = subprocess.run(["git", "-C", CHAT, "check-ignore", "-v", CPP], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("   check-ignore:", (r.stdout or r.stderr or "(未被忽略)").strip()[:160])
print("=== git status（该文件）===")
r2 = subprocess.run(["git", "-C", CHAT, "status", "--porcelain", "--", CPP], capture_output=True,
                    text=True, encoding="utf-8", errors="replace")
print("   " + (r2.stdout.strip() or "(无变化)"))
print("=== 磁盘上的实际内容 ===")
p = os.path.join(CHAT, CPP)
for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().splitlines(), 1):
    if "glClearColor" in l:
        print("   %5d| %s" % (i, l.strip()[:120]))

# 若被忽略 → 强制加入
if r.returncode == 0:
    print("=== 被忽略 → 强制加入 ===")
    subprocess.run(["git", "-C", CHAT, "add", "-f", CPP], capture_output=True)
    print("   git add -f 完成")
else:
    subprocess.run(["git", "-C", CHAT, "add", CPP], capture_output=True)

MSG = """fix(ar): 去掉 AR 里的黑底 —— LApp 清屏 alpha 1.0 → 0.0（并强制纳入版本管理）

AR 里模型能显示但被一块不透明黑底包住（不是真正的实景叠加）。
定位：app/src/main/cpp/LApp/LAppDelegate.cpp 的每帧清屏为
    glClearColor(0.0f, 0.0f, 0.0f, 1.0f);   // alpha=1 → 不透明黑
（JNI 自己的 Live2DJni.cpp 里其实是 (0,0,0,0)，被这一处覆盖。）
改为 glClearColor(0.0f, 0.0f, 0.0f, 0.0f)。

配合 overlay 时的 setZOrderMediaOverlay(true) + holder.setFormat(TRANSLUCENT)
+ setEGLConfigChooser(8,8,8,8,16,0)，AR 画面现在真正把相机实景透出来。

注意：该目录在 .gitignore 忽略范围内，因此本次用 git add -f 强制纳入，
避免这个关键修复在下次 checkout/清理时丢失（此前 AR 的 Live2D 改动就这样被回滚冲掉过）。

验证：真机截图 dev/shots/ar_verify_transparent.png —— 丛雨全身、背景完全透明、
相机实景（订书钉盒与桌面）从她周围透出。
"""
msg = os.path.join(MAP, "_msg_noblack2.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("提交: " + (r3.stdout or r3.stderr or "").splitlines()[0][:120])
print("未推送: " + subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                  capture_output=True, text=True).stdout.strip() + " 条")
print("工作区:", subprocess.run(["git", "-C", CHAT, "status", "--porcelain"], capture_output=True,
                                text=True).stdout.strip()[:200] or "干净 ✓")
