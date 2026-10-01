# -*- coding: utf-8 -*-
"""本地视觉模型的**接缝**（本项目不自带模型，留给用户自己接）。

为什么单独一个模块：项目原来只有云端视觉（`longtext.model_config.get_vision_model_config()`
给的模型名 + API Key，走本地代理转发）。用户想用**自己的本地视觉模型**（离线、不上云）时，
不应该去改业务代码 —— 这一个模块就是那个口子：

配置（config.json，默认全空 = 完全不启用，行为与从前一字不差）
    vision_source         "cloud"（默认）| "local"
    vision_local_url      本地服务的 HTTP 地址（POST 一张图，回描述）
    vision_local_command  或者：一个命令行程序（把图片路径当参数，stdout 当描述）
    vision_local_model    可选，随请求一起发过去（多模型服务用）
    vision_local_timeout  秒，默认 20

HTTP 契约（最宽松的那种，能对上一个是一个）
    请求：POST <vision_local_url>，JSON：
        {"model": "<vision_local_model>", "prompt": "<要它做什么>",
         "image_b64": "<纯 base64，不带 data: 前缀>"}
    响应：任选其一即可（按顺序尝试）
        {"text": "..."} / {"description": "..."} / {"result": "..."}
        {"choices": [{"message": {"content": "..."}}]}      ← OpenAI 兼容
        纯文本（非 JSON）

CLI 契约
    <vision_local_command> <图片文件路径> [--prompt <prompt>]
    描述读 stdout（UTF-8）。

失败一律**说人话**：返回 {"ok": False, "error": "…怎么配…"}，调用方打印出来 ——
绝不静默失败（这一条是 2026-09-29 审计里反复出现的坑）。
"""
import base64
import json
import os
import subprocess
import tempfile
import time

try:
    from tool.config import as_bool, enum_of, get_config, num   # noqa: F401
except Exception:                                     # 极端情况下也不要 import 期炸
    get_config = None
    enum_of = lambda v, allowed, default, name="": default   # noqa: E731
    num = lambda v, default, lo=None, hi=None: default       # noqa: E731
    as_bool = lambda v, default=False: default               # noqa: E731

SOURCES = ("cloud", "local")


def _cfg() -> dict:
    try:
        return get_config("./config.json") or {}
    except Exception:
        return {}


def source() -> str:
    """视觉来源：cloud（默认，走原来的云端链路）/ local（用户自己接的）。"""
    return enum_of(_cfg().get("vision_source"), SOURCES, "cloud", "vision_source")


def config() -> dict:
    """本地视觉的四个参数（都做了兜底）。"""
    c = _cfg()
    return {
        "url": str(c.get("vision_local_url") or "").strip(),
        "command": str(c.get("vision_local_command") or "").strip(),
        "model": str(c.get("vision_local_model") or "").strip(),
        "timeout": num(c.get("vision_local_timeout"), 20.0, 1.0, 600.0),
    }


def available() -> bool:
    """选 local 且至少配了 url / command 之一，才算"能用"。"""
    c = config()
    return bool(c["url"] or c["command"])


def status_text() -> str:
    """给人看的一句话状态（设置页/状态页/日志都用它，口径统一）。"""
    c = config()
    if c["url"] and c["command"]:
        return "本地视觉：已配 HTTP(%s) 与命令，优先用 HTTP" % c["url"]
    if c["url"]:
        return "本地视觉：HTTP %s（超时 %.0fs）" % (c["url"], c["timeout"])
    if c["command"]:
        return "本地视觉：命令 %s（超时 %.0fs）" % (c["command"], c["timeout"])
    return ("本地视觉还没接：选「本地（自己接）」就得填下面之一 ——"
            "「本地视觉服务地址」(config.json: vision_local_url) 或 "
            "「本地视觉命令」(config.json: vision_local_command)；"
            "不填就请把「视觉来源」(vision_source) 切回「云端」")


def _split_command(cmd: str) -> list:
    """把 `vision_local_command` 拆成 argv。

    为什么需要：用户写的往往是 `python D:\\tools\\describe.py`（带参数）或
    `"C:\\Program Files\\x\\v.exe"`（带空格）—— 直接当单个可执行名去跑必然失败。
    Windows 上路径里的反斜杠不能被 shlex 当转义符吃掉，所以 posix=False；
    但 posix=False 下引号会原样保留，于是再手工剥一层成对引号。
    """
    s = str(cmd or "").strip()
    if not s:
        return []
    try:
        import shlex
        if os.name == "nt":
            parts = shlex.split(s, posix=False)
            return [p[1:-1] if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'" else p
                    for p in parts]
        return shlex.split(s)
    except Exception:
        return [s]


