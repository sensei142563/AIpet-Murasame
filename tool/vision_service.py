# -*- coding: utf-8 -*-
"""本地视觉服务：把「屏幕截图 → 一段中文描述」跑在本机显卡上。

为什么单独起一个服务：
  桌宠本体的 venv 里 torch 加载不起来（c10.dll 初始化失败），而 GPT-SoVITS 的
  runtime_rocm 里 torch + ROCm 是好的、显卡也是通的 → 视觉模型交给它跑，
  用 HTTP 暴露给桌宠，和 TTS 服务一个套路。

启动（由启动器自动拉起）：
    <GPT-SoVITS>/runtime_rocm/Scripts/python.exe tool/vision_service.py
环境变量（都可省）：
    VISION_MODEL_DIR   模型目录（默认读 config.json 的 vision_local_model_dir）
    VISION_PORT        监听端口（默认读 config.json 的 vision_local_port）

接口：
    GET  /            健康检查 → {"ok": true, "model": ..., "device": ...}
    POST /describe    {"image_b64": "...", "prompt": "可选"}
                      → {"ok": true, "text": "屏幕内容描述..."}
"""
import base64
import ctypes
import io
import json
import os
import sys
import threading
import time

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
CFG_PATH = os.path.join(APP, "config.json")

DEFAULT_MODEL_DIR = r"D:\下载\AI桌宠\vision\Qwen2-VL-2B-Instruct"
DEFAULT_PORT = 28460
DEFAULT_PROMPT = (
    "你现在要担任一个AI桌宠的视觉识别助手。我会向你提供用户此时的屏幕截图，"
    "你要详细描述屏幕内容与使用的软件，描述页面主题。"
    "请用中文、两到四句话说完，不要分点、不要写markdown。"
)


def _cfg() -> dict:
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def model_dir() -> str:
    v = os.environ.get("VISION_MODEL_DIR") or str(_cfg().get("vision_local_model_dir") or "").strip()
    return v or DEFAULT_MODEL_DIR


def max_side() -> int:
    """截图长边压到多少像素再喂给模型。

    越大认字越准（窗口标题、网页文字），越小越快 —— 视觉编码耗时随像素数
    近似平方增长（本机 1280 约 17s、896 约 6s）。想快就把 config.json 里的
    vision_max_side 调小。
    """
    try:
        return max(280, int(os.environ.get("VISION_MAX_SIDE") or _cfg().get("vision_max_side") or 1280))
    except Exception:
        return 1280


def port() -> int:
    try:
        return int(os.environ.get("VISION_PORT") or _cfg().get("vision_local_port") or DEFAULT_PORT)
    except Exception:
        return DEFAULT_PORT


def idle_unload_seconds() -> float:
    """空闲多久就把模型挪出显存（秒）。0 = 从不挪。

    为什么要让：8G 显卡上视觉模型独占约 6G，而语音合成（GPT-SoVITS）也要显卡，
    两边抢起来会显存不足。所以闲置一会儿就先把模型退回内存，下次识别再搬回来
    （几秒钟，MIOpen 缓存还在，不用重新调优）。
    """
    try:
        v = os.environ.get("VISION_IDLE_UNLOAD")
        if v is None:
            v = _cfg().get("vision_idle_unload", 300)
        return float(v)
    except Exception:
        return 300.0


def device_pref() -> str:
    """用哪块设备跑：cuda / cpu；留空 = 有显卡就用显卡。

    没装显卡驱动版 torch 的机器（安装时选了「不配置本地视觉模型环境」又自己
    装了 CPU 版 torch）也能跑，就是慢很多，所以这里让用户能强制指定。
    """
    try:
        v = str(os.environ.get("VISION_DEVICE") or _cfg().get("vision_device") or "").strip().lower()
        return v if v in ("cuda", "cpu") else ""
    except Exception:
        return ""


# image_processor / tokenizer / 模型本体，加载好后放这里
_model = {"qwen": None, "ip": None, "tok": None, "device": "cpu", "model_dir": "",
          "error": "", "last_use": 0.0, "offloaded": False}
_lock = threading.Lock()   # 一次只跑一个识别：就一张显卡，排队比互相抢显存稳


