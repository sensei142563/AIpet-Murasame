# -*- coding: utf-8 -*-
"""提交 agent 任务链的恢复。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """fix(lost): 恢复「agent 任务」整条链 —— test_qt_lifecycle 不再崩，通过项 +24

问题：`test_qt_lifecycle.py` **直接崩**（ValueError: substring not found），
      因为源码里没有 `_run_agent_task` / `_on_agent_done`，也没有 `/agent` 命令分发；
      而 `classes/Worker_class.py` 里连 `AgentWorker` 类都不存在。

证据（对照覆盖前备份 remotes/origin/backup/main-before-overwrite-20261001）：
  · 备份 classes/Worker_class.py 有 `class AgentWorker(QThread)`（56 行），
    本树只有 qwen3_lora / cloud_API / Screen / Camera 四个 worker。
  · 备份 classes/murasame_class.py 有 `_run_agent_task`（含「**同一时间只允许一个 agent 任务**」
    守卫，注释写明理由：它会以主人的身份操作电脑，起第二个 = 两个 agent 同时动这台机器）
    与 `_on_agent_done`（信号回主线程显示结果）。
  · 备份在 `start_thread` 开头有 `/agent ` 分发（先问主人、默认按钮「否」）。
  · `tool/agent_bridge.py` 本树**是有的**（enabled/available/run_task/should_stop/_kill_tree 齐全），
    所以缺的只是上面三块"自包含新增"。

恢复方式（全部从备份原样搬入，逐块校验）：
  ① classes/Worker_class.py     ← 追加 `AgentWorker`（56 行）
  ② classes/murasame_class.py   ← 在 `start_thread` 定义之前插入 `_run_agent_task` / `_on_agent_done`（58 行）
  ③ classes/murasame_class.py   ← 在 `start_thread` 的 docstring 之后插入 `/agent` 分发（8 行）
     ⚠ 注意本树 `start_thread(self, text, role, t=False, no_act=False)` 签名与备份不同（备份无 no_act），
       所以锚点按本树实际签名取；插入时**直接用备份原块**（相对缩进本来就是对的），
       不要"再补一层缩进"——《本轮踩过这个坑》：先多加了 8 空格，第二次又把内部行压平，
       两次都 IndentationError，第三次改用原块才通过。

效果（实测 tests/run_all.py）：
  · test_qt_lifecycle.py：**崩溃 → 23 通过 / 7 失败**（A1 的 6 项源码守卫全绿，
    含「agent 有『同时只跑一个』的守卫，且在弹确认框之前」这条原先崩在这里的检查）
  · 全仓通过项：**225 → 249（+24）**
  · 注意：失败可见数 36 → 43，是因为原先的崩溃把 7 项"藏"住了，现在它们作为可见 FAIL 露出
    （不是新引入的回归）。

仍未通过（下一轮）：test_qt_lifecycle 余 7 项集中在下游行为（守卫返回值、stop_all_workers
三秒内停掉 agent、引用清空、记忆写临时目录、外部进程收尾、QThread 告警、
以及 run.py/main.py 的 `_spawn_console + _watch_child`）。
"""
p = os.path.join(MAP, "_msg_agent.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("桌面仓:", (r.stdout or r.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
