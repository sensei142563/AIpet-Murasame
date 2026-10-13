# -*- coding: utf-8 -*-
"""提交《PPT 录屏/截图操作单》。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """docs(ppt): 新增《PPT 录屏/截图操作单》—— 8 张截图 + 5 段录屏，照着点即可

红测试收官（10 个文件 / 381 项全绿）后，转入 PPT 阶段的第一件事：
给用户一份**照抄就能做**的操作单，而不是现场口头讲。

内容：
· 准备：素材目录建议放**仓库外**（E:\\university\\order\\ppt-assets\\，分 shots/ 与 clips/），
  避免大文件进 git；录制工具（Win+G 或 OBS 1080p/30fps，码率 8~12Mbps）；每段单独录。
· 截图 8 张（S1~S8）：封面主图 / 右键菜单全貌 / 换装生效 / 对话 / 状态页四分类 /
  启动器侧栏 / 设置页语音块 / **测试全绿那一行**（附可直接复制的命令）。
  每张都写明"停在哪个画面"和"这张用来说明什么"。
· 录屏 5 段（C1~C5）：她活着 / 换装立即生效 / 会聊天会记事 / 她能操作电脑 / 一键自检全绿。
  每段给操作步骤 + 时长 + 这段要讲的话。
· 录完交接：按汇报PPT规划的四幕结构对号入座 → 生成 .pptx（**中文、不署名**、只留页码）
  → 渲染逐页 PNG 做视觉质检。
· 提醒：素材别提交进仓库；跑测试前先清终端；市场调研部分不需要用户录（文档已备好）。

⚠ 顺带记一次 PowerShell 翻车：用 `@"..."@` here-string 配合 git commit 的 `<<<`（bash 语法）
  直接报 ParserError。本机 shell 是 Windows PowerShell，提交信息一律**写文件 + `git commit -F`**。
"""
p = os.path.join(MAP, "_msg_ppt_sheet.txt")
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
