# -*- coding: utf-8 -*-
"""
QQ 特殊指令处理 — 当前支持 /clear（清空会话记忆，仅大号可用）。

后续可扩展：
- /status：查看当前模型/服务状态
- /memory：查看记忆条数
"""

import os
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pet_display_name() -> str:
    """当前角色显示名（用于指令回复，替代硬编码「丛雨」）"""
    try:
        from pets.pet_registry import get_pet_config
        cfg = get_pet_config()
        return cfg.get("display_name") or cfg.get("name") or "丛雨"
    except Exception:
        return "丛雨"


def clear_session_memory(session_key: str, user_id=None):
    """
    清空某个会话的记忆。

    - 大号私聊（session_key=private_<大号>）：清空 long_history.json（保留 history.json 短文本记忆）
    - 其他私聊/群聊：清空对应分仓文件（data/qq_memory/xxx.json）
    """
    try:
        from qq.qq_memory import resolve_memory_path
        path = resolve_memory_path(session_key)

        now = time.strftime("%Y-%m-%d %H:%M:%S")

        # 大号 → 共享记忆（仅清空 long_history.json，保留 history.json 短文本记忆）
        if path is None:
            long_path = os.path.join(BASE_DIR, "data", "long_history.json")
            if os.path.exists(long_path):
                with open(long_path, "w", encoding="utf-8") as f:
                    json.dump({"history": [], "updated_at": now}, f, ensure_ascii=False, indent=2)
            print(f"[QQCmd] ✅ 已清空共享记忆（long_history.json，保留 history.json）")
            return True

        # 分仓 → 清空对应文件
        if os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"history": [], "updated_at": now}, f, ensure_ascii=False, indent=2)
            print(f"[QQCmd] ✅ 已清空分仓记忆: {os.path.basename(path)}")
            return True

        print(f"[QQCmd] 分仓文件不存在，无需清空: {path}")
        return True
    except Exception as e:
        print(f"[QQCmd] ⚠ 清空记忆失败: {e}")
        return False


def _get_memory_count(session_key: str) -> int:
    """获取某会话记忆条数"""
    try:
        from qq.qq_memory import load_memory
        history = load_memory(session_key, max_turns=1000)
        return len(history) // 2
    except Exception:
        return 0


def handle_qq_command(text: str, session_key: str, user_id) -> str:
    """
    处理 QQ 特殊指令。
    返回: 回复文本；若非指令返回 None（走正常对话流程）。
    """
    if not text or not text.startswith("/"):
        return None

    parts = text.strip().split()
    cmd = parts[0].lower()
    from qq.qq_memory import is_owner

    is_private_owner = session_key.startswith("private_") and is_owner(user_id)

    # /clear — 清空当前会话记忆（仅大号）
    if cmd == "/clear":
        if is_private_owner:
            ok = clear_session_memory(session_key, user_id)
            if ok:
                return "记忆已清空，我们重新开始吧~"
            return "清空记忆时出了点问题，稍后再试试？"
        else:
            return "这个指令只有主人能用哦~"

    # /which — 查看当前服务的是哪个桌宠（所有人可用）
    if cmd == "/which":
        return f"🐾 当前为你服务的是：{_pet_display_name()}"

    # /status — 查看当前模型/服务状态（所有人可用）
    if cmd == "/status":
        try:
            from longtext.model_config import get_longtext_model_name
            from qq.qq_config import get_qq_config, check_port_open, F5TTS_PORT
            cfg = get_qq_config()
            model = get_longtext_model_name()
            f5tts = "✅ 就绪" if check_port_open(F5TTS_PORT) else "❌ 未运行"
            vision = "✅ 开启" if cfg["vision_enabled"] else "❌ 关闭"
            voice = "✅ 开启" if cfg["send_voice"] else "❌ 关闭"
            sticker = "✅ 开启" if cfg["send_sticker"] else "❌ 关闭"
            pet_name = _pet_display_name()
            return (
                f"🍃 {pet_name}状态\n"
                f"🤖 长文本模型：{model}\n"
                f"🎙 语音输出：{voice}\n"
                f"🎙 F5-TTS：{f5tts}\n"
                f"👁 图片识别：{vision}\n"
                f"🖼 表情包：{sticker}\n"
                f"👥 群聊@：{'✅' if cfg['allow_groups'] else '❌'}"
            )
        except Exception as e:
            return f"查询状态失败：{e}"

    # /memory — 查看当前会话记忆条数（所有人可用）
    if cmd == "/memory":
        count = _get_memory_count(session_key)
        return f"当前会话记忆：{count} 轮对话"

    # /install（别名 /help /extensions）— 指令大全（所有人可用）
    if cmd in ("/install", "/help", "/extensions"):
        pet_name = _pet_display_name()
        lines = [
            f"🍃 {pet_name}指令列表：",
            "/which       查看当前服务的是哪个桌宠",
            "/status      查看模型/语音/F5-TTS/图片识别/表情包状态",
            "/memory      查看当前会话记忆轮数",
            "/install     显示全部指令与功能说明",
            "/help        同 /install",
        ]
        if is_private_owner:
            lines.append("/clear       清空我的记忆（仅主人）")
            lines.append("/switch 模型 切换 qwen 或 deepseek（仅主人）")
        else:
            lines.append("/clear 与 /switch 仅主人可用")
        return "\n".join(lines)

    # /switch — 切换长文本模型（仅大号）
    if cmd == "/switch":
        if not is_private_owner:
            return "这个指令只有主人能用哦~"
        if len(parts) < 2:
            return "用法：/switch qwen 或 /switch deepseek"
        target = parts[1].lower()
        if target not in ("qwen", "deepseek"):
            return "只支持 qwen 或 deepseek"
        try:
            import json as _json
            cfg_path = os.path.join(BASE_DIR, "config.json")
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = _json.load(f)
            cfg["longtext_model"] = target
            with open(cfg_path, "w", encoding="utf-8") as f:
                _json.dump(cfg, f, ensure_ascii=False, indent=2)
            return f"✅ 长文本模型已切换为：{target}"
        except Exception as e:
            return f"切换失败：{e}"

    # 未知指令
    return "未知指令，发送 /help 查看可用指令~"
