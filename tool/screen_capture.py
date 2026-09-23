# -*- coding: utf-8 -*-
"""Win32 抓屏：可以在后台线程安全调用（替代 Qt 的 QScreen.grabWindow）。

为什么必须换（实测事故）：
    QScreen.grabWindow() 只能在 GUI 线程调用，而桌宠的截图线程（ScreenWorker，QThread）
    和"看屏幕"流程（普通 threading.Thread）都在后台线程里调它 →
    进程直接崩掉（日志没有任何报错、进程凭空消失，残留的视觉/语音服务还占着显存），
    用户看到的就是"桌宠未响应/不见了"。全屏游戏下 QScreen 抓屏更慢更不稳，更容易崩。

做法：GDI 的 BitBlt + GetDIBits，纯 Win32、毫秒级、不碰任何 Qt 界面对象；
只有最后构造 QImage（QImage 允许在非 GUI 线程使用，QPixmap 不行）并保存 PNG。
"""
import ctypes
import ctypes.wintypes as wt
import os
import time

SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0

_last = {"t": 0.0, "ms": 0.0}


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def _gdi():
    return ctypes.windll.gdi32, ctypes.windll.user32


def monitors() -> list:
    """所有显示器的 (left, top, right, bottom)，按 Windows 的顺序"""
    g, u = _gdi()
    out = []
    MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                         ctypes.POINTER(wt.RECT), ctypes.c_void_p)

    def _cb(hmon, hdc, lprc, lp):
        out.append((int(lprc.contents.left), int(lprc.contents.top),
                    int(lprc.contents.right), int(lprc.contents.bottom)))
        return 1

    try:
        u.EnumDisplayMonitors(None, None, MONITORENUMPROC(_cb), None)
    except Exception:
        pass
    if not out:                                  # 兜底：整个虚拟桌面
        u.GetSystemMetrics.restype = ctypes.c_int
        x, y = u.GetSystemMetrics(SM_XVIRTUALSCREEN), u.GetSystemMetrics(SM_YVIRTUALSCREEN)
        w, h = u.GetSystemMetrics(SM_CXVIRTUALSCREEN), u.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        out = [(x, y, x + w, y + h)]
    return out


def capture_qimage(index: int = None):
    """抓一块屏幕，返回 QImage（失败返回 None）。index 为空/越界 → 主显示器。

    ⚠ QImage 可以在后台线程构造与保存；QPixmap 不行（那是 GUI 线程专用的）。
    """
    try:
        from PyQt5.QtGui import QImage
    except Exception:
        return None
    g, u = _gdi()
    rects = monitors()
    if not rects:
        return None
    try:
        i = int(index) if index is not None else 0
        if i < 0 or i >= len(rects):
            i = 0
        l, t, r, b = rects[i]
        w, h = int(r - l), int(b - t)
        if w <= 0 or h <= 0:
            return None
        hdc_src = u.GetDC(0)
        hdc_mem = g.CreateCompatibleDC(hdc_src)
        hbmp = g.CreateCompatibleBitmap(hdc_src, w, h)
        g.SelectObject(hdc_mem, hbmp)
        t0 = time.time()
        ok = bool(g.BitBlt(hdc_mem, 0, 0, w, h, hdc_src, l, t, SRCCOPY))
        ms = (time.time() - t0) * 1000.0
        _last["t"], _last["ms"] = time.time(), ms
        if ms > 800:
            print(f"[抓屏] ⚠ 这次抓屏用了 {ms:.0f}ms（可能有独占全屏程序）")
        if not ok:
            g.DeleteObject(hbmp)
            g.DeleteDC(hdc_mem)
            u.ReleaseDC(0, hdc_src)
            return None
        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h            # 负数 = 自上而下，省得再翻转
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        buf = ctypes.create_string_buffer(w * h * 4)
        got = g.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
        g.DeleteObject(hbmp)
        g.DeleteDC(hdc_mem)
        u.ReleaseDC(0, hdc_src)
        if not got:
            return None
        img = QImage(buf.raw, w, h, w * 4, QImage.Format_RGB32).copy()   # copy 出来，别指着临时缓冲
        return img
    except Exception as e:
        print(f"[抓屏] ⚠ 抓屏失败: {type(e).__name__}: {e}")
        return None


