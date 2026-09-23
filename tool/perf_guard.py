# -*- coding: utf-8 -*-
"""性能守卫：桌宠开着的时候别拖累主人打游戏。

两个手段：

1. **全屏游戏检测 → 自动降级**（`game_mode()`）
   用 Windows 的 SHQueryUserNotificationState（D3D 全屏 / 忙碌 / 演示模式）+ 前台窗口
   是否占满整块屏幕（覆盖无边框全屏游戏）来判定。桌宠检测到以后会：
     · 暂停定时截屏识别（不再反复调用视觉模型、不再抢显卡）
     · 让视觉服务立刻把模型移出显存（8G 卡上那是 6G 的大块头）
     · 停掉主动搭话/空闲闲聊（不让它在对局里插话）
     · 把桌宠自己的进程优先级降到最低
   游戏一结束自动恢复（原来开着的截屏识别会重新启动）。

2. **进程优先级**：桌宠平时就跑在 BelowNormal（低于正常），游戏时降到 Idle（最低），
   这样调度器永远优先伺候游戏，桌宠"卡一下"没人在意。

为什么需要（现场数据）：vision_idle_unload 默认 300 秒、而 screen_interval 是 150 秒 →
两次识别间隔比闲置阈值还短，视觉模型**会一直留在显存里**，打游戏时直接跟游戏抢显存。
"""
import ctypes
import ctypes.wintypes as wt
import os
import time

_cache = {"t": 0.0, "game": False}
_last_state = [None]

# SHQueryUserNotificationState 的返回值
_QUNS_BUSY = 2
_QUNS_RUNNING_D3D_FULL_SCREEN = 3
_QUNS_PRESENTATION_MODE = 4

# 进程优先级
_BELOW_NORMAL = 0x00004000
_IDLE = 0x00000040


def _u32():
    return ctypes.windll.user32


def fullscreen_foreground() -> bool:
    """前台窗口是不是占满了整块屏幕（无边框全屏游戏也认）"""
    try:
        u = _u32()
        h = u.GetForegroundWindow()
        if not h:
            return False
        r = wt.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        w, hh = int(r.right - r.left), int(r.bottom - r.top)
        if w <= 0 or hh <= 0:
            return False
        # 用窗口所在显示器的分辨率比对（多屏时取窗口中心那块）
        MONITOR_DEFAULTTONEAREST = 2
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = POINT((r.left + r.right) // 2, (r.top + r.bottom) // 2)
        mon = u.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong),
                        ("rcMonitor", wt.RECT),
                        ("rcWork", wt.RECT),
                        ("dwFlags", ctypes.c_ulong)]
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if not u.GetMonitorInfoW(mon, ctypes.byref(mi)):
            return False
        sw = int(mi.rcMonitor.right - mi.rcMonitor.left)
        sh = int(mi.rcMonitor.bottom - mi.rcMonitor.top)
        # 覆盖 99% 以上算全屏（留一点边框误差）
        return w >= sw * 0.99 and hh >= sh * 0.99
    except Exception:
        return False


def notification_state() -> int:
    """Windows 认为现在该不该打扰用户（返回 -1 表示拿不到）"""
    try:
        v = ctypes.c_int(0)
        hr = ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(v))
        return int(v.value) if hr == 0 else -1
    except Exception:
        return -1


def _detect() -> bool:
    """是不是真的在全屏独占游戏/演示（**只认这两个**）

    ⚠ 以前还认 QUNS_BUSY(2) 和"前台窗口占满屏"：
      · QUNS_BUSY 在很多正常场景也会返回 2（用户没玩游戏也命中）；
      · "占满屏"在任务栏自动隐藏时，任何最大化窗口都会被当成全屏。
      实测用户根本没玩游戏，桌宠却说"你在打游戏"（用户反馈），就是这两条误报。
      现在只认 QUNS_RUNNING_D3D_FULL_SCREEN(3) 和 QUNS_PRESENTATION_MODE(4)。
    """
    st = notification_state()
    return st in (_QUNS_RUNNING_D3D_FULL_SCREEN, _QUNS_PRESENTATION_MODE)


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
    """把当前进程优先级调低（桌宠不该和游戏抢 CPU）

    ⚠ 64 位下 GetCurrentProcess 返回的是句柄（指针大小），不声明 restype 会被 ctypes
      截断成 int → SetPriorityClass 拿到无效句柄直接失败（实测 False）。
    """
    try:
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        k32.SetPriorityClass.restype = ctypes.c_int
        h = k32.GetCurrentProcess()
        return bool(k32.SetPriorityClass(h, _IDLE if low else _BELOW_NORMAL))
    except Exception as e:
        print(f"[性能] ⚠ 调优先级失败: {e}")
        return False


def unload_vision_now() -> bool:
    """让本地视觉服务立刻把模型移出显存（打游戏前腾显卡）"""
    try:
        from tool.config import get_config
        port = int(get_config("./config.json").get("vision_local_port") or 28460)
    except Exception:
        port = 28460
    try:
        import requests
        r = requests.get(f"http://127.0.0.1:{port}/unload", timeout=6)
        ok = (r.status_code == 200)
        if ok:
            print(f"[性能] 已让视觉服务移出显存：{r.text[:80]}")
        return ok
    except Exception:
        return False          # 服务没开就算了（本来就没占显卡）


def note_state(is_game: bool):
    """状态变化时写一行日志（只写变化，不刷屏）

    ⚠ 桌宠侧在游戏模式里**只降进程优先级**：主人明确要求屏幕识别与主动搭话都不许动，
      所以这里不涉及暂停任何功能。
    """
    if _last_state[0] == is_game:
        return
    _last_state[0] = is_game
    if is_game:
        print("[性能] 🎮 检测到全屏游戏/勿扰状态 → 桌宠进程优先级降到最低（识别与搭话照常）")
    else:
        print("[性能] 🎮 游戏结束 → 桌宠优先级恢复（低于正常）")


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("通知状态:", notification_state(), "（3=D3D全屏 2=忙碌 4=演示 5=正常）")
    print("前台全屏:", fullscreen_foreground())
    print("游戏模式:", game_mode(fresh=True))
    print("视觉服务卸载:", unload_vision_now())
    print("降优先级:", set_process_priority(True), "| 恢复:", set_process_priority(False))
