import os
import threading

# 先取配置（tool.config 不触发 huggingface_hub import）
from tool.config import get_config
stt_model = str(get_config("./config.json").get("stt_model", "large-v3"))

# ===== HF 离线判定必须在任何 huggingface_hub / faster_whisper import 之前执行 =====
# huggingface_hub 的 HF_HUB_OFFLINE 是 import 期常量（is_offline_mode() 返回缓存值），
# 等 faster_whisper 已 import 后再 setenv 无效 → A 卡场景仍会每次联网探测（审计 P1）。
# 另：只校验 repo 目录存在会命中"中断下载的半缓存"，一旦 offline 生效即永久锁死 → 必须
# 确认存在 snapshots/ 与 refs/（快照树完整）才算"缓存可用"。
def _set_hf_offline_if_cached(model_size="large-v3"):
    try:
        cache_root = os.environ.get(
            "HF_HOME",
            os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub"),
        )
        cache_root = os.environ.get("HF_HUB_CACHE", cache_root)
        repo_dir = os.path.join(cache_root, f"models--Systran--faster-whisper-{model_size}")
        snap = os.path.join(repo_dir, "snapshots")
        refs = os.path.join(repo_dir, "refs")
        if os.path.isdir(snap) and os.path.isdir(refs) and os.listdir(refs):
            os.environ["HF_HUB_OFFLINE"] = "1"  # 用赋值（非 setdefault）：明确进入离线
            return True
    except Exception:
        pass
    return False


_set_hf_offline_if_cached(stt_model)

# faster_whisper 在离线判定之后才 import（否则 HF_HUB_OFFLINE 不生效）
from faster_whisper import WhisperModel

# ===== 模型单例缓存：一个进程只加载一次（large-v3 加载需数十秒 + 数 GB 内存，
#       旧实现每次识别都新建模型，QQ 收到语音时会把收包线程卡死）=====
_model_cache = {}
_model_lock = threading.Lock()


def _get_model(model_size=None):
    """懒加载单例 Whisper 模型（GPU 优先，失败自动回退 CPU；缓存命中后离线加载）。"""
    if not model_size:
        model_size = stt_model or "large-v3"
    with _model_lock:
        if model_size not in _model_cache:
            _set_hf_offline_if_cached(model_size)
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


def warmup(model_size=None) -> bool:
    """后台预热模型（QQ 语音识别开启时启动阶段调用，避免首条语音阻塞数十秒）。
    返回 True = 模型已就绪；False = 预热失败（调用方可决定是否重试）。"""
    if not model_size:
        model_size = stt_model or "large-v3"
    try:
        _get_model(model_size)
        print("[STT] ✅ 语音识别模型已加载")
        return True
    except Exception as e:
        print(f"[STT] ⚠ 模型预热失败: {e}")
        return False


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
