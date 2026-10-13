# -*- coding: utf-8 -*-
"""在 chatter 仓提交"捏合识别 + 单测"。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"

MSG = """feat(hand): 捏合（捏脸）识别 + 9 个单测 —— 不依赖真机即可验证

用户提过的"可互动"里有一条是"识别到在捏脸"。这一步用**已经拿到的两个关键点**做掉它，
不引入任何新模型/新依赖，而且用 JVM 单测钉死，**不需要真机**就能验证。

## 改动
1. `ui/HandDetector.kt`：输出从 1 个点变成 **2 个点** —— `[0] 食指指尖(8)`、`[1] 拇指指尖(4)`。
   ⚠ 顺序是有意义的：`VrmArScreen` 取 `points()[0]` 当"手的位置"做命中判定，
   **保持第一位仍是食指** ⇒ 既有行为一个字都不变。
2. 新增 `ui/HandGesture.kt`（纯计算，不碰相机/UI）：
   · `pinchRatio(points, frameW, frameH)`：拇指-食指距离 ÷ **画面短边**（归一化，
     所以同一个人靠近/远离镜头不会乱跳）；
   · `isPinch(...)`：阈值判定（默认 0.08 ≈ 指尖几乎贴上，含等号）；
   · `Latch`：去抖 —— 连续 3 帧捏住才算一次，之后 15 帧冷却（避免手指微抖连发）。
   边界处理：点不够 / 尺寸为 0 / NaN ⇒ 一律返回 `Float.MAX_VALUE`（= 不可能算作捏合），
   **绝不除零、绝不误判**。
3. 新增 `app/src/test/.../HandGestureTest.kt`：9 个用例。

## 验证（**不是"BUILD SUCCESSFUL"就算过，看了结果 XML**）
```
TEST-com.aipet.murasame.HandGestureTest.xml
    tests=9  failures=0  errors=0  skipped=0
      ✓ 指尖贴合算捏合 / ✓ 手张开不算捏合 / ✓ 边界值恰好等于阈值算捏合（含等号）
      ✓ 归一化用短边而不是长边 / ✓ 点不够时不误判 / ✓ 画面尺寸为0时不除零
      ✓ NaN 输入不会算出捏合 / ✓ 去抖：连续三帧才触发一次，之后进入冷却
      ✓ 去抖：中途松手要重新计数
全部单测汇总：tests=145  failures=0  errors=0   （没弄坏任何既有用例）
```

## 下一步（仍是真机上的事）
把手势接进交互：AR 页面里 `HandGesture.Latch().feed(pinchRatio(...))` 为 true 时，
给它一个反应（例如切表情/触发捏脸反应）。这一步同样可以先在单测层钉死，
再在真机上只调"相机朝向 / 镜像"两个变量 —— 与手部命中那条链路分工一致。
"""
p = os.path.join(MAP, "_msg_gesture.txt")
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
