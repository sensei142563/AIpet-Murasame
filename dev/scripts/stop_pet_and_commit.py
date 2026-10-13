# -*- coding: utf-8 -*-
"""停掉我起的桌宠（避免占着 GPU 还留一份进程），然后提交本轮成果。"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

print("=== ① 停掉桌宠相关进程 ===")
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
                    "Select-Object ProcessId,CommandLine | ConvertTo-Csv -NoTypeInformation"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
killed = 0
for line in (r.stdout or "").splitlines()[1:]:
    f = [x.strip('"') for x in line.split('","')]
    if len(f) >= 2:
        pid, cmd = f[0], f[1]
        if any(k in cmd for k in ("run.py", "main.py", "f5tts_server", "GPT-SoVITS")):
            try:
                subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, timeout=60)
                print("   已停 PID %s" % pid)
                killed += 1
            except Exception as e:
                print("   停 %s 失败: %s" % (pid, e))
time.sleep(2)
r2 = subprocess.run(["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_Process -Filter \"Name like '%python%'\").Count"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
print("   停了 %d 个；剩余 python 进程数: %s" % (killed, (r2.stdout or "").strip()))

MSG = """fix(env): 补上缺失的 comtypes（UIA 静默降级）+ 清 pip 残留 + 本机实跑记录

用户反馈"似乎有一些东西在协作者电脑上可以，咱们电脑不行（全局 Python / GPU 加速）"。
本轮**在本机实测**定位，结果如下（全部可复现，脚本在 dev/scripts/）：

一、真正的差异：comtypes 缺失（这条会静默降级，很难自己发现）
  · `requirements.txt` 里写了 `comtypes`，但**项目 venv 和全局 Python 都没有**。
  · 后果（项目自己的日志）：`tool/uia.py` 报
      [UIA] ⚠ 不可用（ModuleNotFoundError: No module named 'comtypes'）→ 退回模拟键鼠方式
    即精确的 UI Automation 后台控制不可用；`tool/music.py` 也明写"没装 comtypes 只能用系统媒体键"
    （网易云等 CEF 界面的后台控制失效）。
  · 处置：装进项目 venv（comtypes 1.4.17），复验 `comtypes/UIA 可用: True`。
  · 全套依赖体检：`requirements.txt` 28 条，venv 里**只缺这一条**，已补齐。

二、顺手清掉 pip 残留（另一个"本机特有"的噪音）
  · `runtime/venv/Lib/site-packages` 里有 `~orch`、`~umpy`、`~umpy-2.1.3.dist-info`、`~umpy.libs`
    （pip 卸载未删干净的"待删除"标记）⇒ 每次 pip 操作都报 `Ignoring invalid distribution -umpy`。
  · 处置：**移到** `dev/tmp/venv_junk/`（不删、留档）⇒ 告警清零。

三、发现但**未擅自修**的冲突（留给用户定）
  · `pip check`：`opencv-python 4.12.0.88` 要求 `numpy>=2`，而实际 `numpy 1.26.4`
    （`requirements.txt` 明确 `numpy>=1.26.4,<2`）。改 numpy 风险大，故只记录不动作。

四、澄清一个"看起来像 bug 其实不是"的现象
  · `run.py` 在 Windows 上会看到 venv 的 python.exe 只占 4MB、1 线程，并拉起一个 base python 子进程
    —— 这是 virtualenv 转发器的正常行为；子进程内 `sys.executable`/`sys.prefix` 都正确指向 venv、
    `torch` 也确实来自 venv。**venv 工作正常**，不需要"修"。

五、本机实跑记录（桌宠真的能跑）
  · `runtime\\venv\\Scripts\\python.exe run.py` 启动成功；28565 由 main.py 监听、9881 由 F5-TTS 监听、
    GPT-SoVITS 常驻；立绘正常渲染（dev/shots/pet_locate.png），对话管线在跑
    （qwen-talk/portrait/emotion/translate → gpt-sovits-tts）。
  · 如实标注未验证项：**右键菜单的实机截图没拿到** —— 合成右键被她当成左键/触摸
    （她弹了「【丛雨】思考中…」），只能由用户用真实鼠标确认；菜单修复本身已由代码与离屏渲染验证。

六、文档
  · 新增 `dev/docs/环境差异-协作者机器vs本机.md`（结论表 + 可复现命令 + 给协作者的同步建议）。
"""
p = os.path.join(MAP, "_msg_env.txt")
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
