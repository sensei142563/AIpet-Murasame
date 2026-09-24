import os
import threading

# HF 模型缓存统一放到项目内（D 盘），不放 C 盘用户目录：
# ① C 盘空间紧张；② C 盘清理工具会把用户目录里的模型当"缓存"删掉，
#    曾导致 large-v3 约 3GB 权重被清空、语音识别失效（model.bin 无法打开）。
# 目录名取清楚点：`models/stt`（语音识别），实际权重在 `models/stt/hub/` 下。
#   兼容更早的 `models/hf`（老下载脚本用的名字）——见 _hf_cache_roots()。
try:
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("HF_HOME", os.path.join(_BASE, "models", "stt"))
except Exception:
    pass

# 先取配置（tool.config 不触发 huggingface_hub import）
from tool.config import get_config
stt_model = str(get_config("./config.json").get("stt_model", "large-v3"))

# ===== HF 离线判定必须在任何 huggingface_hub / faster_whisper import 之前执行 =====
# huggingface_hub 的 HF_HUB_OFFLINE 是 import 期常量（is_offline_mode() 返回缓存值），
# 等 faster_whisper 已 import 后再 setenv 无效 → A 卡场景仍会每次联网探测（审计 P1）。
# 另：只校验 repo 目录存在会命中"中断下载的半缓存"，一旦 offline 生效即永久锁死 → 必须
# 确认存在 snapshots/ 与 refs/（快照树完整）才算"缓存可用"。
def _hf_cache_roots():
    """HF 缓存根候选目录（HF_HUB_CACHE / HF_HOME / HF_HOME/hub / 项目内老目录 / 用户目录）。

    背景：本文件顶部把 HF_HOME 指到项目内 `models/stt`（避免 C 盘被清理），而
    huggingface_hub 的实际快照在 `$HF_HOME/hub`（新布局）或 `$HF_HOME`（旧布局），
    因此只查一个根会漏判 → 离线开关失效、每次启动仍联网探测。
    """
    roots = []
    hub_cache = (os.environ.get("HF_HUB_CACHE") or "").strip()
    if hub_cache:
        roots.append(hub_cache)
    hf_home = (os.environ.get("HF_HOME") or "").strip()
    if hf_home:
        roots.append(hf_home)
        roots.append(os.path.join(hf_home, "hub"))
    # 项目内的历史位置（download_stt.py 早期版本写进 models/hf）——别让老装好的模型白放
    if "_BASE" in globals():
        roots.append(os.path.join(_BASE, "models", "hf"))
        roots.append(os.path.join(_BASE, "models", "hf", "hub"))
    roots.append(os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub"))
    seen, out = set(), []
    for r in roots:
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out


def cache_roots_with_model(model_size="large-v3"):
    """哪些缓存根里**确实**有完整模型（返回 hub 缓存目录，按候选顺序排）"""
    model_size = model_size or "large-v3"
    out = []
    for cache_root in _hf_cache_roots():
        repo_dir = os.path.join(cache_root, f"models--Systran--faster-whisper-{model_size}")
        snap = os.path.join(repo_dir, "snapshots")
        refs = os.path.join(repo_dir, "refs")
        if os.path.isdir(snap) and os.path.isdir(refs) and os.listdir(refs):
            out.append(cache_root)
    return out


def cache_state(model_size="large-v3"):
    """语音识别模型有没有**可用的本地缓存**：返回 (ok, 实际/预期路径)

    为什么要单独一个函数：`HF_HUB_OFFLINE` 一旦设上，缺模型时永远下不下来
    （用户机器上 huggingface.co 还不一定通）→ 表现为"语音识别开着但完全没反应"。
    调用方必须先问 cache_state()，**缓存可用才进离线**。
    """
    model_size = model_size or "large-v3"
    roots = cache_roots_with_model(model_size)
    if roots:
        return True, os.path.join(roots[0], f"models--Systran--faster-whisper-{model_size}")
    first = (_hf_cache_roots() or ["models/hf"])[0]
    return False, os.path.join(first, f"models--Systran--faster-whisper-{model_size}")


def _prepare_hf_env(model_size="large-v3") -> bool:
    """把 HF 环境指到**真正有模型**的那个缓存目录；有模型才进离线。

    ⚠ 必须在 huggingface_hub / faster_whisper import **之前**调用：HF_HUB_OFFLINE 与
      HF_HUB_CACHE 都是它们的 import 期常量，之后再改环境变量没用。

    为什么需要它（用户 2026-09-24 的日志）：
      · 我们把 HF_HOME 指到项目内 models/hf（避免 C 盘被清理工具删），
      · 但模型其实躺在默认用户缓存（C:\\Users\\...\\.cache\\huggingface\\hub）里，
      · 于是"找的是空目录 + 被锁离线"→ 报
        "Cannot find an appropriate cached snapshot folder … outgoing traffic has been
        disabled"，语音识别看着开着、实际完全不可用。
      现在：命中哪个根就把 HF_HUB_CACHE 指过去；都没命中就不锁离线（让首次下载能成）。
    """
    model_size = model_size or "large-v3"
    roots = cache_roots_with_model(model_size)
    if roots:
        os.environ["HF_HUB_CACHE"] = roots[0]
        os.environ["HF_HUB_OFFLINE"] = "1"      # 用赋值：明确进入离线，省掉联网探测
        return True
    os.environ.pop("HF_HUB_OFFLINE", None)      # 没缓存就别锁死，允许下载
    return False


def _set_hf_offline_if_cached(model_size="large-v3"):
    """兼容旧调用名（打包脚本/别处可能引用）：等价于 _prepare_hf_env"""
    return _prepare_hf_env(model_size)


def stt_hint(model_size=None) -> str:
    """模型没就绪时给用户看的一句话（说清怎么修，而不是甩一串英文异常）"""
    model_size = model_size or stt_model or "large-v3"
    ok, where = cache_state(model_size)
    if ok:
        return f"语音识别模型 {model_size} 已在本地：{where}"
    return (f"语音识别模型 {model_size} 还没下载到本地（预期位置：{where}）。\n"
            f"修法任选其一：\n"
            f"  1) 运行 download_stt.py 下载（会走国内镜像）；\n"
            f"  2) 在设置里把 stt_model 换成更小的模型（如 small，几百 MB）；\n"
            f"  3) 不需要语音识别就在设置里关掉「语音识别」——关掉后不会再尝试加载。")


_HF_CACHE_READY = _prepare_hf_env(stt_model)

# faster_whisper 在离线判定之后才 import（否则 HF_HUB_OFFLINE 不生效）
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
            # 若配置里换了别的模型：能定位到本地缓存就指过去（HF_* 是 import 期常量，
            # 这一步只对"还没 import 过 huggingface_hub 的场景"有效，正常启动时已在
            # 模块顶部准备好了；这里是为了让"换模型后重启"也走在正确路径上）
            if not cache_roots_with_model(model_size):
                print("[STT] " + stt_hint(model_size).replace("\n", "\n[STT] "))
            _prepare_hf_env(model_size)
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
        # 不要只甩英文异常：说清"模型没下载 / 怎么修"（用户看到的就这一行）
        print(f"[STT] ⚠ 模型预热失败: {e}")
        print("[STT] " + stt_hint(model_size).replace("\n", "\n[STT] "))
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