def _b64_of(image, is_b64: bool = False) -> str:
    """把 data:URL / 文件路径 / 纯 base64 统一成**纯 base64**。"""
    s = str(image or "").strip()
    if s.startswith("data:") and "," in s:
        return s.split(",", 1)[1]
    if is_b64:
        return s
    if os.path.isfile(s):
        with open(s, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    return s                                   # 交给调用方/服务端去判


def _from_response(raw: str) -> str:
    """从各种可能的响应形状里抠出描述文字（宽松）。"""
    t = (raw or "").strip()
    if not t:
        return ""
    try:
        d = json.loads(t)
    except Exception:
        return t                               # 纯文本
    if isinstance(d, str):
        return d.strip()
    if isinstance(d, dict):
        for k in ("text", "description", "result", "content", "answer", "output"):
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        ch = d.get("choices")
        if isinstance(ch, list) and ch:
            m = (ch[0] or {}).get("message") or {}
            if isinstance(m.get("content"), str):
                return m["content"].strip()
    return ""


def describe(image, *, is_b64: bool = False, prompt: str = "") -> dict:
    """请本地视觉描述一张图。

    image: 文件路径 / data:URL / （is_b64=True 时）纯 base64
    返回 {"ok", "text", "error", "source": "local", "backend": "http"|"command", "elapsed"}
    失败时 error 一定是**能照着做**的中文（缺什么配什么）。
    """
    t0 = time.time()
    out = {"ok": False, "text": "", "error": "", "source": "local", "backend": "",
           "elapsed": 0.0}
    c = config()
    prompt = prompt or "请用简短的中文描述这张图里的场景、人物和主要活动，不超过50个字。"
    if not available():
        out["error"] = status_text()
        return out
    # ① HTTP（优先：跨语言、不用起临时文件）
    if c["url"]:
        out["backend"] = "http"
        try:
            import requests
            body = {"model": c["model"], "prompt": prompt, "image_b64": _b64_of(image, is_b64)}
            r = requests.post(c["url"], json=body, timeout=c["timeout"])
            text = _from_response(getattr(r, "text", "") or "")
            if r.status_code != 200:
                out["error"] = ("本地视觉服务返回 HTTP %s：%s"
                                % (r.status_code, (getattr(r, "text", "") or "")[:160]))
            elif not text:
                out["error"] = ("本地视觉服务返回了 200，但我没从响应里认出描述文字。"
                                "请让它回 {\"text\": \"...\"} 或 OpenAI 兼容的 choices[0].message.content")
            else:
                out["ok"] = True
                out["text"] = text
        except Exception as e:
            out["error"] = ("连本地视觉服务失败（%s: %s）。检查 vision_local_url 是否写对、"
                            "服务是否在跑" % (type(e).__name__, e))
        out["elapsed"] = round(time.time() - t0, 2)
        return out
    # ② CLI
    out["backend"] = "command"
    tmp = None
    try:
        img_path = image
        s = str(image or "")
        if is_b64 or s.startswith("data:"):
            tmp = tempfile.NamedTemporaryFile(prefix="aipet_vision_", suffix=".jpg",
                                              delete=False)
            tmp.write(base64.b64decode(_b64_of(image, is_b64) + "=="))
            tmp.close()
            img_path = tmp.name
        argv = _split_command(c["command"]) + [str(img_path)]
        if prompt:
            argv += ["--prompt", prompt]
        p = subprocess.run(argv, capture_output=True, timeout=c["timeout"])
        text = _from_response((p.stdout or b"").decode("utf-8", "replace"))
        if p.returncode != 0 and not text:
            out["error"] = ("本地视觉命令退出码 %s：%s"
                            % (p.returncode,
                               (p.stderr or b"").decode("utf-8", "replace")[:200]))
        elif not text:
            out["error"] = "本地视觉命令没在 stdout 给出描述（检查 vision_local_command）"
        else:
            out["ok"] = True
            out["text"] = text
    except Exception as e:
        out["error"] = ("跑本地视觉命令失败（%s: %s）。检查 vision_local_command 路径"
                        % (type(e).__name__, e))
    finally:
        if tmp is not None:
            try:
                os.remove(tmp.name)
            except Exception:
                pass
    out["elapsed"] = round(time.time() - t0, 2)
    return out
