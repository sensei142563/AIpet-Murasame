# -*- coding: utf-8 -*-
"""识图自检：一句话回答「屏幕识图 / 摄像头识图现在通不通，断在哪一环」。

为什么要有这个
--------------
云端识图这条路要四样东西同时成立：
  1) config.json 的 `vision_model_name`（默认 deepseek-flash）
  2) 对应厂商的 API Key（`APIKEY.deepseek` 或 `APIKEY.qwen`）
  3) 本机 API 代理在跑（`api.py`，`local_api.cloud_api`，默认 127.0.0.1:28565/cloudAPI）
  4) 外网可达
任何一环断了，桌宠的表现都是"看不到"，而主人不容易知道断在哪 —— 以前 `cloud_vl` 还会
把"（未配置视觉模型 API Key）"这种**错误提示当成屏幕内容**返回给对话模型，让她照着念。
所以这里把四环逐条报出来，并且可以真的发一张**自造的纯色小图**（不含任何屏幕内容、
不含隐私）走完整链路，看云端到底回什么。

用法：
    python -m tool.vision_check               # 只查配置与本机代理，**不发外网请求**
    python -m tool.vision_check --live         # 真发一张自造小图，看云端回什么
    python -m tool.vision_check --live --image 某张图.png

退出码：0 = 配置齐全且本机代理在跑；1 = 有环节缺失（详情见输出）
"""
import json
import os
import struct
import sys
import zlib

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP not in sys.path:
    sys.path.insert(0, APP)


def cfg_path() -> str:
    return os.path.join(APP, "config.json")


