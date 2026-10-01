# -*- coding: utf-8 -*-
"""后台线程体检：起得来，也要**停得掉**；点了启动"秒退"时界面必须说话。

覆盖两件（合并自 2026-09-29 的两个审计探针）：

A. **线程收尾**（`classes/murasame_class.py` + `tool/agent_bridge.py`）
   真实案例：`self._agent_worker` 只有赋值、**没有任何人能停**，而 agent 会**以主人身份操作电脑**
   （起外部进程，超时默认 600 秒）→ 关掉桌宠后它还能继续操作电脑最多 10 分钟；
   而且 `requestInterruption()` 一开始**根本没用**（`run_task` 的等待循环只认超时，
   实测 `wait(3000)` 会整整等满 3 秒）。现在取消会立刻 `_kill_tree`（本文件用**真外部进程**验证）。

B. **启动秒退要说**（`pcl_launcher/silicon_window.py`）
   真实案例（用户原话"点启动微信秒卡退"）：控制台一闪就关、也没人回查子进程死活。
   现在 Windows 上套 `cmd /k`（控制台留在屏幕上）+ `_watch_child()` 1.8 秒后回查并说明退出码。

用法：`python tests/test_qt_lifecycle.py`（需要 PyQt5；用 offscreen，不会真的开窗口）
"""
import io
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIPET_NO_SPAWN", "1")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FAILS = []


def check(name, cond, extra=""):
    if cond:
        print("  [OK]   %s %s" % (name, extra))
    else:
        print("  [FAIL] %s %s" % (name, extra))
        FAILS.append(name)


def read(rel):
    return io.open(os.path.join(REPO, rel), encoding="utf-8", errors="replace").read()


print("== A1) 源码守卫：收尾方法 / 退出钩子 / 单实例 / 取消回调 ==")
mc = read("classes/murasame_class.py")
check("有 stop_agent_worker（interrupt + quit + wait）",
      "def stop_agent_worker" in mc and "w.wait(3000)" in mc)
check("有 stop_all_workers（截图/摄像头/agent/聊天都收）",
      "def stop_all_workers" in mc and all(('"%s"' % n) in mc for n in
                                          ("stop_screenshot_worker", "stop_camera_worker",
                                           "stop_agent_worker")))
check("agent 有「同时只跑一个」的守卫，且在弹确认框之前",
      mc.index("我还在做上一件事") < mc.index("要让她去做吗"))
mj = read("main.py")
check("退出时挂上 stop_all_workers（aboutToQuit），且在保存状态之后",
      "aboutToQuit.connect(lambda: pet.stop_all_workers())" in mj
      and mj.index("save_window_pos(pet)") < mj.index("pet.stop_all_workers()"))
ab = read("tool/agent_bridge.py")
check("run_task 支持 should_stop 且取消时杀进程树",
      "should_stop=None" in ab and "if cancelled:" in ab and "_kill_tree(proc)" in ab)
check("AgentWorker 把线程中断接到 should_stop",
      "should_stop=lambda: self.isInterruptionRequested()" in read("classes/Worker_class.py"))

