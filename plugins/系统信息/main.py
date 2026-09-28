# -*- coding: utf-8 -*-
"""示例插件：系统信息（内置，演示插件怎么写）。

她写「【插件:系统信息】」时，桌宠会调用下面的 handle()，把返回的话交给她说。
没有引入任何新依赖：能用项目里现成的 tool.pc_info 就用，拿不到就用 ctypes 兜底。
"""
import ctypes
import os
import time


def rules() -> str:
    return "可以看电脑状态（写【插件:系统信息】）。"


def _mem_gb():
    try:
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        m = MEMORYSTATUSEX()
        m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        used = (m.ullTotalPhys - m.ullAvailPhys) / 1024.0 ** 3
        total = m.ullTotalPhys / 1024.0 ** 3
        return "内存用了 %.1fG / 共 %.1fG（%d%%）" % (used, total, m.dwMemoryLoad)
    except Exception:
        return ""


def _uptime():
    try:
        ms = ctypes.windll.kernel32.GetTickCount64()
        h = ms / 1000.0 / 3600.0
        return "开机 %.1f 小时" % h
    except Exception:
        return ""


def _disk():
    try:
        from tool.pc_info import _disks
        return _disks()
    except Exception:
        return ""


def _cpu_name():
    try:
        return os.environ.get("PROCESSOR_IDENTIFIER", "")[:60]
    except Exception:
        return ""


def handle(arg: str = "") -> str:
    parts = []
    mem = _mem_gb()
    if mem:
        parts.append(mem)
    up = _uptime()
    if up:
        parts.append(up)
    d = _disk()
    if d:
        parts.append(d)
    c = _cpu_name()
    if c:
        parts.append("处理器：" + c)
    if not parts:
        return "我这边读不到系统信息。"
    return "；".join(parts) + "。"


if __name__ == "__main__":
    print(handle(""))
