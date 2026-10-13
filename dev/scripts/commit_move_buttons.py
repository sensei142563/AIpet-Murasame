# -*- coding: utf-8 -*-
"""提交：把两个预载按钮从顶部行挪进「快捷工具」；并跑自检。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """fix(launcher): 两个「预载」按钮从顶部行挪进「快捷工具」卡片

## 用户原话
"首页的两个预加载模型的模块删了，丑丑的，或者换个地方，放在下面几个板块。"

## 改法（选"换个地方"）
- 顶部动作行：原来 5 个按钮（启动桌宠 / 启动 QQ / 启动微信 / 预载语音 / 预载视觉）→ **只留 3 个启动按钮**；
- 两个预载按钮挪进下面的「快捷工具」卡片，与 立绘工坊 / 桌宠设置 / NapCat WebUI /
  重新扫码登录 / 打开程序目录 / 更新日志 同排；
- 顺手去掉它们各自的 `setMinimumHeight(46)`（那是"主操作按钮"的高度），
  与工具按钮统一，避免挪过去之后仍然突兀。
- 按钮文字保留上一轮加的"（当前角色）"，点击时仍会打印预载的是哪个角色。

## 关于「模型状态似乎不起作用」
查证结论：**不是坏了，是设计使然**。
`silicon_window.py:638-640` 写得很清楚：通义千问（阿里云 DashScope）**没有公开的余额接口**，
所以 `_qwen_balance()` 直接返回固定文案「阿里云无余额接口，控制台查看」；
而 DeepSeek 那条是**真查**（`https://api.deepseek.com/user/balance`）。
用户的 config 是 `model_type=qwen` ⇒ 两行都走 qwen ⇒ 都显示那句固定文案。

⇒ 两行都"像是按钮但点了没反应"（它现在确实是纯 QLabel 文本）。
**待用户确认**要 A 还是 B：
  A. 余额永远不显示（因为阿里云没接口）→ 可改文案为"点此打开控制台"；
  B. 「控制台查看」点了没反应 → 可做成可点链接 + 加"最后检查时间"+「刷新」按钮。
（此改动需界面确认，等用户点头再做——无头环境无法目视验证 GUI。）

## 验证
`py_compile pcl_launcher/silicon_window.py` ✓；全量自检见下。
"""
p = os.path.join(MAP, "_msg_move_buttons.txt")
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
print("=== 全量自检（改了启动器布局）===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n")[-4:]:
    print("   " + l.strip()[:120])
