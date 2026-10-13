# -*- coding: utf-8 -*-
"""提交：恢复「沫子的日常」主题 + 修丛雨头像的 JPEG 冒名问题；并跑自检。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """fix: 恢复「沫子的日常」主题 + 修丛雨头像（JPEG 冒名 .png）

## 一、用户报：「我本地有一套『沫子的日常』视频主题，也不见了」
### 查到的根因
`pcl_launcher/themes/senrenbanka_copy/` 里**只剩** `assets/bg_custom.mp4`（71 MB），
**`theme.json` 不见了** ⇒ 启动器枚举主题时看不到它 ⇒ 主题从列表消失。
`docs/handover/2026-09-24.md:2011` 明确记着：**`senrenbanka_copy` 的名字就是「沫子的日常」**。
（历史提交 `87339bb` 把 `themes/*_copy/` 移出 git 跟踪但"文件保留在磁盘"—— 文件后来在磁盘上丢了。）

### 修法（全部可回溯）
1. 从 git 历史取回原文：`git show c974e6db:pcl_launcher/themes/senrenbanka_copy/theme.json`
   （1348 字节，`name` = 「沫子的日常」，`background` = `{type: video, source: assets/bg_custom.mp4}` ✓）
2. 写回磁盘；并从同源的 `senrenbanka` 复制缺失的 9 个资源（`assets/bg.jpg` + `assets/nav/*.png`）
   —— 代码本来对缺图标会回落（`colors.py:367`），但补齐后才是用户说的"一**套**"。
3. 验证：四个主题现在都能枚举到 ——
   `classic 旧版主题` / `senrenbanka 千恋万花·樱华` / **`senrenbanka_copy 沫子的日常`（video 背景）** / `silicon Silicon 现代`

## 二、用户报：「诺瓦的头像废了，变成乱码了」
### 查证结果：**诺瓦是好的**
```
pets/noir/avatar.png = 货真价实的 PNG ✓（155,988 B）
pet.json: "name": "诺瓦", "avatar": "avatar.png" ✓
全仓"文件名像乱码"的文件：0 个
```
协作者的最新提交 `22ffb37` 正是「诺瓦头像改 PNG（Qt 内置解码，不依赖 JPEG 插件）…修『头像图片没了』」
⇒ **他修的就是诺瓦，而且修对了**。

### 但顺着查出**同一个病还有一处没修**
```
pets/murasame/avatar.png 其实是 **JPEG** ✗（扩展名骗人）
```
⇒ 与诺瓦当初的症状同源（依赖 JPEG 插件，没有就"头像没了/显示异常"）。
**已修（非破坏性）**：原图另存为 `avatar.jpg` 保留，再把 `avatar.png` 写成**真正的 PNG**
（505,052 B）—— `pet.json` 里的 `"avatar": "avatar.png"` **不用改**。
复查全部 6 个角色：`arona/PNG ✓  hiyori/JPEG ✓  murasame/PNG ✓  natsume/PNG ✓  noir/PNG ✓`

### 仍需用户确认
如果看到的坏头像**不是**丛雨，请告知**在哪个界面**（启动器角色卡 / QQ / 微信 / 桌宠立绘）
并给一张截图 —— 文件层面诺瓦确实没问题，我需要现象才能继续定位。

## 三、磁盘：按用户指示**一律不删**
（之前列出的 ~6.16 GB 可回收项**一个都没动**；只做了安全的 `git gc`，已在上一个提交说明。）
"""
p = os.path.join(MAP, "_msg_restore.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))

print()
print("=== 全量自检 ===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n")[-4:]:
    print("   " + l.strip()[:120])
