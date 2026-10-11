import re
import time
import socket
import asyncio
import functools
import io
import json
import os
import threading
from datetime import datetime
from typing import List, Dict, Optional, TYPE_CHECKING

import aiohttp
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse

from tool.config import enum_of, get_config
from pets.pet_registry import get_prompt_path

# ============== App ==============
app = FastAPI()


# ===== 重型任务闸门（docs/plan/03：TTS/识图必须排队）=====
# 本机显存实测 6141MiB，F5 常驻占 5668MiB、只余 253MiB；本地 LLM 与 whisper 再并发只会互相挤爆。
# 这里让 api.py 进程内的重型接口**串行**，并对外暴露 /heavy/status 供手机显示"电脑正忙"。
# 注意：F5-TTS 跑在独立进程（9881），不在本闸门范围内（已在 status 里如实标注）。
from tool.heavy_gate import GATE as _HEAVY, Busy as _HeavyBusy


def heavy_route(name, timeout=120.0):
    """把一个重型接口纳入串行闸门；忙满上限时返回 503 + error=busy（便于手机优雅回退到本机离线 TTS）。"""
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(*a, **kw):
            try:
                tok = await asyncio.to_thread(_HEAVY.acquire, name, timeout)
            except _HeavyBusy as e:
                return JSONResponse(
                    {"error": "busy", "holder": e.holder, "waited_ms": int(e.waited * 1000),
                     "hint": "电脑正忙，可改用手机本机离线 TTS / SenseVoice"},
                    status_code=503)
            try:
                return await fn(*a, **kw)
            finally:
                _HEAVY.release(tok)
        return wrapper
    return deco


@app.get("/heavy/status")
async def heavy_status():
    """重型任务闸门状态：手机端可据此显示"电脑正忙（合成中）"。"""
    return _HEAVY.status()



# ── Jev（TypeSafe "System One"）───────────────────────────────────────────────
# 只服务**封闭、可验证**的判断（如"从角色 biaoqingbao/ 的文件名里挑一个"）。
# 手机端通过 POST /jev/choose 调用本机这一层，因此手机侧不需要能访问 TypeSafe
# （TypeSafe 对部分地区返回 HTTP 451，本机有代理即可）。
def jev_choose_sync(state, options, question, timeout: float = 4.0):
    """同步实现，便于离线单测。任何异常/无 key 都返回 name=None，调用方保持原行为。"""
    try:
        opts = [str(o) for o in (options or [])]
        if not state or not opts:
            return {"name": None, "confidence": 0.0, "reason": "no state/options"}
        from tool.jev import available, choose
        if not available(None):
            return {"name": None, "confidence": 0.0, "reason": "no key"}
        name, conf = choose(state=str(state), options=opts,
                            instructions=str(question or "从给定选项里选一个。"),
                            cfg=None, timeout=float(timeout or 4.0))
        return {"name": name, "confidence": float(conf or 0.0)}
    except Exception as e:
        return {"name": None, "confidence": 0.0, "reason": type(e).__name__}


@app.post("/jev/choose")
async def jev_choose(request: Request):
    """手机端调用：POST {state, options[], question?, timeout?} → {name, confidence, reason?}"""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"name": None, "confidence": 0.0, "reason": "bad json"})
    out = jev_choose_sync(data.get("state"), data.get("options"), data.get("question"),
                          data.get("timeout", 4.0))
    return JSONResponse(out)

# Upstream service endpoints
OLLAMA_UPSTREAM_URL = os.getenv("OLLAMA_UPSTREAM_URL", "http://localhost:11434/api/generate")

# ============== Local Model (optional) ==============
base_model_path = "./models/Qwen3-14B"
lora_model_path = "./models/Murasame"

# 仅用于类型提示（不影响运行时）
if TYPE_CHECKING:
    from transformers import AutoModelForCausalLM, AutoTokenizer

model: Optional["AutoModelForCausalLM"] = None
tokenizer: Optional["AutoTokenizer"] = None


def _lazy_import_local_deps():
    """仅在需要本地推理时导入重依赖"""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    return torch, PeftModel, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def load_model_and_tokenizer():
    torch, PeftModel, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig = _lazy_import_local_deps()
    if torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"

    tok = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )

    mdl = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        device_map=device,
        quantization_config=bnb_config,
        trust_remote_code=True,
        offload_buffers=True,
    )
    mdl = PeftModel.from_pretrained(mdl, lora_model_path)
    mdl.eval()
    return mdl, tok


