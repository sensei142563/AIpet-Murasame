# -*- coding: utf-8 -*-
"""本地视觉模型的「一键配置」：下模型 + 备运行时 + 写配置。

谁在用：
  * 安装包（tool/pack/installer_main.py）：安装时勾了「配置本地视觉模型」
  * 命令行：python tool/vision_setup.py [--model-only] [--no-install-runtime]
  * 启动器设置页里的状态/说明也可以引用这里的默认值

做的事：
  1) 从 ModelScope 拉 Qwen2-VL-2B-Instruct 的 11 个文件（约 4.1G，支持断点续传、逐个校验大小）
  2) 找一个能跑 torch 的解释器：优先 GPT-SoVITS 整合包里的（自带显卡版 torch，最快）；
     没有就建 <程序目录>/vision_runtime 并装 torch（NVIDIA 显卡能自动加速；别的显卡只能
     靠 GPT-SoVITS 的 ROCm/CUDA 运行时，否则识别会慢到没法用 —— 这种情况会把识别来源
     保持在「云端」，并在日志里说清楚）
  3) 把 vision_* 配置写进 config.json（只动这几个键，不碰用户其它设置）

只依赖标准库：安装器的冻结环境里也能直接 import 使用。
"""
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

# ── 模型清单：文件名 → 字节数（用来判断「下过了/下完了」，也用来算总进度）──
MODEL_REPO = "Qwen/Qwen2-VL-2B-Instruct"
MODEL_HOSTS = [
    "https://modelscope.cn/models/Qwen/Qwen2-VL-2B-Instruct/resolve/master",
    "https://www.modelscope.cn/models/Qwen/Qwen2-VL-2B-Instruct/resolve/master",
]
MODEL_FILES = {
    "chat_template.json": 1050,
    "config.json": 1196,
    "generation_config.json": 272,
    "merges.txt": 1671839,
    "model-00001-of-00002.safetensors": 3988609112,
    "model-00002-of-00002.safetensors": 429441656,
    "model.safetensors.index.json": 56411,
    "preprocessor_config.json": 347,
    "tokenizer.json": 7029741,
    "tokenizer_config.json": 4190,
    "vocab.json": 2776833,
}
MODEL_TOTAL = sum(MODEL_FILES.values())

DEFAULT_PORT = 28460
DEFAULT_MAX_SIDE = 1280
DEFAULT_IDLE_UNLOAD = 300
# pip 源：国内优先（装 torch 动辄几个 G，官方源容易慢到超时）
PIP_INDEXES = [
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
    "https://pypi.org/simple",
]


def _log(log, msg):
    try:
        (log or print)(msg)
    except Exception:
        pass


