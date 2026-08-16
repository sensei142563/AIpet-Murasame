# -*- coding: utf-8 -*-
"""
QQ 图片识别 — 收到图片消息时用 qwen3-vl-plus 识别内容。

流程：
1. 从 QQ 消息段提取图片（本地路径 或 URL）
2. 本地路径直接读取；URL 先下载到临时文件
3. 调用 qwen3-vl-plus 视觉模型识别
4. 返回图片内容描述文本

由 config.json 的 "qq_vision_enabled" 控制开关。
"""

import os
import base64
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def extract_image_path(message: list):
    """
    从 OneBot11 message 段中提取第一张图片。
    message: [{"type": "image", "data": {"file": "...", "url": "..."}}, ...]
    返回:
        - 本地已有文件 → 绝对路径
        - 远程 URL → 下载到临时目录后返回路径
        - 无法获取 → None
    """
    if not isinstance(message, list):
        return None

    for seg in message:
        if not isinstance(seg, dict) or seg.get("type") != "image":
            continue
        data = seg.get("data", {}) or {}
        file_path = data.get("file", "")
        url = data.get("url", "")
        print(f"[QQVision] 🔎 图片段: file={str(file_path)[:80]} url={str(url)[:80]}")

        # 1. 本地路径（NapCat 通常会给出 file:/// 或相对/绝对路径）
        if file_path:
            # 去掉 file:/// 前缀
            p = str(file_path).replace("file:///", "").replace("file://", "")
            # 去掉 Windows 路径开头的多余斜杠（如 /E:/  →  E:/）
            if len(p) > 2 and p[0] == "/" and p[2] == ":":
                p = p[1:]
            if os.path.exists(p):
                return p
            # 尝试拼接项目根目录（NapCat 可能给相对路径）
            alt = os.path.join(BASE_DIR, p)
            if os.path.exists(alt):
                return alt

        # 2. 远程 URL → 下载
        if url:
            try:
                resp = requests.get(url, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Referer": "https://qun.qq.com/",
                })
                if resp.status_code == 200 and resp.content:
                    tmp_dir = os.path.join(BASE_DIR, "tmp")
                    os.makedirs(tmp_dir, exist_ok=True)
                    ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
                    tmp_path = os.path.join(tmp_dir, f"qq_vision_{os.getpid()}{ext}")
                    with open(tmp_path, "wb") as f:
                        f.write(resp.content)
                    print(f"[QQVision] 已下载图片: {tmp_path} ({len(resp.content)} bytes)")
                    return tmp_path
                else:
                    print(f"[QQVision] ⚠ 图片 URL 下载失败: HTTP {resp.status_code} len={len(resp.content)}")
            except Exception as e:
                print(f"[QQVision] ⚠ 下载图片失败: {e}")

        # 3. 仅尝试 base64 数据（NapCat 有时内联）
        b64 = data.get("data_base64", "") or data.get("base64", "")
        if b64:
            try:
                import base64 as _b64
                raw = _b64.b64decode(b64)
                tmp_dir = os.path.join(BASE_DIR, "tmp")
                os.makedirs(tmp_dir, exist_ok=True)
                tmp_path = os.path.join(tmp_dir, f"qq_vision_b64_{os.getpid()}.jpg")
                with open(tmp_path, "wb") as f:
                    f.write(raw)
                print(f"[QQVision] 已从 base64 保存图片: {tmp_path}")
                return tmp_path
            except Exception as e:
                print(f"[QQVision] ⚠ base64 解码失败: {e}")

    return None


def find_image_file_id(message):
    """从消息段取第一个 image 段的 file 字段（NapCat 常见为纯 file_id 文件名）。"""
    if not isinstance(message, list):
        return ""
    for seg in message:
        if isinstance(seg, dict) and seg.get("type") == "image":
            return str((seg.get("data") or {}).get("file", "") or "")
    return ""