def _offload_now(reason: str = "") -> bool:
    """立刻把模型移出显存（打游戏/用完时用）。返回是否真的做了搬运。"""
    try:
        import torch
        with _lock:
            if _model["qwen"] is None or _model["offloaded"]:
                return False
            if _model["device"] != "cuda":
                return False
            _model["qwen"].to("cpu")
            torch.cuda.empty_cache()
            _model["offloaded"] = True
        print(f"[vision] 模型已移出显存（{reason or '手动'}），下次识别自动搬回来", flush=True)
        return True
    except Exception as e:
        print(f"[vision] ⚠ 移出显存失败：{type(e).__name__}: {e}", flush=True)
        return False


def _parent_alive() -> bool:
    """启动我的那个进程还在吗（不在了就该自己退出，别占着显存当孤儿）

    为什么需要：桌宠崩过一次（QScreen.grabWindow 在后台线程用，进程直接没了），
    结果这个视觉服务还活着、继续占着约 5G 显存，主人打游戏更卡了。
    """
    try:
        ppid = os.getppid()
        if not ppid:
            return True
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
        h = k32.OpenProcess(0x1000, False, int(ppid))   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong(0)
            ok = k32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
            return bool(ok) and code.value == 259          # STILL_ACTIVE
        finally:
            try:
                k32.CloseHandle(ctypes.c_void_p(h))
            except Exception:
                pass
    except Exception:
        return True          # 判断不了就当它还活着，别乱退出


def idle_guard():
    """后台盯着：长时间没人用就把模型移出显存，把显卡让给语音合成。

    顺便看管"启动我的那个进程还在不在"——不在了就自己退出（不留占显存的孤儿）。
    """
    import torch

    while True:
        time.sleep(30)
        try:
            if not _parent_alive():
                print("[vision] 启动我的程序已经退出 → 视觉服务自行结束（释放显存）", flush=True)
                try:
                    _offload_now("父进程已退出")
                except Exception:
                    pass
                os._exit(0)
        except Exception:
            pass
        try:
            idle = idle_unload_seconds()
            if idle <= 0 or _model["qwen"] is None or _model["offloaded"]:
                continue
            if _model["device"] != "cuda" or not ready_event.is_set():
                continue
            if time.time() - float(_model["last_use"] or 0) < idle:
                continue
            _offload_now(f"闲置超过 {idle:.0f}s")
        except Exception as e:
            print(f"[vision] ⚠ 显存回收失败：{type(e).__name__}: {e}", flush=True)


ready_event = threading.Event()   # 模型加载（含预热）完成


def build_io(model_dir_path: str) -> dict:
    """装配「图像处理器 + 分词器」，绕开 torchvision。

    transformers 5.x 的 AutoProcessor 会连带装配 Qwen2VLVideoProcessor，而它只有
    torchvision 后端（没有 PIL 版），这个环境里没装也不能装：给 ROCm 版 torch 配
    错版本的 torchvision 会把本来能用的 TTS 运行时搞坏。纯图片识别用不到视频
    处理器，所以这里只取图像处理器（缺 torchvision 时它自动退到 PIL 后端）
    和分词器，图像占位符的展开按官方规则自己做（见 describe）。
    """
    from transformers import AutoTokenizer, Qwen2VLImageProcessor

    return {
        "ip": Qwen2VLImageProcessor.from_pretrained(model_dir_path),
        "tok": AutoTokenizer.from_pretrained(model_dir_path),
    }


def load_model():
    import torch
    from transformers import Qwen2VLForConditionalGeneration

    d = model_dir()
    if not os.path.isdir(d):
        raise RuntimeError(f"模型目录不存在：{d}")
    pref = device_pref()
    if pref == "cuda" and not torch.cuda.is_available():
        print("[vision] ⚠ 设置了用显卡，但这套 torch 不支持（或没显卡）→ 改用 CPU（会很慢）", flush=True)
        pref = "cpu"
    dev = pref or ("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float16 if dev == "cuda" else torch.float32
    t0 = time.time()
    print(f"[vision] 正在加载视觉模型 {d}（设备 {dev}）…", flush=True)
    io_parts = build_io(d)
    print("[vision] 处理器就绪（图像 + 分词，未依赖 torchvision）", flush=True)
    try:
        mdl = Qwen2VLForConditionalGeneration.from_pretrained(
            d, torch_dtype=dtype, device_map=dev, trust_remote_code=True)
    except Exception:
        mdl = Qwen2VLForConditionalGeneration.from_pretrained(
            d, torch_dtype=dtype, trust_remote_code=True).to(dev)
    mdl.eval()
    _model.update({"qwen": mdl, "ip": io_parts["ip"], "tok": io_parts["tok"],
                   "device": dev, "model_dir": d})
    print(f"[vision] 加载完成，用时 {time.time() - t0:.1f}s", flush=True)
    warmup()


def warmup():
    """先拿一张跟真实截图差不多大的图跑一遍。

    AMD 显卡上 MIOpen 第一次遇到某个尺寸要现场搜卷积内核（能慢到三十多秒），
    这里提前跑掉并写进 MIOpen 缓存，用户真用的时候就快多了。
    """
    try:
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (1280, 720), (128, 128, 128)).save(buf, format="PNG")
        t0 = time.time()
        describe(base64.b64encode(buf.getvalue()).decode(), "用一句话描述这张图。", max_new=8)
        print(f"[vision] 预热完成，用时 {time.time() - t0:.1f}s", flush=True)
    except Exception as e:
        print(f"[vision] ⚠ 预热失败（不影响使用）：{type(e).__name__}: {e}", flush=True)


