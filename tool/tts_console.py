# -*- coding: utf-8 -*-
"""语音服务的"控制台外壳" —— 让那个窗口好看、安静、有名字，而且**看得懂**。

为什么不直接改 api.py：GPT-SoVITS 是第三方整合包，**不动它的原文件**（改坏了不好还原）。
所以在外面包一层。

用法（由 run.py 调用，一般不用手敲）：
    <GPT-SoVITS 的 python> tool/tts_console.py <配置.json> -- <真正的脚本> [参数...]

配置 json（由 run.py 写，UTF-8，避免中文经命令行传参被 mangle）：
    {"title": "窗口标题", "lines": ["横幅第 1 行", ...],
     "log": "data/tts_service.log", "say_log": "data/tts_say.log"}

控制台上会看到什么（只挑关键行，其余全部进日志）：
    ====================================================
      AIpet 语音服务 · 丛雨
      GPT-SoVITS · 服务端口 9880 · …
    ====================================================
    · 收到一次合成请求
    ✅ 模型已彻底起来（可以说话了）
    [00:12:01] 说：「今天有点累呢，主人」
    ⚠ …（只有出错时才出现）
"""
import ctypes
import io
import json
import os
import subprocess
import sys
import threading
import time

IS_WIN = os.name == "nt"


def _set_title(title: str) -> None:
    if not IS_WIN:
        sys.stdout.write("\033]0;%s\007" % title)
        sys.stdout.flush()
        return
    try:
        ctypes.windll.kernel32.SetConsoleTitleW(str(title))
    except Exception:
        pass


def _width(s: str) -> int:
    return sum(2 if ord(c) > 0x2E80 else 1 for c in s)


def _banner(lines) -> None:
    inner = 74
    print("=" * inner)
    for l in lines:
        pad = max(0, inner - 2 - _width(l))
        print("  " + l + " " * pad)
    print("=" * inner)
    print()
    sys.stdout.flush()


def _say(text: str) -> None:
    """把"她要说的话"打到控制台（带时间）。"""
    print("[%s] 说：「%s」" % (time.strftime("%H:%M:%S"), text))
    sys.stdout.flush()


def _curated(line: str, state: dict) -> None:
    """从服务本体的一行输出里挑出值得显示在控制台上的，其余只进日志。"""
    low = line.lower()
    if ("uvicorn running on" in low or "application startup complete" in low) \
            and not state.get("ready"):
        state["ready"] = True
        print()
        print("✅ 模型已彻底起来 —— 现在可以说话了（端口 %s）"
              % state.get("port", "9880"))
        sys.stdout.flush()
        return
    if "/tts" in low and ('"' in line) and (" 200" in line or " 4" in line or " 5" in line):
        print("· 收到一次合成请求")
        sys.stdout.flush()
        return
    if any(k in line for k in ("Traceback", "Error", "ERROR", "错误", "失败",
                               "CUDA out of memory", "Exception")):
        print("⚠ " + line.strip()[:160])
        sys.stdout.flush()


def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print("用法: tts_console.py <配置.json> -- <脚本> [参数...]")
        return 2
    cut = argv.index("--")
    cfg_path = argv[0] if cut else ""
    rest = argv[cut + 1:]
    if not rest:
        print("✗ 没有给出要启动的脚本")
        return 2

    cfg = {}
    try:
        with io.open(cfg_path, encoding="utf-8", errors="replace") as f:
            cfg = json.load(f) or {}
    except Exception as e:
        print("⚠ 读配置失败（不影响启动）：%s" % e)

    _set_title(cfg.get("title") or "AIpet 语音服务")
    _banner(cfg.get("lines") or ["AIpet 语音服务"])

    log_path = os.path.abspath(cfg.get("log") or os.path.join("data", "tts_service.log"))
    say_path = os.path.abspath(cfg.get("say_log") or os.path.join("data", "tts_say.log"))
    for p in (log_path, say_path):
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
        except Exception:
            pass

    try:
        logf = io.open(log_path, "a", encoding="utf-8", errors="replace", buffering=1)
    except Exception:
        logf = None

    print("  日志：%s" % log_path)
    print("  本窗口保持打开即为正常运行；关掉本窗口＝停止语音服务。")
    print()
    sys.stdout.flush()
    if logf:
        logf.write("\n" + "=" * 78 + "\n[%s] 语音服务启动：%s\n"
                   % (time.strftime("%Y-%m-%d %H:%M:%S"), " ".join(rest)))
        logf.flush()

    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUNBUFFERED", "1")

    # ★ 起服务本体。rest[0] 通常是 "api.py"（脚本不是 exe），必须用当前解释器跑它 ——
    #   直接 Popen(["api.py", ...]) 会 OSError: [WinError 193]（2026-10-13 实测踩到）。
    cmd = rest
    if rest and str(rest[0]).lower().endswith(".py"):
        cmd = [sys.executable] + list(rest)

    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    state = {"ready": False, "port": cfg.get("port") or "9880"}
    stop = threading.Event()

    def _pump():
        """服务本体的输出：**全部**写进日志；控制台只显示关键行。"""
        try:
            for raw in iter(proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if logf:
                    try:
                        logf.write(line + "\n")
                        logf.flush()
                    except Exception:
                        pass
                _curated(line, state)
        except Exception:
            pass

    def _tail_say():
        """跟 data/tts_say.log：桌宠每要合成一句话就往里追加一行（时间\\t文本）。
           这是唯一能把"她要说的话"送进这个窗口的办法 ——
           因为服务只看得见 HTTP 请求，看不到 POST 正文里的文字。"""
        pos = 0
        try:
            pos = os.path.getsize(say_path) if os.path.exists(say_path) else 0
        except Exception:
            pos = 0
        while not stop.is_set():
            try:
                size = os.path.getsize(say_path) if os.path.exists(say_path) else 0
                if size < pos:          # 文件被清空/轮转过
                    pos = 0
                if size > pos:
                    with io.open(say_path, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(pos)
                        for l in f:
                            l = l.rstrip("\n")
                            if not l.strip():
                                continue
                            txt = l.split("\t", 1)[-1] if "\t" in l else l
                            _say(txt[:200])
                        pos = f.tell()
            except Exception:
                pass
            stop.wait(0.4)

    th_out = threading.Thread(target=_pump, daemon=True)
    th_say = threading.Thread(target=_tail_say, daemon=True)
    th_out.start()
    th_say.start()

    try:
        rc = proc.wait()
        return rc
    except KeyboardInterrupt:
        print("\n  收到 Ctrl-C，正在停止语音服务…")
        return 0
    finally:
        stop.set()
        # ★ 不留孤儿：外壳结束时把服务本体一起收掉
        try:
            if proc.poll() is None:
                if IS_WIN:
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    proc.kill()
        except Exception:
            pass
        if logf:
            try:
                logf.write("[%s] 语音服务已退出。\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
                logf.close()
            except Exception:
                pass


if __name__ == "__main__":
    # ★ 外壳**自己**出错时也要留下证据（写日志 + 打到窗口）
    _log_for_err = os.path.abspath(os.path.join("data", "tts_service.log"))
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:
        import traceback
        tb = traceback.format_exc()
        try:
            os.makedirs(os.path.dirname(_log_for_err), exist_ok=True)
            with io.open(_log_for_err, "a", encoding="utf-8", errors="replace") as f:
                f.write("\n[外壳异常]\n" + tb + "\n")
        except Exception:
            pass
        sys.stderr.write("\n[外壳异常] 起语音服务失败，详见日志：%s\n%s\n" % (_log_for_err, tb))
        sys.exit(1)
