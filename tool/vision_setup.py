# -*- coding: utf-8 -*-
"""本地视觉模型的「一键准备」：清单校验 + 运行时发现 + 写配置。

为什么单独一个模块
------------------
tool/screen_intent.py 目前只会走云端视觉 API（cloud_vl）。想让识别跑在本机显卡上，
得凑齐三样东西：模型文件、一个真能 import torch 的解释器、config.json 里那几个
vision_* 键。本模块只负责「凑齐并如实报告」，不做任何隐式联网或装包动作：

  * 默认**只体检**：按文件大小核对模型、找解释器、打印结论，不联网
  * 下模型要显式 --download（约 4.1G，断点续传、逐文件校验）
  * 建运行环境/装 torch 要显式 --install-runtime（几百 MB ~ 2GB）
  * 写配置只改 vision_* 与 local_api.vision，其它键原样保留，且原子替换

命令行：
    python tool/vision_setup.py                  # 体检 + 写配置（不联网）
    python tool/vision_setup.py --download       # 顺带下模型
    python tool/vision_setup.py --install-runtime
    python tool/vision_setup.py --dry-run        # 只看结论，不写配置

只依赖标准库：安装器/冻结环境里也能直接 import 使用。
"""
import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

try:      # 控制台被重定向（管道/日志）时 Windows 会用 GBK 编码 stdout
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── 模型清单：文件名 → 字节数（判断「下过了/下完了」，也算总进度）──
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
# ⚠ 这一档是和 tool/vision_service.py 对齐后的值：长边 1280 在本机实测一屏要 37.6 秒，
#   896 只要 13.5 秒（后台每 150 秒会自己看一次屏）。曾经两边默认值不一致
#   （setup 写 1280 / 服务读 896），结果"跑一次 setup 反而把调好的默认值改慢了"。
DEFAULT_MAX_SIDE = 896
DEFAULT_IDLE_UNLOAD = 300
DEFAULT_MAX_NEW = 160
# 允许被 apply_config 改写的键（其余键一律不碰）
VISION_KEYS = ("vision_source", "vision_local_model_dir", "vision_local_port",
               "vision_runtime_python", "vision_max_side", "vision_idle_unload")
# pip 源：国内优先（装 torch 动辄几个 G，官方源容易慢到超时）
PIP_INDEXES = [
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
    "https://pypi.org/simple",
]
# 找解释器时的候选相对路径（按优先级）；不存在的直接跳过
RUNTIME_CANDIDATES = (
    os.path.join(".venv", "Scripts", "python.exe"),
    os.path.join("vision_runtime", "Scripts", "python.exe"),
    os.path.join("runtime", "venv", "Scripts", "python.exe"),
    os.path.join("runtime", "python", "python.exe"),
    os.path.join("python", "python.exe"),
)


def _log(log, msg):
    try:
        (log or print)(msg)
    except Exception:
        pass


