# -*- coding: utf-8 -*-
"""在 chatter 仓提交 __pinch 的 JS 实现，并跑一次构建确认（资源变更不影响构建）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"

MSG = """feat(hand): 补上 window.__pinch —— 捏合这条链终于闭合（捏了真的有反应）

上一提交只到"原生侧调用 `window.__pinch()`"，但 **3D 页面里没有这个钩子** ⇒ 捏了不会有反应。
这一步把它补上，并和已有的 `__poke` **在行为上区分开**。

## 改动（`assets/vrm/index.html`）
新增 `window.__pinch`（与 `__poke` 同风格：入口先查 `window.__vrm`、全程 try/catch、返回 boolean）：
- **区分两个动作**：`__poke`（被戳）是"给表情 + 轻轻一跳"；
  `__pinch`（被捏脸）是"**扭头躲一下 + 身体缩一下**" + 一个偏**抗拒/吃痛**的表情
  （优先 `surprised|angry|pain|sad`，退回 happy，再退回第一个），持续 1.2 s 后复位。
- 作用点更准：优先用 **VRM humanoid 的 `head` 骨骼**
  （`humanoid.getNormalizedBoneNode('head')`）转头 —— 脸是头的动作；
  取不到该骨骼时**退化为整体旋转**，不会因为模型差异就失效。
- 动画用**正弦包络**（起 → 最大 → 回原位），结束一定复位，不留偏移。

## 验证
- **`node --check` 通过**（把 `__pinch` 片段抽出来单独检查 ⇒ `OK`）。
  顺带确认：**本机有 node**，以后 JS 改动都可以这样先过一遍语法，不必等真机。
- 复核页面里的钩子清单（行号）：
  ```
  131  window.__poke
  156  window.__pinch        ← 新增
  186  window.__setFov
  191  window.__setPitch
  198  window.__vrmFeetPx
  219  window.__placeOnGround
  ```
- 本次只动资源（html），不改 Kotlin；`window.__pinch` 的调用方已在上一提交接好。

## 这条链现在是完整的
```
相机帧 → HandDetector(MediaPipe) → HandTracker.provider
  → VrmArScreen：命中判定（只吃食指）+ 捏合判定（拇指↔食指距离、独立去抖）
  → evaluateJavascript("__pinch()") → 3D 页面扭头躲 + 缩一下 + 抗拒表情
```

## 剩下的仍是真机
编译/语法/单测都过了，但"真手捏一下她会不会躲"必须真机上验：
手机插上 → 进 AR → 关掉「试手」→ 手伸过去捏一下 → 看日志有没有 `捏合触发 ratio=…`。
"""
p = os.path.join(MAP, "_msg_pinch_js.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", REPO, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", REPO, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", REPO, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", REPO, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
