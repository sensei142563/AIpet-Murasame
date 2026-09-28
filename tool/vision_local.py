# -*- coding: utf-8 -*-
"""本地视觉服务客户端：问本机那个「截图 → 中文描述」服务要一段描述。

为什么要单独一层
----------------
tool/vision_setup.py 负责把「模型 + 解释器 + 配置」凑齐，真正跑推理的是**另一个进程**
（tool/vision_service.py，借带显卡的 torch 环境，用 HTTP 暴露出来）。桌宠本体不该为了
一次识别就把 torch 拉进自己的进程 —— 本机实测过：先 Qt 后 torch 会崩；而且那套
ROCm/CUDA 运行时只在它自己的解释器里能用。所以这里只做 HTTP 客户端：

    GET  /            健康检查 → {"ok": bool, "loading": bool, "device": "cuda"/"cpu"}
    POST /describe    {"image_b64": ..., "prompt": ..., "max_new": ..., "max_side": ...}
                      → {"ok": true, "text": "屏幕内容描述..."}
    POST /unload      让服务把模型挪出显存（打游戏前 / 用完）

三条口径
  1. **短超时**：识别只是「顺便看一眼」，不能把主人的对话卡住；超时就回落云端。
     长边 896 在本机实测约 13.5 秒，所以默认给 25 秒余量（config: vision_describe_timeout）
  2. 服务没起来 / 没开本地来源 / 超时 / 返回乱码 → 一律返回**空串**，由调用方回落云端。
     绝不编内容，也绝不把 HTTP 错误当描述。
  3. 只在 config 的 vision_source == "local" 时才发请求（别人机器上默认走云端，零副作用）
"""
import base64
import json
import os
import socket
import sys
import urllib.error
import urllib.request

try:      # 控制台被重定向时 Windows 会用 GBK 编码 stdout
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DEFAULT_PORT = 28460
DEFAULT_TIMEOUT = 25.0          # 一次识别最多等多久（秒）
DEFAULT_HEALTH_TIMEOUT = 1.5    # 健康检查：只想知道"在不在"，必须很快
DEFAULT_PROMPT = (
    "你现在要担任一个AI桌宠的视觉识别助手。我会向你提供用户此时的屏幕截图，"
    "你要详细描述屏幕内容与使用的软件，描述页面主题。"
    "请用中文、两到四句话说完，不要分点、不要写markdown。"
)


def _cfg() -> dict:
    """读 config.json（缺失时由 tool.config 回退 config.example.json）"""
    try:
        from tool.config import get_config
        return get_config("./config.json") or {}
    except Exception:
        return {}


def enabled(cfg: dict = None) -> bool:
    """主人有没有把识别来源设成本地"""
    c = cfg if isinstance(cfg, dict) else _cfg()
    return str(c.get("vision_source") or "cloud").strip().lower() == "local"


def port(cfg: dict = None) -> int:
    c = cfg if isinstance(cfg, dict) else _cfg()
    try:
        return int(c.get("vision_local_port") or DEFAULT_PORT)
    except Exception:
        return DEFAULT_PORT


def describe_url(cfg: dict = None) -> str:
    return "http://127.0.0.1:%d/describe" % port(cfg)


def health_url(cfg: dict = None) -> str:
    return "http://127.0.0.1:%d/" % port(cfg)


def timeout_sec(cfg: dict = None) -> float:
    c = cfg if isinstance(cfg, dict) else _cfg()
    try:
        v = float(c.get("vision_describe_timeout") or DEFAULT_TIMEOUT)
    except Exception:
        v = DEFAULT_TIMEOUT
    return max(3.0, min(600.0, v))


def _int_cfg(cfg: dict, key: str, default: int, low: int, high: int) -> int:
    try:
        v = int(cfg.get(key) or default)
    except Exception:
        v = default
    return max(low, min(high, v))


