# -*- coding: utf-8 -*-
"""语音服务（GPT-SoVITS）的启动与预载 —— 启动器「预载语音服务」按钮用的入口。

为什么单独一个文件：启动器是个冻结的 exe，只能拉起"脚本"，
而启动逻辑（选环境/设环境变量/开服务）都在 run.py 里。这里薄薄包一层：
  · 复用 run.py 的 pick_tts_env / prepare_tts_env / start_tts_api（同一套逻辑，不重复实现）
  · 提供 is_ready() 给界面查状态
  · preload() = 没起来就起来 + 真合成一句预热（第一次合成要编译内核，会慢十几秒）

命令行：python tool/tts_service.py preload
退出码 0 = 已就绪并预热完成；非 0 = 失败（界面据此显示"预载失败"）
"""
import importlib.util
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

GSV_URL = "http://127.0.0.1:9880"


def _load_run():
    """把 run.py 当模块加载（它有 __main__ 守卫，导入不会启动桌宠）"""
    spec = importlib.util.spec_from_file_location("aipet_run", os.path.join(BASE, "run.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def is_ready(timeout: float = 3.0) -> bool:
    """语音服务是否在监听（已加载好模型）"""
    try:
        import urllib.request
        with urllib.request.urlopen(GSV_URL + "/docs", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _say(text: str, times: int = 1) -> bool:
    """发一次真合成请求（预热用）：走的是桌宠平时用的同一套参数"""
    try:
        import requests
    except Exception:
        return False
    ref = os.path.join(BASE, "reference_voices", "long_chinese", "953244.wav")
    ref_text = "能和老师在一起，我真的，好高兴！"
    params = {
        "refer_wav_path": ref, "prompt_text": ref_text, "prompt_language": "zh",
        "text": text, "text_language": "zh",
        "top_k": 15, "top_p": 1, "temperature": 1, "speed": 1.0,
        "sample_steps": 16, "if_sr": "false",
    }
    ok = False
    for _ in range(max(1, times)):
        try:
            r = requests.get(GSV_URL + "/", params=params, timeout=(10, 600))
            ok = r.status_code == 200 and r.content[:4] == b"RIFF"
        except Exception:
            ok = False
    return ok


def _desired_model() -> dict:
    """现在**应该**加载哪套模型（按 config.json 的 gsv_model_version + 当前角色权重算）

    与 run.py 启动服务时的选择逻辑保持一致（它才是真正加载模型的地方）。
    """
    try:
        import json
        run = _load_run()
        cfg = {}
        try:
            with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
                cfg = json.load(f) or {}
        except Exception:
            cfg = {}
        mv = str(cfg.get("gsv_model_version", "auto")).strip().lower() or "v2"
        g, s, ver, pid = run.pet_voice_weights()
        if mv in ("finetuned", "auto") and g and s:
            return {"model_version": mv, "pet": pid, "gpt": os.path.basename(g),
                    "sovits": os.path.basename(s)}
        return {"model_version": mv if mv in ("v2", "v4") else "v2", "pet": "", "gpt": "", "sovits": ""}
    except Exception as e:
        print(f"[预载] ⚠ 计算目标模型失败: {e}", flush=True)
        return {}


def _loaded_model() -> dict:
    try:
        import json
        with open(os.path.join(BASE, "data", "tts_model.json"), encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _stop_running_service(marker: dict) -> None:
    """停掉正在跑的语音服务（换模型时必须重启，否则设了也不生效）"""
    pid = 0
    try:
        pid = int(marker.get("pid") or 0)
    except Exception:
        pid = 0
    killed = False
    if pid > 0:
        try:
            import subprocess as _sp
            _sp.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                    creationflags=(_sp.CREATE_NO_WINDOW if os.name == "nt" else 0))
            killed = True
            print(f"[预载] 已停掉旧模型的语音服务（PID {pid}）", flush=True)
        except Exception as e:
            print(f"[预载] ⚠ 停止旧服务失败: {e}", flush=True)
    if not killed:
        # 拿不到 PID 时兜底：按命令行找（只杀 GPT-SoVITS 的 api 进程）
        try:
            import subprocess as _sp
            _sp.run(["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                     "Where-Object { $_.CommandLine -match 'GPT-SoVITS\\\\api' } | "
                     "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                    creationflags=(_sp.CREATE_NO_WINDOW if os.name == "nt" else 0))
            print("[预载] 已按进程名停掉旧的语音服务", flush=True)
        except Exception as e:
            print(f"[预载] ⚠ 兜底停止失败: {e}", flush=True)
    time.sleep(2.0)


def preload(wait_ready: int = 600) -> int:
    """启动（如果需要）+ 预热。返回 0 表示可用。

    ★ 2026-10-01：模型不一致时**必须重启服务** —— 以前 `is_ready()` 一为真就直接预热，
      于是"在设置里换了语音模型（或刚训练好专属模型）"完全没效果：服务里还是旧模型。
      现在先比对 data/tts_model.json（上次实际加载的）与当前应该加载的，不一致就重启。
    """
    want, have = _desired_model(), _loaded_model()
    _diff = bool(want) and bool(have) and any(
        str(want.get(k) or "") != str(have.get(k) or "") for k in ("model_version", "gpt", "sovits"))
    if is_ready() and _diff:
        print("[预载] 语音模型有变化：%s/%s → %s/%s，重启语音服务…"
              % (have.get("gpt") or have.get("model_version") or "?",
                 have.get("sovits") or "", want.get("gpt") or want.get("model_version") or "?",
                 want.get("sovits") or ""), flush=True)
        _stop_running_service(have)
    if is_ready():
        print("[预载] 语音服务已在运行（模型一致），直接预热…", flush=True)
    else:
        print("[预载] 正在启动语音服务（首次加载模型约 1~2 分钟）…", flush=True)
        try:
            run = _load_run()
            proc = run.start_tts_api()
            if proc is None and not is_ready():
                print("[预载] 启动失败：没找到 GPT-SoVITS 或运行环境", flush=True)
                return 2
        except Exception as e:
            print("[预载] 启动异常：%s" % e, flush=True)
            return 2

        print("[预载] 等待模型加载…", flush=True)
        t0 = time.time()
        while time.time() - t0 < wait_ready:
            if is_ready():
                break
            time.sleep(5)
        else:
            print("[预载] 等待超时（模型没在 %d 秒内就绪）" % wait_ready, flush=True)
            return 3

    print("[预载] 正在预热（第一次要编译内核，通常十几秒）…", flush=True)
    t0 = time.time()
    if not _say("你好。", times=1):
        print("[预载] 预热请求失败", flush=True)
        return 4
    _say("好，我准备好了。", times=1)          # 第二次才是全速
    print("[预载] 完成（用时 %.1fs），现在说话不用等冷启动" % (time.time() - t0), flush=True)
    return 0


if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "preload").strip().lower()
    if cmd in ("preload", "warm", "start"):
        raise SystemExit(preload())
    if cmd == "status":
        print("ready" if is_ready() else "not-ready")
        raise SystemExit(0 if is_ready() else 1)
    print("用法: python tool/tts_service.py [preload|status]")
    raise SystemExit(1)
