
try:  # 控制台被重定向（管道/日志）时 Windows 会用 GBK 编码 stdout，
    # 打印 emoji 会 UnicodeEncodeError 直接打断进程 → 统一降级成替换字符
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
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

from tool.config import as_bool, get_config

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
        }

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"无法解析 config.json: {e}，使用默认云端配置。", "WARN")
        return {
            "model_type": "deepseek",
            "tts_type": "cloud",
        }


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
        # A 卡/核显（AMD/Intel）：本机无 CUDA，本地 GPU 推理不可用，
        # 但对话/QQ/微信走云端 API、F5-TTS 走 CPU，均不受影响 → 提示后走 CPU，不退出
        if any(bad in gpu_lower for bad in ("amd", "radeon", "intel", "iris", "arc")):
            log("检测到 AMD/Intel 显卡（无 NVIDIA/CUDA），本地 GPU 推理不可用。", "WARN")
            log("已自动切换 CPU 模式：对话/QQ/微信走云端不受影响；本地语音/TTS 合成较慢属正常。", "INFO")
            return "cpu"
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


def _want_cuda_torch(cfg) -> bool:
    """是否需要给项目 venv 装 CUDA 版 torch。

    只在「全局显卡加速开着」且下面任一成立时需要：
      - 本地模型（model_type=local）要 GPU 推理；
      - 长语音（F5-TTS）开着、且它自己的 GPU 加速也开着 —— F5 服务由
        `_find_f5tts_python()` 挑解释器（候选顺序：runtime\venv → 当前解释器），
        与 `_project_python()` 的候选顺序一致，所以「装 CUDA 版 torch」会落在
        F5 真正要用的那个解释器上。
        ⚠ 开发机上通常没有 runtime\venv → 两者都落到**当前解释器**（往往是系统
          Python）；而项目里那个 `.venv` 只是开发用的虚拟环境，F5 看不懂它
          （在它里面找不到 f5_tts 时会直接判定「长语音不可用」）。
    短语音（GPT-SoVITS）用的是整合包自带的解释器，跟本 venv 的 torch 无关。
    """
    if not as_bool(cfg.get("gpu_accel"), True):
        return False
    if str(cfg.get("model_type", "")).strip().lower() == "local":
        return True
    long_on = as_bool(cfg.get("longtext_enabled"), True)
    return long_on and as_bool(cfg.get("longtts_gpu"), True)


def _tts_use_gpu(cfg, key: str) -> bool:
    """某个语音功能是否走 GPU：全局显卡加速 + 它自己的开关，都为真才走。"""
    return as_bool(cfg.get("gpu_accel"), True) and as_bool(cfg.get(key), True)


def _torch_cuda_mismatch(torch_cuda, driver_cuda) -> bool:
    """已装的 torch 是否需要换一个 CUDA 版本？

    - torch 是 CPU 版、但机器有 CUDA → 需要（最常见的「有 N 卡却跑在 CPU 上」）；
    - torch 的 CUDA 主版本**高于**驱动支持的版本 → 需要（装新了，加载会失败）；
    - torch 的 CUDA 主版本**低于或等于**驱动 → **不需要**：CUDA 向后兼容，
      驱动 13.1 上跑 cu128 构建完全正常。

    ⚠ 旧逻辑要求「主版本相同」，于是把好好的 cu128 判成不匹配（驱动报 13.1）
      → 白白重下几个 GB 的 torch，还得多重启一次。现在只按「装新了」判。
    """
    dc = str(driver_cuda or "").strip()
    if not dc:
        return False
    tc = str(torch_cuda or "").strip().upper()
    if tc in ("", "CPU", "NONE"):
        return True
    try:
        return int(tc.split(".")[0]) > int(dc.split(".")[0])
    except Exception:
        return False


