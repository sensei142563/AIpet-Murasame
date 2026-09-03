# -*- coding: utf-8 -*-
"""QQ AIpet 独立启动入口 — 不依赖桌宠（PyQt5）即可运行。"""
import os
import sys
import time
import socket
import signal
import subprocess

# 控制台 UTF-8（GBK 控制台下打印 emoji 会崩线程）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

F5TTS_PORT = 9881
F5TTS_PID_FILE = os.path.join(BASE_DIR, "data", "qq_f5tts.pid")


def check_port_open(port, host="127.0.0.1", timeout=1):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def _cleanup_f5tts():
    try:
        if os.path.exists(F5TTS_PID_FILE):
            with open(F5TTS_PID_FILE, "r", encoding="utf-8") as f:
                pid = f.read().strip()
            if pid.isdigit():
                subprocess.run(["taskkill", "/F", "/T", "/PID", pid],
                               capture_output=True, timeout=10)
                print(f"[QQ] ✅ 已关闭 run_qq 拉起的 F5-TTS（PID={pid}）")
            os.remove(F5TTS_PID_FILE)
    except Exception as e:
        print(f"[QQ] ⚠ 关闭 F5-TTS 失败: {e}")


def ensure_f5tts(cfg):
    if not cfg.get("send_voice", False):
        return
    if cfg.get("f5tts_ready", False):
        print(f"[QQ] 🎙 F5-TTS 服务已就绪（端口 {F5TTS_PORT}）")
        return
    print(f"[QQ] 语音消息已开启，F5-TTS 服务未运行（端口 {F5TTS_PORT}）")
    print(f"[QQ] 正在自动启动 F5-TTS 服务（新控制台，模型加载约 10-45 秒）...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "longtext.f5tts_server"],
            cwd=BASE_DIR,
            creationflags=(0x00000010 if os.name == "nt" else 0)
        )
        try:
            os.makedirs(os.path.dirname(F5TTS_PID_FILE), exist_ok=True)
            with open(F5TTS_PID_FILE, "w", encoding="utf-8") as f:
                f.write(str(proc.pid))
        except Exception:
            pass
    except Exception as e:
        print(f"[QQ] ⚠ F5-TTS 服务启动失败: {e}")
        return
    for i in range(60):
        time.sleep(1)
        if check_port_open(F5TTS_PORT):
            print(f"[QQ] ✅ F5-TTS 服务已就绪（{i + 1} 秒）")
            return
    print(f"[QQ] ⚠ 等待 F5-TTS 超时（60 秒）")


def main():
    print("=" * 50)
    # 当前角色显示名（从 pets 注册中心读取）
    pet_name = "丛雨"
    try:
        from pets.pet_registry import get_pet_config
        _pc = get_pet_config()
        pet_name = _pc.get("display_name") or _pc.get("name") or "丛雨"
    except Exception:
        pass
    print(f"  QQ AIpet — {pet_name} QQ 聊天模块")
    print("=" * 50)

    try:
        import websocket  # noqa: F401
    except ImportError:
        print("[✗] 缺少依赖 websocket-client")
        return

    from qq.qq_config import get_qq_config
    cfg = get_qq_config()
    print(f"[配置] NapCat WS  : {cfg['ws_url']}")
    print(f"[配置] 表情包      : {'开' if cfg['send_sticker'] else '关'}")
    print(f"[配置] 语音消息    : {'开' if cfg['send_voice'] else '关'}")
    print(f"[配置] 群聊(需@)   : {'开' if cfg['allow_groups'] else '关'}")
    print()

    ensure_f5tts(cfg)

    from qq.qq_bridge import QQBotBridge
    bridge = QQBotBridge()

    def _on_signal(sig, frame):
        print("\n[QQ] 正在关闭...")
        try:
            # 正常退出时写准基线（否则离线补拉窗口=上次启动时间，
            # 会把上次在线期间已实时回复的消息重复补拉回复 → 主人被重复回复）
            from qq.qq_offline import save_last_exit_time
            save_last_exit_time()
        except Exception:
            pass
        bridge.stop()
        _cleanup_f5tts()
        sys.exit(0)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    # NapCat WS 就绪检测（带清晰提示，避免"目标计算机积极拒绝"）
    # 首次使用必须先进 NapCat 扫码登录一次，否则 WS 3001 不会真正监听。
    # host 从 ws_url 解析（支持局域网 NapCat），不写死 127.0.0.1
    try:
        import urllib.parse as _up
        _u = _up.urlparse(cfg['ws_url'])
        ws_host = _u.hostname or "127.0.0.1"
        ws_port = _u.port or 3001
    except Exception:
        ws_host, ws_port = "127.0.0.1", 3001
    if not check_port_open(ws_port, host=ws_host):
        print(f"[QQ] ⏳ 检测到 NapCat 尚未就绪（{ws_host}:{ws_port} 未监听），等待中...")
        print("[QQ]   首次使用请先运行:  NapCat.Shell.Windows.OneKey\\start_napcat.bat 并扫码登录。")
        print("[QQ]   若已启动但此处仍等不到，请确认已登录、且 NapCat 的 onebot 正向 WS 端口 = 3001。")
        print("[QQ]   （本程序会自动重试；NapCat 就绪后无需重启本窗口）")
        # 交给 bridge 的重连循环去等，这里不额外阻塞
    print(f"[QQ] 第 1 次尝试连接（NapCat 未就绪也会自动重试）...")
    bridge.connect()  # 内部已包含连接前等待 + 断开自动重连


if __name__ == "__main__":
    main()