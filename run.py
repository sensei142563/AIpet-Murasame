import platform
import subprocess
import sys
import os
import json
import time


# ⚠ 第一件事：确保用的是**项目自带解释器**（runtime/venv）。
#   用系统 Python 跑本项目会缺依赖 → 直接崩（Windows 事件日志里的 MSVCP140 访问违规），
#   而且会和正常桌宠抢 28565 端口 → 云端代理一断，桌宠就"没有任何回复"。
#   这里检测到解释器不对就自动用 venv 重新执行自己（os.execv，不会留下多份进程）。

# 本机地址绕过系统代理（挂加速器/梯子时代理会连 127.0.0.1 一起劫持 → "信号不正常"）
try:
    from tool.net_env import bypass_proxy_for_local as _bpfl
    _bpfl()
except Exception:
    pass

def _ensure_project_python():
    try:
        if os.environ.get("AIPET_REEXEC") == "1":
            return
        _base = os.path.dirname(os.path.abspath(__file__))
        _venv = os.path.join(_base, "runtime", "venv", "Scripts", "python.exe")
        if not os.path.exists(_venv):
            return
        # 已经在用项目解释器（按路径字符串判断，避免"转发器"导致的误判循环）
        if os.path.normcase(str(_venv)) in os.path.normcase(sys.executable or ""):
            return
        if os.path.normcase(os.path.abspath(sys.executable)) == os.path.normcase(os.path.abspath(_venv)):
            return
        print(f"[AIpet] 当前解释器不是项目自带的（{sys.executable}）→ 改用 {_venv} 重新启动", flush=True)
        _env = dict(os.environ)
        _env["AIPET_REEXEC"] = "1"
        # ⚠ 不用 os.execv（Windows 上换解释器实测会 segfault）：拉起子进程后本进程退出
        subprocess.Popen([_venv, os.path.abspath(__file__)] + sys.argv[1:],
                         cwd=_base, env=_env)
        sys.exit(0)
    except Exception as _e:
        print(f"[AIpet] ⚠ 切换项目解释器失败（继续用当前解释器）: {_e}")


_ensure_project_python()

from tool.config import get_config

TORCH_OK = False        # 是否成功加载了 torch（云端模式不加载也能跑）

SUPPORTED_CLOUD_MODEL_TYPES = ("deepseek", "qwen")

# Live2D 依赖检测（包名 live2d-py，import 为 live2d）
# ⚠ 配置里关掉 Live2D 时**不导入**：个别显卡/驱动下 Cubism 原生库导入即崩进程
#   （表现：桌宠启动/运行一两分钟后突然消失，控制台没有任何报错）
LIVE2D_SKIP = False
def _live2d_enabled_in_cfg() -> bool:
    try:
        import json as _j
        with open("./config.json", "r", encoding="utf-8") as f:
            return str((_j.load(f) or {}).get("live2d_enabled", "false")).lower() == "true"
    except Exception:
        return False

if not _live2d_enabled_in_cfg():
    LIVE2D_SKIP = True
    print("[AIpet] 配置 live2d_enabled=false → 跳过 Live2D 依赖检测（避免个别驱动下崩溃）")
else:
    try:
        import live2d.v3
        import OpenGL.GL
    except ImportError:
        LIVE2D_SKIP = True


def _project_python() -> str:
    """跑本项目子进程（main.py / pip 等）一律用「项目自带解释器」。

    ⚠ 直接用 sys.executable 不可靠：venv 的 Scripts\\python.exe 在 Windows 上常常是
    一个"转发器"，进程内 sys.executable 会指向**基础 Python**（没有项目依赖）→
    拉起的 main.py 会直接崩（事件日志里的 MSVCP140 访问违规），还会和正常桌宠抢
    28565 端口；云端代理一断，桌宠就"一句话都不回"。
    """
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "runtime", "venv", "Scripts", "python.exe")
        if os.path.exists(p):
            return p
    except Exception:
        pass
    return sys.executable


def _f5tts_venv_python():
    """拉起 F5-TTS 优先使用项目自带 runtime\venv 的 Python：
    若入口被系统 Python 执行（如无 venv 的旧副本启动器），sys.executable 拉出的
    f5tts 服务会因缺 f5_tts/torchaudio 修复而卡死并占住 9881。"""
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "runtime", "venv", "Scripts", "python.exe")
        if os.path.exists(p):
            return p
    except Exception:
        pass
    return sys.executable


def log(msg, level="INFO"):
    """打印日志；纯净模式下控制台被隐藏 → 同时追加到 data/pet_run.log，方便事后排查"""
    levels = {
        "INFO": "[AIpet]",
        "WARN": "⚠️ [警告]",
        "ERROR": "❌ [错误]",
        "SUCCESS": "✅ [成功]",
    }
    prefix = levels.get(level, "[AIpet]")
    print(f"{prefix} {msg}")
    try:
        if quiet_mode():
            import os as _os
            _lp = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data", "pet_run.log")
            _os.makedirs(_os.path.dirname(_lp), exist_ok=True)
            if _os.path.isfile(_lp) and _os.path.getsize(_lp) > 2 * 1024 * 1024:
                _os.remove(_lp)
            with open(_lp, "a", encoding="utf-8") as _f:
                _f.write("%s %s %s\n" % (__import__("time").strftime("%Y-%m-%d %H:%M:%S"), prefix, msg))
    except Exception:
        pass