def _app_dir() -> str:
    """程序根目录（桌宠安装目录）"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_cfg(app_dir: str) -> dict:
    try:
        with open(os.path.join(app_dir, "config.json"), encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def default_model_dir(app_dir: str = "") -> str:
    """默认放哪：<程序目录>/vision/Qwen2-VL-2B-Instruct（自包含，卸载时一起删）"""
    return os.path.join(app_dir or _app_dir(), "vision", "Qwen2-VL-2B-Instruct")


def model_complete(model_dir: str) -> bool:
    """模型是不是已经齐了（按文件大小逐个核对）"""
    if not os.path.isdir(model_dir):
        return False
    for name, size in MODEL_FILES.items():
        p = os.path.join(model_dir, name)
        try:
            if os.path.getsize(p) != size:
                return False
        except OSError:
            return False
    return True


# ── 下载 ────────────────────────────────────────────────
def _open_url(url: str, timeout: float = 30.0, headers: dict = None, direct: bool = True):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "AIpet-Murasame/vision-setup"})
    if direct:
        # 默认直连：国内下 ModelScope 走代理反而更慢
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    else:
        # 直连不通（比如只能通过代理上网）时再用系统代理
        op = urllib.request.build_opener()
    return op.open(req, timeout=timeout)


def _download_one(url: str, dst: str, size: int, on_bytes, stop=None) -> bool:
    """下单个文件；.part 断点续传。直连不行就换系统代理再试。返回是否成功。"""
    last_err = None
    for direct in (True, False):
        try:
            return _download_attempt(url, dst, size, on_bytes, stop, direct)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
            last_err = e
            if not direct:
                raise
    if last_err:
        raise last_err
    return False


def _download_attempt(url: str, dst: str, size: int, on_bytes, stop=None,
                      direct: bool = True) -> bool:
    part = dst + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    if have > size:                 # 本地比远端还大 → 文件坏了，重下
        os.remove(part)
        have = 0
    headers = {"User-Agent": "AIpet-Murasame/vision-setup"}
    if have:
        headers["Range"] = f"bytes={have}-"
    with _open_url(url, timeout=30.0, headers=headers, direct=direct) as r:
        code = getattr(r, "status", r.getcode())
        if have and code != 206:        # 服务端不支持续传 → 从头来
            have = 0
            try:
                os.remove(part)
            except OSError:
                pass
        mode = "ab" if have else "wb"
        got = have
        with open(part, mode) as f:
            while True:
                if stop is not None and stop():
                    return False
                chunk = r.read(1024 * 512)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                on_bytes(got, size)
        if got != size:
            return False            # 大小不对 → 留 .part 下次续传
    if os.path.exists(dst):
        os.remove(dst)
    os.rename(part, dst)
    return True


def download_model(model_dir: str, log=None, progress=None, stop=None) -> bool:
    """下载整个模型。progress(done_bytes, total_bytes, filename) 可选。"""
    os.makedirs(model_dir, exist_ok=True)
    done_total = 0
    for name, size in MODEL_FILES.items():
        dst = os.path.join(model_dir, name)
        if os.path.exists(dst) and os.path.getsize(dst) == size:
            done_total += size
            if progress:
                progress(done_total, MODEL_TOTAL, name)
            continue
        _log(log, f"[视觉] 下载 {name}（{size / 1e9:.2f} GB）…")
        ok = False
        last_err = None
        for host in MODEL_HOSTS:
            url = f"{host}/{name}"
            try:
                ok = _download_one(
                    url, dst, size,
                    lambda got, tot, _b=done_total: progress(_b + got, MODEL_TOTAL, name) if progress else None,
                    stop=stop)
                if ok:
                    break
            except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
                last_err = e
                _log(log, f"[视觉]{host} 下载失败：{type(e).__name__}: {e}")
        if not ok:
            _log(log, f"[视觉]{name} 没下完（下次运行会自动续传）：{last_err}")
            return False
        done_total += size
        if progress:
            progress(done_total, MODEL_TOTAL, name)
    if not model_complete(model_dir):
        _log(log, "[视觉] 下载完了但校验没过（可能有文件被截断）")
        return False
    _log(log, f"[视觉] 模型就绪：{model_dir}（{MODEL_TOTAL / 1e9:.2f} GB）")
    return True


# ── 运行时 ──────────────────────────────────────────────
def _has_torch(py: str) -> bool:
    """这个解释器里有没有 torch（看文件，不启动进程，快）"""
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(py)))   # <env>/Scripts/python.exe → <env>
        sp = os.path.join(root, "Lib", "site-packages")
        return os.path.isdir(os.path.join(sp, "torch"))
    except Exception:
        return False


def torch_works(py: str) -> tuple:
    """真跑一次 import torch（慢一点但准），返回 (能不能用, 说明)"""
    try:
        r = subprocess.run(
            [py, "-c", "import torch,sys;"
                       "c=torch.cuda.is_available();"
                       "print('cuda' if c else 'cpu', torch.cuda.get_device_name(0) if c else '')"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "").strip()[-300:]
        out = (r.stdout or "").strip()
        return True, out
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def find_runtime(app_dir: str = "", cfg: dict = None) -> str:
    """找一个能跑视觉服务的 python：配置里指定的 → GPT-SoVITS 的 → 专用 venv → 本体 venv

    全部返回绝对路径：调用方（启动器/安装器）的工作目录不一定是程序目录。
    """
    app_dir = os.path.abspath(app_dir or _app_dir())
    cfg = cfg if cfg is not None else _load_cfg(app_dir)
    cands = []
    pref = str(cfg.get("vision_runtime_python") or "").strip()
    if pref:
        cands.append(pref if os.path.isabs(pref) else os.path.join(app_dir, pref))
    for rel in (os.path.join("GPT-SoVITS", "runtime_rocm", "Scripts", "python.exe"),
                os.path.join("GPT-SoVITS", "runtime", "Scripts", "python.exe"),
                os.path.join("GPT-SoVITS", "runtime", "python.exe")):
        cands.append(os.path.join(app_dir, rel))
    cands.append(os.path.join(app_dir, "vision_runtime", "Scripts", "python.exe"))
    cands.append(os.path.join(app_dir, "runtime", "venv", "Scripts", "python.exe"))
    for p in cands:
        if p and os.path.isfile(p):
            return os.path.abspath(p)
    return ""


def find_gpu_runtime(app_dir: str = "", cfg: dict = None) -> str:
    """找一个「带显卡加速」的 python（GPT-SoVITS 整合包 / 专用运行时里 torch 能用显卡）"""
    app_dir = app_dir or _app_dir()
    py = find_runtime(app_dir, cfg)
    if py and _has_torch(py):
        ok, info = torch_works(py)
        if ok and str(info).startswith("cuda"):
            return py
    return ""


def ensure_runtime(app_dir: str = "", log=None, install_if_missing=True) -> str:
    """保证有一个能跑视觉服务的 python。返回路径（空 = 没搞定）。

    有 GPT-SoVITS 整合包的直接用它（自带显卡版 torch，识别几十秒）。
    没有就在 <程序目录>/vision_runtime 建一个虚拟环境装 torch —— 别人机器上
    这一步能不能用显卡取决于显卡型号，所以装完会实测一次，不行就把识别来源
    留在云端（见 apply_config 的 use_local 参数）。
    """
    app_dir = os.path.abspath(app_dir or _app_dir())
    py = find_gpu_runtime(app_dir)
    if py:
        _log(log, f"[视觉] 找到可用的显卡运行时：{py}")
        return py
    if not install_if_missing:
        _log(log, "[视觉] 没找到带显卡加速的运行时（可装 GPT-SoVITS 整合包）")
        return find_runtime(app_dir)

    base_py = ""
    for rel in (os.path.join("python", "python.exe"),
                os.path.join("runtime", "python", "python.exe")):
        if os.path.isfile(os.path.join(app_dir, rel)):
            base_py = os.path.join(app_dir, rel)
            break
    if not base_py:
        _log(log, "[视觉] ⚠ 没找到随包分发的 python，无法自动建运行环境"
                  "（装了 GPT-SoVITS 整合包就能直接用它的）")
        return ""
    env_dir = os.path.join(app_dir, "vision_runtime")
    venv_py = os.path.join(env_dir, "Scripts", "python.exe")
    if not os.path.isfile(venv_py):
        _log(log, f"[视觉] 正在创建运行环境：{env_dir}")
        try:
            r = subprocess.run([base_py, "-m", "venv", env_dir], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=600,
                               creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
            if r.returncode != 0 or not os.path.isfile(venv_py):
                _log(log, f"[视觉] 建虚拟环境失败：{(r.stderr or r.stdout or '')[-300:]}")
                return ""
        except Exception as e:
            _log(log, f"[视觉] 建虚拟环境异常：{type(e).__name__}: {e}")
            return ""
    if _has_torch(venv_py):
        _log(log, "[视觉] 运行环境已存在，跳过安装")
        return venv_py

    _log(log, "[视觉] 安装依赖（torch + transformers + pillow，几百 MB ~ 2 GB，耐心等）…")
    pkgs = ["torch", "transformers", "pillow"]
    for idx in PIP_INDEXES:
        try:
            r = subprocess.run([venv_py, "-m", "pip", "install", "--no-input",
                                "--disable-pip-version-check", "-i", idx] + pkgs,
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=7200,
                               creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
            if r.returncode == 0 and _has_torch(venv_py):
                _log(log, f"[视觉] 依赖装好了（源：{idx}）")
                return venv_py
            _log(log, f"[视觉]{idx} 安装没成功：{(r.stderr or r.stdout or '')[-200:]}")
        except Exception as e:
            _log(log, f"[视觉]{idx} 安装异常：{type(e).__name__}: {e}")
    _log(log, "[视觉] 依赖没装上，本地视觉暂时用不了（识别会走云端 API）")
    return ""


# ── 写配置 ──────────────────────────────────────────────
def apply_config(app_dir: str, model_dir: str, port: int = DEFAULT_PORT,
                 use_local: bool = True, runtime_py: str = "") -> dict:
    """把 vision_* 写进 config.json（只改这几个键）。返回写进去的内容。"""
    p = os.path.join(app_dir, "config.json")
    cfg = _load_cfg(app_dir)
    cfg["vision_source"] = "local" if use_local else "cloud"
    cfg["vision_local_model_dir"] = model_dir
    cfg["vision_local_port"] = int(port)
    cfg.setdefault("vision_max_side", DEFAULT_MAX_SIDE)
    cfg.setdefault("vision_idle_unload", DEFAULT_IDLE_UNLOAD)
    la = cfg.setdefault("local_api", {})
    if isinstance(la, dict):
        la["vision"] = f"http://127.0.0.1:{int(port)}/describe"
    if runtime_py:
        cfg["vision_runtime_python"] = runtime_py
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, p)
    return cfg


# ── 一把梭 ──────────────────────────────────────────────
def setup(app_dir: str = "", log=None, progress=None, stop=None,
          model_dir: str = "", install_runtime: bool = True,
          use_local_when_ready: bool = True) -> dict:
    """完整流程。返回 {"ok":bool, "model_dir":…, "runtime_py":…, "gpu":bool, "note":…}"""
    app_dir = os.path.abspath(app_dir or _app_dir())
    cfg = _load_cfg(app_dir)
    out = {"ok": False, "model_dir": "", "runtime_py": "", "gpu": False, "note": ""}

    # 1) 模型
    dest = model_dir or str(cfg.get("vision_local_model_dir") or "").strip() or default_model_dir(app_dir)
    dest = os.path.abspath(dest)
    if model_complete(dest):
        _log(log, f"[视觉] 模型已存在，跳过下载：{dest}")
    else:
        if not download_model(dest, log=log, progress=progress, stop=stop):
            out["model_dir"] = dest
            out["note"] = "模型没下完（可重新运行本程序续传）"
            return out
    out["model_dir"] = dest

    # 2) 运行时
    rt = ensure_runtime(app_dir, log=log, install_if_missing=install_runtime) if install_runtime else find_runtime(app_dir, cfg)
    out["runtime_py"] = rt
    gpu = False
    if rt:
        ok, info = torch_works(rt)
        gpu = bool(ok and str(info).startswith("cuda"))
        _log(log, f"[视觉] 运行时自检：{'可用' if ok else '不可用'}（{info or '没有 torch'}）")
    out["gpu"] = gpu

    # 3) 配置：只有真能跑（有显卡加速）才把识别切到本地，否则留在云端并说清楚
    use_local = bool(use_local_when_ready and gpu)
    apply_config(app_dir, dest, DEFAULT_PORT, use_local=use_local, runtime_py=rt)
    if use_local:
        out["ok"] = True
        out["note"] = "本地视觉已启用（识别约 30 秒一屏）"
    else:
        out["ok"] = bool(dest)
        out["note"] = ("本地视觉模型已下载，但没检测到可用的显卡加速 → 识别仍用云端 API。"
                       "装了 GPT-SoVITS 整合包（自带显卡版 torch）后，到启动器设置里把"
                       "「识别来源」改成本地即可。")
    _log(log, "[视觉] " + out["note"])
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    def _arg(name, default=""):
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return argv[i + 1]
        return default

    app_dir = _arg("--app-dir", "") or _app_dir()
    model_dir = _arg("--model-dir", "")
    install_runtime = "--no-install-runtime" not in argv
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    def _prog(done, total, name):
        pct = done * 100.0 / max(1, total)
        sys.stdout.write(f"\r[视觉] 下载进度 {pct:5.1f}%  ({done / 1e9:.2f}/{total / 1e9:.2f} GB)  {name}    ")
        sys.stdout.flush()

    r = setup(app_dir=app_dir, model_dir=model_dir, install_runtime=install_runtime,
              log=lambda m: print(m, flush=True), progress=_prog)
    print()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
