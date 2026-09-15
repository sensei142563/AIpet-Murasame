# -*- coding: utf-8 -*-
"""全局异常兜底（让「一个小错误」不再等于「启动器整个消失」）。

背景：PyQt5 里只要**槽函数/事件处理/虚拟重写**里抛出未捕获异常，默认行为是
`qFatal()` → `abort()`：进程直接消失，冻结版还没有控制台 → 用户只看到
「点了没反应 / 窗口卡住 / 突然没了」，且没有任何日志。

实测（Qt 5.15.2 + PyQt 5.15.7）：只要 `sys.excepthook` 被替换成自己的实现，
PyQt 就不再 abort —— 进程会继续活着，异常被记录到 tmp/pcl_error.log。
所以这里做两件事：
1) 装一个「写日志」的 excepthook（同时兼容冻结版：脚本目录 = exe 目录）；
2) 提供 `guard(fn)`：把 QTimer 之类需要「绝不出错」的回调包一层 try/except。
"""

import os
import sys
import traceback

_LOG_NAME = "pcl_error.log"


def _base_dir() -> str:
    """程序根目录（冻结后 = exe 所在目录）"""
    try:
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        return os.getcwd()


def log_exc(where: str, exc: BaseException = None, tb=None) -> str:
    """把异常写进 tmp/pcl_error.log（尽量不抛异常）"""
    path = ""
    try:
        d = os.path.join(_base_dir(), "tmp")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, _LOG_NAME)
        if exc is None:
            exc = sys.exc_info()[1]
        if tb is None:
            tb = exc.__traceback__ if exc is not None else None
        import time
        head = f"[{time.strftime('%m-%d %H:%M:%S')}] {where} :: {type(exc).__name__}: {exc}\n"
        body = "".join(traceback.format_exception(type(exc), exc, tb)) if exc is not None else ""
        with open(path, "a", encoding="utf-8", errors="replace") as f:
            f.write(head + body + "-" * 60 + "\n")
        return path
    except Exception:
        return path


def install(tag: str = "launcher") -> bool:
    """安装全局兜底（幂等）。应在 QApplication 建好之后尽早调用。"""
    if getattr(install, "_installed", False):
        return True

    def _hook(tp, val, tb):
        try:
            log_exc(f"{tag}: 未捕获异常", val, tb)
        except Exception:
            pass
        # 仍然打印一份到控制台（有控制台时便于开发排查）
        try:
            traceback.print_exception(tp, val, tb)
        except Exception:
            pass

    try:
        sys.excepthook = _hook
        install._installed = True
        try:
            os.makedirs(os.path.join(_base_dir(), "tmp"), exist_ok=True)
        except Exception:
            pass
        print(f"[Safety] 已启用全局异常兜底（异常写入 tmp/{_LOG_NAME}，不再直接终止进程）")
        return True
    except Exception as e:
        print(f"[Safety] ⚠ 兜底安装失败: {e}")
        return False


def guard(fn, where: str = ""):
    """包一层 try/except：用于 QTimer.singleShot / 延迟回调等「出错也不能崩」的地方"""
    def _inner(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as e:
            log_exc(where or getattr(fn, "__name__", "callback"), e)
            return None
    return _inner
