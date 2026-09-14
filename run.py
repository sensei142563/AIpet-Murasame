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
    levels = {
        "INFO": "[AIpet]",
        "WARN": "⚠️ [警告]",
        "ERROR": "❌ [错误]",
        "SUCCESS": "✅ [成功]",
    }
    prefix = levels.get(level, "[AIpet]")
    print(f"{prefix} {msg}")


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
    try:
        import cv2
        import numpy
        import PyQt5.QtCore
        import pygame
        import soundfile
        log("核心依赖已就绪，跳过自动安装。", "SUCCESS")
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
            check=True
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
        ], check=True, timeout=1800)
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
        log("检测到 DeepSeek 云端模式，跳过 PyTorch 安装。")
        ensure_cpu_torch()
        return "deepseek"
    elif model_type == "qwen":
        log("检测到 Qwen 云端模式，跳过 PyTorch 安装。")
        ensure_cpu_torch()
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
            ], check=True)
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
            ], check=True)
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

        log(f"正在运行模型下载脚本：{script_path}", "INFO")
        try:
            # ⚠ 这里以前用裸 "python"（PATH 里的系统 Python）：系统 Python 没有本项目的
            #   依赖，跑 download.py 会直接崩（事件日志里的 MSVCP140 访问违规就是这么来的）。
            #   统一用项目解释器：优先 runtime venv。
            subprocess.run([_f5tts_venv_python(), "download.py"],)
            log("模型下载完成。", "SUCCESS")
        except subprocess.CalledProcessError as e:
            log(f"下载脚本运行失败: {e}", "ERROR")
    elif tts_type == "cloud":
        log("检测到 tts_type = cloud, 跳过模型下载", "INFO")

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

    log("检测到长文本模式已开启，启动 F5-TTS 服务（新控制台）...", "INFO")
    try:
        proc = subprocess.Popen(
            [_f5tts_venv_python(), "-m", "longtext.f5tts_server"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            creationflags=(0x00000010 if os.name == "nt" else 0)
        )
        time.sleep(3)
        log("F5-TTS 服务已在新控制台启动（端口 9881）。")
        return proc
    except Exception as e:
        log(f"启动 F5-TTS 失败: {e}", "ERROR")
        return None


def start_tts_api():
    """使用 GPT-SoVITS 自带解释器在新的控制台窗口中启动 TTS API。"""
    tts_type = get_config("./config.json")["tts_type"]
    if tts_type == "local":
        log("检测到 tts_type = local", "INFO")
        python_path = os.path.abspath(r".\GPT-SoVITS\runtime\python.exe")
        script_path = os.path.abspath(r".\GPT-SoVITS\api_v2.py")
        work_dir = r".\GPT-SoVITS"

        if not os.path.exists(os.path.join(work_dir, script_path)):
            log("未找到 GPT-SoVITS 整合包（api_v2.py），短文本日语语音不可用。", "WARN")
            log("提示：将 GPT-SoVITS 整合包放入项目根目录，或 config 中 tts_type 改用 cloud。", "INFO")
            return None

        log(f"使用解释器 {python_path} 启动 TTS 服务（新控制台）...")

        try:
            proc = subprocess.Popen(
                [python_path, script_path],
                cwd=work_dir,
                creationflags=(0x00000010 if os.name == "nt" else 0)
            )
            time.sleep(5)
            log("TTS 服务已在新控制台启动。")
            return proc
        except Exception as e:
            log(f"启动 TTS 失败: {e}", "ERROR")
            return None
    elif tts_type == "cloud":
        log("检测到 tts_type = cloud", "INFO")
        try:
            proc = subprocess.Popen(
                  ["ssh", "aipet", "-t", "bash -lc 'bash run.sh; bash'"],
                  creationflags=(0x00000010 if os.name == "nt" else 0)
            )
            time.sleep(5)
            log("TTS 服务已在新控制台启动。")
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


def run_main():
    script_path = os.path.abspath(r".\main.py")

    if not os.path.exists(script_path):
        log(f"未找到文件: {script_path}", "ERROR")
        return

    log(f"正在运行主程序：{script_path}", "INFO")
    try:
        subprocess.run([_project_python(), "main.py"],)
    except subprocess.CalledProcessError as e:
        log(f"桌宠启动失败: {e}", "ERROR")

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
    if _already_running():
        log("检测到桌宠已在运行（API 端口 28565 已被占用）。", "WARN")
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
