# -*- coding: utf-8 -*-
"""本机地址绕过系统代理 + 代理挂掉时自动直连重试。

为什么需要（真实故障：挂着加速器/梯子时桌宠"信号不正常"）
--------------------------------------------------------
① 很多加速器会把系统代理设成**全局**代理（HTTP_PROXY / HTTPS_PROXY，或 Windows 的
   「Internet 选项 → 局域网设置」），连 `http://127.0.0.1:28565`（桌宠控制接口）、
   `http://127.0.0.1:9880`（本地语音服务）也一起送去代理 → 代理连不上本机 → 请求失败。
   表现：启动器显示"未运行"、语音没声、对话超时。
② Windows 的系统代理（注册表 Internet Settings）**不认 NO_PROXY 环境变量**，而且很多
   加速器把"绕过列表"留空 → 只设环境变量还不够。
③ 代理端口没开（实测：ProxyEnable=1 指向 http://127.0.0.1:12000，但那个代理没在跑）→
   **所有**外网请求（DeepSeek/Qwen 对话与视觉）全部失败 → 桌宠直接哑掉，日志只有
   "本轮回复为空"。pip / modelscope / huggingface 下载同理（WinError 10061）。

做法
----
· `bypass_proxy_for_local()`：把 127.0.0.1 / localhost / ::1 / 0.0.0.0 **追加**进
  NO_PROXY / no_proxy（只追加，用户自己的绕过项不丢），并把 urllib 的 proxy_bypass
  判定换成"本机地址永远绕过"（requests 内部也用它，所以对 requests 同样生效）。
  幂等，各入口启动时调一次即可（requests/urllib 每次请求都读它）。
· `post_with_direct_fallback()`：POST 失败时用「直连（忽略系统代理）」再试一次，
  代理挂了也能正常对话。

排查用：`python -m tool.net_env`
"""
import os
import sys

try:  # 控制台被重定向时 Windows 用 GBK，打印中文会 UnicodeEncodeError
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1", "0.0.0.0")


def _say(msg: str) -> None:
    """编码安全的打印（被管道接走时也不能炸）"""
    try:
        print(msg)
    except Exception:
        try:
            sys.stdout.write((msg + "\n").encode("utf-8", "replace").decode("utf-8", "replace"))
        except Exception:
            pass


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
    ② Windows 的系统代理不吃 NO_PROXY → 把 urllib 的"是否绕过代理"判定换成本机地址永远绕过，
       requests 内部也调用这个函数，因此它同样生效。
    """
    # ① 环境变量（只追加）
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
    """POST；失败时改用「直连（忽略系统代理）」再试一次。

    返回 requests 的 Response；两次都失败则抛出第一次的异常（保持调用方原有的异常语义）。
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
            _say("[net] 走系统代理失败（%s）→ 已改直连并成功" % type(e1).__name__)
            return r
        except Exception:
            raise e1


def proxy_state() -> dict:
    """当前代理相关状态（排查用）"""
    st = {k: os.environ.get(k, "") for k in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
                                             "http_proxy", "https_proxy", "no_proxy")}
    try:
        import urllib.request as _u
        st["urllib.getproxies()"] = _u.getproxies()
    except Exception as e:
        st["urllib.getproxies()"] = "取不到: %s" % e
    return st


if __name__ == "__main__":
    _say("=== 当前代理状态 ===")
    for k, v in proxy_state().items():
        _say("  %-22s %s" % (k, v))
    _say("\n=== 调用 bypass_proxy_for_local() ===")
    bypass_proxy_for_local()
    for k in ("NO_PROXY", "no_proxy"):
        _say("  %-22s %s" % (k, os.environ.get(k, "")))
    try:
        import urllib.request as _u
        _say("  本机 127.0.0.1 绕过代理? %s" % _u.proxy_bypass("127.0.0.1:28565"))
        _say("  外网 example.com 绕过代理? %s" % _u.proxy_bypass("example.com"))
    except Exception as e:
        _say("  自检失败: %s" % e)
