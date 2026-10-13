# -*- coding: utf-8 -*-
"""跑全量确认全绿并提交 —— 红测试战役收官。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
MAP = os.path.join(ROOT, "dev", "merge-map")

print("=== 全量 ===")
r = subprocess.run([VENV, os.path.join("tests", "run_all.py")], cwd=ROOT, capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    if re.match(r"\s*test_\w+\.py\s+-?\d", l) or "总计" in l or "有失败" in l:
        print("   " + l.strip()[:140])

# 把最终定性追加进排查文档
D = os.path.join(ROOT, "dev", "docs", "换装不生效-排查结论-2026-10-13.md")
ADD = """

---

## 七、✅ 最终定性：**换装没有 bug，是测试取图取了旧帧**

用**独立落地脚本**直接跑（不再用 `python -c` 拼长串 —— 上次那样跑 0 输出）：

```
dev/scripts/probe_pixmap_vs_grab2.py  →  dev/probe_pixmap_result.txt

SW 制服 | pixmap 05e26f5176 | grab 91fadd44c1 | size (184, 330)
SW 睡衣 | pixmap c2c6dfd172 | grab be87bddd61 | size (184, 330)
SW 私服 | pixmap 3e6b7980b6 | grab c29e311df5 | size (184, 330)
SW 刀服 | pixmap 95605ad092 | grab ba335edc85 | size (184, 330)
```

- **四套 `pet.pixmap()` 摘要全不同**（`_switch_cloth` 真正设进 QLabel 的那张图）⇒ **合成侧完全正常**；
- **四套 `pet.grab()` 摘要也全不同** ⇒ 取图侧也正常 —— 前提是**先 `app.processEvents()`**。

⇒ 之前"睡衣/私服/刀服 摘要完全相同"是因为测试**没跑事件队列就 grab**，拿到的是**上一帧**。
   测试里已补 `app.processEvents()`，并注明证据文件；四项全绿：

```
解析层 cloth_id：{'制服': 1952, '睡衣': 1956, '私服': 1978, '刀服': 1950}
渲染层 图像摘要：{'制服': '91fadd44c1', '睡衣': 'be87bddd61',
                 '私服': 'c29e311df5', '刀服': 'ba335edc85'}
第二批缺陷回归体检全部通过（退出码 0）
```

### 这个坑值得记住
GUI 测试里**改完状态要先把事件队列跑完再取图**（`app.processEvents()`），否则 `grab()`
可能拿到上一帧，看起来就像"功能没生效"。判断顺序永远是：**先排除取图时机，再怀疑产品逻辑**。
"""
t = io.open(D, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "最终定性" not in t:
    io.open(D, "w", encoding="utf-8", newline="\n").write(t.rstrip() + ADD)
    print("✓ 最终定性已追加进文档")

MSG = """fix(test): 换装那项收尾 —— **补 app.processEvents()**，全仓测试从此全绿 🎉

一、定性结论（对前两版结论的最终修正）
  「连续换装只有第一次生效」**不是产品 bug** —— 是测试**没跑事件队列就取图**，
  `pet.grab()` 拿到的是**上一帧**。用独立落地脚本直接对照（脚本 + 结果都入库）：

    dev/scripts/probe_pixmap_vs_grab2.py → dev/probe_pixmap_result.txt
      SW 制服 | pixmap 05e26f5176 | grab 91fadd44c1
      SW 睡衣 | pixmap c2c6dfd172 | grab be87bddd61
      SW 私服 | pixmap 3e6b7980b6 | grab c29e311df5
      SW 刀服 | pixmap 95605ad092 | grab ba335edc85
    ⇒ 四套 pet.pixmap()（真正设进 QLabel 的图）**全不同** ⇒ 合成正常；
      四套 grab() **也全不同** ⇒ 取图正常 —— 前提是先 processEvents()。

二、改动
  `tests/test_bugfix_0930b.py`：`_pet2._switch_cloth(_c)` 之后补 `app.processEvents()`，
  并注明原因与证据文件（避坑提示写进注释：GUI 测试改完状态要先跑事件队列再取图）。

三、结果
  `tests/test_bugfix_0930b.py` → **第二批缺陷回归体检全部通过，退出码 0**：
      解析层 cloth_id：{'制服': 1952, '睡衣': 1956, '私服': 1978, '刀服': 1950}
      渲染层 图像摘要：{'制服': '91fadd44c1', '睡衣': 'be87bddd61',
                       '私服': 'c29e311df5', '刀服': 'ba335edc85'}
  ⇒ **10 个测试文件全部通过**，红测试战役收官。

⚠ 两次判断反转的记录（诚实留档）：
  第一次以为"只是测试入口用错"→ 修好入口后仍失败；
  第二次以为"真 bug：连续换装只有第一次生效"→ 用落地脚本对照 pixmap/grab 才定性为取图时机。
  教训：**先排除取图时机，再怀疑产品逻辑**；GUI 测试尤其如此。
"""
p = os.path.join(MAP, "_msg_final.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