print("== A2) 行为：真对象 + 真 AgentWorker + 真外部进程被取消 ==")
CODE = r'''
import os, sys, time, subprocess, tempfile
sys.path.insert(0, %r)
try:
    sys.stdout.reconfigure(line_buffering=True)   # ⚠ 最后 os._exit()，不缓冲会丢输出
except Exception:
    pass
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["AIPET_NO_SPAWN"] = "1"
pidfile = os.path.join(tempfile.gettempdir(), "aipet_tests_agent_pid.txt")
if os.path.exists(pidfile):
    os.remove(pidfile)

# ⚠ 隔离记忆目录：这个探针会真的跑 AgentWorker（会写 experience/state/care），
#   不隔离就会把「测试任务」写进主人的真实 memory（我自己踩过：experience.json 里
#   多了一条 测试任务 fail=19）。
import tempfile
import pets.pet_registry as _pr
_TMPMEM = tempfile.mkdtemp(prefix='aipet_test_mem_')
_pr.get_memory_dir = lambda pet_id=None: _TMPMEM
print('TMPMEM', _TMPMEM)

import tool.agent_bridge as ab
FAKE = [sys.executable, "-c",
        "import os,sys,time; open(sys.argv[1],'w').write(str(os.getpid())); time.sleep(30)",
        pidfile]
ab._argv_for = lambda backend, task: (list(FAKE), {})
ab.available = lambda *a, **k: {"chosen": "dsh", "dsh": True, "codex": False, "reason": ""}
ab.backend_pref = lambda: "dsh"
ab.enabled = lambda: True      # ⚠ run_task 第一道闸；不桩掉它函数立刻返回，什么都测不到

def alive(p):
    try:
        out = subprocess.run(["tasklist", "/FI", "PID eq %%d" %% p, "/NH"],
                             capture_output=True, text=True, timeout=20).stdout
        return str(p) in out
    except Exception:
        return True

from PyQt5.QtWidgets import QApplication
app = QApplication([])
from classes.murasame_class import Murasame
from classes.Worker_class import AgentWorker

t0 = time.time()
r = ab.run_task("测试任务", on_confirm=lambda t: True, should_stop=lambda: (time.time()-t0) > 0.6)
print("RUN_TASK_SECS", round(time.time() - t0, 2))
print("CANCELLED", bool(r.get("cancelled")))
time.sleep(0.6)
pid = int(open(pidfile).read().strip()) if os.path.exists(pidfile) else -1
print("AGENT_ALIVE_AFTER_CANCEL", alive(pid) if pid > 0 else "NO_PID")

pet = Murasame()
print("HAS_STOP_ALL", hasattr(pet, "stop_all_workers"))
pet.stop_all_workers()
print("IDLE_STOP_OK")
if os.path.exists(pidfile):
    os.remove(pidfile)
pet._agent_worker = AgentWorker("测试任务", pet)
pet._agent_worker.done.connect(lambda *a: None)
pet._agent_worker.start()
time.sleep(0.8)
print("RUNNING", pet._agent_worker.isRunning())
print("SECOND_RETURNED", pet._run_agent_task("第二个任务"))
_t = time.time()
pet.stop_all_workers()
print("STOPPED_IN", round(time.time() - _t, 2))
print("TMPMEM_FILES", len(os.listdir(_TMPMEM)))
print("REF_CLEARED", getattr(pet, "_agent_worker", None) is None)
time.sleep(0.6)
pid2 = int(open(pidfile).read().strip()) if os.path.exists(pidfile) else -1
print("AGENT2_ALIVE_AFTER_STOP", alive(pid2) if pid2 > 0 else "NO_PID")
sys.stdout.flush()
os._exit(0)
''' % REPO
env = dict(os.environ, PYTHONIOENCODING="utf-8", QT_QPA_PLATFORM="offscreen", AIPET_NO_SPAWN="1")
r = subprocess.run([sys.executable, "-c", CODE], cwd=REPO, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=env, timeout=300)
outp = (r.stdout or "") + (r.stderr or "")
KEYS = ("RUN_TASK_SECS", "CANCELLED", "AGENT_ALIVE_AFTER_CANCEL", "HAS_STOP_ALL", "IDLE_STOP_OK",
        "RUNNING", "SECOND_RETURNED", "STOPPED_IN", "REF_CLEARED", "AGENT2_ALIVE_AFTER_STOP")
for line in outp.splitlines():
    if any(line.startswith(k) for k in KEYS):
        print("      子进程：%s" % line)
if "AGENT_ALIVE_AFTER_CANCEL False" not in outp:
    print("      ---- 子进程输出尾部（诊断）----")
    for ln in outp.strip().splitlines()[-10:]:
        print("      | %s" % ln[:116])
m = re.search(r"RUN_TASK_SECS ([0-9.]+)", outp)
check("run_task 取消后很快返回（<3s，而不是等 600s 超时）",
      bool(m) and float(m.group(1)) < 3.0, m.group(0) if m else "没打印")
check("结果标明「已取消」", "CANCELLED True" in outp)
check("★ 外部 agent 进程真的被杀掉", "AGENT_ALIVE_AFTER_CANCEL False" in outp)
check("真对象上有 stop_all_workers", "HAS_STOP_ALL True" in outp)
check("没东西在跑时收尾不报错", "IDLE_STOP_OK" in outp)
check("agent 任务真的起来了", "RUNNING True" in outp)
check("第二个任务被守卫拦住（返回 True = 已消化）", "SECOND_RETURNED True" in outp)
m2 = re.search(r"STOPPED_IN ([0-9.]+)", outp)
check("stop_all_workers 能在 3 秒内停掉 agent（改前会等满 3 秒）",
      bool(m2) and float(m2.group(1)) < 3.0, m2.group(0) if m2 else "没打印")