def _opener():
    # 和 tool/net_env.py 同一个思路：本机地址绝不走系统代理（挂了梯子也要能连上自己）
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _read_json(resp) -> dict:
    """把响应读成 dict；读不到 / 不是 JSON 一律返回空 dict"""
    try:
        raw = resp.read(1 << 20)
        obj = json.loads(raw.decode("utf-8", "replace") or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _http_error_json(e) -> dict:
    """HTTP 错误码也是**有内容的**：服务用 400/503 报「缺图」「模型还在加载」，
    body 里那句人话要留着，否则出问题时主人只看到"没反应"（踩过）。"""
    obj = _read_json(e)
    if obj:
        return obj
    return {"ok": False, "error": "HTTP %s" % getattr(e, "code", "?")}


def _post(url: str, payload: dict, timeout: float) -> dict:
    """POST 一段 JSON；任何异常都返回 dict（调用方按"没拿到"处理，绝不让它抛）"""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with _opener().open(req, timeout=max(0.5, float(timeout))) as r:
            return _read_json(r)
    except urllib.error.HTTPError as e:
        return _http_error_json(e)
    except Exception:
        return {}


def health(cfg: dict = None, timeout: float = DEFAULT_HEALTH_TIMEOUT) -> dict:
    """服务在不在。

    返回里 `ok`=模型已就绪、`loading`=还在加载；服务报错码时带上 `error`
    （500 之类）。**连不上**才返回空 dict —— 这两种情况要分得开，不然
    「服务炸了」会被说成「没开服务」，查起来一头雾水。
    """
    c = cfg if isinstance(cfg, dict) else _cfg()
    req = urllib.request.Request(health_url(c))
    try:
        with _opener().open(req, timeout=max(0.2, float(timeout))) as r:
            return _read_json(r)
    except urllib.error.HTTPError as e:
        return _http_error_json(e)
    except Exception:
        return {}


def something_listening(p: int = 0, host: str = "127.0.0.1") -> bool:
    """端口上有没有人在听 —— 用 bind 试探，**零网络往返**。

    为什么不用 connect：本机实测（_audit_fish9269/probe_local_connect.py，2026-09-24）
    Windows 上连一个没在听的回环端口**不会立刻被拒**，裸 socket 也要等满超时
    （1.511s；urllib 1.501s）—— 这台机器上像是安全软件静默丢掉了 SYN。而
    「顺手看一眼屏幕」不该先白等 1.5 秒，所以先用 bind 判一下：
      bind 失败（EADDRINUSE）= 有人在听；bind 成功 = 没人 → 立刻返回。

    ⚠ 前提是占位方没开 SO_REUSEADDR。tool/vision_service.py 明确把
      allow_reuse_address 关掉了（就是为了防"静默双开"），所以对我们的服务是准的。
      万一别人用别的程序占着这个端口，最坏结果只是"多走一次 HTTP 探测"，不会误判成"在跑"。
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, int(p)))
        return False
    except OSError:
        return True
    finally:
        try:
            s.close()
        except Exception:
            pass


def alive(cfg: dict = None) -> bool:
    """端口上有没有一个视觉服务在应答（不要求模型已经加载完）

    先做零成本端口预检，再问 HTTP —— 服务没开时这个函数必须是"几乎不花时间"的，
    否则每次问屏幕都要先赔上 1.5 秒。
    """
    c = cfg if isinstance(cfg, dict) else _cfg()
    if not something_listening(port(c)):
        return False
    h = health(c)
    return bool(h) and ("ok" in h or "loading" in h)


def describe_b64(image_b64: str, prompt: str = "", cfg: dict = None,
                 timeout: float = 0.0, url: str = "") -> str:
    """把一张已编码的图交给本地服务识别。拿不到就返回空串。"""
    c = cfg if isinstance(cfg, dict) else _cfg()
    b64 = str(image_b64 or "").strip()
    if not b64:
        return ""
    payload = {
        "image_b64": b64,
        "prompt": (prompt or DEFAULT_PROMPT).strip(),
        "max_new": _int_cfg(c, "vision_max_new", 160, 40, 1024),
        "max_side": _int_cfg(c, "vision_max_side", 896, 280, 4096),
    }
    obj = _post(url or describe_url(c), payload, timeout or timeout_sec(c))
    if not obj.get("ok"):
        # 服务明确报错时吱一声（连接不上是常态，不吵主人）
        if obj.get("error"):
            print("[本地视觉] ⚠ 识别没成功：%s" % str(obj.get("error"))[:160])
        return ""
    return str(obj.get("text") or "").strip()


def describe_file(img_path: str, prompt: str = "", cfg: dict = None,
                  timeout: float = 0.0, url: str = "") -> str:
    """把磁盘上的一张图交给本地服务识别（读不到文件 / 识别失败都返回空串）"""
    try:
        with open(img_path, "rb") as f:
            raw = f.read()
    except Exception:
        return ""
    if not raw:
        return ""
    return describe_b64(base64.b64encode(raw).decode("ascii"), prompt, cfg, timeout, url)


def unload(cfg: dict = None, timeout: float = 3.0) -> bool:
    """让服务把模型挪出显存（打游戏前 / 用完）。真做了搬运才返回 True。"""
    c = cfg if isinstance(cfg, dict) else _cfg()
    obj = _post("http://127.0.0.1:%d/unload" % port(c), {}, timeout)
    return bool(obj.get("unloaded"))


def look(img_path: str, prompt: str = "", cfg: dict = None, timeout: float = 0.0) -> str:
    """给 tool/screen_intent.py 用的一步到位：能用本地就用本地，否则返回空串。

    ⚠ 这里**故意**只判断 vision_source 与「服务在不在」两件事，不做任何云端兜底 ——
      回落逻辑留在 screen_intent 里，免得两个地方各兜一半、出错时说不清是谁的锅。
    """
    c = cfg if isinstance(cfg, dict) else _cfg()
    if not enabled(c):
        return ""
    if not alive(c):
        return ""
    return describe_file(img_path, prompt, c, timeout)


def status_text(cfg: dict = None) -> str:
    """一句话状态（给状态窗/自检用）"""
    c = cfg if isinstance(cfg, dict) else _cfg()
    if not enabled(c):
        return "识别来源：云端（本地视觉没开）"
    if not something_listening(port(c)):
        return "识别来源：本地，但 127.0.0.1:%d 上没有程序在监听" % port(c)
    h = health(c)
    if not h:
        return "识别来源：本地，端口有人监听但不应答（不是视觉服务？）"
    if h.get("ok"):
        return "识别来源：本地，服务就绪（设备 %s）" % (h.get("device") or "未知")
    if h.get("loading"):
        return "识别来源：本地，服务正在加载模型…"
    return "识别来源：本地，服务状态异常：%s" % str(h.get("error") or "")[:80]


if __name__ == "__main__":
    # 手动体检：python tool/vision_local.py [图片路径]
    _c = _cfg()
    print(status_text(_c))
    print("describe 地址:", describe_url(_c))
    if len(sys.argv) > 1:
        t = describe_file(sys.argv[1], cfg=_c)
        print("识别结果:", t or "（没拿到描述）")