def _gsv_config_with_device(work_dir: str, use_gpu: bool):
    """为 GPT-SoVITS 生成一份「改过 custom.device」的 tts_infer.yaml 副本，返回绝对路径。

    - 只改 custom: 段 —— TTS_Config 只取这一段（TTS.py: `configs_.get("custom", ...)`）；
    - **不改整合包里的原文件**（第三方文件，改坏了不好还原）；api_v2.py 支持 `-c` 指定配置路径；
    - 写 cuda 也是安全的：TTS_Config 发现 torch.cuda.is_available() 为假时会自己回退 CPU
      （并把 is_half 关掉），所以 A 卡/无 CUDA 机器不会因此崩；
    - 解析不出来就返回 None（调用方退回整合包自带配置，并在日志里说明）。
    """
    src = os.path.join(work_dir, "GPT_SoVITS", "configs", "tts_infer.yaml")
    if not os.path.isfile(src):
        return None
    try:
        with open(src, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception:
        return None

    device = "cuda" if use_gpu else "cpu"
    half = "true" if use_gpu else "false"
    out, in_custom, patched_dev = [], False, False
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if indent == 0 and stripped and not stripped.startswith("#"):
            in_custom = stripped.startswith("custom:")     # 顶层键：只看 custom 段
        elif in_custom and indent > 0:
            if stripped.startswith("device:"):
                line = " " * indent + "device: " + device
                patched_dev = True
            elif stripped.startswith("is_half:"):
                line = " " * indent + "is_half: " + half
        out.append(line)

    if not patched_dev:
        return None
    base = os.path.dirname(os.path.abspath(__file__))
    dst = os.path.join(base, "tmp", "gsv_tts_infer_%s.yaml" % device)
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
    except Exception as e:
        log(f"写入 GPT-SoVITS 配置副本失败: {e}", "WARN")
        return None
    return dst


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

    cloud = model_type in SUPPORTED_CLOUD_MODEL_TYPES
    if cloud:
        log(f"检测到 {model_type} 云端模式，跳过本地模型的 PyTorch 安装。")
        if not _want_cuda_torch(cfg):
            ensure_cpu_torch()
            return model_type
        # 云端对话本身不需要显卡，但**本地语音**（F5-TTS）开了 GPU 加速：
        # F5 用项目解释器跑 → venv 里必须是 CUDA 版 torch，所以继续往下走显卡/CUDA 检测。
        log("但长语音（F5-TTS）已开启 GPU 加速 → 继续检测显卡与 CUDA，改装 CUDA 版 PyTorch。", "INFO")
    else:
        log("检测到本地运行模式。")

    # 如果是CPU模式，直接跳过PyTorch安装
    if hardware_type is None:
        hardware_type = check_hardware()

    if hardware_type == "cpu":
        log("检测到 CPU 模式，跳过 CUDA 版 PyTorch 安装。", "INFO")
        # 但 torch 本身还是得有：本地模型与本地语音都依赖它，而 requirements.txt
        # 里并不含 torch（历史上由本函数管理）。ensure_cpu_torch() 已装则只做检测，
        # 不会把已有的 CUDA 版降级；失败也只告警不退出。
        ensure_cpu_torch()
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

    # Step 4️⃣ 选择 PyTorch 安装源（这里只决定「万一要装时用哪个源」，
    # 是否真的要装由下面的版本匹配判定决定 —— 所以别在这里就说"将安装"，会误导排查）
    if not cuda_version:
        torch_url = "https://download.pytorch.org/whl/cpu"
    elif cuda_version.startswith("13"):
        torch_url = "https://download.pytorch.org/whl/cu130"
    elif cuda_version.startswith("12"):
        torch_url = "https://download.pytorch.org/whl/cu128"
    elif cuda_version.startswith("11"):
        torch_url = "https://download.pytorch.org/whl/cu128"
    else:
        torch_url = "https://download.pytorch.org/whl/cpu"
        log(f"未识别的 CUDA 版本 {cuda_version}，如需安装将使用 CPU 版。", "WARN")

    # Step 5️⃣ 检查 PyTorch 是否已安装
    try:
        import torch
        installed_version = torch.__version__
        torch_cuda_version = torch.version.cuda or "CPU"
        log(f"已检测到 PyTorch {installed_version} (CUDA {torch_cuda_version})", "SUCCESS")

        # 检查版本匹配情况（判定规则见 _torch_cuda_mismatch 的文档）
        mismatch = _torch_cuda_mismatch(torch_cuda_version, cuda_version)
        if mismatch:
            if str(torch_cuda_version).strip().upper() in ("", "CPU", "NONE"):
                log(f"检测到系统 CUDA {cuda_version}，但已安装的 PyTorch 为 CPU 版。", "WARN")
            else:
                log(f"已安装的 PyTorch 基于 CUDA {torch_cuda_version}，高于驱动支持的 "
                    f"CUDA {cuda_version} → 需要换一个匹配的版本。", "WARN")

        if mismatch:
            log(f"开始安装与当前 CUDA 版本匹配的 PyTorch（源：{torch_url}）...", "INFO")
            try:
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
            except Exception as e:
                # ⚠ 以前这里 check=True 且没有 try：源里没有对应 cu 版本 / 网络不通时
                #   会抛 CalledProcessError 一路冒到 __main__ → 桌宠直接起不来。
                #   现在降级：继续用现有 torch（CPU 版也能跑，只是慢）。
                log(f"CUDA 版 PyTorch 安装失败：{e}", "WARN")
                log("→ 继续使用现有 PyTorch（本地语音/模型会走 CPU，较慢）", "INFO")
                log(f"  需要 GPU 时可手动执行：{_project_python()} -m pip install -U torch "
                    f"torchvision torchaudio --index-url {torch_url}", "INFO")

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
        except Exception as e:
            # 与 ensure_cpu_torch() 同一策略：装不上也不退出。
            # 云端模式不需要 torch；只有本地模型/本地语音会不可用。
            log(f"PyTorch 安装失败：{e}", "WARN")
            log("→ 继续以「无 torch」方式启动（云端模式可用；本地模型/语音不可用）", "INFO")
            log(f"  需要时手动执行：{_project_python()} -m pip install torch torchvision "
                f"torchaudio --index-url {torch_url}", "INFO")

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

def _f5tts_python_candidates():
    """F5-TTS 解释器候选列表（按优先级）：runtime\\venv → 当前解释器。"""
    cands = []
    try:
        from tool.paths import venv_python
        p = venv_python()
        if p and p not in cands:
            cands.append(p)
    except Exception:
        pass
    if sys.executable not in cands:
        cands.append(sys.executable)
    return cands


def _find_f5tts_python():
    """多候选探测：谁装了 f5_tts 用谁（N 卡调试 §3.5）。

    只按"venv 目录存在"选解释器，会在 venv 缺可选库时架空已装好库的系统 Python。
    这里逐个候选跑 `import f5_tts`，返回第一个可用的解释器；都没有返回 None。
    """
    for cand in _f5tts_python_candidates():
        try:
            _probe = subprocess.run(
                [cand, "-c", "import f5_tts"],
                capture_output=True, timeout=30,
            )
            if _probe.returncode == 0:
                return cand
        except Exception:
            continue
    return None


def start_f5tts_api():
    """启动 F5-TTS HTTP 服务（端口 9881，长文本模式中文语音合成）"""
    cfg = get_config("./config.json")
    # 长语音没有独立开关：它跟着「长文本模式」走（longtext_enabled 原本就是这条链的门禁）。
    # ⚠ 别再为「是否启动长语音」加第二个开关 —— 那是重复的。
    if not as_bool(cfg.get("longtext_enabled"), True):
        log("长文本模式已关闭，跳过 F5-TTS 服务启动。", "INFO")
        return None

    # F5-TTS 为可选语音库：多候选探测（runtime\venv → 系统 Python），谁有 f5_tts 用谁。
    f5_py = _find_f5tts_python()
    if f5_py is None:
        log("未检测到 f5_tts 库（venv 与系统 Python 均未安装），长文本语音不可用。", "WARN")
        log("如需语音功能：安装 f5-tts 后重试（推荐在 runtime\\venv 内安装）。", "INFO")
        return None

    # 设备 = 全局显卡加速 + 「长语音 GPU 加速」都为真才用 cuda；
    # F5 服务内部还会再确认一次 torch.cuda.is_available()，不可用会自己回退 CPU。
    _dev = "cuda" if _tts_use_gpu(cfg, "longtts_gpu") else "cpu"
    _env = dict(os.environ)
    _env["F5TTS_DEVICE"] = _dev
    log(f"检测到长文本模式已开启，启动 F5-TTS 服务（新控制台，设备 {_dev.upper()}）...", "INFO")
    try:
        proc = subprocess.Popen(
            [f5_py, "-m", "longtext.f5tts_server"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            env=_env,
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
    cfg = get_config("./config.json")
    tts_type = cfg.get("tts_type", "local")
    if tts_type == "local":
        # 「启用短语音」关掉时不必把服务拉起来：GPT-SoVITS 一启动就会把模型加载进显存，
        # 白占几 GB。开关的语义是"不用短语音"，那就服务也别起。
        if not as_bool(cfg.get("voice_synthesis_enable"), True):
            log("短语音已在设置里关闭，跳过 GPT-SoVITS 服务启动。", "INFO")
            return None
        log("检测到 tts_type = local", "INFO")
        python_path = os.path.abspath(r".\GPT-SoVITS\runtime\python.exe")
        script_path = os.path.abspath(r".\GPT-SoVITS\api_v2.py")
        work_dir = r".\GPT-SoVITS"

        if not os.path.exists(os.path.join(work_dir, script_path)):
            log("未找到 GPT-SoVITS 整合包（api_v2.py），短文本日语语音不可用。", "WARN")
            log("提示：将 GPT-SoVITS 整合包放入项目根目录，或 config 中 tts_type 改用 cloud。", "INFO")
            return None

        # 设备 = 全局显卡加速 + 「短语音 GPU 加速」；改写的是 tmp/ 下的配置副本，
        # 不动整合包里的原文件。整合包自己没装 CUDA 时，TTS_Config 会回退 CPU。
        _gpu = _tts_use_gpu(cfg, "short_tts_gpu")
        cmd = [python_path, script_path]
        _cfg_copy = _gsv_config_with_device(work_dir, _gpu)
        if _cfg_copy:
            cmd += ["-c", _cfg_copy]
            log(f"短语音设备: {'CUDA（GPU 加速）' if _gpu else 'CPU'}", "INFO")
        elif not _gpu:
            log("⚠ 未能改写 GPT-SoVITS 配置 → 短语音仍按整合包自带设置运行。", "WARN")
            log("  如需强制 CPU，请手动把 GPT-SoVITS/GPT_SoVITS/configs/tts_infer.yaml "
                "的 custom.device 改成 cpu。", "INFO")

        log(f"使用解释器 {python_path} 启动 TTS 服务（新控制台）...")

        try:
            proc = subprocess.Popen(
                cmd,
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
    # 显卡加速开关（默认开，启动器「设置 → 对话模型与推理 → 显卡加速（NVIDIA）」可改）：
    #   开 → 传 None，由 setup_runtime_and_pytorch 按模式决定：
    #        云端（deepseek/qwen）提前返回、压根不做显卡检测；
    #        本地（local）才调 check_hardware()，N 卡走 CUDA，不是 N 卡/没 CUDA 回退 CPU。
    #   关 → 传 "cpu"，直接跳过整套显卡检测，不装 CUDA 版 torch。
    # ⚠ 别再写死 "cpu"：那会让本地 + N 卡的机器永远拿不到 CUDA 版 torch。
    hardware_type = None if as_bool(cfg.get("gpu_accel"), True) else "cpu"
    check_python()
    install_requirements()
    setup_runtime_and_pytorch(cfg=cfg, hardware_type=hardware_type)
    run_download()
    install_live2d_deps()
    start_tts_api()
    start_f5tts_api()
    run_main()
