# -*- coding: utf-8 -*-
"""
F5-TTS HTTP 服务 — 长文本模式中文语音合成
端口: 9881

用法:
    python -m longtext.f5tts_server

接口:
    POST /infer
    {
        "text": "要合成的文本",
        "ref_audio": "reference_voices/long_chinese/953244.wav",
        "ref_text": "能和老师在一起，我真的，好高兴！"
    }
    → 返回 wav 音频流 (24000Hz, 16bit mono)

GPU 优先，CPU 回退。
"""

import io
import os
import sys
import json
import time
import threading
from pathlib import Path

# ── 路径准备 ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# 将项目根目录加入 sys.path（保证 longtext/ 内可直接 import）
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ── 全局状态 ─────────────────────────────────────────────
_model = None
_model_lock = threading.Lock()
_model_ready = False
_device = "cpu"

# 角色语音包优先，全局兜底 —— 由 pet_registry.get_long_ref() 动态解析
from pets.pet_registry import get_long_ref
DEFAULT_REF_AUDIO, DEFAULT_REF_TEXT = get_long_ref()
DEFAULT_REF_AUDIO = str(DEFAULT_REF_AUDIO)


def _arabic_to_chinese(text: str) -> str:
    """
    合成前将阿拉伯数字转为中文读音（显示文本不受影响）。
    例如: "第31次，0.4秒" → "第三十一次，零点四秒"
    需要 pip install cn2an；未安装时跳过转换，不影响 TTS。
    """
    try:
        import re
        import cn2an
    except ImportError:
        return text

    # 小数：0.4 → 零点四
    text = re.sub(
        r"\d+\.\d+",
        lambda m: cn2an.an2cn(m.group(0)),
        text,
    )
    # 整数：31 → 三十一（"low" 模式，不带百千万前缀）
    text = re.sub(
        r"\d+",
        lambda m: cn2an.an2cn(m.group(0), "low"),
        text,
    )
    return text


def _detect_device() -> str:
    """GPU 优先，CPU 回退"""
    try:
        import torch
        if torch.cuda.is_available():
            print(f"[F5TTS] 检测到 GPU: {torch.cuda.get_device_name(0)}")
            return "cuda"
    except Exception as e:
        print(f"[F5TTS] torch 不可用: {e}")
    print("[F5TTS] 使用 CPU 模式")
    return "cpu"


def load_model():
    """加载 F5-TTS 模型（首次调用时，之后常驻内存）"""
    global _model, _model_ready, _device
    with _model_lock:
        if _model_ready and _model is not None:
            return _model

        _device = _detect_device()

        # 查找模型权重目录
        candidates = [
            BASE_DIR / "F5-TTS_Models" / "F5TTS_v1_Base",
            BASE_DIR / "F5-TTS_Models",
            Path(os.environ.get("HF_HOME", "~/.cache/huggingface")).expanduser() / "hub" / "models--SWivid--F5-TTS",
        ]
        model_dir = None
        for c in candidates:
            if c.exists():
                model_dir = str(c)
                print(f"[F5TTS] 使用模型目录: {model_dir}")
                break
        if model_dir is None:
            # 自动下载（走 HF_HUB）
            print("[F5TTS] 未找到本地模型，尝试从 HuggingFace 下载...")
            try:
                from huggingface_hub import snapshot_download
                model_dir = snapshot_download(
                    "SWivid/F5-TTS",
                    local_dir=str(BASE_DIR / "F5-TTS_Models"),
                )
            except Exception as e:
                raise RuntimeError(f"F5-TTS 模型下载失败: {e}\n"
                                   f"请手动下载后放入 F5-TTS_Models/F5TTS_v1_Base/")

        print("[F5TTS] 正在加载模型（首次约 10-30 秒，之后常驻）...")
        t0 = time.time()

        # 注册 pypinyin 自定义多音字词典（覆盖默认决策，一劳永逸）
        # 测试中发现读错的词可加到这里
        try:
            from pypinyin import load_phrases_dict
            load_phrases_dict({
                "重庆": [["chong2"], ["qing4"]],
                "音乐": [["yin1"], ["yue4"]],
                "行": [["xing2"]],
                # 数 = shǔ（数数/计数），不是 shù（数字/数学）
                "我数过": [["wo3"], ["shu3"], ["guo4"]],
                "数着数着": [["shu3"], ["zhe5"], ["shu3"], ["zhe5"]],
                # 按需补充：用户测试发现读错的词
            })
            print("[F5TTS] pypinyin 自定义多音字词典已注册")
        except Exception as e:
            print(f"[F5TTS] pypinyin 词典注册失败（不影响运行）: {e}")

        try:
            from f5_tts.api import F5TTS
            print("[F5TTS] import f5_tts.api OK")
        except ImportError as e:
            raise RuntimeError(f"f5-tts 未安装: {e}")

        # F5TTS 构造函数签名: F5TTS(model=, ckpt_file=, vocab_file=, device=, vocoder_local_path=)
        # 直接指定本地权重文件 + 本地声码器，避免从 HF 重复下载/超时
        ckpt_file = str(BASE_DIR / "F5-TTS_Models" / "F5TTS_v1_Base" / "model_1250000.safetensors")
        vocab_file = str(BASE_DIR / "F5-TTS_Models" / "F5TTS_v1_Base" / "vocab.txt")
        vocoder_local_path = str(BASE_DIR / "F5-TTS_Models" / "vocos-mel-24khz")

        print(f"[F5TTS] ckpt_file={ckpt_file}")
        print(f"[F5TTS] vocab_file={vocab_file}")
        print(f"[F5TTS] vocoder_local_path={vocoder_local_path}")
        print(f"[F5TTS] 开始构造 F5TTS 实例...")
        _model = F5TTS(
            model="F5TTS_v1_Base",
            ckpt_file=ckpt_file,
            vocab_file=vocab_file,
            device=_device,
            vocoder_local_path=vocoder_local_path,
        )
        print(f"[F5TTS] F5TTS 实例创建成功")

        _model_ready = True
        print(f"[F5TTS] 模型加载完成 ({time.time()-t0:.1f}s, device={_device})")
        return _model