check("停完引用清空", "REF_CLEARED True" in outp)
_m3 = re.search(r"TMPMEM_FILES (\d+)", outp)
check("★ 探针把记忆写进了临时目录（不再污染主人的真实 memory）",
      bool(_m3) and int(_m3.group(1)) > 0, _m3.group(0) if _m3 else "没打印")
check("★ 收尾后外部 agent 进程也没了", "AGENT2_ALIVE_AFTER_STOP False" in outp)
check("没有 QThread 告警/abort", "QThread: Destroyed" not in outp and "Aborted" not in outp)

print("== B1) 源码守卫：三处启动走共用方法，控制台留得住 ==")
SRC = read("pcl_launcher/silicon_window.py")
for script, label, attr in (("run.py", "桌宠", "pet"), ("run_wechat.py", "微信桥接", "wx"),
                            ("run_qq.py", "QQ 桥接", "qq")):
    check("%s 用 _spawn_console + _watch_child" % label,
          ('self._spawn_console(py, os.path.join(base, "%s"), base)' % script) in SRC
          and ("_watch_child(self.shell._%s_proc" % attr) in SRC)
check("全仓只剩一处裸 CREATE_NEW_CONSOLE（在共用方法里）",
      SRC.count("creationflags=subprocess.CREATE_NEW_CONSOLE") == 1)
check("Windows 上套 cmd /k（控制台退出后不关）", 'argv = ["cmd", "/k"] + argv' in SRC)
check("没有别的裸 Popen 起控制台程序（.bat 也走共用方法）",
      "Popen([bat]" not in SRC and 'getattr(subprocess, "CREATE_NEW_CONSOLE", 0)' not in SRC)

print("== B2) 行为：假进程喂 poll()（已死必须说、活着不许说）==")
from PyQt5.QtWidgets import QApplication   # noqa: E402
app = QApplication(sys.argv[:1])
import pcl_launcher.silicon_ui as S        # noqa: E402
S.install(app)
import pcl_launcher.silicon_window as SW   # noqa: E402
import time as _time                       # noqa: E402


class _FakeProc:
    def __init__(self, rc):
        self._rc = rc

    def poll(self):
        return self._rc


win = SW.SiliconLauncher()
win.setAttribute(SW.Qt.WA_DontShowOnScreen, True)
win.show()
home = win.pages["home"]
home._prewarm_started = True
calls = []
home._msg = lambda title, text, detail="": calls.append((title, text, detail))
home.refresh_status = lambda: None
spawned = []
_real_popen = SW.subprocess.Popen
SW.subprocess.Popen = lambda argv, **kw: (spawned.append((argv, kw)), _FakeProc(1))[1]
try:
    home._spawn_console("PY", "run_wechat.py", "BASE")
finally:
    SW.subprocess.Popen = _real_popen
argv, kw = spawned[0]
check("argv 前面是 cmd /k", argv[:2] == ["cmd", "/k"], str(argv[:4]))
check("argv 后面还是解释器 + 脚本", argv[2:] == ["PY", "run_wechat.py"], str(argv[2:]))
check("仍是新控制台 + 工作目录正确",
      kw.get("creationflags") == SW.subprocess.CREATE_NEW_CONSOLE and kw.get("cwd") == "BASE")

calls.clear()
home._watch_child(_FakeProc(1), "微信桥接", "常见原因：\n· 测试提示", delay_ms=300)
for _ in range(12):
    app.processEvents()
    _time.sleep(0.1)
check("秒退 → 弹了「启动后立刻退出了」", any("立刻退出" in c[0] for c in calls), str(calls[:1])[:90])
if calls:
    t, txt, det = calls[0]
    check("标题含桥接名 / 正文含退出码 / 详情给常见原因与控制台指引",
          "微信桥接" in t and "退出码" in txt and "常见原因" in det and "控制台" in det)
calls.clear()
home._watch_child(_FakeProc(None), "微信桥接", "不该出现", delay_ms=300)
for _ in range(12):
    app.processEvents()
    _time.sleep(0.1)
check("还活着 → 什么都不弹（正常启动不打扰）", not calls, str(calls)[:60])

print()
if FAILS:
    print("FAILED %d 项：%s" % (len(FAILS), "、".join(FAILS)))
    sys.exit(1)
print("后台线程体检全部通过")
sys.exit(0)
