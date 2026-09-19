# -*- coding: utf-8 -*-
"""本机地址绕过系统代理。

为什么需要：
    挂加速器 / 梯子时，很多客户端会把系统代理环境变量（HTTP_PROXY / HTTPS_PROXY）
    设成全局代理，连 `http://127.0.0.1:9880`（桌宠自己的语音服务）、
    `http://127.0.0.1:28565`（控制接口）也一起走代理 → 代理连不上本机 → 请求失败，
    表现就是"开梯子时桌宠信号不正常"（语音没声、状态显示未运行、对话超时）。

做法：
    把本机地址（127.0.0.1 / localhost / ::1）追加进 NO_PROXY / no_proxy。
    requests、urllib 都是"每次请求读环境变量"，所以启动时设一次就够，
    并且**只追加**——用户自己配置的绕过项不会丢。
"""
import os

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1", "0.0.0.0")


def _is_local_host(host) -> bool:
    """是不是本机地址（127.x / localhost / ::1 / 0.0.0.0）"""
    try:
        h = str(host or "").strip().lower()
        if h.startswith("["):                     # [::1]:1234
            h = h[1:].split("]")[0]
        h = h.split(":")[0]
        return h in ("127.0.0.1", "localhost", "::1", "0.0.0.0", "") or h.startswith("127.")
    except Exception:
        return False


def bypass_proxy_for_local() -> None:
    """本机地址一律绕过代理（幂等，可重复调用）

    ① 环境变量 NO_PROXY —— 对 curl / 命令行工具生效；
    ② Windows 的系统代理（注册表 Internet Settings）**不吃 NO_PROXY**，
       而且很多加速器/梯子会把绕过列表留空 → 连 127.0.0.1 都送去代理，
       代理没开时就表现为"桌宠信号不正常"（语音没声、状态未运行、请求 502）。
       所以这里把 urllib 的"是否绕过代理"判定换成：本机地址永远绕过。
       requests 内部也调用这个函数，因此它同样生效。
    """
    # ① 环境变量
    try:
        for key in ("NO_PROXY", "no_proxy"):
            cur = os.environ.get(key, "")
            parts = [p.strip() for p in cur.split(",") if p.strip()]
            for h in LOCAL_HOSTS:
                if h not in parts:
                    parts.append(h)
            os.environ[key] = ",".join(parts)
    except Exception:
        pass

    # ② 系统代理：换掉本机判定
    try:
        import urllib.request as _u
        _orig = getattr(_u, "proxy_bypass", None)
        if _orig is not None and not getattr(_orig, "_aipet_local", False):
            def _bypass(host, _orig=_orig):
                if _is_local_host(host):
                    return True
                try:
                    return bool(_orig(host))
                except Exception:
                    return False
            _bypass._aipet_local = True
            _u.proxy_bypass = _bypass
            try:
                _u.proxy_bypass_environment = _bypass
            except Exception:
                pass
            # requests 若已导入，把它命名空间里绑定的同名函数也换掉
            for _mod in ("requests.utils", "requests.adapters", "requests.sessions"):
                try:
                    _m = __import__(_mod, fromlist=["x"])
                    if hasattr(_m, "proxy_bypass"):
                        _m.proxy_bypass = _bypass
                except Exception:
                    continue
    except Exception:
        pass


def post_with_direct_fallback(url, **kw):
    """POST 请求；失败时改用「直连（忽略系统代理）」再试一次。

    为什么需要：挂加速器/梯子时系统代理可能指向一个没开着的本地端口
    （实测 ProxyEnable=1 → http://127.0.0.1:65533，绕过列表为空）→ 所有外网请求
    （DeepSeek/Qwen 对话与视觉）都会失败，桌宠就哑了（日志：本轮回复为空）。
    这里第一次失败就直连重试一次，梯子挂了也能正常对话。
    """
    try:
        import requests
    except Exception:
        return None
    kw.setdefault("timeout", (15, 300))
    try:
        return requests.post(url, **kw)
    except Exception as e1:
        try:
            r = requests.post(url, proxies={"http": None, "https": None}, **kw)
            print("[net] 走系统代理失败（%s）→ 已改直连并成功" % type(e1).__name__)
            return r
        except Exception:
            raise e1