def synthesize(text: str, ref_audio: str = None, ref_text: str = None, speed: float = 1.0):
    """
    合成中文语音。

    text:      要合成的文本
    ref_audio: 参考音频路径（零样本音色克隆）
    ref_text:  参考音频对应的文本
    speed:     语速（1.0 = 正常）
    """
    model = load_model()

    if ref_audio is None or not os.path.exists(ref_audio):
        ref_audio = DEFAULT_REF_AUDIO
    if ref_text is None:
        ref_text = DEFAULT_REF_TEXT

    # 阿拉伯数字 → 中文（合成前转换，音频念标准中文，显示文字不受影响）
    text = _arabic_to_chinese(text)

    print(f"[F5TTS] 合成: '{text[:50]}...' ref={os.path.basename(ref_audio)}")
    t0 = time.time()

    # F5-TTS infer 返回 (wav, sr, spec)
    wav, sr, _ = model.infer(
        ref_file=ref_audio,
        ref_text=ref_text,
        gen_text=text,
        remove_silence=True,
    )

    elapsed = time.time() - t0
    duration = len(wav) / sr if sr > 0 else 0
    rtf = elapsed / duration if duration > 0 else 0
    print(f"[F5TTS] 合成完成: {duration:.1f}s 音频, {elapsed:.1f}s 耗时, RTF={rtf:.2f}")

    return wav, int(sr)


# ══════════════════════════════════════════════════════════
# FastAPI 服务
# ══════════════════════════════════════════════════════════

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
import numpy as np
import soundfile as sf

app = FastAPI()


class InferRequest(BaseModel):
    text: str
    ref_audio: str = None
    ref_text: str = None
    speed: float = 1.0


@app.post("/infer")
async def infer(req: InferRequest):
    """中文 TTS 合成，返回 wav 音频流"""
    try:
        if not req.text or not req.text.strip():
            return Response(json.dumps({"error": "text 不能为空"}, ensure_ascii=False), media_type="application/json", status_code=400)

        wav, sr = synthesize(
            text=req.text.strip(),
            ref_audio=req.ref_audio,
            ref_text=req.ref_text,
            speed=req.speed,
        )

        # 写入 wav 内存
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        buf.seek(0)

        return Response(
            content=buf.read(),
            media_type="audio/wav",
            headers={"X-Sample-Rate": str(sr)},
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response(
            json.dumps({"error": str(e)}, ensure_ascii=False),
            media_type="application/json",
            status_code=500,
        )


@app.get("/health")
async def health():
    return {"status": "ok", "ready": _model_ready, "device": _device}


def _preload_model():
    """后台线程预加载模型，加速首次合成"""
    try:
        load_model()
        print("[F5TTS] 模型预加载完成，已就绪 ✅")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[F5TTS] 模型预加载失败: {e}")


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print(" F5-TTS 服务启动中... 端口 9881")
    print(f" 参考音频: {DEFAULT_REF_AUDIO}")
    print(f" 参考文本: {DEFAULT_REF_TEXT}")
    print(" 模型将在后台预加载，请稍候...")
    print("=" * 60)

    # 后台线程预加载模型（避免阻塞 uvicorn 启动）
    threading.Thread(target=_preload_model, daemon=True).start()

    uvicorn.run(app, host="127.0.0.1", port=9881, log_level="info")
