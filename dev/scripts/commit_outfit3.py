# -*- coding: utf-8 -*-
"""把"四次换装都保存成功"的证据追加进文档并提交。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

D = os.path.join(ROOT, "dev", "docs", "换装不生效-排查结论-2026-10-13.md")
ADD = """

---

## 六、再进一步：**四次换装其实都保存成功了**（缩小到"重画/取图"这一层）

直接抓 `_switch_cloth()` 的日志：

```
[桌宠] 👗 a 立绘已换装: 制服（QQ 立绘同步生效）
[桌宠] 👗 a 立绘已换装: 睡衣（QQ 立绘同步生效）
[桌宠] 👗 a 立绘已换装: 私服（QQ 立绘同步生效）
[桌宠] 👗 a 立绘已换装: 刀服（QQ 立绘同步生效）
[桌宠] 👗 保持当前服装（本句想换 1952 → 沿用 1950）
```

- 前四行 ⇒ **四次换装全部走通并保存**（也说明素材存在性检查、`save_outfit`、`swap_body`
  这几步都没问题）；
- 最后一行是**测试收尾还原原装扮**时触发的「服装粘性」（渲染请求 1952、当前已是 1950 → 沿用），
  属**预期行为**，不是 bug。

⇒ 于是问题被夹到很窄的一段：**保存与图层替换都对，但画出来的像素只有第一次不同**。
下一轮优先查这两个：

1. `_compose_pixmap()` 是否有**按衣服号做的缓存**（换了号却命中旧缓存）；
2. 测试侧的取图方式 —— `pet.grab()` 是否会拿到**上一帧**（必要时先 `app.processEvents()`
   或 `pet.repaint()` 再 grab）。**先排除 2 再改 1**，别把测试问题当产品问题修。
"""
t = io.open(D, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "四次换装其实都保存成功了" not in t:
    io.open(D, "w", encoding="utf-8", newline="\n").write(t.rstrip() + ADD)
    print("✓ 已追加第六节")

MSG = """docs(outfit): 补证据 —— 四次换装其实**都保存成功**，问题夹到「重画/取图」这一层

抓 `_switch_cloth()` 的日志：
    [桌宠] 👗 a 立绘已换装: 制服 / 睡衣 / 私服 / 刀服      ← 四次全部走通并保存 ✓
    [桌宠] 👗 保持当前服装（本句想换 1952 → 沿用 1950）    ← 测试收尾还原装扮时触发的粘性，
                                                            属预期行为，不是 bug
⇒ 排除了"素材存在性检查 / save_outfit / swap_body"这几步；
  问题被夹到：**保存与图层替换都对，但画出来的像素只有第一次不同**。

下一轮按顺序查（先排除测试侧，别把测试问题当产品问题修）：
  1. `pet.grab()` 是否拿到**上一帧**（必要时先 processEvents()/repaint() 再 grab）；
  2. `_compose_pixmap()` 是否有**按衣服号做的缓存**（换了号却命中旧缓存）。

文档：dev/docs/换装不生效-排查结论-2026-10-13.md 追加第六节。
"""
p = os.path.join(MAP, "_msg_outfit3.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
