import threading

from faster_whisper import WhisperModel
from tool.config import get_config

stt_model = get_config("./config.json")["stt_model"]

# ===== 模型单例缓存：一个进程只加载一次（large-v3 加载需数十秒 + 数 GB 内存，
#       旧实现每次识别都新建模型，QQ 收到语音时会把收包线程卡死）=====
_model_cache = {}
_model_lock = threading.Lock()


def _get_model(model_size="large-v3"):
    """懒加载单例 Whisper 模型（GPU 优先，失败自动回退 CPU）。"""
    with _model_lock:
        if model_size not in _model_cache:
            try:
                _model_cache[model_size] = WhisperModel(
                    model_size, device="cuda", compute_type="float16"
                )
            except Exception:
                print("⚠ GPU 初始化失败，使用 CPU")
                _model_cache[model_size] = WhisperModel(
                    model_size, device="cpu", compute_type="int8"
                )
        return _model_cache[model_size]


def warmup(model_size="large-v3"):
    """后台预热模型（QQ 语音识别开启时启动阶段调用，避免首条语音阻塞数十秒）。"""
    try:
        _get_model(model_size)
        print("[STT] ✅ 语音识别模型已加载")
    except Exception as e:
        print(f"[STT] ⚠ 模型预热失败: {e}")


def transcribe_full(audio_path: str, model_size=None, device="cuda", language=None) -> str:
    """识别语音文字。

    - model_size: 默认用 config.json 的 stt_model
    - language=None → 自动检测语言（中文/日语都能识别，不再硬编码 zh）
    - device 参数保留兼容旧调用（实际设备由 _get_model 决定）
    """
    if not model_size:
        model_size = stt_model or "large-v3"
    model = _get_model(model_size)

    # 识别（语言自动检测）
    segments, info = model.transcribe(audio_path, language=language, beam_size=5)

    # 合并成一句完整话
    full_text = "".join(seg.text for seg in segments).strip()
    return full_text
