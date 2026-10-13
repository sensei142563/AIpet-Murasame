# -*- coding: utf-8 -*-
"""语音服务的"控制台外壳" —— 让那个窗口好看、安静、有名字。

为什么不直接改 api.py：GPT-SoVITS 是第三方整合包，**不动它的原文件**（改坏了不好还原）。
所以在外面包一层：自己设标题、自己打横幅，把 api.py 的输出**全部导进日志文件**。

用法（由 run.py 调用，一般不用手敲）：
    <GPT-SoVITS 的 python> tool/tts_console.py <配置.json> -- <真正的脚本> [参数...]

配置 json（由 run.py 写，UTF-8，避免中文经命令行传参被 mangle）：
    {"title": "窗口标题", "lines": ["横幅第 1 行", ...], "log": "data/tts_service.log"}

行为：
  1. 设控制台标题；
  2. 打印横幅（含"日志在哪"）；
  3. 起真正的服务，stdout/stderr 追加写进日志文件（UTF-8，行缓冲）；
  4. 前台等待；收到 Ctrl-C 或被杀时，**把孩子一起带走**（不留孤儿）。
"""
import ctypes
import io
import json
import os
import subprocess
import sys
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


def _banner(lines) -> None:
    """整齐的横幅：上下两条等长横线，中间是内容（按显示宽度补空格）。"""
    def width(s: str) -> int:
        # 中日韩字符按 2 格算
        return sum(2 if ord(c) > 0x2E80 else 1 for c in s)

    inner = 74
    print("=" * inner)
    for l in lines:
        pad = max(0, inner - 2 - width(l))
        print("  " + l + " " * pad)
    print("=" * inner)
    print()
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

    log_path = cfg.get("log") or os.path.join("data", "tts_service.log")
    log_path = os.path.abspath(log_path)
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
    except Exception:
        pass

    # ★ 关键：把服务的输出全部写进日志 —— 窗口里就只剩上面那几行，不再刷屏
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

    # ★ 起服务本体。注意：rest[0] 通常是 "api.py"（一个脚本，不是 exe），
    #   必须用**当前解释器**去跑它 —— 直接用 Popen(["api.py", ...]) 会得到
    #   OSError: [WinError 193] %1 不是有效的 Win32 应用程序（2026-10-13 实测踩到）。
    cmd = rest
    if rest and str(rest[0]).lower().endswith(".py"):
        cmd = [sys.executable] + list(rest)
    proc = subprocess.Popen(cmd, env=env, stdout=logf or subprocess.DEVNULL,
                            stderr=subprocess.STDOUT if logf else subprocess.DEVNULL)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        print("\n  收到 Ctrl-C，正在停止语音服务…")
        return 0
    finally:
        # ★ 不留孤儿：外壳结束时，把服务本体一起收掉
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
    # ★ 外壳**自己**出错时也要留下证据：写进日志 + 打到窗口。
    #   （2026-10-13 教训：一开始外壳的 stderr 只进控制台，
    #     结果子进程起不来时日志里一片空白，只能满世界找原因。）
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
