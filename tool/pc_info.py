# -*- coding: utf-8 -*-
"""让她平时自己了解一点电脑上的情况，好在闲聊时有话说。

不碰任何私密内容，只看"电脑状态"这一类事实：
    * 磁盘还剩多少空间
    * 桌面上有几个文件、最近动过的是哪几个（只有名字和时间，不读内容）
    * 现在开着哪些程序（进程/窗口标题）
    * 今天改过的文件
    * 有没有插着耳机/摄像头这类设备（无线索则略过）

开关：右键菜单 →「允许读取电脑文件」（和看文件共用一个开关，config 的 file_access_enabled）

用法：桌宠每隔一段时间（默认 12 分钟）采一次，写进她的「最近的观察」，
她自己决定要不要拿这些当话题——不做任何打扰，也不额外花模型额度。
"""
import os
import time

_SAMPLE_GAP_MIN = 12          # 两次采样至少间隔（分钟）
_last_sample = [0.0]
_snapshot = [None]            # 最近一次快照（本轮/上轮给她的话题素材）


def _fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%.1f%s" % (n, unit)
        n /= 1024.0
    return "%.1fTB" % n


def _disks() -> str:
    try:
        import ctypes
        out = []
        for letter in "CDEFGH":
            root = letter + ":\\"
            if not os.path.exists(root):
                continue
            try:
                free = ctypes.c_ulonglong(0)
                total = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(root), None,
                    ctypes.byref(total), ctypes.byref(free))
                if total.value:
                    out.append("%s 盘还剩 %s / 共 %s" % (
                        letter, _fmt_size(free.value), _fmt_size(total.value)))
            except Exception:
                continue
        return "；".join(out)
    except Exception:
        return ""


def _desktop_recent(n: int = 5) -> str:
    try:
        from tool.file_access import _user_dirs
        d = _user_dirs().get("Desktop")
        if not d or not os.path.isdir(d):
            return ""
        items = []
        for name in os.listdir(d):
            if name.startswith("$") or name == "desktop.ini":
                continue
            p = os.path.join(d, name)
            try:
                items.append((name, os.path.getmtime(p)))
            except Exception:
                continue
        items.sort(key=lambda x: -x[1])
        if not items:
            return "桌面上空空的"
        recent = "、".join("%s（%s）" % (nm, time.strftime("%m-%d %H:%M", time.localtime(mt)))
                          for nm, mt in items[:n])
        return "桌面上有 %d 项，最近动过的是：%s" % (len(items), recent)
    except Exception:
        return ""


def _running_apps(limit: int = 8) -> str:
    """当前开着的程序：优先取窗口标题（比进程名可读）"""
    names = []
    _noise = ("python", "pythonw", "program manager", "windows 输入体验", "设置",
              "microsoft text input application", "aipet 丛雨桌宠 · 启动器", "nexus", "nxdock",
              "default ime", "candidate", "snippingtool")
    try:
        import ctypes
        from ctypes import wintypes

        def _cb(hwnd, _):
            try:
                if not ctypes.windll.user32.IsWindowVisible(hwnd):
                    return True
                ln = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if ln <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(ln + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, ln + 1)
                t = (buf.value or "").strip()
                if t and t.lower() not in _noise and t not in names:
                    names.append(t)
            except Exception:
                pass
            return True

        CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        ctypes.windll.user32.EnumWindows(CB(_cb), 0)
    except Exception:
        pass
    if not names:
        return ""
    return "现在开着的窗口：" + "；".join(names[:limit])


def _today_changed(root: str, limit: int = 5) -> str:
    """今天动过的文件（只看名字，不读内容）"""
    try:
        today = time.strftime("%Y-%m-%d")
        out = []
        for r, subs, files in os.walk(root):
            subs[:] = [d for d in subs if d not in
                       (".git", "node_modules", "__pycache__", "runtime", "_internal", "tmp")]
            for f in files:
                p = os.path.join(r, f)
                try:
                    if time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p))) == today:
                        out.append((f, os.path.getmtime(p)))
                except Exception:
                    continue
            if len(out) > 60:
                break
        out.sort(key=lambda x: -x[1])
        if not out:
            return ""
        return "今天动过的文件：" + "、".join(n for n, _ in out[:limit])
    except Exception:
        return ""


def sample(force: bool = False) -> str:
    """采一次电脑情况，返回给模型看的一段文字（空 = 这次没采/没东西可说）"""
    if not force and (time.time() - float(_last_sample[0] or 0)) < _SAMPLE_GAP_MIN * 60:
        return ""
    try:
        from tool import file_access
        if not file_access.enabled():
            return ""
        _last_sample[0] = time.time()
    except Exception:
        return ""
    parts = []
    for fn, label in ((_disks, "磁盘"), (_running_apps, "窗口"),
                      (_desktop_recent, "桌面"),):
        try:
            v = fn()
            if v:
                parts.append(v)
        except Exception:
            continue
    try:
        from tool.file_access import _user_dirs
        v = _today_changed(_user_dirs()["_root"])
        if v:
            parts.append(v)
    except Exception:
        pass
    if not parts:
        return ""
    txt = "【电脑近况】" + "；".join(parts) + "。"
    _snapshot[0] = txt
    return txt


def recent() -> str:
    """最近一次快照（给她当话题用）"""
    return _snapshot[0] or ""


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    t0 = time.time()
    print("采样（开关关着应该为空）:", repr(sample(force=True)))
    # 临时强制：直接调各子函数看看内容
    print()
    print("磁盘:", _disks())
    print("窗口:", _running_apps())
    print("桌面:", _desktop_recent())
    from tool.file_access import _user_dirs
    print("今天:", _today_changed(_user_dirs()["_root"]))
    print("耗时: %.2fs" % (time.time() - t0))
