# -*- coding: utf-8 -*-
"""Win32 抓屏：**可以在后台线程安全调用**（替代 Qt 的 QScreen.grabWindow）。

为什么必须换（实测事故，我们这边同样存在）
----------------------------------------
`QScreen.grabWindow()` **只能在 GUI 线程调用**。而桌宠的截图线程（`ScreenWorker`，QThread）
和"看屏幕"流程都在后台线程里调它 → 进程直接崩掉：日志没有任何报错、进程凭空消失，
用户看到的就是"桌宠未响应 / 不见了"（残留的视觉/语音服务还占着显存）。
全屏游戏下 `grabWindow` 更慢更不稳，更是必崩。

做法：GDI 的 BitBlt + GetDIBits —— 纯 Win32、毫秒级、不碰任何 Qt 界面对象；
只有最后构造 `QImage`（QImage 允许在非 GUI 线程用，**QPixmap 不行**）并保存 PNG。

对外接口
--------
    monitors()                     → [{'index','x','y','w','h','primary','name'}, …]
    capture_qimage(index=None)     → QImage（index=None 表示整块虚拟桌面）
    capture_png(path, index=None)  → 存成 PNG，返回路径
    changed_ratio(a, b)            → 两张图的"变化比例"（0~1，粗粒度分块比较，够便宜）
    is_blank(img)                  → 是否基本全黑/全白（抓失败时常见）
    quick_hash(img) / hash_distance(a, b)   → 给"屏幕变化"打分的廉价指纹
    last_capture_ms()              → 上一次抓屏耗时（毫秒）
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes as wt

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79

_user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
_gdi32 = ctypes.windll.gdi32 if hasattr(ctypes, "windll") else None

_last_ms = [0.0]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


class _MONITORINFOEXW(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT),
                ("dwFlags", wt.DWORD), ("szDevice", wt.WCHAR * 32)]


def available() -> bool:
    """Win32 抓屏能不能用（非 Windows 或 DLL 缺失就 False）"""
    return bool(_user32 and _gdi32)


def monitors() -> list:
    """列出显示器（含虚拟坐标与主屏标记）"""
    out = []
    if not available():
        return out
    try:
        MONITORENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC,
                                            ctypes.POINTER(wt.RECT), wt.LPARAM)
        prim = _user32.GetPrimaryMonitorHandle if hasattr(_user32, "GetPrimaryMonitorHandle") else None

        def _cb(hmon, hdc, lprc, lparam):
            try:
                mi = _MONITORINFOEXW()
                mi.cbSize = ctypes.sizeof(_MONITORINFOEXW)
                if _user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                    r = mi.rcMonitor
                    out.append({"index": len(out), "x": int(r.left), "y": int(r.top),
                                "w": int(r.right - r.left), "h": int(r.bottom - r.top),
                                "primary": bool(mi.dwFlags & 1),
                                "name": str(mi.szDevice or "")})
            except Exception:
                pass
            return True

        _user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_cb), 0)
    except Exception:
        pass
    if not out:                       # 兜底：整块虚拟桌面当一个显示器
        try:
            w = int(_user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
            h = int(_user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
            x = int(_user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
            y = int(_user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
            out.append({"index": 0, "x": x, "y": y, "w": w, "h": h, "primary": True,
                        "name": "virtual"})
        except Exception:
            pass
    return out


def capture_qimage(index: int = None):
    """抓屏 → QImage（**后台线程可安全调用**）。

    index=None 抓整块虚拟桌面；给了序号就抓那台显示器（越界自动回落整屏）。
    失败返回 None（绝不抛异常给调用方）。
    """
    t0 = time.time()
    try:
        from PyQt5.QtGui import QImage
    except Exception:
        return None
    if not available():
        return None
    hdc = memdc = bmp = old = None
    try:
        mons = monitors()
        if index is not None and 0 <= int(index) < len(mons):
            m = mons[int(index)]
            x, y, w, h = m["x"], m["y"], m["w"], m["h"]
        else:
            x = int(_user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
            y = int(_user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
            w = int(_user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
            h = int(_user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
        if w <= 0 or h <= 0:
            return None
        hdc = _user32.GetDC(0)
        memdc = _gdi32.CreateCompatibleDC(hdc)
        bmp = _gdi32.CreateCompatibleBitmap(hdc, w, h)
        old = _gdi32.SelectObject(memdc, bmp)
        if not _gdi32.BitBlt(memdc, 0, 0, w, h, hdc, x, y, SRCCOPY):
            return None
        bi = _BITMAPINFO()
        bi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bi.bmiHeader.biWidth = w
        bi.bmiHeader.biHeight = -h              # 负数 = 自上而下（省一次翻转）
        bi.bmiHeader.biPlanes = 1
        bi.bmiHeader.biBitCount = 32
        bi.bmiHeader.biCompression = BI_RGB
        buf = ctypes.create_string_buffer(w * h * 4)
        n = _gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bi), DIB_RGB_COLORS)
        if not n:
            return None
        # QImage 不复制传入内存 → 必须 .copy()（缓冲区马上就释放了）
        img = QImage(buf, w, h, w * 4, QImage.Format_RGB32).copy()
        _last_ms[0] = (time.time() - t0) * 1000.0
        return img
    except Exception:
        return None
    finally:
        try:
            if memdc and old:
                _gdi32.SelectObject(memdc, old)
            if bmp:
                _gdi32.DeleteObject(bmp)
            if memdc:
                _gdi32.DeleteDC(memdc)
            if hdc:
                _user32.ReleaseDC(0, hdc)
        except Exception:
            pass


def capture_png(path: str, index: int = None) -> str:
    """抓屏存 PNG，返回路径（失败返回空串）"""
    try:
        img = capture_qimage(index)
        if img is None or img.isNull():
            return ""
        d = os.path.dirname(os.path.abspath(path))
        if d:
            os.makedirs(d, exist_ok=True)
        return path if img.save(path, "PNG") else ""
    except Exception:
        return ""


def _sample_grid(img, cols: int = 24, rows: int = 14):
    """把图缩成 cols×rows 的灰度样本（够用来判变化，且很便宜）"""
    try:
        small = img.scaled(cols, rows)
        vals = []
        for y in range(rows):
            for x in range(cols):
                c = small.pixelColor(x, y)
                vals.append((c.red() + c.green() + c.blue()) // 3)
        return vals
    except Exception:
        return []


def changed_ratio(a, b) -> float:
    """两张图的"变化比例"（0~1）：分块灰度差异超过阈值就算变了"""
    try:
        if a is None or b is None or a.isNull() or b.isNull():
            return 0.0
        va, vb = _sample_grid(a), _sample_grid(b)
        if not va or len(va) != len(vb):
            return 0.0
        diff = sum(1 for x, y in zip(va, vb) if abs(int(x) - int(y)) > 12)
        return diff / float(len(va))
    except Exception:
        return 0.0


def is_blank(img) -> bool:
    """是不是基本全黑/全白（抓失败时常见，用来别把黑屏当"看到了什么"）"""
    try:
        if img is None or img.isNull():
            return True
        v = _sample_grid(img, 12, 8)
        if not v:
            return True
        avg = sum(v) / float(len(v))
        spread = max(v) - min(v)
        return (avg < 8 or avg > 247) and spread < 6
    except Exception:
        return True


def quick_hash(img) -> int:
    """廉价指纹（用来算"屏幕变了多少"，见 hash_distance）"""
    try:
        v = _sample_grid(img, 16, 10)
        h = 0
        for i, x in enumerate(v):
            h = (h * 131 + int(x) * (i + 1)) & 0xFFFFFFFF
        return h
    except Exception:
        return 0


def hash_distance(a: int, b: int) -> int:
    """两个指纹的距离（判"有没有变"用；同一张图两次算出来距离为 0）"""
    try:
        return bin(int(a) ^ int(b)).count("1")
    except Exception:
        return 0


def last_capture_ms() -> float:
    return float(_last_ms[0])


if __name__ == "__main__":
    print("Win32 抓屏可用:", available())
    for m in monitors():
        print("  显示器 %d: %dx%d @ (%d,%d) 主屏=%s %s"
              % (m["index"], m["w"], m["h"], m["x"], m["y"], m["primary"], m["name"]))
    img = capture_qimage()
    if img is None:
        print("抓屏失败")
    else:
        print("抓屏成功: %dx%d  耗时 %.1f ms  空白=%s  指纹=%d"
              % (img.width(), img.height(), last_capture_ms(), is_blank(img), quick_hash(img)))