def load_runtime_config(config_path="config.json"):
    if not os.path.exists(config_path):
        log("未找到 config.json，使用默认云端配置。", "WARN")
        return {
            "model_type": "deepseek",
            "tts_type": "cloud",
            "force_gpu_check": "false",
        }

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"无法解析 config.json: {e}，使用默认云端配置。", "WARN")
        return {
            "model_type": "deepseek",
            "tts_type": "cloud",
            "force_gpu_check": "false",
        }


def config_enabled(value):
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def should_check_hardware(cfg):
    model_type = str(cfg.get("model_type", "deepseek")).strip().lower()
    tts_type = str(cfg.get("tts_type", "cloud")).strip().lower()

    if config_enabled(cfg.get("force_gpu_check", False)):
        log("检测到 force_gpu_check = true，将强制执行显卡检查。", "INFO")
        return False

    if model_type == "local":
        log("检测到 model_type = local，需要检查本机显卡。", "INFO")
        return False

    if tts_type == "local":
        log("检测到 tts_type = local，需要检查本机显卡。", "INFO")
        return False

    log("检测到对话与 TTS 均为云端模式，跳过本机显卡检查。", "INFO")
    return False

def check_hardware():
    """检测操作系统与显卡兼容性（支持 Windows + NVIDIA GPU 或 CPU）"""
    system = platform.system()
    log(f"检测到系统: {system}")

    # Step 1️⃣ 检查系统类型
    if system != "Windows":
        log("当前系统不受支持：仅支持 Windows 设备运行。", "ERROR")
        log("如果你是 macOS 或 Linux 用户，请使用云端版本或 Docker 环境。", "INFO")
        sys.exit(1)

    # Step 2️⃣ 检测显卡信息（使用 PowerShell 替代 wmic）
    try:
        result = subprocess.run(
            [
                "powershell",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"
            ],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        gpu_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        gpu_name = ", ".join(gpu_lines) if gpu_lines else "未知"
        log(f"检测到显卡: {gpu_name}")
    except Exception as e:
        log(f"无法获取显卡信息: {e}", "WARN")
        gpu_name = "未知"

    # Step 3️⃣ 判断显卡类型
    gpu_lower = gpu_name.lower()
    if "nvidia" not in gpu_lower:
        # 如果未找到NVIDIA显卡，允许使用CPU模式
        if any(bad in gpu_lower for bad in ("amd", "radeon", "intel", "iris", "arc")):
            log("当前显卡不受支持：仅支持 NVIDIA 显卡。", "ERROR")
            log("请使用带 NVIDIA GPU 的电脑，或切换到云端模式。", "INFO")
            sys.exit(1)
        else:
            log("未检测到 NVIDIA 显卡，系统将运行在 CPU 模式。", "INFO")
            # 继续执行，允许使用CPU
            return "cpu"

    log("系统兼容性检测通过：Windows + NVIDIA 显卡", "SUCCESS")
    return "nvidia"

def check_python():
    """检测 Python 版本是否满足 ≥ 3.10"""
    version_info = sys.version_info
    current_version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    log(f"检测到 Python 版本: {current_version}")

    # 检查版本
    if version_info < (3, 10):
        log("当前 Python 版本过低，Murasame 桌宠运行需要 Python ≥ 3.10。", "ERROR")
        sys.exit(1)
    else:
        log("Python 版本满足要求 (≥ 3.10)", "SUCCESS")

def install_requirements():
    """自动安装 requirements.txt 中的依赖"""
    req_path = "requirements.txt"

    # Step 1️⃣ 快速检查 requirements 内的关键依赖是否已存在（避免每次启动都跑 pip）
    # 注意：torch 与 f5_tts 不在此检查——torch 由 setup_runtime_and_pytorch 管理，
    #       f5_tts 是可选语音库，由 start_f5tts_api 单独引导。
    # ★ 缓存：requirements.txt 没变过、上次检查也通过 → 直接跳过
    #   （每次启动 import cv2/numpy/PyQt5/pygame/soundfile 大约要 3 秒，纯白等；
    #    桌宠自己那个进程还会再 import 一次，run.py 这份纯属浪费）
    try:
        import json as _json
        _st = os.path.join("data", ".deps_ok.json")
        _sig = None
        try:
            _stt = os.stat(req_path)
            _sig = "%d:%d" % (int(_stt.st_mtime), int(_stt.st_size))
        except Exception:
            pass
        if _sig:
            try:
                with open(_st, encoding="utf-8") as _f:
                    if _json.load(_f).get("sig") == _sig:
                        log("核心依赖已就绪（上次检查通过，跳过）。", "SUCCESS")
                        return
            except Exception:
                pass
    except Exception:
        _sig = None
    try:
        import cv2
        import numpy
        import PyQt5.QtCore
        import pygame
        import soundfile
        log("核心依赖已就绪，跳过自动安装。", "SUCCESS")
        try:
            if _sig:
                import json as _json2
                os.makedirs("data", exist_ok=True)
                with open(os.path.join("data", ".deps_ok.json"), "w", encoding="utf-8") as _f:
                    _json2.dump({"sig": _sig}, _f)
        except Exception:
            pass
        return
    except ImportError:
        pass

    # Step 2️⃣ 检查文件是否存在
    if not os.path.exists(req_path):
        log("未找到 requirements.txt，跳过依赖安装。", "WARN")
        return

    # Step 3️⃣ 执行安装命令（不带 --upgrade，只装缺失的）
    log("正在安装缺失依赖，请稍候...")
    try:
        subprocess.run(
            [_project_python(), "-m", "pip", "install", "-r", req_path, "--no-warn-script-location"],
            check=True, creationflags=_console_flags()
        )
        log("依赖安装完成。", "SUCCESS")
    except subprocess.CalledProcessError:
        log("依赖安装失败！请检查网络或 pip 源设置。", "ERROR")
        log("你可以尝试手动运行以下命令：", "INFO")
        log(f"    {sys.executable} -m pip install -r {req_path}", "INFO")
        sys.exit(1)

def ensure_cpu_torch():
    """
    确保存在可用的 torch（CPU 版即可）。
    说明：本地模式需要 torch；云端模式（deepseek/qwen）只是 main.py 会 import 一下，
    而 main.py 现在是容错导入 → 所以这里**任何失败都不再退出程序**。
    （以前 torch 的 DLL 加载失败会让桌宠直接启动失败，用户看到的就是「启动桌宠失败」。）
    """
    global TORCH_OK
    try:
        import torch
        log(f"已检测到 PyTorch {torch.__version__} (CUDA {torch.version.cuda or 'CPU'})", "SUCCESS")
        TORCH_OK = True
        return True
    except ImportError:
        TORCH_OK = False
    except Exception as e:
        # DLL 初始化失败等：重装也修不好，直接放行（云端模式不需要它）
        TORCH_OK = False
        log(f"PyTorch 加载失败（{e}）", "WARN")
        log("→ 云端模式不受影响，继续启动；本地模型 / 本地语音功能将不可用。", "INFO")
        return False

    log("未检测到 PyTorch，尝试安装 CPU 版本（云端模式其实不需要，本地模式必需）。", "INFO")
    try:
        subprocess.run([
            _project_python(), "-m", "pip", "install",
            "torch", "torchvision", "torchaudio",
            "--index-url", "https://download.pytorch.org/whl/cpu",
            "--no-warn-script-location"
        ], check=True, timeout=1800, creationflags=_console_flags())
        import torch
        log(f"成功安装 PyTorch {torch.__version__} (CPU)", "SUCCESS")
        TORCH_OK = True
        return True
    except Exception as e:
        # ⚠ 以前这里 sys.exit(1)：离线/网络受限时桌宠完全起不来。现在降级继续。
        TORCH_OK = False
        log(f"PyTorch 安装/加载失败：{e}", "WARN")
        log("→ 继续以「无 torch」方式启动（云端模式可用；本地模型不可用）。", "INFO")
        log("  需要本地模型时手动执行：pip install torch torchvision torchaudio "
            "--index-url https://download.pytorch.org/whl/cpu", "INFO")
        return False


def setup_runtime_and_pytorch(config_path="config.json", cfg=None, hardware_type=None):
    # Step 1️⃣ 判断配置文件
    if cfg is None and not os.path.exists(config_path):
        log("未找到 config.json，默认进入 DeepSeek 云端模式。", "WARN")
        return "deepseek"

    try:
        if cfg is None:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        model_type = cfg.get("model_type", "deepseek").lower()
        log(f"读取配置: model_type = {model_type}")
    except Exception as e:
        log(f"无法解析 config.json: {e}")
        log("默认进入 DeepSeek 云端模式。", "WARN")
        return "deepseek"

    # Step 2️⃣ 判断模式
    if model_type not in ("local", *SUPPORTED_CLOUD_MODEL_TYPES):
        log(f"未识别的 model_type: {model_type}，默认视为 DeepSeek 云端模式。", "WARN")
        return "deepseek"

    if model_type == "deepseek":
        # ⚠ 云端模式根本不需要 torch，以前还去 ensure_cpu_torch()：每次启动白等约 4 秒
        #   （尝试 import torch → DLL 初始化失败 → 打印警告继续）。直接跳过。
        log("检测到 DeepSeek 云端模式，跳过 PyTorch 安装。")
        return "deepseek"
    elif model_type == "qwen":
        log("检测到 Qwen 云端模式，跳过 PyTorch 安装。")
        return "qwen"

    log("检测到本地运行模式。")

    # 如果是CPU模式，直接跳过PyTorch安装
    if hardware_type is None:
        hardware_type = check_hardware()

    if hardware_type == "cpu":
        log("检测到 CPU 模式，跳过 PyTorch 安装。", "INFO")
        return "cpu"

    # Step 3️⃣ 检测 CUDA 环境
    cuda_version = None
    driver_version = None
    try:
        # 调用 nvidia-smi 获取原始输出
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True, text=True, encoding="gbk", check=True
        )
        output = result.stdout

        import re
        driver_match = re.search(r"Driver Version:\s*([\d\.]+)", output)
        cuda_match = re.search(r"CUDA Version:\s*([\d\.]+)", output)

        if driver_match:
            driver_version = driver_match.group(1)
        if cuda_match:
            cuda_version = cuda_match.group(1)

        if cuda_version:
            log(f"检测到 CUDA 环境: 驱动 {driver_version or '未知'}，CUDA {cuda_version}")
        else:
            log("未检测到 CUDA 版本信息，可能未正确安装显卡驱动或驱动版本过旧。", "WARN")

    except FileNotFoundError:
        log("未检测到 nvidia-smi，请确认已安装 NVIDIA 驱动。", "ERROR")
    except subprocess.CalledProcessError as e:
        log(f"执行 nvidia-smi 失败: {e}", "ERROR")
    except Exception as e:
        log(f"检测 CUDA 版本时出错: {e}", "WARN")

    if not cuda_version:
        log("未检测到 CUDA，将使用 CPU 模式。", "WARN")

    # Step 4️⃣ 选择正确的 PyTorch 安装源
    if not cuda_version:
        torch_url = "https://download.pytorch.org/whl/cpu"
        log("未检测到 CUDA，安装 CPU 版本 PyTorch。")
    elif cuda_version.startswith("13"):
        torch_url = "https://download.pytorch.org/whl/cu130"
        log("检测到 CUDA 13.x，将安装 cu130 版本。")
    elif cuda_version.startswith("12"):
        torch_url = "https://download.pytorch.org/whl/cu128"
        log("检测到 CUDA 12.x，将安装 cu128 版本。")
    elif cuda_version.startswith("11"):
        torch_url = "https://download.pytorch.org/whl/cu128"
        log("检测到 CUDA 11.x，将安装 cu128 版本。")
    else:
        torch_url = "https://download.pytorch.org/whl/cpu"
        log(f"未识别的 CUDA 版本 {cuda_version}，将安装 CPU 版本。", "WARN")

    # Step 5️⃣ 检查 PyTorch 是否已安装
    try:
        import torch
        installed_version = torch.__version__
        torch_cuda_version = torch.version.cuda or "CPU"
        log(f"已检测到 PyTorch {installed_version} (CUDA {torch_cuda_version})", "SUCCESS")

        # 检查版本匹配情况
        mismatch = False
        if torch_cuda_version == "CPU" and cuda_version:  # 系统有 CUDA，但 torch 是 CPU 版
            mismatch = True
            log(f"检测到系统 CUDA {cuda_version}，但已安装的 PyTorch 为 CPU 版。", "WARN")
        elif cuda_version and not torch_cuda_version.startswith(cuda_version.split('.')[0]):
            mismatch = True
            log(f"当前 CUDA 版本为 {cuda_version}，但 PyTorch 构建基于 CUDA {torch_cuda_version}。", "WARN")

        if mismatch:
            log("开始安装与当前 CUDA 版本匹配的 PyTorch...", "INFO")
            subprocess.run([
                _project_python(), "-m", "pip", "install", "-U",
                "torch", "torchvision", "torchaudio",
                "--index-url", torch_url,
                "--no-warn-script-location"
            ], check=True, creationflags=_console_flags())
            import torch
            log("已安装与当前 CUDA 匹配的 PyTorch 版本。", "SUCCESS")
            log("⚠️⚠️请关闭并重新运行程序，以加载新的 PyTorch 版本。⚠️⚠️", "INFO")
            sys.exit(0)

    except ImportError:
        log("未检测到 PyTorch，开始安装...", "INFO")
        try:
            subprocess.run([
                _project_python(), "-m", "pip", "install",
                "torch", "torchvision", "torchaudio",
                "--index-url", torch_url,
                "--no-warn-script-location"
            ], check=True, creationflags=_console_flags())
            import torch
            log(f"成功安装 PyTorch {torch.__version__} (CUDA {torch.version.cuda or 'CPU'})", "SUCCESS")
        except subprocess.CalledProcessError:
            log("PyTorch 安装失败！请检查网络或 CUDA 环境。", "ERROR")
            sys.exit(1)

    return model_type