def now_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============== Endpoints ==============
# qwen3-lora (local inference)
from pydantic import BaseModel

class Qwen3LoraRequest(BaseModel):
    history: List[Dict[str, str]]


@app.post("/qwen3-lora")
@heavy_route("qwen3-lora")
async def qwen3_lora(req: Qwen3LoraRequest):
    global model, tokenizer
    history = req.history

    model_type = enum_of(get_config("./config.json").get("model_type"), ("local", "qwen", "deepseek"), "qwen", "model_type")
    if model_type != "local":
        return {"error": "qwen3-lora 不可用：当前为云端模式"}

    if model is None or tokenizer is None:
        model, tokenizer = load_model_and_tokenizer()

    text = tokenizer.apply_chat_template(
        history,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    import torch
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.9,
            top_p=0.95,
            top_k=20,
            pad_token_id=tokenizer.eos_token_id,
        )

    gen_ids = outputs[0][inputs["input_ids"].shape[-1]:]
    reply = tokenizer.decode(gen_ids, skip_special_tokens=True).strip()
    return reply


class OllamaRequest(BaseModel):
    prompt: dict
    headers: dict


@app.post("/ollama")
@heavy_route("ollama")
async def ollama_qwen3(req: OllamaRequest):
    try:
        timeout = aiohttp.ClientTimeout(total=180)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(OLLAMA_UPSTREAM_URL, headers=req.headers, json=req.prompt) as resp:
                data = await resp.json()
                if resp.status != 200:
                    return data
                return data
    except Exception as e:
        return {"error": f"upstream request failed: {e}"}


class GPTSoVITSTTSRequest(BaseModel):
    params: dict


@app.post("/tts")
@heavy_route("tts")
async def gpt_sovits_tts(req: GPTSoVITSTTSRequest):
    url = "http://localhost:9880/tts"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=req.params,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as response:
                if response.status == 200:
                    content = await response.read()
                    return StreamingResponse(io.BytesIO(content), media_type="audio/wav")
                else:
                    text = await response.text()
                    return {"error": f"TTS API返回错误: {await response.json()}"}
    except Exception as e:
        return {"error": f"TTS upstream 请求失败: {e}"}


class cloudAPIRequest(BaseModel):
    payload: dict
    headers: dict


@app.post("/cloudAPI")
async def cloudAPI(req: cloudAPIRequest):
    # URL 路由按模型名前缀决定（deepseek* → deepseek，其余 → dashscope），
    # 不依赖 model_type 配置，兼容视觉模型 / 自定义模型名的自由切换。
    url_deepseek = "https://api.deepseek.com/chat/completions"
    url_qwen = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    model = str(req.payload.get("model", "")).strip().lower()
    if model.startswith("deepseek"):
        url = url_deepseek
    else:
        url = url_qwen

    # ⚠ 以前这里只有一次请求，而且失败时 `await response.json()` 会直接抛异常：
    #   上游一个 429/5xx、或者代理抽风返回空响应体，中转就吐「500 + 空 body」，
    #   桌宠那边看到的就是"响应体为空/非 JSON" → 弹「信号好像不太好」（用户反馈）。
    #   现在：① 失败会重试；② 第二次改直连（绕过系统代理，梯子挂了也能通）；
    #   ③ 任何情况都返回 JSON（不再 500 空响应），把真正的原因带回给桌宠日志。
    last_err = "未知错误"
    for attempt in range(3):
        trust_env = attempt == 0          # 第一次走系统代理，之后直连
        try:
            timeout = aiohttp.ClientTimeout(total=180 if attempt == 0 else 90)
            async with aiohttp.ClientSession(trust_env=trust_env, timeout=timeout) as session:
                async with session.post(url, headers=req.headers, json=req.payload) as response:
                    raw = await response.read()
                    if response.status == 200:
                        try:
                            return json.loads(raw.decode("utf-8", "replace"))
                        except Exception:
                            last_err = "上游 200 但响应体为空/非 JSON"
                    else:
                        body = raw.decode("utf-8", "replace")[:300]
                        last_err = f"上游 HTTP {response.status}: {body}"
                        # 4xx 是请求本身的问题（密钥/额度/参数），重试没意义
                        if 400 <= response.status < 500:
                            print(f"[cloudAPI] {last_err}（不重试）")
                            return {"error": last_err}
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        print(f"[cloudAPI] ⚠ 第 {attempt + 1}/3 次失败（{'走代理' if trust_env else '直连'}）：{last_err}")
        if attempt < 2:
            await asyncio.sleep(0.8 * (attempt + 1))
    print(f"[cloudAPI] ✗ 3 次都没成功：{last_err}")
    return {"error": last_err}


