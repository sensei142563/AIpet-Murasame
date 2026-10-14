# -*- coding: utf-8 -*-
"""提交：把用户截图贴进 deck（24 页 / 15 图 / 24 讲稿）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """build(ppt): 把用户截图贴进 deck —— 24 页 / 15 张图 / 24 段讲稿

## 素材（用户放在 E:\\university\\order\\python\\pet\\新建文件夹）
盘点出 **22 张图、0 段视频**：
- 手机竖图 9 张（chatter 主页 / AR-3D 实景 ×2 / IM 聊天 6 张）
- 桌面横图 7 张（启动器：设置页×2、插件页、记忆页、**状态页五页签**、总览+模型状态、更新日志）
- 桌宠 6 张（**右键菜单展开** / 深色刀服 / 浅色和服 ×4）
⇒ 已按用途规范命名为 `S1-cover.png` / `S2-menu.png` … 放进 **仓库外** 的
  `E:\\university\\order\\ppt-assets\\shots\\`（未提交进 git）。

## 新增脚本（都写在脚本层，**不动 E:\\Codex\\workflows\\ppt 的引擎文件**）
- `dev/scripts/ppt_add_images.py`：按页映射贴图（页码 1-based，与讲稿/操作单一致）
- `dev/scripts/slide_overview.py`：24 页拼总览图，一次验收全部版式
- `dev/scripts/inventory_user_assets.py`：素材盘点 + 规范命名 + 拼对照图

## 贴了哪 9 页（共 15 张）
```
第 1  页 封面          S1（**去白底**，见下）
第 13 页 她能做的事     S2 菜单 + S4b 聊天
第 14 页 形象与语音     S3a/S3b 两套换装
第 15 页 记忆与陪伴     S5 状态页 + S5b 记忆页
第 16 页 出桌面·上手机  S6 启动器 + S9 手机主页 + S10b 会话列表
第 17 页 工程质量       S8（测试输出）
第 19 页 近期           S9 + S11 AR
第 20 页 互动           S11 AR
第 22 页 远期           S11 AR
```

## 版式迭代（每轮都**渲染看图**才下结论，共 3 轮）
1. 第一版把"下半区等高并排"套**所有页** ⇒ 封面图小得可怜、单张竖图只有 1.3in 宽 ✗
2. 第二版：封面改"右侧大图 + 紧裁白边"，单图放宽到 3.4in ⇒ 封面仍是一块**白方块** ✗
3. 第三版（定稿）：
   - **封面去背**：把**与四边相连**的浅色区域填成透明（不用全局白色键控 —— 她那身浅色
     衣服会被一起吃掉），于是她**站在**深咖封面上；
   - 缩放改为"**先按宽度填满求高度**"，多图不再只会往下缩；
   - **一横一竖搭配不再强制等高**（各自按比例放大、底部对齐）⇒ 第 13 页从"图小 + 大片空白"变正常。

## 补了一张 S8
用户没给"测试全绿"的截图 ⇒ 我用**真实运行输出**渲染了一张终端风格图
（`S8-tests.png`，1400×560，内容未改，只做了终端配色；图内也注明了这一点）。
**若用户想要真·终端截图，随时可替换**（换掉同名文件重跑贴图即可）。

## 验证
```
Deck.pptx：页数 24 / 有讲稿 24 / 图片 15 ✓
render_qc：Rendered 24 slides + Deck.pdf ✓
目视复核：24 页总览 + 13/14/15/19/20/22 重点页 ✓
备份：dev/ppt/out/Deck-文字版.pptx（纯文字版，随时回退）
```

## 仍缺（不硬凑）
- **视频 0 段**：C1~C7 都没录 ⇒ 页面暂不加视频占位（等录了再放"占位框 + 现场播放"）
- 桌面端的**对话框**截图（S4）；手机聊天已能顶上
- 真·S8 终端截图（见上）
"""
p = os.path.join(MAP, "_msg_images.txt")
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
print("=== 产物 ===")
for f in ("Deck.pptx", "Deck.pdf", "Deck-文字版.pptx"):
    p2 = os.path.join(ROOT, "dev", "ppt", "out", f)
    if os.path.isfile(p2):
        print("   %-22s %8.1f KB" % (f, os.path.getsize(p2) / 1024))