def run_download():
    tts_type = get_config("./config.json")["tts_type"]
    if tts_type == "local":
        log("检测到 tts_type = local", "INFO")
        script_path = os.path.abspath(r".\download.py")

        if not os.path.exists(script_path):
            log(f"未找到文件: {script_path}", "ERROR")
            return

        # ★ 模型已经在本地 → 直接跳过（这脚本每次都会去 ModelScope 联网检查，
        #   实测要 17 秒，是启动最慢的一段）。要强制重新下载就删掉这两个目录。
        try:
            _gs = os.path.abspath(r".\GPT-SoVITS")
            _gpt_ok = any(f.endswith((".ckpt", ".pth"))
                          for f in os.listdir(os.path.join(_gs, "GPT_weights")))
            _sov_ok = any(f.endswith((".pth", ".ckpt"))
                          for f in os.listdir(os.path.join(_gs, "SoVITS_weights")))
            if _gpt_ok and _sov_ok:
                log("语音模型已就绪，跳过下载检查（省下十几秒）。", "SUCCESS")
                return
        except Exception:
            pass

        log(f"正在运行模型下载脚本：{script_path}", "INFO")
        try:
            # ⚠ 这里以前用裸 "python"（PATH 里的系统 Python）：系统 Python 没有本项目的
            #   依赖，跑 download.py 会直接崩（事件日志里的 MSVCP140 访问违规就是这么来的）。
            #   统一用项目解释器：优先 runtime venv。
            subprocess.run([_f5tts_venv_python(), "download.py"],
                           creationflags=_console_flags())
            log("模型下载完成。", "SUCCESS")
        except subprocess.CalledProcessError as e:
            log(f"下载脚本运行失败: {e}", "ERROR")
    elif tts_type == "cloud":
        log("检测到 tts_type = cloud, 跳过模型下载", "INFO")