# ============== Control Endpoints (PCL 启动器按钮调用) ==============
_control_flags: Dict[str, bool] = {"voice": False, "screenshot": False, "camera": False,
                                   "live2d": False, "longtext": False,
                                   "reset_position": False,      # 重置桌宠位置（回屏幕中央）
                                   "reload_touch": False}        # 重新读取触摸区域（编辑器保存后）
_control_lock = threading.Lock()
_feature_status: Dict[str, str] = {"voice": "off", "screenshot": "off", "camera": "off",
                                   "live2d": "off", "longtext": "off"}

# 桌宠窗口位置（由 main.py 定期同步；PCL「重置桌宠位置」按钮读它做提示）
_window_pos: Dict[str, int] = {"x": -1, "y": -1}


def set_window_pos(x: int, y: int) -> None:
    _window_pos["x"], _window_pos["y"] = int(x), int(y)

# 长文本模式当前是否激活（由桌宠同步）
_long_text_mode_active = False

# 语音识别流程控制（PCL 按钮长按 → 录音 → STT → 对话）
_voice_start_flag = False
_voice_end_flag = False


@app.get("/control")
async def control_status():
    return {"flags": _control_flags.copy(), "status": _feature_status.copy()}


# 关闭桌宠（启动器「关闭桌宠」按钮）——必须放在 /control/{feature} 之前，
# 否则会被通配路由吃掉（历史 bug：请求返回「不支持的功能: shutdown」，桌宠关不掉）
_shutdown_request = False


@app.post("/control/shutdown")
async def control_shutdown():
    global _shutdown_request
    _shutdown_request = True
    print("[API] 收到关闭请求（启动器「关闭桌宠」）")
    return {"ok": True, "action": "关闭桌宠"}


def check_shutdown() -> bool:
    """由 main.py 轮询：为 True 时优雅退出（会保存窗口位置）"""
    global _shutdown_request
    if _shutdown_request:
        _shutdown_request = False
        return True
    return False


@app.post("/control/{feature}")
async def control_feature(feature: str):
    mapping = {"voice": "语音识别", "screenshot": "屏幕识别", "camera": "摄像头", "live2d": "Live2D",
               "longtext": "长文本模式切换", "reset_position": "重置桌宠位置（回到屏幕中央）",
               "reload_touch": "重新读取触摸区域（全身触摸范围）",
               # ★ 2026-10-01：主题页改了「对话框文字粗细」这类显示设置后，让桌宠重读配置
               "reload_theme": "重新应用主题/字体设置（对话框文字粗细等）"}
    if feature not in mapping:
        return {"error": f"不支持的功能: {feature}"}
    with _control_lock:
        _control_flags[feature] = True
    return {"ok": True, "action": mapping[feature]}


@app.get("/pet/position")
async def pet_position():
    """桌宠窗口当前坐标（供启动器显示 / 判断在不在屏幕内）"""
    return dict(_window_pos)


# ===== 手机端 STT：收原始 WAV 字节，复用 tool/stt.py 的 faster-whisper large-v3 =====
# 手机本地只有 sherpa 14M（效果一般），连得上电脑时改走这里，质量直接对齐桌面端。
try:
    import threading as _th
    _th.Timer(1.0, _stt_warmup).start()
except Exception:
    pass


# ===== QQ 通道（搬手机第一步：只读状态与会话）=====
# NapCat/OneBot11 的实时收发在桌面端进程里，这里先提供"看"的能力：
#   /qq/status    连接方式与在线状态 + 会话数
#   /qq/sessions  所有 QQ 会话（私聊/群）与最后一条消息预览
#   /qq/messages  某个会话的最近消息
# 发送通道（命令队列）见 /qq/queue/send，桌面端轮询后经 OneBot11 WS 发出。
def _qq_memory_module():
    import importlib.util as _ilu
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qq", "qq_memory.py")
    spec = _ilu.spec_from_file_location("aipet_qq_memory", p)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _qq_mem_dir():
    try:
        mod = _qq_memory_module()
        d = getattr(mod, "_active_qq_memory_dir", None)
        if callable(d):
            return str(d())
    except Exception:
        pass
    pet = "murasame"
    try:
        cfg = json.loads(io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "config.json"), encoding="utf-8").read())
        pet = cfg.get("qq_pet") or cfg.get("active_pet") or pet
    except Exception:
        pass
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "pets", pet, "memory", "qq")