def load_cfg() -> dict:
    try:
        with open(cfg_path(), encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def proxy_url() -> str:
    """本机 API 代理地址（识图请求实际发到这里，由 api.py 转发到真云端）"""
    try:
        return str((load_cfg().get("local_api") or {}).get("cloud_api")
                   or "http://localhost:28565/cloudAPI")
    except Exception:
        return "http://localhost:28565/cloudAPI"


def proxy_host_port() -> tuple:
    """从代理地址里抠出 host / port（抠不出来就给默认值）"""
    try:
        from urllib.parse import urlparse
        u = urlparse(proxy_url())
        host = u.hostname or "127.0.0.1"
        port = int(u.port or (443 if u.scheme == "https" else 80))
        return host, port
    except Exception:
        return "127.0.0.1", 28565


def proxy_alive() -> bool:
    """本机代理在不在（用 bind 预检，0ms；连不上的话不要在这白等超时）"""
    try:
        from tool.net_env import port_open
        return bool(port_open(*proxy_host_port()))
    except Exception:
        return False


def tiny_png(path: str, rgb=(90, 140, 190), size: int = 48) -> str:
    """写一张自造的纯色 PNG（只用标准库，不依赖 Qt/PIL）。

    自检用的图必须是我们自己造的：拿屏幕截图当测试图会把主人屏幕内容送出去。
    """
    w = h = int(size)
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return path


def check() -> dict:
    """查配置与本机代理（**不发外网请求**）"""
    from longtext.model_config import get_vision_model_config, DEFAULT_VISION_MODEL, _model_family
    cfg = load_cfg()
    model = str(cfg.get("vision_model_name", "")).strip() or DEFAULT_VISION_MODEL
    family = _model_family(model)
    keys = cfg.get("APIKEY") or {}
    has_key = bool(str(keys.get(family, "") or "").strip())
    vcfg = get_vision_model_config()
    host, port = proxy_host_port()
    alive = proxy_alive()
    out = {
        "config": cfg_path(),
        "vision_model_name": model,
        "vision_model_default": DEFAULT_VISION_MODEL,
        "key_family": family,
        "key_present": has_key,
        "key_masked": (str(keys.get(family, ""))[:6] + "…") if has_key else "",
        "proxy_url": proxy_url(),
        "proxy_host": host,
        "proxy_port": port,
        "proxy_alive": alive,
        "other_keys": sorted([k for k, v in keys.items() if str(v or "").strip()]),
        "usable": bool(has_key and alive),
        "note": "",
    }
    if not has_key:
        out["note"] = ("config.json 的 APIKEY.%s 是空的 → 识图一定失败。"
                       "把对应厂商的 Key 填进去即可（视觉模型走哪个厂商由模型名前缀决定）。"
                       % family)
    elif not alive:
        out["note"] = ("API Key 有了，但本机 API 代理 %s:%d 没在跑（它是 api.py，"
                       "桌宠启动时会一起起）→ 识图请求发不出去。" % (host, port))
    else:
        out["note"] = "配置齐全、本机代理在跑；想验证整条链路请加 --live（会发一张自造小图）。"
    return out


def raw_probe(image_path: str = "", timeout: float = 60.0) -> dict:
    """真发一次请求，返回云端的原始答复（用于诊断"到底错在哪"）。

    ⚠ 会联网。默认不调用，只有 --live / --image 才走这里。
    """
    import base64
    import tempfile
    from longtext.model_config import get_vision_model_config
    vcfg = get_vision_model_config()
    if not vcfg:
        return {"ok": False, "stage": "config", "error": "没配视觉模型 Key"}
    path = image_path
    tmp = ""
    if not path:
        tmp = os.path.join(tempfile.gettempdir(), "aipet_vision_check.png")
        path = tiny_png(tmp)
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        return {"ok": False, "stage": "read", "error": "%s: %s" % (type(e).__name__, e)}
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "webp": "webp", "bmp": "bmp"}.get(ext, "png")
    payload = {
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/%s;base64,%s" % (mime, b64)}},
            {"type": "text", "text": "用一句话说你看到了什么颜色。"}]}],
        "model": vcfg["model"],
        "max_tokens": 64,
        "stream": False,
    }
    headers = {"Accept": "application/json", "Content-Type": "application/json",
               "Authorization": "Bearer " + vcfg["api_key"]}
    try:
        from tool.net_env import post_with_direct_fallback as _postf
        resp = _postf(proxy_url(), json={"payload": payload, "headers": headers},
                      timeout=(10, timeout))
        data = resp.json()
    except Exception as e:
        return {"ok": False, "stage": "post", "error": "%s: %s" % (type(e).__name__, e),
                "proxy": proxy_url()}
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass
    if isinstance(data, dict) and data.get("choices"):
        try:
            text = data["choices"][0]["message"]["content"] or ""
            return {"ok": bool(str(text).strip()), "stage": "done",
                    "text": str(text).strip(), "model": vcfg["model"]}
        except Exception as e:
            return {"ok": False, "stage": "parse", "error": str(e), "raw": str(data)[:300]}
    return {"ok": False, "stage": "cloud", "error": "云端没给 choices",
            "raw": str(data)[:300], "model": vcfg["model"]}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    def _arg(name, default=""):
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return argv[i + 1]
        return default

    r = check()
    print("=== 识图自检（屏幕识图 / 摄像头识图共用这条路）===")
    print("  配置文件          : %s" % r["config"])
    print("  视觉模型名        : %s%s" % (r["vision_model_name"],
          "（没写 config，用的是默认）" if not load_cfg().get("vision_model_name") else ""))
    print("  厂商 / Key        : %s / %s %s" % (r["key_family"],
          "已配置 " + r["key_masked"] if r["key_present"] else "**缺失**",
          "（config 里还有：%s）" % ", ".join(r["other_keys"]) if r["other_keys"] else ""))
    print("  本机 API 代理     : %s（%s）" % (r["proxy_url"],
          "在跑" if r["proxy_alive"] else "**没在跑**"))
    print("  结论              : %s" % r["note"])

    if "--live" in argv or _arg("--image"):
        if not r["key_present"]:
            print("\n--live 跳过：连 Key 都没有，发出去也只会 401。")
            return 1
        if not r["proxy_alive"]:
            print("\n--live 跳过：本机 API 代理没在跑，请求发不出去。")
            return 1
        print("\n=== 真发一张图（自造纯色小图，不含屏幕内容）===")
        lv = raw_probe(_arg("--image", ""))
        print(json.dumps(lv, ensure_ascii=False, indent=2))
        if lv.get("ok"):
            print("\n识图链路通了：云端说的是「%s」。" % lv.get("text", ""))
            return 0
        print("\n识图没通（阶段：%s）。上面的 raw/error 就是云端原话，照它排查。"
              % lv.get("stage"))
        return 1
    return 0 if r["usable"] else 1


if __name__ == "__main__":
    sys.exit(main())