def capture_window_qimage(hwnd, index: int = None):
    """只抓**某个窗口**的画面（游戏用）——返回 QImage；失败退回"屏幕裁剪"。

    为什么要它（2026-09-24 用户反馈"恶魔轮盘没正常游玩"）：
      以前游戏里看画面是抓**整块屏幕** → 桌宠窗口、任务栏、别的窗口全在里面，
      本地小视觉模型经常把 **桌宠自己** 或别的东西描述成画面内容（实测把它认成
      "RPG 的标题界面" ✗）→ 计划就离谱了。
      这里先试 PrintWindow（能拿到窗口自己的内容，被挡住也行），失败再退回按窗口矩形从
      整屏里裁一块。

    参考做法：开源 GUI Agent（OmniParser / SeeAct / UI-TARS 那类）都强调
      **喂给模型的画面要干净**（只含目标窗口），别把无关东西混进去。
    """
    try:
        from PyQt5.QtGui import QImage
        import ctypes
        from ctypes import wintypes as wt
        u = ctypes.windll.user32
        g = ctypes.windll.gdi32
        hwnd = int(hwnd or 0)
        if not hwnd:
            return None
        r = wt.RECT()
        if not u.GetWindowRect(hwnd, ctypes.byref(r)):
            return None
        w, h = int(r.right - r.left), int(r.bottom - r.top)
        if w <= 8 or h <= 8 or w > 20000 or h > 20000:
            return None
        # ① PrintWindow（含 PW_RENDERFULLCONTENT，DWM 合成窗口/DirectX 也大多能拿到）
        try:
            hdc = u.GetWindowDC(hwnd)
            mem = g.CreateCompatibleDC(hdc)
            bmp = g.CreateCompatibleBitmap(hdc, w, h)
            g.SelectObject(mem, bmp)
            PW_RENDERFULLCONTENT = 0x00000002
            ok = u.PrintWindow(hwnd, mem, PW_RENDERFULLCONTENT)
            if ok:
                bmi = _BITMAPINFO()
                bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
                bmi.bmiHeader.biWidth = w
                bmi.bmiHeader.biHeight = -h
                bmi.bmiHeader.biPlanes = 1
                bmi.bmiHeader.biBitCount = 32
                bmi.bmiHeader.biCompression = BI_RGB
                buf = ctypes.create_string_buffer(w * h * 4)
                got = g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
                g.DeleteObject(bmp)
                g.DeleteDC(mem)
                u.ReleaseDC(hwnd, hdc)
                if got:
                    img = QImage(buf.raw, w, h, w * 4, QImage.Format_RGB32).copy()
                    if not is_blank(img):
                        return img
            else:
                g.DeleteObject(bmp)
                g.DeleteDC(mem)
                u.ReleaseDC(hwnd, hdc)
        except Exception:
            pass
        # ② 退回：从整屏里按窗口矩形裁一块（窗口在最前面时效果一样）
        img = capture_qimage(index)
        if img is None:
            return None
        x0 = max(0, int(r.left))
        y0 = max(0, int(r.top))
        x1 = min(img.width(), int(r.right))
        y1 = min(img.height(), int(r.bottom))
        if x1 - x0 < 8 or y1 - y0 < 8:
            return None
        return img.copy(x0, y0, x1 - x0, y1 - y0)
    except Exception as e:
        print(f"[抓屏] ⚠ 抓窗口失败: {type(e).__name__}: {e}")
        return None