def napcat_get_image(ws, file_id, timeout=10):
    """NapCat get_image API：把 QQ 图片 file_id 解析为本地绝对路径。

    返回 (path, stray_events)；失败返回 (None, stray_events)。
    注意：本函数在 WS 收包线程内调用（串行无竞争），期间收到的实时事件
    会被收集返回——调用方必须补处理，不能丢消息。
    """
    import json as _json
    import time as _time
    import uuid as _uuid
    import websocket as _websocket
    echo = f"getimg_{_uuid.uuid4().hex[:8]}"
    stray = []
    try:
        ws.send(_json.dumps({"action": "get_image", "params": {"file": file_id}, "echo": echo}))
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            try:
                raw = ws.recv()
                if not raw:
                    continue
                d = _json.loads(raw)
                if d.get("echo") != echo:
                    stray.append(raw)
                    continue
                if d.get("status") == "ok" and d.get("data"):
                    p = str((d["data"].get("file") or d["data"].get("path") or "")).strip()
                    p = p.replace("file:///", "").replace("file://", "")
                    if p and os.path.exists(p):
                        print(f"[QQVision] get_image → 本地文件: {p}")
                        return p, stray
                    b64 = str(d["data"].get("base64") or "")
                    if b64:
                        try:
                            tmp_dir = os.path.join(BASE_DIR, "tmp")
                            os.makedirs(tmp_dir, exist_ok=True)
                            tmp_path = os.path.join(tmp_dir, f"qq_vision_getimg_{os.getpid()}.jpg")
                            with open(tmp_path, "wb") as f:
                                f.write(base64.b64decode(b64))
                            print(f"[QQVision] get_image base64 → {tmp_path}")
                            return tmp_path, stray
                        except Exception as e:
                            print(f"[QQVision] ⚠ get_image base64 落盘失败: {e}")
                print(f"[QQVision] ⚠ get_image 响应不可用: {str(d)[:200]}")
                return None, stray
            except _websocket.WebSocketTimeoutException:
                continue
            except Exception:
                break
    except Exception as e:
        print(f"[QQVision] ⚠ get_image 请求失败: {e}")
    return None, stray


def describe_image(image_path: str) -> str:
    """
    调用 qwen3-vl-plus 识别图片内容。
    返回: 图片内容描述文本；失败返回空字符串。
    """
    try:
        from longtext.model_config import get_vision_model_config
    except Exception:
        print("[QQVision] ⚠ 无法导入 model_config")
        return ""

    cfg = get_vision_model_config()
    if not cfg:
        print("[QQVision] ⚠ 未配置 qwen API Key，无法识别图片")
        return ""

    if not image_path or not os.path.exists(image_path):
        print(f"[QQVision] ⚠ 图片不存在: {image_path}")
        return ""

    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        print(f"[QQVision] ⚠ 读取图片失败: {e}")
        return ""

    # 按当前活动角色自称（多角色架构：诺瓦/阿洛娜等角色不能自称丛雨）
    pet_name = "丛雨"
    try:
        from pets.pet_registry import get_pet_config
        pet_name = (get_pet_config() or {}).get("name") or "丛雨"
    except Exception:
        pass

    identity = (
        "你是一个AI桌宠的助手，主人给你发来了一张图片。"
        f"你需要在屏幕上看到这张图片并以{pet_name}的口吻简要描述主人发来的内容。"
        "可以描述图中的人物、场景、文字、屏幕内容等。"
        "只输出描述内容，不要有任何前后缀或客套话。"
        "控制在 100 字以内。"
    )

    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    {"type": "text", "text": identity},
                ],
            }
        ],
        "model": cfg["model"],
        "max_tokens": 300,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(cfg["url"], json=payload, headers=headers, timeout=(15, 15))
        if resp.status_code != 200:
            print(f"[QQVision] ⚠ API 错误 {resp.status_code}: {resp.text[:200]}")
            return ""
        data = resp.json()
        reply = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        reply = (reply or "").strip()
        print(f"[QQVision] 识别结果: {reply[:80]}...")
        return reply
    except Exception as e:
        print(f"[QQVision] ⚠ 识别请求异常: {e}")
        return ""


def clean_vision_tmp():
    """清理临时下载的图片文件"""
    try:
        tmp_dir = os.path.join(BASE_DIR, "tmp")
        if os.path.isdir(tmp_dir):
            for f in os.listdir(tmp_dir):
                if f.startswith("qq_vision_"):
                    try:
                        os.remove(os.path.join(tmp_dir, f))
                    except Exception:
                        pass
    except Exception:
        pass