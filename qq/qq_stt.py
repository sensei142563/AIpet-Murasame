# -*- coding: utf-8 -*-
"""QQ 语音识别 — 收到 QQ 语音消息时转文字后回复。"""
import os, json, time, uuid

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def extract_voice_path(message):
    """提取 record 语音段 (file/path)"""
    if not isinstance(message, list):
        return None
    for seg in message:
        if isinstance(seg, dict) and seg.get("type") == "record":
            d = seg.get("data", {}) or {}
            return {"file": d.get("file", ""), "path": d.get("path", "") or d.get("file", "")}
    return None

def _napcat_get_record(ws, file_id):
    """NapCat get_record: silk -> wav"""
    try:
        import websocket
        echo = f"getr_{uuid.uuid4().hex[:8]}"
        ws.send(json.dumps({"action": "get_record", "params": {"file": file_id, "out_format": "wav"}, "echo": echo}))
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                raw = ws.recv()
                if not raw: continue
                d = json.loads(raw)
                if d.get("echo") != echo: continue
                if d.get("status") == "ok" and d.get("data"):
                    p = d["data"].get("file") or d["data"].get("path") or ""
                    if p and os.path.exists(p): return p
                return None
            except websocket.WebSocketTimeoutException: continue
            except Exception: break
    except Exception as e:
        print(f"[QQStt] ⚠ get_record 失败: {e}")
    return None

def _decrypt_voice(voice_data, ws):
    """尝试获取可用的本地 wav 路径"""
    file_id = voice_data.get("file", "")
    local = voice_data.get("path", "")
    if ws and file_id:
        p = _napcat_get_record(ws, file_id)
        if p: return p
    if local:
        local = local.replace("file:///", "").replace("file://", "")
        if os.path.exists(local): return local
    return None

def transcribe_voice(voice_data, ws=None):
    """识别语音文字（faster-whisper）"""
    if not voice_data: return ""
    path = _decrypt_voice(voice_data, ws)
    if not path or not os.path.exists(path):
        print(f"[QQStt] ⚠ 无法获取语音文件")
        return ""
    try:
        import sys
        for p in (BASE_DIR,):
            if p not in sys.path: sys.path.insert(0, p)
        from tool.stt import transcribe_full
        text = (transcribe_full(path) or "").strip()
        print(f"[QQStt] 🎤 识别: {text[:50]}...")
        return text
    except Exception as e:
        print(f"[QQStt] ⚠ 识别失败: {e}")
        return ""