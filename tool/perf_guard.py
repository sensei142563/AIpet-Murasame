# -*- coding: utf-8 -*-
"""性能守卫：桌宠开着的时候别拖累主人打游戏。

手段
----
1. **全屏游戏/演示检测**（`game_mode()`）
   用 Windows 的 SHQueryUserNotificationState，只认两个状态：
     · QUNS_RUNNING_D3D_FULL_SCREEN(3) —— D3D 独占全屏
     · QUNS_PRESENTATION_MODE(4)      —— 演示模式（投影/勿扰）
   ⚠ **故意不认** QUNS_BUSY(2) 和"前台窗口占满整屏"：
     · BUSY 在很多正常场景也返回 2（没玩游戏也命中）；
     · 任务栏自动隐藏时，任何最大化窗口都"占满屏"。
     这两条会导致误报"你在打游戏"（实测踩过），所以现在只认上面两个。
2. **进程优先级**：平时 BelowNormal（低于正常），检测到上面两个状态时降到 Idle（最低），
   这样调度器永远优先伺候游戏，桌宠"卡一下"没人在意。

⚠ 语义边界（主人明确要求，别自作聪明）：
   游戏模式里**只调进程优先级** —— **不暂停**屏幕识别、**不暂停**主动搭话。
   `unload_vision_now()` 只是给上层提供"腾显存"的能力（本地视觉服务存在时才有用），
   调用与否由上层决定。

排查用：`python -m tool.perf_guard`（打印当前状态与进程优先级类）
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_cache = {"t": 0.0, "game": False}
_last_state = [None]

# SHQueryUserNotificationState 的返回值
_QUNS_BUSY = 2
_QUNS_RUNNING_D3D_FULL_SCREEN = 3
_QUNS_PRESENTATION_MODE = 4

# 进程优先级类
_BELOW_NORMAL = 0x00004000
_IDLE = 0x00000040
_PRIORITY_NAMES = {
    0x00000040: "Idle（最低）",
    0x00004000: "BelowNormal（低于正常）",
    0x00000020: "Normal（正常）",
    0x00008000: "AboveNormal（高于正常）",
    0x00000080: "High（高）",
    0x00000100: "Realtime（实时）",
}


def _say(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        pass


def notification_state() -> int:
    """Windows 认为现在该不该打扰用户（-1 = 拿不到）"""
    try:
        v = ctypes.c_int(0)
        hr = ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(v))
        return int(v.value) if hr == 0 else -1
    except Exception:
        return -1


def fullscreen_foreground() -> bool:
    """前台窗口是不是占满整块屏幕（**不用于判定游戏**，仅诊断/备用）"""
    try:
        u = ctypes.windll.user32
        h = u.GetForegroundWindow()
        if not h:
            return False
        r = wt.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        w, hh = int(r.right - r.left), int(r.bottom - r.top)
        if w <= 0 or hh <= 0:
            return False
        MONITOR_DEFAULTTONEAREST = 2

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong),
                        ("rcMonitor", wt.RECT),
                        ("rcWork", wt.RECT),
                        ("dwFlags", ctypes.c_ulong)]

        pt = POINT((r.left + r.right) // 2, (r.top + r.bottom) // 2)
        mon = u.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if not u.GetMonitorInfoW(mon, ctypes.byref(mi)):
            return False
        sw = int(mi.rcMonitor.right - mi.rcMonitor.left)
        sh = int(mi.rcMonitor.bottom - mi.rcMonitor.top)
        return w >= sw * 0.99 and hh >= sh * 0.99
    except Exception:
        return False


def _detect() -> bool:
    """是不是真的在全屏游戏/演示（只认 D3D 全屏与演示模式，见模块说明的误报教训）"""
    return notification_state() in (_QUNS_RUNNING_D3D_FULL_SCREEN, _QUNS_PRESENTATION_MODE)


def game_mode(fresh: bool = False) -> bool:
    """现在是不是"在打游戏/全屏"（结果缓存 3 秒，1 秒一次的定时器调用也不心疼）"""
    try:
        now = time.time()
        if fresh or now - float(_cache["t"] or 0) > 3.0:
            _cache["game"] = _detect()
            _cache["t"] = now
        return bool(_cache["game"])
    except Exception:
        return False


def set_process_priority(low: bool = True) -> bool:
    """调进程优先级：low=True → Idle（游戏里），False → BelowNormal（平时）

    ⚠ 64 位下 GetCurrentProcess 返回的是**句柄（指针大小）**，不声明 restype 会被 ctypes
      截断成 int → SetPriorityClass 拿到无效句柄，静默失败（实测返回 False）。
    """
    try:
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        k32.SetPriorityClass.restype = ctypes.c_int
        h = k32.GetCurrentProcess()
        return bool(k32.SetPriorityClass(h, _IDLE if low else _BELOW_NORMAL))
    except Exception as e:
        _say("[性能] ⚠ 调优先级失败: %s" % e)
        return False


def priority_class() -> str:
    """当前进程优先级类（人话），拿不到返回 '?'"""
    try:
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.GetPriorityClass.argtypes = [ctypes.c_void_p]
        k32.GetPriorityClass.restype = ctypes.c_uint
        v = int(k32.GetPriorityClass(k32.GetCurrentProcess()))
        return _PRIORITY_NAMES.get(v, "0x%X" % v)
    except Exception:
        return "?"


def unload_vision_now() -> bool:
    """让本地视觉服务立刻把模型移出显存（打游戏前腾显卡）。

    没有这个服务（端口不通）就返回 False —— 本来也没占显卡，不影响调用方。
    端口取 config.json 的 vision_local_port（默认 28460）。
    """
    try:
        from tool.config import get_config
        port = int(get_config("./config.json").get("vision_local_port") or 28460)
    except Exception:
        port = 28460
    try:
        import requests
        r = requests.get("http://127.0.0.1:%d/unload" % port, timeout=6)
        ok = (r.status_code == 200)
        if ok:
            _say("[性能] 已让视觉服务移出显存: %s" % str(r.text)[:80])
        return ok
    except Exception:
        return False


def note_state(is_game: bool) -> None:
    """状态变化时写一行日志（只写变化，不刷屏）"""
    if _last_state[0] == is_game:
        return
    _last_state[0] = is_game
    if is_game:
        _say("[性能] 🎮 检测到全屏游戏/演示 → 桌宠进程优先级降到最低"
             "（识别与搭话照常，只把 CPU 让给游戏）")
    else:
        _say("[性能] 🎮 游戏结束 → 桌宠优先级恢复（低于正常）")


if __name__ == "__main__":
    st = notification_state()
    _say("通知状态 = %s（3=D3D全屏 4=演示模式 2=忙碌 -1=拿不到）" % st)
    _say("前台窗口占满屏 = %s（**不参与判定**，仅参考）" % fullscreen_foreground())
    _say("game_mode() = %s" % game_mode(fresh=True))
    _say("当前进程优先级 = %s" % priority_class())
    _say("视觉服务可卸载 = %s" % unload_vision_now())