def quiet_mode() -> bool:
    """纯净模式（设置 → 其他配置）：启动桌宠时不弹终端窗口。

    这些服务进程本身照常运行，只是不给它们开控制台窗口，
    想排查问题时在设置里关掉纯净模式即可看到日志。
    """
    try:
        return str(get_config("./config.json").get("quiet_mode", "false")).strip().lower() in (
            "true", "1", "yes", "on")
    except Exception:
        return False


def _console_flags(quiet: bool = None) -> int:
    """子进程窗口标志：纯净模式用 CREATE_NO_WINDOW(0x08000000)，否则开新控制台(0x10)"""
    if os.name != "nt":
        return 0
    if quiet is None:
        quiet = quiet_mode()
    return 0x08000000 if quiet else 0x00000010


def start_f5tts_api():
    """启动 F5-TTS HTTP 服务（端口 9881，长文本模式中文语音合成）"""
    cfg = get_config("./config.json")
    if cfg.get("longtext_enabled") != "true":
        log("长文本模式已关闭，跳过 F5-TTS 服务启动。", "INFO")
        return None

    # F5-TTS 为可选语音库，缺失时仅提示，不阻塞程序
    try:
        import f5_tts  # noqa: F401
    except ImportError:
        log("未检测到 f5_tts 库，长文本语音不可用。", "WARN")
        log("如需语音功能，请参考 README 安装 F5-TTS。", "INFO")
        return None

    log("检测到长文本模式已开启，启动 F5-TTS 服务%s..." % ("" if quiet_mode() else "（新控制台）"), "INFO")
    try:
        proc = subprocess.Popen(
            [_f5tts_venv_python(), "-m", "longtext.f5tts_server"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            creationflags=_console_flags()
        )
        time.sleep(3)
        log("F5-TTS 服务已启动%s（端口 9881）。" % ("" if quiet_mode() else "（新控制台）"))
        return proc
    except Exception as e:
        log(f"启动 F5-TTS 失败: {e}", "ERROR")
        return None


# ── TTS 运行目录：都在 D 盘（不使用 C 盘）──
def _tts_dirs():
    """返回 (日语字典目录, MIOpen 缓存目录)，ASCII 路径，必要时创建"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目所在的盘
    drive = (os.path.splitdrive(os.path.abspath(base))[0] or "D:") + os.sep
    dic_dir = os.path.join(drive, "aipet_tts", "jtalk_dic")
    mio_dir = os.path.join(drive, "aipet_tts", "miopen")
    return dic_dir, mio_dir


def _ascii_path(path: str) -> str:
    """尽量把路径变成纯 ASCII：优先 8.3 短路径（不复制文件）"""
    try:
        path.encode("ascii")
        return path                      # 本来就是 ASCII
    except Exception:
        pass
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.windll.kernel32.GetShortPathNameW(path, buf, 1024)
        if n and buf.value:
            buf.value.encode("ascii")
            return buf.value             # 例：D:\XIAZAI~1\...
    except Exception:
        pass
    return ""


def prepare_tts_env(python_exe: str) -> dict:
    """准备好日语字典与 MIOpen 目录，返回要传给子进程的环境变量"""
    env = {}
    try:
        # ① 日语字典：先在"当前环境自带的 pyopenjtalk 包里"找
        site = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(python_exe))),
                            "lib", "site-packages")
        pkg = os.path.join(site, "pyopenjtalk")
        cands = []
        if os.path.isdir(pkg):
            for d in os.listdir(pkg):
                if d.lower().startswith("open_jtalk_dic"):
                    cands.append(os.path.join(pkg, d))
        # ② 自带 runtime(3.9) 的字典做兜底
        alt = os.path.join(os.path.dirname(os.path.abspath(python_exe)), "..", "..",
                           "runtime", "Lib", "site-packages", "pyopenjtalk")
        if os.path.isdir(alt):
            for d in os.listdir(alt):
                if d.lower().startswith("open_jtalk_dic"):
                    cands.append(os.path.join(os.path.abspath(alt), d))
        dic_src = next((c for c in cands if os.path.isdir(c)), "")
        if dic_src:
            # 优先用 8.3 短路径指向原位置（不复制）；不行再复制到 D:\aipet_tts\jtalk_dic
            ascii_now = _ascii_path(dic_src)
            if ascii_now:
                env["AIPET_JTALK_DIC"] = ascii_now
            else:
                dic_dir, _ = _tts_dirs()
                if not os.path.isdir(os.path.join(dic_dir, "char.bin")):
                    os.makedirs(dic_dir, exist_ok=True)
                    import shutil
                    for f in os.listdir(dic_src):
                        s0 = os.path.join(dic_src, f)
                        d0 = os.path.join(dic_dir, f)
                        try:
                            if os.path.isdir(s0):
                                if not os.path.isdir(d0):
                                    shutil.copytree(s0, d0)
                            else:
                                shutil.copy2(s0, d0)
                        except Exception:
                            pass
                env["AIPET_JTALK_DIC"] = dic_dir
        # ③ MIOpen 求解器缓存
        _, mio_dir = _tts_dirs()
        os.makedirs(mio_dir, exist_ok=True)
        env["AIPET_MIOPEN_DIR"] = mio_dir
        env["MIOPEN_USER_DB_PATH"] = mio_dir          # 运行时直接读这个
        # ④ nltk 数据：句子里的英文/数字要靠它做分词和音素（"下载了 3 个文件"这种）
        #    新 nltk(≥3.9) 要 averaged_perceptron_tagger_eng，而且自带 pathsec 沙箱，
        #    只允许读 NLTK_DATA 指定目录内的文件 —— 不指就会在合成中途抛异常，
        #    客户端表现为 "Response ended prematurely"（听起来就是"这句没声音"）。
        for _nd in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool", "nltk_data"),
                    os.path.join(_tts_dirs()[0], "..", "nltk_data"),
                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "GPT-SoVITS", "runtime", "nltk_data")):
            if os.path.isdir(_nd):
                env["NLTK_DATA"] = os.path.abspath(_nd)
                break
    except Exception as e:
        log(f"TTS 运行目录准备失败（不影响启动）：{e}", "WARN")
    return env


def _probe_gpu(py: str) -> bool:
    """探测这个环境能不能用 GPU（导入 torch 并查 cuda 可用性）"""
    try:
        r = subprocess.run([py, "-c", "import torch;print('1' if torch.cuda.is_available() else '0')"],
                           capture_output=True, text=True, timeout=120,
                           creationflags=(0x08000000 if os.name == "nt" else 0))
        return r.stdout.strip().endswith("1")
    except Exception:
        return False


def _runtime_py(root: str) -> str:
    """取 GPT-SoVITS 运行时里的解释器。

    两种布局都要认：自带 runtime 是便携版（python.exe 在根下），
    runtime_rocm 是 venv 版（Scripts\\python.exe）—— 写死一种会让另一种"找不到环境"。
    """
    for rel in ("python.exe", os.path.join("Scripts", "python.exe")):
        p = os.path.join(root, rel)
        if os.path.exists(p):
            return p
    return os.path.join(root, "Scripts", "python.exe")


def pick_tts_env():
    """返回 (python 路径, 是否用 A 卡 ROCm)。任何异常都回退到自带 runtime。"""
    base = os.path.dirname(os.path.abspath(__file__))
    cpu_py = _runtime_py(os.path.join(base, "GPT-SoVITS", "runtime"))
    rocm_py = _runtime_py(os.path.join(base, "GPT-SoVITS", "runtime_rocm"))
    want = None
    try:
        cfg = get_config("./config.json")
        if "gsv_use_rocm" in cfg:
            want = str(cfg.get("gsv_use_rocm")).lower() in ("true", "1", "yes")
    except Exception:
        want = None
    if want is True:                       # 明确要求 A 卡
        if os.path.exists(rocm_py):
            return rocm_py, True
        log("配置要求用 A 卡（gsv_use_rocm=true），但没找到 runtime_rocm → 回退 CPU。", "WARN")
    elif want is False:                    # 明确要求不用 A 卡
        if os.path.exists(cpu_py):
            return cpu_py, False
        if os.path.exists(rocm_py):
            return rocm_py, True
        return None, False
    # 没配置 → 自动挑：优先能跑 GPU 的
    for py, is_rocm in ((rocm_py, True), (cpu_py, False)):
        if os.path.exists(py) and _probe_gpu(py):
            log(f"自动选择 TTS 环境：{'A 卡(ROCm)' if is_rocm else '自带环境'}（检测到可用 GPU）", "INFO")
            return py, is_rocm
    if os.path.exists(cpu_py):
        return cpu_py, False
    if os.path.exists(rocm_py):
        return rocm_py, True
    return None, False


def start_tts_api():
    """使用 GPT-SoVITS 自带解释器在新的控制台窗口中启动 TTS API。"""
    tts_type = get_config("./config.json")["tts_type"]
    if tts_type == "local":
        log("检测到 tts_type = local", "INFO")
        # 用哪个 Python 环境跑 TTS 交给 pick_tts_env()：
        #   config.json 写了 gsv_use_rocm → 按写的来
        #   没写 → 自动探测（有 runtime_rocm 且能用 GPU 就用 A 卡，否则自带 runtime）
        python_path, _rocm = pick_tts_env()
        if python_path is None:
            log("未找到可用的 TTS Python 环境（runtime/runtime_rocm），短语音不可用。", "WARN")
            return None
        # 模型版本（CPU 实测，同一句话）：
        #   v2 基座 → 约 4.5 秒（默认，音质现代、速度可接受）
        #   v4 基座 → 约 60 秒；v4 微调（桌宠本人权重）→ 约 100 秒
        # 用 config.json 的 gsv_model_version 切换：v2 / v4 / finetuned
        try:
            _mv = str(get_config("./config.json").get("gsv_model_version", "v2")).strip().lower()
        except Exception:
            _mv = "v2"
        _gsv = os.path.abspath(r".\GPT-SoVITS")
        _pm = os.path.join(_gsv, "GPT_SoVITS", "pretrained_models")
        _extra = []
        # A 卡（ROCm）必需的一组参数：MIOpen 求解器缓存 + HIP 分配器展开段 + 关 SDMA，
        # 不加这些会退化成"比 CPU 还慢"（实测 RTF 3.8 → 0.33，比 CPU 的 1.7 还快）
        # 目录本身由 prepare_tts_env() 建好并返回 MIOPEN_USER_DB_PATH
        _rocm_env = {}
        if _rocm:
            _rocm_env = {
                "is_half": "false",
                "MIOPEN_FIND_MODE": "FAST",
                "PYTORCH_HIP_ALLOC_CONF": "expandable_segments:True",
                "HSA_ENABLE_SDMA": "0",
            }
        if _mv in ("v4", "finetuned"):
            _script = os.path.join(_gsv, "api_v2.py")
            if _mv == "finetuned":
                _extra = []
            else:
                _extra = ["-s", os.path.join(_pm, "gsv-v4-pretrained", "s2Gv4.pth"),
                          "-g", os.path.join(_pm, "s1v3.ckpt")]
        else:
            _script = os.path.join(_gsv, "api.py")
            _extra = ["-s", os.path.join(_pm, "gsv-v2final-pretrained", "s2G2333k.pth"),
                      "-g", os.path.join(_pm, "gsv-v2final-pretrained",
                                         "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt")]
        script_path = _script
        work_dir = r".\GPT-SoVITS"

        if not os.path.exists(os.path.join(work_dir, script_path)):
            log("未找到 GPT-SoVITS 整合包（api.py / api_v2.py），短文本语音不可用。", "WARN")
            log("提示：将 GPT-SoVITS 整合包放入项目根目录，或 config 中 tts_type 改用 cloud。", "INFO")
            return None

        log("使用解释器 %s 启动 TTS 服务%s..." % (python_path, "" if quiet_mode() else "（新控制台）"))

        try:
            _pop_env = dict(os.environ)
            _pop_env.update(_rocm_env)
            if _rocm:                      # 只有 A 卡环境需要（中文路径下的字典问题）
                _pop_env.update(prepare_tts_env(python_path))
            proc = subprocess.Popen(
                [python_path, script_path] + _extra,
                cwd=work_dir,
                env=_pop_env,
                creationflags=_console_flags()
            )
            time.sleep(1.5)
            log("TTS 服务已启动%s。" % ("" if quiet_mode() else "（新控制台）"))

            def _warm():
                """服务就绪后先合成一句短的：模型预热，避免第一句等十来秒（失败无所谓）"""
                import threading

                def _run():
                    try:
                        import requests as _rq
                    except Exception:
                        return
                    ref = os.path.abspath(os.path.join("reference_voices", "long_chinese", "953244.wav"))
                    for _ in range(60):                 # 最多等 10 分钟（模型加载慢）
                        try:
                            if _rq.get("http://127.0.0.1:9880/docs", timeout=3).status_code == 200:
                                break
                        except Exception:
                            pass
                        time.sleep(10)
                    for _i in range(2):                # 第一次编译/调优内核，第二次才到全速
                        try:
                            _rq.get("http://127.0.0.1:9880/", params={
                                "refer_wav_path": ref, "prompt_text": "能和老师在一起，我真的，好高兴！",
                                "prompt_language": "zh", "text": "你好。", "text_language": "zh",
                                "sample_steps": 16, "if_sr": "false", "speed": 1.0}, timeout=(8, 300))
                        except Exception:
                            break
                    log("TTS 已预热完成（第一句不会再等冷启动）。")

                threading.Thread(target=_run, daemon=True).start()

            _warm()
            return proc
        except Exception as e:
            log(f"启动 TTS 失败: {e}", "ERROR")
            return None
    elif tts_type == "cloud":
        log("检测到 tts_type = cloud", "INFO")
        try:
            proc = subprocess.Popen(
                  ["ssh", "aipet", "-t", "bash -lc 'bash run.sh; bash'"],
                  creationflags=_console_flags()
            )
            time.sleep(1.5)
            log("TTS 服务已启动%s。" % ("" if quiet_mode() else "（新控制台）"))
            return proc
        except Exception as e:
            log(f"启动 TTS 失败: {e}", "ERROR")
            return None


def install_live2d_deps():
    """检查并提示安装 Live2D 依赖"""
    if LIVE2D_SKIP:
        log("未检测到 live2d 或 PyOpenGL，长按 Shift 2 秒切换 Live2D 将不可用。", "WARN")
        log("如需 Live2D 功能，请运行：pip install live2d-py PyOpenGL", "INFO")
    else:
        log("Live2D 依赖已安装，长按 Shift 2 秒可切换 Live2D 模式。", "SUCCESS")


def _find_main_window(pid: int):
    """找这个进程自己的可见顶层窗口（桌宠是无边框窗口，MainWindowHandle 常为 0）"""
    try:
        import ctypes
        u = ctypes.windll.user32
        found = []
        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def _cb(hwnd, lp):
            try:
                p = ctypes.c_uint()
                u.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
                if p.value == pid and u.IsWindowVisible(hwnd):
                    ln = u.GetWindowTextLengthW(hwnd)
                    found.append((int(hwnd), ln))
            except Exception:
                pass
            return True

        u.EnumWindows(EnumProc(_cb), None)
        # 优先带标题的（桌宠窗口没标题，托盘消息窗有类名但没有可见性）→ 取第一个可见的
        if found:
            return found[0][0]
    except Exception:
        pass
    return 0


def _supervise_pet(cmd, **kw):
    """跑桌宠并盯着它：窗口长时间不响应就自动重启（别让主人对着"未响应"干等）。

    为什么要这个：桌宠偶尔会卡在原生调用里（界面完全不响应，但进程还活着）。
    它跑在后台线程里的日志还在写，主人只看到一只点不动的桌宠。
    这里每 10 秒问一次系统"这个窗口还响应吗"，连续 3 次不响应（约 30 秒）就
    记一行日志、结束它、重新拉起 —— 自动恢复。
    """
    import time as _t
    restart_limit = 2
    restarts = 0
    while True:
        proc = subprocess.Popen(cmd, **kw)
        hung_checks = 0
        hwnd = 0
        # Windows：IsHungAppWindow 是系统自己判断"未响应"的那个 API
        try:
            import ctypes
            _u = ctypes.windll.user32
            _IsHung = getattr(_u, "IsHungAppWindow", None)
        except Exception:
            _IsHung = None
        while True:
            try:
                rc = proc.poll()
            except Exception:
                rc = None
            if rc is not None:
                break
            _t.sleep(10)
            if _IsHung is None:
                continue
            try:
                if not hwnd:
                    hwnd = _find_main_window(proc.pid)
                if hwnd and _IsHung(hwnd):
                    hung_checks += 1
                    log(f"检测到桌宠窗口未响应（第 {hung_checks}/3 次）…", "WARN")
                else:
                    if hung_checks:
                        hung_checks = 0
            except Exception:
                hung_checks = 0
            if hung_checks >= 3:
                log("桌宠窗口连续 30 秒未响应 → 结束它并自动重启（用户不用管）", "WARN")
                try:
                    proc.kill()
                    proc.wait(timeout=8)
                except Exception:
                    pass
                restarts += 1
                break
        if proc.returncode is not None and restarts and restarts <= restart_limit:
            log(f"正在重新拉起桌宠（第 {restarts} 次自动重启）…", "INFO")
            _t.sleep(2.0)
            continue
        return proc.returncode


def run_main():
    script_path = os.path.abspath(r".\main.py")

    if not os.path.exists(script_path):
        log(f"未找到文件: {script_path}", "ERROR")
        return

    log(f"正在运行主程序：{script_path}", "INFO")
    try:
        # 纯净模式下没有终端窗口，主程序的输出会全部丢掉（出问题没法查）→ 追加到同一份日志
        _kw = {}
        if quiet_mode():
            try:
                _lp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pet_run.log")
                os.makedirs(os.path.dirname(_lp), exist_ok=True)
                _fo = open(_lp, "a", encoding="utf-8", errors="replace")
                _kw = {"stdout": _fo, "stderr": subprocess.STDOUT}
            except Exception:
                _kw = {}
        _supervise_pet([_project_python(), "main.py"], creationflags=_console_flags(), **_kw)
    except Exception as e:
        log(f"桌宠启动失败: {e}", "ERROR")
    finally:
        # 桌宠退出 → 顺手把视觉/语音服务停掉，别让它们当孤儿继续占显存
        try:
            _cleanup_services()
        except Exception:
            pass


def _cleanup_services():
    """桌宠退出后收尾：停掉本脚本启动的视觉服务与语音服务（释放显存）"""
    try:
        import json as _json
        port = 28460
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
                      encoding="utf-8") as _f:
                port = int(_json.load(_f).get("vision_local_port") or 28460)
        except Exception:
            pass
        try:
            import urllib.request as _ur
            _ur.urlopen(f"http://127.0.0.1:{port}/unload", timeout=3).read()
            log("已让视觉服务释放显存", "INFO")
        except Exception:
            pass
    except Exception:
        pass


def _pet_pid_alive() -> bool:
    """data/pet.pid 里记的桌宠进程还活着吗（比探测 HTTP 端口可靠：启动期间端口还没起）

    为什么要它：桌宠启动要三十秒，这期间端口探测必然失败 → 会被当成"没在跑"，
    于是又拉一只起来（用户反馈"会启动多个桌宠"）。
    """
    try:
        import ctypes
        pf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pet.pid")
        if not os.path.exists(pf):
            return False
        with open(pf, encoding="utf-8") as f:
            pid = int((f.read() or "0").strip() or 0)
        if pid <= 0:
            return False
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
        k32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        h = k32.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong(0)
            ok = k32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
            return bool(ok) and code.value == 259        # STILL_ACTIVE
        finally:
            try:
                k32.CloseHandle(ctypes.c_void_p(h))
            except Exception:
                pass
    except Exception:
        return False


def _already_running() -> bool:
    """单实例保护：桌宠 API 端口已被占用 → 说明已经有一个桌宠在跑。

    不做这个检查的话，第二个实例的 API 会报
    "ERROR: [Errno 10048] error while attempting to bind ... 28565"
    （端口只能被一个进程监听），而且会出现两只桌宠同时说话。
    """
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.6)
            return s.connect_ex(("127.0.0.1", 28565)) == 0
    except Exception:
        return False


if __name__ == "__main__":
    if _already_running() or _pet_pid_alive():
        log("检测到桌宠已在运行（端口被占用或进程锁还在）→ 本次启动自动退出。", "WARN")
        log("为避免出现两只桌宠 / 端口冲突报错，本次启动已自动退出。", "INFO")
        log("・想切换角色：在启动器里「关闭桌宠」后再启动即可", "INFO")
        log("・确实要开第二个（不推荐）：先关闭当前桌宠窗口", "INFO")
        try:
            import time as _t
            _t.sleep(2.2)
        except Exception:
            pass
        sys.exit(0)
    cfg = load_runtime_config()
    # 强制使用 CPU 模式，跳过所有显卡检测
    hardware_type = "cpu"
    check_python()
    install_requirements()
    setup_runtime_and_pytorch(cfg=cfg, hardware_type=hardware_type)
    run_download()
    install_live2d_deps()
    start_tts_api()
    start_f5tts_api()
    run_main()
