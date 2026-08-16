# -*- coding: utf-8 -*-
"""
微信 ClawBot 桌宠入口：首次扫码登录（凭据持久化，重启免扫码）→ 长轮询桥。

用法：python run_wechat.py（或双击 启动微信.bat）
前置：config.json 里 wechat_enabled="true"；微信更新到支持 ClawBot 的版本，
     并在「我-设置-插件」里开启 ClawBot。
"""
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

from tool.config import get_config
from tool.paths import data_path

F5TTS_PORT = 9881
F5TTS_PID_FILE = data_path("data", "wechat_f5tts.pid")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


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
                print(f"[WeChatBot] ✅ 已关闭 run_wechat 拉起的 F5-TTS（PID={pid}）")
            os.remove(F5TTS_PID_FILE)
    except Exception as e:
        print(f"[WeChatBot] ⚠ 关闭 F5-TTS 失败: {e}")


def ensure_f5tts(send_voice):
    """语音回复开启时自动拉起 F5-TTS（与 QQ 入口一致）"""
    if not send_voice:
        return
    if check_port_open(F5TTS_PORT):
        print(f"[WeChatBot] 🎙 F5-TTS 服务已就绪（端口 {F5TTS_PORT}）")
        return
    print(f"[WeChatBot] 语音回复已开启，F5-TTS 服务未运行（端口 {F5TTS_PORT}）")
    print("[WeChatBot] 正在自动启动 F5-TTS 服务（新控制台，模型加载约 10-45 秒）...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "longtext.f5tts_server"],
            cwd=BASE_DIR,
            creationflags=(0x00000010 if os.name == "nt" else 0)
        )
        os.makedirs(os.path.dirname(F5TTS_PID_FILE), exist_ok=True)
        with open(F5TTS_PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(proc.pid))
    except Exception as e:
        print(f"[WeChatBot] ⚠ F5-TTS 服务启动失败: {e}")
        return
    for i in range(60):
        time.sleep(1)
        if check_port_open(F5TTS_PORT):
            print(f"[WeChatBot] ✅ F5-TTS 服务已就绪（{i + 1} 秒）")
            return
    print("[WeChatBot] ⚠ 等待 F5-TTS 超时（60 秒）")


def _show_qr(qr_url):
    """本地生成二维码图片并打开（服务端返回的是 URL 不是图片）"""
    try:
        import qrcode
        png = data_path("data", "wechat_qrcode.png")
        os.makedirs(os.path.dirname(png), exist_ok=True)
        qrcode.make(qr_url).save(png)
        print(f"[WeChatBot] 二维码图片: {png}（也可复制链接打开）")
        try:
            os.startfile(png)
        except Exception:
            pass
    except Exception as e:
        print(f"[WeChatBot] ⚠ 生成二维码图片失败: {e}")


def _login_flow():
    """扫码登录流程（官方 login-qr.js 的 Python 移植）"""
    from wechat.ilink_client import (
        fetch_qrcode, poll_qrcode_status, save_credentials, load_credentials,
        FIXED_BASE_URL,
    )

    print("[WeChatBot] 获取登录二维码...")
    qr = fetch_qrcode()
    qrcode_id = qr.get("qrcode") or ""
    qr_url = qr.get("qrcode_img_content") or ""
    if not qrcode_id or not qr_url:
        print(f"[WeChatBot] ⚠ 获取二维码失败: {qr}")
        return None
    print(f"[WeChatBot] 二维码链接: {qr_url}")
    _show_qr(qr_url)

    base_url = FIXED_BASE_URL
    pending_code = ""
    refresh = 0
    print("[WeChatBot] 等待扫码确认（二维码约 5 分钟有效）...")
    while True:
        try:
            st = poll_qrcode_status(qrcode_id, base_url, verify_code=pending_code)
        except Exception as e:
            print(f"[WeChatBot] ⚠ 状态轮询异常: {e}")
            time.sleep(3)
            continue
        status = st.get("status")
        if status == "confirmed":
            token = st.get("bot_token") or ""
            bot_id = st.get("ilink_bot_id") or ""
            user_id = st.get("ilink_user_id") or ""
            baseurl = st.get("baseurl") or base_url
            if not token:
                print("[WeChatBot] ⚠ 登录确认但缺少 bot_token")
                return None
            save_credentials({
                "token": token,
                "bot_id": bot_id,
                "user_id": user_id,
                "baseurl": baseurl,
            })
            print(f"[WeChatBot] ✅ 登录成功（bot_id={bot_id}），凭据已保存，重启免扫码")
            return load_credentials()
        elif status == "scaned":
            if pending_code:
                print("[WeChatBot] ✅ 验证码正确，继续等待确认...")
                pending_code = ""
            else:
                print("[WeChatBot] 📱 已扫码，等待确认...")
        elif status == "scaned_but_redirect":
            if st.get("redirect_host"):
                base_url = "https://" + st["redirect_host"]
                print(f"[WeChatBot] ↪ 切换服务器: {base_url}")
        elif status == "need_verifycode":
            pending_code = input("[WeChatBot] 请输入手机微信上显示的数字：").strip()
        elif status == "expired":
            refresh += 1
            if refresh > 3:
                print("[WeChatBot] 二维码多次过期，放弃。请稍后重试。")
                return None
            print("[WeChatBot] 二维码过期，刷新中...")
            qr = fetch_qrcode()
            qrcode_id = qr.get("qrcode") or ""
            qr_url = qr.get("qrcode_img_content") or ""
            if not qrcode_id:
                print("[WeChatBot] ⚠ 刷新二维码失败")
                return None
            print(f"[WeChatBot] 新二维码链接: {qr_url}")
            _show_qr(qr_url)
        elif status == "binded_redirect":
            print("[WeChatBot] ⚠ 该微信已绑定过其他机器人，无法重复连接。")
            return None
        elif status == "verify_code_blocked":
            print("[WeChatBot] ⛔ 验证码错误次数过多，请稍后再试。")
            return None
        time.sleep(2)


def main():
    cfg = get_config("./config.json")
    if str(cfg.get("wechat_enabled", "false")).lower() != "true":
        print("[WeChatBot] wechat_enabled=false，微信桌宠未启用。可在 config.json 中开启。")
        return

    from wechat.ilink_client import load_credentials
    creds = load_credentials()
    if not creds:
        print("[WeChatBot] 首次使用：需要扫码登录（凭据会保存在本地 data/，不会上传）")
        creds = _login_flow()
        if not creds:
            print("[WeChatBot] 登录未完成，退出。")
            return

    from wechat.wechat_bridge import WeChatBridge
    send_voice = str(cfg.get("wechat_send_voice", "false")).lower() == "true"
    ensure_f5tts(send_voice)

    bridge = WeChatBridge(
        owner_id=str(cfg.get("wechat_owner_id", "") or "").strip(),
        bot_agent=str(cfg.get("wechat_bot_agent", "") or "AIpet/1.12").strip(),
        send_voice=send_voice,
    )
    print("[WeChatBot] 提示：对方发来第一条消息后，日志会显示 from_user_id（xxx@im.wechat），"
          "可把它填进 config.json 的 wechat_owner_id 开启白名单。")

    def _on_signal(sig, frame):
        print("\n[WeChatBot] 正在关闭...")
        bridge.stop()
        _cleanup_f5tts()
        sys.exit(0)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        bridge.start()
    except KeyboardInterrupt:
        bridge.stop()
        _cleanup_f5tts()
        print("[WeChatBot] 已退出")


if __name__ == "__main__":
    main()