def _qq_cfg():
    try:
        return json.loads(io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                               "config.json"), encoding="utf-8").read())
    except Exception:
        return {}


def _port_open(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


@app.get("/qq/status")
async def qq_status():
    cfg = _qq_cfg()
    ws_url = str(cfg.get("qq_napcat_ws") or "ws://127.0.0.1:3001")
    http_url = str(cfg.get("qq_napcat_http") or "http://127.0.0.1:6099")
    m = re.search(r"//([^:/]+):(\d+)", ws_url)
    host, port = (m.group(1), int(m.group(2))) if m else ("127.0.0.1", 3001)
    d = _qq_mem_dir()
    files = []
    if os.path.isdir(d):
        files = [f for f in os.listdir(d) if f.endswith(".json")]
    return {
        "qq_enabled": str(cfg.get("qq_enabled", "")) == "true",
        "napcat_ws": ws_url,
        "napcat_http": http_url,
        "napcat_ws_listening": _port_open(host, port),
        "owner_id": cfg.get("qq_owner_id"),
        "memory_dir": d,
        "sessions": len(files),
        "note": "实时收发在桌面端进程内（OneBot11 正向 WS）；此处只读会话与状态",
    }


@app.get("/qq/sessions")
async def qq_sessions():
    d = _qq_mem_dir()
    out = []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if not f.endswith(".json"):
                continue
            p = os.path.join(d, f)
            last = None
            cnt = 0
            try:
                j = json.loads(io.open(p, encoding="utf-8").read())
                h = j.get("history") or []
                cnt = len(h)
                if h:
                    last = str(h[-1].get("content") or "")[:80]
            except Exception:
                pass
            out.append({"file": f, "key": f[:-5], "messages": cnt, "last": last,
                        "mtime": int(os.path.getmtime(p))})
    out.sort(key=lambda x: -x["mtime"])
    return {"dir": d, "count": len(out), "sessions": out[:50]}


@app.get("/qq/messages")
async def qq_messages(session: str, limit: int = 30):
    d = _qq_mem_dir()
    f = os.path.join(d, session if session.endswith(".json") else session + ".json")
    if not os.path.isfile(f):
        return {"session": session, "error": "not found", "dir": d}
    try:
        j = json.loads(io.open(f, encoding="utf-8").read())
        h = j.get("history") or []
        return {"session": session, "total": len(h), "messages": h[-max(1, min(limit, 200)):]}
    except Exception as e:
        return {"session": session, "error": "%s: %s" % (type(e).__name__, e)}


@app.get("/qq/outbox")
async def qq_outbox_status(limit: int = 20):
    """手机发起的 QQ 发送队列状态：等待发送 / 最近已处理。"""
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    qf = os.path.join(d, "qq_outbox.jsonl")
    of = os.path.join(d, "qq_outbox.offset")
    af = os.path.join(d, "qq_outbox_ack.jsonl")

    def _tail(p, n):
        if not os.path.isfile(p):
            return []
        out = []
        try:
            for line in io.open(p, encoding="utf-8"):
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
        except Exception:
            pass
        return out[-max(1, min(int(n), 200)):]

    total = 0
    if os.path.isfile(qf):
        try:
            total = int(os.path.getsize(qf))
        except Exception:
            total = 0
    try:
        done = int(io.open(of, encoding="utf-8").read().strip() or 0) if os.path.isfile(of) else 0
    except Exception:
        done = 0
    return {"outbox": qf, "bytes_total": total, "bytes_done": done,
            "pending_bytes": max(0, total - done),
            "queued": _tail(qf, limit), "acked": _tail(af, limit),
            "worker_hint": "消费者在桌面端进程（QQBridge.connect 启动的 qq-outbox 线程）"}


@app.post("/qq/queue/send")
async def qq_queue_send(request: Request):
    """把"要发到 QQ 的消息"写进队列文件，桌面端轮询后经 OneBot11 发出。
    body: {"target_type":"private|group","target_id":123,"text":"...","sticker":"可选"}"""
    body = await request.body()
    try:
        item = json.loads(body.decode("utf-8", "replace") or "{}")
    except Exception:
        return {"ok": False, "error": "bad json"}
    if not item.get("target_id") or not (item.get("text") or item.get("sticker")):
        return {"ok": False, "error": "need target_id and text/sticker"}
    qf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "qq_outbox.jsonl")
    os.makedirs(os.path.dirname(qf), exist_ok=True)
    item["queued_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with io.open(qf, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return {"ok": True, "queued_to": qf, "item": item}


@app.post("/stt")
@heavy_route("stt")
async def stt_transcribe(request: Request):
    import tempfile as _tf
    data = await request.body()
    if not data or len(data) < 1000:
        return {"text": "", "ms": 0, "reason": "audio too small (%d bytes)" % len(data)}
    t0 = time.time()
    tmp = _tf.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        tmp.write(data)
        tmp.close()
        text = await asyncio.to_thread(_stt_transcribe_full, tmp.name)
        return {"text": text or "", "ms": int((time.time() - t0) * 1000), "engine": "faster-whisper-large-v3"}
    except Exception as e:
        return {"text": "", "ms": int((time.time() - t0) * 1000), "error": "%s: %s" % (type(e).__name__, e)}
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


_STT_MOD = None
_STT_LOCK = None


def _stt_module():
    """只加载一次（否则每次请求都会重建 faster-whisper 模型，单条要 20~37 秒）。"""
    global _STT_MOD, _STT_LOCK
    import threading
    if _STT_LOCK is None:
        _STT_LOCK = threading.Lock()
    with _STT_LOCK:
        if _STT_MOD is None:
            import importlib.util as _ilu
            spec = _ilu.spec_from_file_location(
                "aipet_stt",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool", "stt.py"))
            mod = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _STT_MOD = mod
    return _STT_MOD


def _stt_warmup():
    try:
        t0 = time.time()
        _stt_module().warmup("large-v3")
        print("[stt] 预热完成 %.1fs" % (time.time() - t0), flush=True)
    except Exception as e:
        print("[stt] 预热失败: %s: %s" % (type(e).__name__, e), flush=True)


def _stt_transcribe_full(path):
    return _stt_module().transcribe_full(path)


@app.post("/voice/start")
async def voice_start():
    """PCL 按钮按下 → 开始录音"""
    global _voice_start_flag
    with _control_lock:
        _voice_start_flag = True
    return {"ok": True}


@app.post("/voice/end")
async def voice_end():
    """PCL 按钮松开 → 停止录音并识别"""
    global _voice_end_flag
    with _control_lock:
        _voice_end_flag = True
    return {"ok": True}


# ============ Live2D 显示调参（PCL 图形化面板 → main.py 轮询应用）============
_live2d_display_state: Dict = {}
_live2d_display_request = {"apply": None, "save": False, "reset": False}
_live2d_lock = threading.Lock()


@app.get("/live2d/display")
async def live2d_display_get():
    """返回桌宠当前 Live2D 显示参数（供 PCL 面板初始化滑块）"""
    return {"state": dict(_live2d_display_state)}


@app.post("/live2d/display")
async def live2d_display_apply(request: Request):
    """PCL 滑块实时应用显示参数（main.py 轮询后应用到模型）"""
    global _live2d_display_request
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "bad json"}
    if not isinstance(data, dict):
        return {"ok": False, "error": "bad data"}
    with _live2d_lock:
        _live2d_display_request["apply"] = data
    return {"ok": True}


@app.post("/live2d/display/save")
async def live2d_display_save():
    """把当前显示参数持久化到角色 pet.json"""
    with _live2d_lock:
        _live2d_display_request["save"] = True
    return {"ok": True}


@app.post("/live2d/display/reset")
async def live2d_display_reset():
    """重置模型位置 offset 为 0"""
    with _live2d_lock:
        _live2d_display_request["reset"] = True
    return {"ok": True}


def consume_live2d_request():
    """main.py 轮询：取出并清空待处理的显示参数请求"""
    with _live2d_lock:
        if (_live2d_display_request["apply"] is None
                and not _live2d_display_request["save"]
                and not _live2d_display_request["reset"]):
            return None
        req = {
            "apply": _live2d_display_request["apply"],
            "save": _live2d_display_request["save"],
            "reset": _live2d_display_request["reset"],
        }
        _live2d_display_request["apply"] = None
        _live2d_display_request["save"] = False
        _live2d_display_request["reset"] = False
        return req


def set_live2d_display_state(state: dict):
    """main.py 回写当前显示参数（PCL GET 读取）"""
    with _live2d_lock:
        _live2d_display_state.update(state)


def set_feature_status(key: str, value: str):
    """由 main.py 调用，更新功能状态"""
    with _control_lock:
        _feature_status[key] = value


def check_flag(key: str) -> bool:
    """由 main.py 轮询，获取并清除控制标志"""
    with _control_lock:
        if _control_flags.get(key):
            _control_flags[key] = False
            return True
    return False


def set_long_text_mode_active(active: bool):
    """由桌宠调用，同步长文本模式状态"""
    global _long_text_mode_active
    with _control_lock:
        _long_text_mode_active = bool(active)
        _feature_status["longtext"] = "on" if active else "off"


def check_voice_start() -> bool:
    """由 main.py 轮询，检测是否应该开始录音"""
    global _voice_start_flag
    with _control_lock:
        if _voice_start_flag:
            _voice_start_flag = False
            return True
    return False


def check_voice_end() -> bool:
    """由 main.py 轮询，检测是否应该停止录音"""
    global _voice_end_flag
    with _control_lock:
        if _voice_end_flag:
            _voice_end_flag = False
            return True
    return False


# ============== 长文本模式 QQ 预留接口 ==============

class LongTextChatRequest(BaseModel):
    text: str
    history: List[Dict[str, str]] = []
    max_tokens: int = 4096


@app.post("/longtext/chat")
@heavy_route("longtext")
async def longtext_chat(req: LongTextChatRequest):
    """
    QQ 机器人预留接口（SSE 流式返回）。
    入参: text + history → 直接调用长文本模型流式回复（模型由 config 的
    longtext_model / longtext_model_name / reasoning_level 控制）。
    未来 QQ 接入时，直接调用此接口即可获得与桌宠一致的对话。
    """
    import json as _json
    import requests as _req
    from longtext.model_config import get_longtext_model_config

    try:
        mcfg = get_longtext_model_config()
        if not mcfg:
            return {"error": "未配置对话模型 API Key"}

        api_key = mcfg["api_key"]
        url = mcfg["url"]

        # 读取长文本 prompt（按当前角色动态解析）
        prompt_path = get_prompt_path("long")
        system_prompt = "你是一个可爱的桌宠角色。"
        try:
            if prompt_path and os.path.exists(prompt_path):
                with open(prompt_path, "r", encoding="utf-8") as f:
                    system_prompt = f.read().strip()
        except Exception:
            pass

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(req.history[-40:])  # 最近 20 轮
        messages.append({"role": "user", "content": req.text})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": mcfg["model"],
            "messages": messages,
            "max_tokens": req.max_tokens,
            "stream": True,
        }
        # 推理等级附加参数（off 时可能为空 dict）
        payload.update(mcfg.get("reasoning", {}) or {})

        async def sse_stream():
            with _req.post(url, json=payload, headers=headers, stream=True, timeout=(15, 300)) as resp:
                if resp.status_code != 200:
                    yield f"data: {_json.dumps({'error': resp.text[:200]}, ensure_ascii=False)}\n\n"
                    return
                for line in resp.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        yield "data: [DONE]\n\n"
                        break
                    try:
                        chunk = _json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if delta.get("reasoning_content"):
                            continue
                        content = delta.get("content")
                        if content:
                            yield f"data: {_json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                    except Exception:
                        continue

        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            sse_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    except Exception as e:
        return {"error": f"longtext/chat 调用失败: {e}"}


# ============== Entrypoint ==============
if __name__ == "__main__":
    cfg = get_config("./config.json")
    if cfg.get("model_type", "qwen").lower() == "local":
        model, tokenizer = load_model_and_tokenizer()
    # 仅本机：PCL/桌宠都用 localhost 访问；绑 0.0.0.0 会把无鉴权 API 暴露到局域网。
    # 日志/断开噪音的处理统一在 tool/api_server.py（access_log=False + 忽略 10054）
    from tool.api_server import run_blocking
    run_blocking(app, "127.0.0.1", 28565)