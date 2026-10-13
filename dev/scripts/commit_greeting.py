# -*- coding: utf-8 -*-
"""跑全量并提交开机问候 + reset_cache。"""
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
    if re.match(r"\s*test_\w+\.py\s+-?\d", l) or "总计" in l:
        print("   " + l.strip()[:135])

MSG = """fix(greeting): 开机问候三档收尾 + 补 tool/state.reset_cache()；0930b 从崩在 152 行到跑完全程

一、`main.py`：三种方式（off / voice / chat）其实**本来就都实现了**
  （`_mode == "off"` / `== "voice"` / chat 分支，且 362 行已 import `play_voice_wav`）。
  测试缺的是 chat 那档的注释里要有「**老行为**」这个词（它在备份里就是这么标注的：
  chat = 让模型自己说 = 老行为）。已在 chat 分支补上并写清它为什么是"老行为"。

二、`config.example.json`：补 `startup_greeting_mode: "voice"` 与 `startup_greeting_voice: ""`
  （配合既有的 `care_startup_greeting: "true"`；默认播指定语音、不需要 TTS 服务。）

三、`tool/state.py`：补 `reset_cache()`（备份里有、我们这棵树没有）
  它让 `tests/test_bugfix_0930b.py` 不再在 152 行 `AttributeError` 崩掉。
  ⚠ 如实说明：本模块的状态读取**本来就没有缓存**（`_load()` 每次直接读文件），
    所以这里目前是**空操作**；保留它是为了稳定「换了文件路径 → 重新读」这个调用契约
    （测试与外部脚本都按它调用）。将来若给 `_load()` 加缓存，必须在这里清掉。

四、⚠ 修好崩溃后**又露出 6 项**（原来被 AttributeError 挡住，看不到）——**下一轮处理**，
  其中一条是**很严重的真 bug**：
    ★ 四套衣服（制服/睡衣/私服/刀服）画出来的像素统计**完全相同**（32.6104…×4）
      ⇒ **换装不生效**（这是硬证据，不是观感）。
  另外 4 项同源：`pause_all_ai(stop_voice=…)` 默认值反了（当前默认 True，应为 False），
    连带「点击/拖动不该停语音」「用户输入才该停」「focusInEvent 走默认路径」三处调用点；
  还有 1 项：2D 字体没按 `QFont(字体名, 点数)` 构造。

验证：`tests/test_bugfix_0930b.py` 中「main.py 三种方式都处理了」与「示例配置有
     startup_greeting_mode / _voice」两项 **转 OK**；只因后续 6 项新暴露而整体仍红。
"""
p = os.path.join(MAP, "_msg_greet.txt")
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
