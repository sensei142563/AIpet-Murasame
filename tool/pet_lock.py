# -*- coding: utf-8 -*-
"""桌宠进程锁（data/pet.pid）：判断这把锁还对应着**那个**活着的桌宠，并清掉过期锁。

⚠ 2026-10-01 真事故：Windows 会**复用 PID**。
  11:28 那次桌宠退出时没来得及删锁（被强制收尾），锁文件里留着 26224；
  到 13:11，这个 PID 被 EpicWebHelper.exe 占用了 →
  旧判断（只问"这个 PID 的进程还在吗"）返回 True →
  启动器坚信「桌宠正在启动中」→ 点几次都不给开
  （日志：`[NewUI] 桌宠正在启动中（进程已在）→ 不再启动第二只`）。

所以这里除了"活着"，还要能证明它**就是写锁那一刻启动的那个进程**：
  · 镜像名必须是 python / pythonw（拿得到才判）；
  · 进程创建时间不能**晚于**锁文件写入时间（+10 秒容差：写锁发生在 QApplication 之后）；
  · 锁文件写入时间与进程创建时间不能差太多（>180 秒 = 这是别人/很久以前的进程）。
判定为过期 → 顺手把锁文件删掉，别让它继续拦下一次启动。
"""
import ctypes
import os
import time

TOL_NEWER = 10.0     # 进程创建时间最多可比锁文件晚这么多秒
TOL_OLDER = 180.0    # 进程创建时间最多可比锁文件早这么多秒


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]


def _k32():
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = ctypes.c_void_p
    k.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
    k.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    return k


def _proc_info(pid: int):
    """→ (是否活着, 创建时间戳 or None, 镜像名 or "")"""
    try:
        k = _k32()
        h = k.OpenProcess(0x1000, False, int(pid))      # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False, None, ""
        try:
            code = ctypes.c_ulong(0)
            if (not k.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
                    or code.value != 259):              # STILL_ACTIVE
                return False, None, ""
            created = None
            try:
                c, e, kt, u = _FILETIME(), _FILETIME(), _FILETIME(), _FILETIME()
                if k.GetProcessTimes(ctypes.c_void_p(h), ctypes.byref(c), ctypes.byref(e),
                                     ctypes.byref(kt), ctypes.byref(u)):
                    ft = (c.dwHighDateTime << 32) | c.dwLowDateTime
                    if ft:
                        created = ft / 1e7 - 11644473600.0     # FILETIME → Unix 时间
            except Exception:
                created = None
            name = ""
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = ctypes.c_ulong(1024)
                if k.QueryFullProcessImageNameW(ctypes.c_void_p(h), 0, buf, ctypes.byref(size)):
                    name = os.path.basename(buf.value or "")
            except Exception:
                name = ""
            return True, created, name
        finally:
            try:
                k.CloseHandle(ctypes.c_void_p(h))
            except Exception:
                pass
    except Exception:
        return False, None, ""


def alive(pid_file: str) -> bool:
    """锁文件对应的桌宠还在跑吗（且确实是它自己）。过期锁会被就地清掉。"""
    try:
        if not pid_file or not os.path.exists(pid_file):
            return False
        mtime = os.path.getmtime(pid_file)
        with open(pid_file, encoding="utf-8") as f:
            pid = int((f.read() or "0").strip().split()[0] or 0)
        if pid <= 0:
            return False
        ok, created, name = _proc_info(pid)
        if not ok:
            _drop(pid_file)
            return False
        stale = False
        if name and not name.lower().startswith(("python", "pythonw")):
            stale = True
        if created:
            if created > mtime + TOL_NEWER:
                stale = True
            elif mtime - created > TOL_OLDER:
                stale = True
        if stale:
            print("[PetLock] ⚠ pet.pid 里的 %d 已不属于桌宠（%s，创建于 %s）→ 当过期锁清掉"
                  % (pid, name or "?",
                     time.strftime("%m-%d %H:%M:%S", time.localtime(created)) if created else "?"))
            _drop(pid_file)
            return False
        return True
    except Exception:
        return False


def _drop(pid_file: str):
    try:
        os.remove(pid_file)
    except Exception:
        pass


def write(pid_file: str, pid: int = None) -> bool:
    """写锁（桌宠启动时调用）"""
    try:
        d = os.path.dirname(os.path.abspath(pid_file))
        if d:
            os.makedirs(d, exist_ok=True)
        with open(pid_file, "w", encoding="utf-8") as f:
            f.write(str(int(pid or os.getpid())))
        return True
    except Exception:
        return False


def clear(pid_file: str):
    _drop(pid_file)
