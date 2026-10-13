# -*- coding: utf-8 -*-
"""在 chatter 仓提交"捏合接进 AR 交互"。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"

MSG = """feat(hand): 捏合接进 AR 交互 + 显式固定"命中只用食指"（消除一处隐性行为变化）

## 一、先修一处**隐性行为变化**（比新功能更要紧）
上一提交为了让捏合能用，把检测器输出从 1 个点改成 `[食指, 拇指]`。但 `VrmArScreen` 里
判定"碰到她"是 `for ((lx, ly) in pts)` —— 于是**拇指也顺带参与了命中判定**。
那不是这次要改的东西，属于"顺手改了别人不知道的行为"。
⇒ 现在显式写成 `val hitPts = listOf(pts.first())`，并注明：命中只用 **[0] 食指指尖**，
   与接真检测器之前**完全一致**；拇指的位置另有用途（捏合）。

## 二、捏合（捏脸）接进交互
- `VrmArScreen`：新增**独立的**去抖器 `HandGesture.Latch(needFrames = 3, coolingFrames = 20)`。
  为什么不跟 `latch` 共用：共用计数会让"捏一下"被当成"碰一次"，两个动作互相顶掉。
- 每帧算 `HandGesture.pinchRatio(pts, frameW, frameH)`，过阈值且去抖通过 ⇒
  `webRef.evaluateJavascript("window.__pinch && window.__pinch()")`，
  并**写一条日志**（`捏合触发 ratio=… 阈值=… 帧=…`）—— 验收脚本可以直接读日志，
  不用去 dump 里抓一闪而过的提示（沿用命中那条的既有做法）。
- 两者互不影响：手可以既没碰到她又捏了一下。

## 三、验证
```
[assembleDebug]     BUILD SUCCESSFUL in 39s
[testDebugUnitTest] BUILD SUCCESSFUL in 30s        （145 个单测仍全绿）
```
相关行已逐条复核：
```
170| val latch  = HandTouch.Latch(needFrames = 3, coolingFrames = 12)
173| val pinch  = HandGesture.Latch(needFrames = 3, coolingFrames = 20)
201| val hitPts = listOf(pts.first())
210| val pinchRatio = HandGesture.pinchRatio(pts, HandTracker.frameW, HandTracker.frameH)
211| if (pinch.feed(pinchRatio)) { … window.__pinch() … }
```

## 四、踩坑记录
第一次插入捏合声明时，我按 16 空格写锚点，而真实缩进是 **8 空格** ⇒ 声明没插进去，
随即报 `Unresolved reference 'pinch'`。教训同前几轮：**改别人的文件前先把锚点行的
真实缩进打印出来（repr）**，不要凭印象写缩进。

## 五、还差什么（诚实）
`window.__pinch()` 由 WebView 里的 3D 页面实现 —— 也就是说"捏了之后她做什么反应"
还取决于那边的 JS 有没有这个钩子。下一步：确认/补上 `__pinch` 的实现（或在 JS 侧退化为
"切一个表情"），然后真机上关掉「试手」用真手验一次。
"""
p = os.path.join(MAP, "_msg_pinch_wire.txt")
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
