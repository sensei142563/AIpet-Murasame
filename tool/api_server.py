# -*- coding: utf-8 -*-
"""本地控制 API（/control，端口 28565）的启动器。

为什么单独抽一个模块：
  1) **日志刷屏**：启动器 PCL 每 300ms 探一次 `GET /control`，uvicorn 默认把每个请求
     都打成 `INFO: 127.0.0.1:xxxxx - "GET /control HTTP/1.1" 200 OK`
     → 桌宠控制台被刷屏，真正的报错反而被冲掉。这里统一 `access_log=False`。
  2) **WinError 10054 噪音**：客户端短连接提前断开（启动器/浏览器取消请求）时，
     asyncio 会打一整段 `Exception in callback _ProactorBasePipeTransport...`。
     旧代码靠 `asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())` 来避免，
     但 **uvicorn 0.37 的 `loop="auto"` 在 Windows 上直接返回 ProactorEventLoop**
     （见 uvicorn/loops/asyncio.py 的 asyncio_loop_factory），根本不看 policy
     → 那招已经失效，噪音照旧。这里自己建事件循环 + 装异常处理器，明确忽略断开类异常，
     与 uvicorn 版本无关。
"""

import sys


def make_config(app, host: str = "127.0.0.1", port: int = 28565, log_level: str = "info"):
    """构造 uvicorn 配置（关掉 access 日志——/control 是高频轮询，不该进日志）"""
    import uvicorn
    return uvicorn.Config(app, host=host, port=port, log_level=log_level, access_log=False)


def ignore_disconnect_handler(previous=None):
    """事件循环异常处理器：忽略"客户端断开"这类无害异常，其余交给原处理器。"""

    def _handler(loop, context):
        exc = context.get("exception")
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return                                  # 客户端先挂了，不是我们的错，别打 traceback
        if previous is not None:
            previous(loop, context)
        else:
            loop.default_exception_handler(context)

    return _handler


def run_blocking(app, host: str = "127.0.0.1", port: int = 28565, log_level: str = "info"):
    """在当前线程里阻塞运行 API 服务（调用方自己开线程）。

    不调用 `uvicorn.Server.run()`：那样会用 uvicorn 自己的 loop factory（Windows=Proactor），
    我们没法挂异常处理器。
    """
    import asyncio
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

    import uvicorn
    server = uvicorn.Server(make_config(app, host, port, log_level))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(ignore_disconnect_handler(loop.get_exception_handler()))
    try:
        loop.run_until_complete(server.serve())
    finally:
        try:
            loop.close()
        except Exception:
            pass
