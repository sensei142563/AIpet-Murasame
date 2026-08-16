# -*- coding: utf-8 -*-
"""
QQ 聊天模块 — 让丛雨通过 QQ 与主人聊天。

架构：
- qq_bridge: NapCat WebSocket 收发消息
- qq_chat:   对话（共享 long_history 记忆 + 流式 AI）
- qq_sticker: 表情包选择（biaoqingbao/）
- qq_tts:    F5-TTS 语音合成（可选）
"""