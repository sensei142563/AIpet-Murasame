import io
import os
import threading
from datetime import datetime
from typing import List, Dict, Optional, TYPE_CHECKING

import aiohttp
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from tool.config import get_config
from pets.pet_registry import get_prompt_path

# ============== App ==============
app = FastAPI()

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
async def qwen3_lora(req: Qwen3LoraRequest):
    global model, tokenizer
    history = req.history

    model_type = get_config("./config.json")["model_type"]
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
    url_deepseek = "https://api.deepseek.com/chat/completions"
    url_qwen = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    model_type = get_config("./config.json")["model_type"]
    if model_type == "deepseek":
        url = url_deepseek
    elif model_type == "qwen":
        url = url_qwen
    if req.payload["model"] == "qwen3-vl-plus":
        url = url_qwen
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            headers=req.headers,
            json=req.payload,
            timeout=aiohttp.ClientTimeout(total=180),
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"error": f"API返回错误: {await response.json()}"}


# ============== Control Endpoints (PCL 启动器按钮调用) ==============
_control_flags: Dict[str, bool] = {"voice": False, "screenshot": False, "camera": False, "live2d": False, "longtext": False}
_control_lock = threading.Lock()
_feature_status: Dict[str, str] = {"voice": "off", "screenshot": "off", "camera": "off", "live2d": "off", "longtext": "off"}

# 长文本模式当前是否激活（由桌宠同步）
_long_text_mode_active = False

# 语音识别流程控制（PCL 按钮长按 → 录音 → STT → 对话）
_voice_start_flag = False
_voice_end_flag = False


@app.get("/control")
async def control_status():
    return {"flags": _control_flags.copy(), "status": _feature_status.copy()}


@app.post("/control/{feature}")
async def control_feature(feature: str):
    mapping = {"voice": "语音识别", "screenshot": "屏幕识别", "camera": "摄像头", "live2d": "Live2D", "longtext": "长文本模式切换"}
    if feature not in mapping:
        return {"error": f"不支持的功能: {feature}"}
    with _control_lock:
        _control_flags[feature] = True
    return {"ok": True, "action": mapping[feature]}


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


def is_long_text_mode_active() -> bool:
    """PCL / QQ 接口查询长文本模式状态"""
    with _control_lock:
        return _long_text_mode_active


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
async def longtext_chat(req: LongTextChatRequest):
    """
    QQ 机器人预留接口（SSE 流式返回）。
    入参: text + history → 直接调用 qwen-plus 流式回复。
    未来 QQ 接入时，直接调用此接口即可获得与桌宠一致的对话。
    """
    import json as _json
    import requests as _req

    try:
        cfg = get_config("./config.json")
        api_key = cfg.get("APIKEY", {}).get("qwen", "")
        if not api_key:
            return {"error": "未配置 Qwen API Key"}

        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

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
            "model": "qwen-plus",
            "messages": messages,
            "max_tokens": req.max_tokens,
            "stream": True,
        }

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
    if cfg.get("model_type", "deepseek").lower() == "local":
        model, tokenizer = load_model_and_tokenizer()
    uvicorn.run(app, host="0.0.0.0", port=28565)