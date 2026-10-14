# -*- coding: utf-8 -*-
"""核实 PPT 第 21 页「互动：从看着你到看懂你」的三条主张，在手机端代码里到底实现到哪一步：
   A. 手部 21 关键点检测（MediaPipe HandLandmarker）→ 相机帧 → 关键点 → 命中她 → 反应
   B. 视线跟随：关键点换算到屏幕后**驱动 3D 角色的视线目标**  ← 主人质疑的就是这条
   C. 三个手势：捏合=捏脸 / 握拳 / 挥手，各自独立去抖
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"

if not os.path.isdir(REPO):
    print("✗ 找不到 chatter 仓库：%s" % REPO)
    sys.exit(1)

print("=== ① 手部/手势相关文件 ===")
PAT_HAND = re.compile(r"hand|landmark|gesture|pinch|wave|fist|捏|握拳|挥手", re.I)
hits = []
for dp, dn, fn in os.walk(REPO):
    if any(s in dp for s in (".git", "build", ".gradle", ".idea", "\\libs")):
        continue
    for f in fn:
        if not f.endswith((".kt", ".java", ".xml", ".md")):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, REPO)
        if PAT_HAND.search(rel):
            sz = os.path.getsize(p)
            hits.append((sz, rel))
hits.sort(reverse=True)
for sz, rel in hits[:22]:
    print("   %8.1f KB  %s" % (sz / 1024, rel[:96]))

print()
print("=== ② 3D / AR / 渲染相关 ===")
PAT_3D = re.compile(r"SceneView|Filament|arcore|arcore|glb|gltf|model3d|Model3D|3d|ThreeD|"
                    r"ARCore|arscene|ArScene|sceneview", re.I)
h3 = []
for dp, dn, fn in os.walk(REPO):
    if any(s in dp for s in (".git", "build", ".gradle", ".idea", "\\libs")):
        continue
    for f in fn:
        if not f.endswith((".kt", ".java", ".xml", ".gradle", ".md", ".pro")):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, REPO)
        try:
            t = io.open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if PAT_3D.search(t):
            n = len(PAT_3D.findall(t))
            h3.append((n, os.path.getsize(p), rel))
h3.sort(reverse=True)
for n, sz, rel in h3[:18]:
    print("   %3d 处  %8.1f KB  %s" % (n, sz / 1024, rel[:92]))

print()
print("=== ③ 关键：手部关键点**有没有驱动 3D 模型**（找两者同时出现的文件）===")
BOTH = []
for dp, dn, fn in os.walk(REPO):
    if any(s in dp for s in (".git", "build", ".gradle", ".idea", "\\libs")):
        continue
    for f in fn:
        if not f.endswith((".kt", ".java")):
            continue
        p = os.path.join(dp, f)
        try:
            t = io.open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        has_hand = re.search(r"HandLandmarker|handLandmark|landmarks|gesture", t, re.I)
        has_3d = re.search(r"SceneView|Filament|ModelNode|model3d|glb|ARCore|Scene", t, re.I)
        if has_hand and has_3d:
            rel = os.path.relpath(p, REPO)
            BOTH.append((os.path.getsize(p), rel, t))
            print("   ★ %s（%d B）" % (rel, os.path.getsize(p)))
            # 打印两者各自出现的行，看有没有真的连起来
            for i, l in enumerate(t.split("\n"), 1):
                if re.search(r"HandLandmarker|handLandmark|landmarks|gesture|eye|look|视线|"
                             r"SceneView|ModelNode|Filament|model3d", l, re.I):
                    print("        %5d| %s" % (i, l.strip()[:104]))
if not BOTH:
    print("   ✗ **没有任何文件同时涉及手部关键点与 3D 渲染** ⇒ 两者很可能没有连起来")
