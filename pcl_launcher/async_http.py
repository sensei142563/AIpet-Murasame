# -*- coding: utf-8 -*-
"""启动器用的非阻塞 HTTP 小工具。

为什么需要（2026-10-01 用户反馈"切主题字体 / 进引导页等界面时启动器卡一下"）：
    启动器里原来直接 `urllib.request.urlopen(..., timeout=2~5)` 在 **UI 线程**里发请求。
    当桌宠的 API 没起来（或没响应）时，连接不会快速失败，而是**一直等到超时**
    → 实测每次卡 2000 ms（切主题那次 timeout=2，控制指令 timeout=5 更久）。
    → 每次进页面/切字体都像顿一下。

这里的约定：
    · post_async：发完就不管（后台线程），UI 永不等待；
    · api_alive：带缓存的存活探测，后台刷新，UI 读到的永远是上次结果（不阻塞）。
"""
import json
import threading
import time
import urllib.request

_ALIVE_CACHE = {}          # base -> (bool, 时间戳)
_ALIVE_LOCK = threading.Lock()
_ALIVE_TTL = 2.0           # 秒；期间直接返回上次结果
_ALIVE_TIMEOUT = 0.8       # 单次探测最长等这么久（本地端口正常是毫秒级）


def post_async(url, data=b"", timeout=2.0, headers=None, tag=""):
    """后台线程发 POST，不阻塞 UI；失败只打印日志（不抛）。"""
    def _run():
        try:
            req = urllib.request.Request(url, data=data, method="POST",
                                         headers=headers or {})
            urllib.request.urlopen(req, timeout=timeout).read()
            if tag:
                print(f"[AsyncHTTP] {tag} 已发送")
        except Exception as e:
            print(f"[AsyncHTTP] {tag or url} 发送失败（忽略）: {e}")
    threading.Thread(target=_run, daemon=True).start()


def get_json(url, timeout=1.5):
    """同步 GET JSON（调用方自己保证不卡 UI：只用于短超时场景）。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def api_alive(base, ttl=_ALIVE_TTL):
    """桌宠 API 是否活着：**立即**返回上次结果，同时后台探一次（绝不阻塞 UI）。"""
    now = time.time()
    with _ALIVE_LOCK:
        cached = _ALIVE_CACHE.get(base)
        if cached and (now - cached[1]) < ttl:
            return cached[0]

    def _probe():
        ok = False
        try:
            req = urllib.request.Request(base, method="GET")
            with urllib.request.urlopen(req, timeout=_ALIVE_TIMEOUT) as r:
                ok = (r.status == 200)
        except Exception:
            ok = False
        with _ALIVE_LOCK:
            _ALIVE_CACHE[base] = (ok, time.time())

    threading.Thread(target=_probe, daemon=True).start()
    # 首次未知时先按"没起来"处理（避免 UI 等待），下一次调用就有真实结果了
    return cached[0] if cached else False