def _app_dir() -> str:
    """程序根目录（本文件在 <根>/tool/ 下）"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cfg_path(app_dir: str = "") -> str:
    return os.path.join(app_dir or _app_dir(), "config.json")


def _load_cfg(app_dir: str = "") -> dict:
    """原样读 config.json；**不做示例回退**（写回时才能保证不凭空造键）"""
    try:
        with open(_cfg_path(app_dir), encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _seed_cfg(app_dir: str = "") -> dict:
    """写配置时的底稿：config.example.json 的默认值 ← 被 config.json 覆盖。

    ⚠ 为什么不能直接 dump _load_cfg()：tool/config.py 的 get_config() 在
      config.json **不存在**时回退到 config.example.json。如果这里凭空调一份
      只含 vision_* 几个键的 config.json 落盘，就等于把其它所有设置（API Key、
      立绘、屏幕间隔…）整体抹成"没有"，主人下次启动直接变成新装的空壳。
      所以缺 config.json 时先用示例补齐，再叠上用户已有的值。
    """
    app_dir = app_dir or _app_dir()
    base = {}
    try:
        with open(os.path.join(app_dir, "config.example.json"), encoding="utf-8") as f:
            base = json.load(f) or {}
        if not isinstance(base, dict):
            base = {}
    except Exception:
        base = {}
    raw = _load_cfg(app_dir)
    base.update(raw)
    return base


def _newline_of(path: str) -> str:
    """沿用原文件的换行风格（别把主人的 CRLF 配置改成 LF）"""
    try:
        with open(path, "rb") as f:
            head = f.read(65536)
        return "\r\n" if b"\r\n" in head else "\n"
    except Exception:
        return "\n"


def default_model_dir(app_dir: str = "") -> str:
    """默认放哪：<程序目录>/vision/Qwen2-VL-2B-Instruct（自包含，卸载一起删）"""
    return os.path.join(app_dir or _app_dir(), "vision", "Qwen2-VL-2B-Instruct")


# ── 模型体检 ────────────────────────────────────────────
def model_missing(model_dir: str) -> list:
    """列出「缺的或大小不对的」文件名（空列表 = 齐了）"""
    bad = []
    for name, size in MODEL_FILES.items():
        p = os.path.join(model_dir, name)
        try:
            if os.path.getsize(p) != size:
                bad.append(name)
        except OSError:
            bad.append(name)
    return bad


def model_complete(model_dir: str) -> bool:
    """模型是不是已经齐了（按文件大小逐个核对）"""
    if not os.path.isdir(model_dir):
        return False
    return not model_missing(model_dir)


def model_bytes(model_dir: str) -> int:
    """已经下到多少字节（只数清单里那几个文件，用来报告进度）"""
    got = 0
    for name, size in MODEL_FILES.items():
        try:
            got += min(size, os.path.getsize(os.path.join(model_dir, name)))
        except OSError:
            pass
    return got


# ── 下载 ────────────────────────────────────────────────
def _open_url(url: str, timeout: float = 30.0, headers: dict = None, direct: bool = True):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "AIpet-Murasame/vision-setup"})
    if direct:
        # 默认直连：国内下 ModelScope 走代理反而更慢（和 tool/net_env.py 同一个思路）
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    else:
        # 直连不通（比如只能通过代理上网）时再用系统代理
        op = urllib.request.build_opener()
    return op.open(req, timeout=timeout)


def _download_attempt(url: str, dst: str, size: int, on_bytes, stop=None,
                      direct: bool = True) -> bool:
    """真的下一次；.part 断点续传。返回是否成功（大小刚好对上才算成功）。"""
    part = dst + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    if have > size:                 # 本地比目标还大 → 文件坏了，重下
        os.remove(part)
        have = 0
    headers = {"User-Agent": "AIpet-Murasame/vision-setup"}
    if have:
        headers["Range"] = f"bytes={have}-"
    with _open_url(url, timeout=30.0, headers=headers, direct=direct) as r:
        code = getattr(r, "status", None) or r.getcode()
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
                if on_bytes:
                    on_bytes(got, size)
        if got != size:
            if got > size:
                # 比目标还大 → 远端给的不是我们要的文件。留着 .part 只会让下一次
                # 续传永远对不上大小，等于永久卡死，所以这里直接丢掉重来。
                try:
                    os.remove(part)
                except OSError:
                    pass
            return False            # 大小不对 → 留 .part 下次续传
    if os.path.exists(dst):
        os.remove(dst)
    os.rename(part, dst)
    return True


def _download_one(url: str, dst: str, size: int, on_bytes, stop=None) -> bool:
    """下单个文件；直连不行就换系统代理再试一次。"""
    try:
        return _download_attempt(url, dst, size, on_bytes, stop, direct=True)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
        _log(None, f"[视觉] 直连失败（{type(e).__name__}），改用系统代理重试")
        return _download_attempt(url, dst, size, on_bytes, stop, direct=False)


def download_model(model_dir: str, log=None, progress=None, stop=None,
                   hosts=None) -> bool:
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
        for host in (hosts or MODEL_HOSTS):
            url = f"{host}/{name}"
            try:
                ok = _download_one(
                    url, dst, size,
                    (lambda got, tot, _b=done_total, _n=name:
                     progress(_b + got, MODEL_TOTAL, _n)) if progress else None,
                    stop=stop)
                if ok:
                    break
            except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
                last_err = e
                _log(log, f"[视觉] {host} 下载失败：{type(e).__name__}: {e}")
        if not ok:
            _log(log, f"[视觉] {name} 没下完（下次运行会自动续传）：{last_err}")
            return False
        done_total += size
        if progress:
            progress(done_total, MODEL_TOTAL, name)
    if not model_complete(model_dir):
        _log(log, "[视觉] 下载完了但校验没过（可能有文件被截断）")
        return False
    _log(log, f"[视觉] 模型就绪：{model_dir}（{MODEL_TOTAL / 1e9:.2f} GB）")
    return True


# ── 运行时（解释器）────────────────────────────────────
def _env_root(py: str) -> str:
    """<env>/Scripts/python.exe → <env>；<env>/python.exe → <env>"""
    d = os.path.dirname(os.path.abspath(py))
    if os.path.basename(d).lower() in ("scripts", "bin"):
        return os.path.dirname(d)
    return d


def _has_torch(py: str) -> bool:
    """这个解释器里有没有 torch（看文件，不启动进程，快）"""
    try:
        roots = [_env_root(py)]
        if os.path.normcase(os.path.abspath(py)) == os.path.normcase(os.path.abspath(sys.executable)):
            roots.append(sys.prefix)
        for root in roots:
            for sub in (("Lib", "site-packages"), ("lib", "site-packages"),
                        ("lib", "python3", "site-packages")):
                if os.path.isdir(os.path.join(root, *sub, "torch")):
                    return True
        return False
    except Exception:
        return False


def torch_works(py: str, timeout: int = 180) -> tuple:
    """真跑一次 import torch（慢一点但准），返回 (能不能用, 说明)。

    ⚠ 只看文件是不够的：本机 .venv 里 torch 的文件都在，但 MSVC 运行库被停用后
      `import torch` 直接 c10.dll 初始化失败 —— 必须真跑一次才知道能不能用。
    """
    try:
        r = subprocess.run(
            [py, "-c", "import torch,sys;"
                       "c=torch.cuda.is_available();"
                       "print('cuda' if c else 'cpu', torch.cuda.get_device_name(0) if c else '')"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
        if r.returncode != 0:
            return False, ((r.stderr or r.stdout or "").strip()[-300:] or "退出码非 0")
        return True, (r.stdout or "").strip()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def find_runtime(app_dir: str = "", cfg: dict = None) -> str:
    """找一个「文件存在」的解释器：配置指定 → .venv → vision_runtime → runtime/*

    全部返回绝对路径：调用方（安装器/启动器）的工作目录不一定是程序目录。
    """
    app_dir = os.path.abspath(app_dir or _app_dir())
    cfg = cfg if cfg is not None else _load_cfg(app_dir)
    cands = []
    pref = str(cfg.get("vision_runtime_python") or "").strip()
    if pref:
        cands.append(pref if os.path.isabs(pref) else os.path.join(app_dir, pref))
    cands.extend(os.path.join(app_dir, rel) for rel in RUNTIME_CANDIDATES)
    seen = set()
    for p in cands:
        if not p:
            continue
        ap = os.path.abspath(p)
        if os.path.normcase(ap) in seen:
            continue
        seen.add(os.path.normcase(ap))
        if os.path.isfile(ap):
            return ap
    return ""


def find_torch_runtime(app_dir: str = "", cfg: dict = None, probe: bool = True) -> str:
    """找一个真能 import torch 的解释器（probe=False 时只按文件判断）"""
    py = find_runtime(app_dir, cfg)
    if not py:
        return ""
    if not _has_torch(py):
        return ""
    if probe:
        ok, _info = torch_works(py)
        if not ok:
            return ""
    return py


def find_gpu_runtime(app_dir: str = "", cfg: dict = None) -> str:
    """找一个「带显卡加速」的解释器（torch 可用且认得出 cuda）"""
    py = find_torch_runtime(app_dir, cfg, probe=True)
    if not py:
        return ""
    ok, info = torch_works(py)
    return py if (ok and str(info).startswith("cuda")) else ""


def ensure_runtime(app_dir: str = "", log=None, install_if_missing: bool = False) -> str:
    """保证有一个能跑视觉服务的 python；返回路径（空 = 没搞定）。

    默认**不**建环境/装包（几百 MB ~ 2GB，不能替主人决定）；只有显式
    install_if_missing=True 才动 pip。
    """
    app_dir = os.path.abspath(app_dir or _app_dir())
    py = find_gpu_runtime(app_dir)
    if py:
        _log(log, f"[视觉] 找到可用的显卡运行时：{py}")
        return py
    if not install_if_missing:
        py = find_torch_runtime(app_dir)
        _log(log, "[视觉] 没找到带显卡加速的运行时" +
                  (f"（只有 CPU 版：{py}）" if py else "（也没找到能用的 torch）"))
        return py

    base_py = ""
    for rel in RUNTIME_CANDIDATES:
        p = os.path.join(app_dir, rel)
        if os.path.isfile(p) and os.path.normcase(p) != os.path.normcase(sys.executable):
            base_py = p
            break
    if not base_py:
        base_py = sys.executable
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

    _log(log, "[视觉] 安装依赖（torch + transformers + pillow，几百 MB ~ 2GB，耐心等）…")
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
            _log(log, f"[视觉] {idx} 安装没成功：{(r.stderr or r.stdout or '')[-200:]}")
        except Exception as e:
            _log(log, f"[视觉] {idx} 安装异常：{type(e).__name__}: {e}")
    _log(log, "[视觉] 依赖没装上，本地视觉暂时用不了（识别会走云端 API）")
    return ""


# ── 写配置 ──────────────────────────────────────────────
def apply_config(app_dir: str, model_dir: str, port: int = DEFAULT_PORT,
                 use_local: bool = True, runtime_py: str = "", dry_run: bool = False) -> dict:
    """把 vision_* 写进 config.json（只改这几个键 + local_api.vision）。返回写后的内容。

    原子替换：先写 .tmp 再 os.replace，中途断电不会留下半个 config.json。
    """
    app_dir = os.path.abspath(app_dir or _app_dir())
    p = _cfg_path(app_dir)
    cfg = _seed_cfg(app_dir)
    cfg["vision_source"] = "local" if use_local else "cloud"
    cfg["vision_local_model_dir"] = model_dir
    cfg["vision_local_port"] = int(port)
    cfg.setdefault("vision_max_side", DEFAULT_MAX_SIDE)
    cfg.setdefault("vision_idle_unload", DEFAULT_IDLE_UNLOAD)
    la = cfg.get("local_api")
    if not isinstance(la, dict):
        la = {}
        cfg["local_api"] = la
    la["vision"] = f"http://127.0.0.1:{int(port)}/describe"
    if runtime_py:
        cfg["vision_runtime_python"] = runtime_py
    if dry_run:
        return cfg
    nl = _newline_of(p)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="") as f:
        text = json.dumps(cfg, ensure_ascii=False, indent=2)
        if nl != "\n":
            text = text.replace("\n", nl)
        f.write(text + nl)
    os.replace(tmp, p)
    return cfg


def service_url(cfg: dict = None, app_dir: str = "") -> str:
    """本机视觉服务的 /describe 地址（给 tool/screen_intent.py 用）"""
    c = cfg if isinstance(cfg, dict) else _load_cfg(app_dir)
    try:
        port = int(c.get("vision_local_port") or DEFAULT_PORT)
    except Exception:
        port = DEFAULT_PORT
    return f"http://127.0.0.1:{port}/describe"


# ── 结论 ────────────────────────────────────────────────
def readiness(app_dir: str = "", cfg: dict = None, probe: bool = False) -> dict:
    """一句话回答「本地视觉现在能不能用」。

    ⚠ probe=False 时**不猜** torch 能不能起来：本机 .venv 里 torch 文件齐全，但
      MSVC 运行库被停用后 import 就崩 —— 光看文件是会骗人的。所以此时 torch_ok /
      gpu 一律返回 None，意思是「还没实测」；要权威结论就 probe=True
      （代价是真启动一次解释器，可能要几秒到几十秒）。
    """
    app_dir = os.path.abspath(app_dir or _app_dir())
    cfg = cfg if cfg is not None else _load_cfg(app_dir)
    dest = str(cfg.get("vision_local_model_dir") or "").strip() or default_model_dir(app_dir)
    dest = os.path.abspath(dest)
    missing = model_missing(dest) if os.path.isdir(dest) else sorted(MODEL_FILES)
    rt = find_runtime(app_dir, cfg)
    if probe and rt:
        ok_torch, info = torch_works(rt)
        gpu = bool(ok_torch and str(info).startswith("cuda"))
    elif rt:
        ok_torch, info, gpu = None, "", None
    else:
        ok_torch, info, gpu = False, "", False
    return {
        "app_dir": app_dir,
        "model_dir": dest,
        "model_ready": not missing,
        "model_missing": missing,
        "model_bytes": model_bytes(dest),
        "model_total": MODEL_TOTAL,
        "runtime_py": rt,
        "probed": bool(probe and rt),
        "torch_ok": ok_torch,
        "torch_info": str(info or ""),
        "gpu": gpu,
        "usable": bool(not missing and rt and ok_torch),
        "source": str(cfg.get("vision_source") or "cloud"),
        "url": service_url(cfg),
    }


def _note(r: dict) -> str:
    if not r.get("model_ready"):
        return (f"模型没齐（缺 {len(r.get('model_missing') or [])} 个文件，已下 "
                f"{r.get('model_bytes', 0) / 1e9:.2f}/{r.get('model_total', 0) / 1e9:.2f} GB）"
                "→ 识别仍用云端 API；跑 `python tool/vision_setup.py --download` 可续传。")
    if not r.get("runtime_py"):
        return ("模型齐了，但没找到可用的解释器 → 识别仍用云端 API；"
                "可跑 `--install-runtime` 建一个（几百 MB ~ 2GB），或装带显卡版 torch 的整合包。")
    if r.get("torch_ok") is None:
        return (f"模型齐了，解释器是 {r['runtime_py']}，但还没实测它能不能 import torch"
                "（要不要用本地识别得先验一次）→ 暂时仍用云端 API。")
    if not r.get("torch_ok"):
        why = str(r.get("torch_info") or "原因未知")[:80]
        return f"找到解释器 {r['runtime_py']}，但 torch 用不起来（{why}）→ 识别仍用云端 API。"
    if not r.get("gpu"):
        info = str(r.get("torch_info") or "").strip()[:60]
        return (f"torch 可用但没有显卡加速（{info}）→ 本地识别会很慢，"
                "识别来源先留在云端；想强行用本地就把 config.json 的 vision_source 改成 local。")
    return "本地视觉已就绪（有显卡加速）。"


def setup(app_dir: str = "", log=None, progress=None, stop=None, model_dir: str = "",
          download: bool = False, install_runtime: bool = False,
          use_local_when_ready: bool = True, dry_run: bool = False) -> dict:
    """完整流程。返回 {"ok", "model_dir", "runtime_py", "gpu", "source", "note"}。

    ⚠ 默认 download=False / install_runtime=False：只体检 + 写配置，不替主人联网。
    """
    app_dir = os.path.abspath(app_dir or _app_dir())
    cfg = _load_cfg(app_dir)
    out = {"ok": False, "model_dir": "", "runtime_py": "", "gpu": False,
           "source": "cloud", "note": ""}

    dest = model_dir or str(cfg.get("vision_local_model_dir") or "").strip() or default_model_dir(app_dir)
    dest = os.path.abspath(dest)
    out["model_dir"] = dest
    if model_complete(dest):
        _log(log, f"[视觉] 模型已存在，跳过下载：{dest}")
    elif download:
        if not download_model(dest, log=log, progress=progress, stop=stop):
            out["note"] = _note(readiness(app_dir, cfg)) + " 模型这次没下完，重跑可续传。"
            _log(log, "[视觉] " + out["note"])
            return out
    else:
        _log(log, "[视觉] 没下模型（本次没加 --download）")

    # 先找出「候选解释器」，再**真跑一次**拿权威结论（含失败原因）：
    # 只按文件判断过不了本机这种「torch 文件都在、一 import 就崩」的情况，
    # 而"没找到解释器"和"解释器在但 torch 起不来"是两件要分别说清的事。
    if install_runtime:
        rt = ensure_runtime(app_dir, log=log, install_if_missing=True)
        cand = rt
    else:
        cand = find_runtime(app_dir, cfg)
        rt = ""
    ok_torch, info = (torch_works(cand) if cand else (False, ""))
    if ok_torch and not rt:
        rt = cand
    out["runtime_py"] = rt
    out["gpu"] = bool(ok_torch and str(info).startswith("cuda"))

    # 只有真能跑（有显卡加速）才把识别切到本地，否则留在云端并说清原因
    use_local = bool(use_local_when_ready and dest and model_complete(dest) and ok_torch and out["gpu"])
    apply_config(app_dir, dest, DEFAULT_PORT, use_local=use_local, runtime_py=rt, dry_run=dry_run)
    out["source"] = "local" if use_local else "cloud"
    out["ok"] = bool(use_local)
    # 把刚才**实测**到的结果交给 _note，别再用「没探测」的 readiness 复推一遍：
    # 踩过 —— probe=False 会把「torch 文件都在、一 import 就崩」报成「没有显卡加速」，
    # 主人看到的原因就是错的。
    r = readiness(app_dir, _load_cfg(app_dir), probe=False)
    r["model_ready"] = model_complete(dest)
    r["model_missing"] = [] if r["model_ready"] else model_missing(dest)
    r["runtime_py"] = cand          # 给说明用：这是「找到的那个解释器」，哪怕它起不来
    r["torch_ok"] = bool(ok_torch)
    r["torch_info"] = str(info or "")
    r["gpu"] = out["gpu"]
    r["probed"] = bool(cand)
    out["note"] = _note(r)
    _log(log, f"[视觉] 验证：运行时 {'可用' if ok_torch else '不可用'}（{info or '没有 torch'}）")
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

    def _prog(done, total, name):
        pct = done * 100.0 / max(1, total)
        sys.stdout.write(f"\r[视觉] 下载进度 {pct:5.1f}%  "
                         f"({done / 1e9:.2f}/{total / 1e9:.2f} GB)  {name}    ")
        sys.stdout.flush()

    r = setup(app_dir=app_dir,
              model_dir=_arg("--model-dir", ""),
              download="--download" in argv,
              install_runtime="--install-runtime" in argv,
              dry_run="--dry-run" in argv,
              log=lambda m: print(m, flush=True),
              progress=_prog)
    print()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