def _chat_text(text: str) -> str:
    """Qwen2-VL 官方对话格式（单图 + 单段文字，system 用默认那句）。"""
    return ("<|im_start|>system\nYou are a helpful assistant.<|im_end|>\n"
            "<|im_start|>user\n<|vision_start|><|image_pad|><|vision_end|>"
            f"{text}<|im_end|>\n<|im_start|>assistant\n")


def _game_mode() -> bool:
    """现在是不是在打游戏/全屏（决定"用完要不要立刻让出显存"）"""
    try:
        from tool.perf_guard import game_mode
        return bool(game_mode())
    except Exception:
        return False


def describe(image_b64: str, prompt: str = "", max_new: int = 256,
             max_side_px: int = 0) -> str:
    """识别一张图（max_side_px>0 时按调用方要求压缩，越小越快）。

    ⚠ 显存策略：**保持常驻**，用完不卸。
      主人要求"打游戏时识别也要快"，而卸了再用的代价是每次重新搬约 6G 上显卡（实测 7 秒）——
      打游戏本来显卡就吃紧，再叠 7 秒就更慢了。所以统一交给 idle_guard 按闲置阈值处理
      （默认 300 秒没人用才让出显存），想手动腾显存可以打 /unload。
    """
    with _lock:
        return _describe_locked(image_b64, prompt, max_new, max_side_px)