def changed_ratio(a, b) -> float:
    """两张图有多大差别（0~1，粗略：按 16x16 指纹差几位 / 256）

    用来做**动作后校验**：点完之后画面一动不动 → 这一步没用，该换个位置
    （开源 GUI Agent 里通用的 "act → verify" 思路；也能防住"盲点同一个地方"）。
    """
    try:
        h1, h2 = quick_hash(a), quick_hash(b)
        if not h1 or not h2:
            return -1.0
        return hash_distance(h1, h2) / 256.0
    except Exception:
        return -1.0


def capture_png(path: str, index: int = None) -> bool:
    """抓屏并存成 PNG（后台线程可调用）"""
    try:
        img = capture_qimage(index)
        if img is None or img.isNull():
            return False
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        return bool(img.save(path, "PNG"))
    except Exception as e:
        print(f"[抓屏] ⚠ 存 PNG 失败: {type(e).__name__}: {e}")
        return False


def is_blank(img) -> bool:
    """这张图是不是黑的/一片纯色（锁屏、显示器休眠、独占全屏时抓不到内容）。

    兼容 QImage 和 QPixmap（都转成 QImage 再采样，48x48 足够判断，开销可忽略）。
    """
    try:
        import statistics
        from PyQt5.QtCore import Qt
        if img is None:
            return True
        if hasattr(img, "toImage"):           # QPixmap
            img = img.toImage()
        if img.isNull():
            return True
        small = img.scaled(48, 48, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        vals = []
        for y in range(small.height()):
            for x in range(small.width()):
                c = small.pixelColor(x, y)
                vals.append((c.red() + c.green() + c.blue()) / 3.0)
        if not vals:
            return True
        mean = sum(vals) / len(vals)
        dark = sum(1 for v in vals if v < 10) / len(vals)
        try:
            sd = statistics.pstdev(vals)
        except Exception:
            sd = 99.0
        return mean < 12 or dark > 0.97 or sd < 3.0
    except Exception:
        return False


def quick_hash(img) -> int:
    """画面指纹（16x16 平均哈希，256 位）：用来判断"屏幕有没有变化"。

    为什么要它：每 150 秒重描述一遍**没变过的屏幕**纯属浪费——视觉模型要占显卡 10 秒以上，
    还会和语音合成抢显卡（实测语音被拖到 25 秒）。有了指纹就能复用上次的描述，
    既快又不抢显卡（用户反馈"屏幕识别太慢"）。
    """
    try:
        from PyQt5.QtCore import Qt
        if img is None or (hasattr(img, "isNull") and img.isNull()):
            return 0
        if hasattr(img, "toImage"):
            img = img.toImage()
        small = img.scaled(16, 16, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        vals = []
        for y in range(16):
            for x in range(16):
                c = small.pixelColor(x, y)
                vals.append((c.red() * 299 + c.green() * 587 + c.blue() * 114) // 1000)
        if not vals:
            return 0
        avg = sum(vals) / float(len(vals))
        bits = 0
        for i, v in enumerate(vals):
            if v >= avg:
                bits |= (1 << i)
        return bits
    except Exception:
        return 0


def hash_distance(a: int, b: int) -> int:
    """两个指纹差多少位（0~256，越小越像）"""
    try:
        return bin((int(a) ^ int(b)) & 0xFFFFFFFFFFFFFFFF).count("1")
    except Exception:
        return 999


def last_capture_ms() -> float:
    """上一次抓屏耗时（毫秒），排查"卡一下"时很有用"""
    return float(_last["ms"] or 0.0)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("显示器:", monitors())
    t0 = time.time()
    img = capture_qimage(0)
    if img is None:
        print("✗ 抓屏失败")
    else:
        print("尺寸:", img.width(), "x", img.height(),
              "| 耗时 %.0f ms" % ((time.time() - t0) * 1000), "| 空白:", is_blank(img))
        ok = capture_png(os.path.join("tmp", "cap_test.png"))
        print("存 PNG:", ok, "| 文件大小:",
              os.path.getsize(os.path.join("tmp", "cap_test.png")) if ok else "-")
