# -*- coding: utf-8 -*-
"""提交 2D→3D 路线文档与可行性探针。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """docs(3d): 2D→3D 路线调研（拿模型的三条路线 + 安卓渲染的两条路线，含依赖实测）

用户问："最后想想怎么2D转3D，我听说是有网站工具的"。本次给出可执行路线而非泛谈：

结论：
  · Live2D 立绘**不能**自动转 3D（2D 网格变形 vs 3D 拓扑蒙皮，不可逆），双轨（D4）只能各做一套；
  · 拿模型：A) VRoid Studio 手工出 VRM（免费、自带骨骼/表情、动漫脸可控）← 推荐先做；
            B) 网站类 AI（Meshy 等，几分钟出网格，适合探路；动漫脸与绑骨要另做，逐项未验证）；
            C) 本地开源（Hunyuan3D-2 / TripoSR / InstantMesh，同档，吃显存）；
  · 安卓渲染：1) WebView + three.js + @pixiv/three-vrm（最快，VRM 语义现成）；
              2) SceneView / Filament 原生（长期做 AR；VRM 语义与 MToon 要自己补）。

实测取证（dev/scripts/probe_3d.py，可复跑）：
  · Maven Central：io.github.sceneview:sceneview **2.3.0**、arsceneview **2.3.0**、
    com.google.android.filament:filament-android **1.71.5** 均可取；
  · npm：three **0.186.1**、@pixiv/three-vrm **3.5.5** 均可取；
  · 本机/手机仓库：VRM/glb/gltf/fbx/pmx 资产 **0 个**，chatter 的 gradle 里 3D/AR 依赖 **0 处**
    ⇒ 第一步不是写渲染，而是**先拿到一个能动的 .vrm**。

文档：dev/docs/2D转3D路线-2026-10.md（含 M1–M5 里程碑、与"识别地板/碰撞箱/动捕/手部互动"的衔接、
      未验证清单 5 条、参考链接）。放在 dev/docs/，未动 docs/plan/ 的既有结构。
"""
p = os.path.join(MAP, "_msg_3d1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("桌面仓:", (r.stdout or r.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