def _describe_locked(image_b64: str, prompt: str, max_new: int, max_side_px: int = 0) -> str:
    import torch
    from PIL import Image

    mdl, ip, tok = _model["qwen"], _model["ip"], _model["tok"]
    if mdl is None or ip is None:
        raise RuntimeError("模型还没加载好")
    dev = _model["device"]
    if _model.get("offloaded"):
        # 之前空闲让出了显存，现在搬回来（几秒）
        t_back = time.time()
        mdl.to(dev)
        _model["offloaded"] = False
        print(f"[vision] 模型重新载入显存，用时 {time.time() - t_back:.1f}s", flush=True)
    raw = base64.b64decode(image_b64)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    # 屏幕截图往往很大：长边压一压，省显存也更快
    # ⚠ 参数名不能叫 max_side：会遮蔽同名函数 max_side()（踩过：默认档不缩放 → 全尺寸推理超时）
    try:
        cap = max(280, int(max_side_px)) if max_side_px else max_side()
        if max(img.size) > cap:
            r = float(cap) / max(img.size)
            img = img.resize((max(1, int(img.width * r)), max(1, int(img.height * r))))
    except Exception as e:
        print(f"[vision] ⚠ 缩放失败（按原尺寸识别，会慢）：{e}", flush=True)

    enc = ip(images=[img], return_tensors="pt")
    ids = tok(_chat_text((prompt or DEFAULT_PROMPT).strip()), return_tensors="pt")["input_ids"][0]
    # 官方规则：一个 <|image_pad|> 展开成 prod(grid_thw)/merge_size² 个占位符
    pad = tok.convert_tokens_to_ids("<|image_pad|>")
    n = int(enc["image_grid_thw"][0].prod()) // (ip.merge_size ** 2)
    pos = int((ids == pad).nonzero()[0])
    ids = torch.cat([ids[:pos], ids[pos].repeat(n), ids[pos + 1:]]).unsqueeze(0).to(dev)
    pv = enc["pixel_values"].to(dev)
    gthw = enc["image_grid_thw"].to(dev)

    t0 = time.time()
    with torch.no_grad():
        try:
            # 先把图像特征算成 embed 再生成。
            # 为什么不直接把 pixel_values 交给 generate：那样每生成一个词都要
            # 重跑一遍视觉编码器（本机 17s/次），实测 32 个词要 19.9s；改成
            # 预计算只要 2.9s，出图内容完全一样。
            vis = mdl.get_image_features(pixel_values=pv, image_grid_thw=gthw)
            feats = getattr(vis, "pooler_output", None)
            if feats is None:
                feats = vis[0]
            if isinstance(feats, (list, tuple)):
                feats = feats[0]
            emb = mdl.get_input_embeddings()(ids).clone()
            emb[ids == pad] = feats.to(emb.dtype)
            out = mdl.generate(inputs_embeds=emb, attention_mask=torch.ones_like(ids),
                               max_new_tokens=int(max_new), do_sample=False)
            gen = out
        except Exception as e:
            print(f"[vision] ⚠ 预计算图像特征不可用（{type(e).__name__}: {e}）→ 退回直连 pixel_values", flush=True)
            out = mdl.generate(input_ids=ids, pixel_values=pv, image_grid_thw=gthw,
                               max_new_tokens=int(max_new), do_sample=False)
            gen = out[:, ids.shape[1]:]
    res = tok.batch_decode(gen, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    n_in, n_out = int(ids.shape[1]), int(gen.shape[1])
    _model["last_use"] = time.time()
    # 把这次占的显存还给显卡：识别峰值能到 7G 多，不放的话会和语音合成抢
    # （中间张量靠函数返回时自动释放，这里只是把 PyTorch 的缓存块交还驱动）
    try:
        if dev == "cuda":
            torch.cuda.empty_cache()
    except Exception:
        pass
    print(f"[vision] 描述完成，用时 {time.time() - t0:.1f}s"
          f"（输入 {n_in} token，生成 {n_out} token）", flush=True)
    return (res[0] if res else "").strip()


def main():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except Exception:
                pass

        def do_GET(self):
            path = str(getattr(self, "path", "/") or "/")
            # GET /unload → 立刻把模型移出显存（打游戏前/用完就卸，别占着显卡）
            if path.startswith("/unload"):
                return self._json({"ok": True, "unloaded": _offload_now("外部请求")})
            self._json({"ok": _model["qwen"] is not None, "loading": not ready_event.is_set(),
                        "error": _model["error"], "model": _model["model_dir"],
                        "device": _model["device"]})

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                req = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except Exception:
                return self._json({"ok": False, "error": "请求体不是 JSON"}, 400)
            if str(getattr(self, "path", "") or "").startswith("/unload"):
                return self._json({"ok": True, "unloaded": _offload_now("外部请求")})
            img = req.get("image_b64") or ""
            if not img:
                return self._json({"ok": False, "error": "缺少 image_b64"}, 400)
            # 模型还在加载时先等一会儿（首次会慢），别让桌宠白跑一趟云端
            if not ready_event.wait(timeout=300):
                return self._json({"ok": False, "error": "视觉模型还在加载，稍后再试"}, 503)
            if _model["error"]:
                return self._json({"ok": False, "error": _model["error"]}, 503)
            try:
                txt = describe(img, str(req.get("prompt") or ""),
                               int(req.get("max_new") or 256),
                               int(req.get("max_side") or 0))
                return self._json({"ok": True, "text": txt})
            except Exception as e:
                print(f"[vision] ⚠ 识别失败: {type(e).__name__}: {e}", flush=True)
                return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)

    p = port()
    srv = ThreadingHTTPServer(("127.0.0.1", p), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    threading.Thread(target=idle_guard, daemon=True).start()   # 闲置时把显存让给语音
    print(f"[vision] 🌐 本地视觉服务已启动 http://127.0.0.1:{p}/（模型加载中…）", flush=True)
    try:
        load_model()
    except Exception as e:
        import traceback
        _model["error"] = f"模型加载失败：{type(e).__name__}: {e}"
        print(f"[vision] ✗ {_model['error']}", flush=True)
        traceback.print_exc()
    ready_event.set()
    print(f"[vision] ✅ 准备就绪（设备 {_model['device']}）", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
