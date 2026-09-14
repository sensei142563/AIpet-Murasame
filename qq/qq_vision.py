# -*- coding: utf-8 -*-
"""
QQ 图片识别 — 收到图片消息时调用视觉模型识别内容（模型由 vision_model_name 配置）。

流程：
1. 从 QQ 消息段提取图片（本地路径 或 URL）
2. 本地路径直接读取；URL 先下载到临时文件
3. 调用视觉模型识别（默认 qwen3-vl-plus，可在 PCL 设置/config.json 更改）
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


def _get_pet_name():
    """按当前活动角色自称（多角色架构：诺瓦/阿洛娜等角色不能自称丛雨）"""
    try:
        from pets.pet_registry import get_pet_config
        return (get_pet_config() or {}).get("name") or "丛雨"
    except Exception:
        return "丛雨"


def _vision_request(identity: str, image_paths) -> str:
    """底层视觉请求：一张或多张图片(base64) + 提示语 → 模型描述文本"""
    try:
        from longtext.model_config import get_vision_model_config
    except Exception:
        print("[QQVision] ⚠ 无法导入 model_config")
        return ""
    cfg = get_vision_model_config()
    if not cfg:
        print("[QQVision] ⚠ 未配置视觉模型 API Key，无法识别")
        return ""
    paths = [p for p in (image_paths or []) if p and os.path.exists(p)]
    if not paths:
        print("[QQVision] ⚠ 图片/帧文件不存在")
        return ""
    try:
        content = []
        for p in paths:
            with open(p, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}})
        content.append({"type": "text", "text": identity})
    except Exception as e:
        print(f"[QQVision] ⚠ 读取图片失败: {e}")
        return ""
    payload = {
        "messages": [{"role": "user", "content": content}],
        "model": cfg["model"],
        "max_tokens": 400,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(cfg["url"], json=payload, headers=headers, timeout=(15, 30))
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


def describe_image(image_path: str) -> str:
    """
    调用视觉模型（vision_model_name 配置）识别图片内容。
    返回: 图片内容描述文本；失败返回空字符串。
    """
    if not image_path or not os.path.exists(image_path):
        print(f"[QQVision] ⚠ 图片不存在: {image_path}")
        return ""
    pet_name = _get_pet_name()
    # 注意：提示词绝不能出现"主人"字样——识别结果会原样注入回复上下文，
    # 曾导致"主人发来…"进入上下文，诱导模型把任何发图的人都叫成主人。
    identity = (
        "别人发来了一张图片。"
        f"请以{pet_name}的口吻客观简要描述这张图片的内容。"
        "可以描述图中的人物、场景、文字、屏幕内容等。"
        "只输出描述内容，不要有任何前后缀或客套话，不要提是谁发来的。"
        "控制在 100 字以内。"
    )
    return _vision_request(identity, [image_path])


# ═══════════ 视频识别：抽帧 → 多帧一次送入视觉模型 ═══════════
def find_ffmpeg() -> str:
    """定位 ffmpeg.exe（项目内置优先，其次 NapCat native / PATH 兜底）"""
    cands = [
        os.path.join(BASE_DIR, "GPT-SoVITS", "runtime", "ffmpeg.exe"),
        os.path.join(BASE_DIR, "NapCat.Shell.Windows.OneKey",
                     "NapCat", "native", "ffmpeg", "ffmpeg.exe"),
        os.path.join(os.environ.get("APPDATA", ""), "bilibili", "ffmpeg", "ffmpeg.exe"),
    ]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return "ffmpeg"  # PATH 兜底


def extract_video_path(message: list):
    """从 OneBot11 message 段提取第一个 video 段并落到本地文件。
    返回本地绝对路径；失败返回 None（与 extract_image_path 同套路）。"""
    if not isinstance(message, list):
        return None
    for seg in message:
        if not isinstance(seg, dict) or seg.get("type") not in ("video", "record"):
            continue
        data = seg.get("data", {}) or {}
        file_path = data.get("file", "")
        url = data.get("url", "")
        print(f"[QQVision] 🎬 视频段: file={str(file_path)[:70]} url={str(url)[:70]}")
        if file_path:
            p = str(file_path).replace("file:///", "").replace("file://", "")
            if len(p) > 2 and p[0] == "/" and p[2] == ":":
                p = p[1:]
            if os.path.exists(p):
                return p
            alt = os.path.join(BASE_DIR, p)
            if os.path.exists(alt):
                return alt
        if url:
            try:
                resp = requests.get(url, timeout=30, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Referer": "https://qun.qq.com/",
                })
                if resp.status_code == 200 and resp.content:
                    tmp_dir = os.path.join(BASE_DIR, "tmp")
                    os.makedirs(tmp_dir, exist_ok=True)
                    ext = os.path.splitext(url.split("?")[0])[1] or ".mp4"
                    tmp_path = os.path.join(tmp_dir, f"qq_vision_vid_{os.getpid()}{ext}")
                    with open(tmp_path, "wb") as f:
                        f.write(resp.content)
                    print(f"[QQVision] 已下载视频: {tmp_path} ({len(resp.content)} bytes)")
                    return tmp_path
                else:
                    print(f"[QQVision] ⚠ 视频 URL 下载失败: HTTP {resp.status_code}")
            except Exception as e:
                print(f"[QQVision] ⚠ 下载视频失败: {e}")
    return None


def _video_duration_sec(video_path: str) -> float:
    """用 ffmpeg -i 的 stderr 解析视频时长（秒）；解析失败返回 0"""
    import re as _re
    import subprocess as _sp
    try:
        # encoding+errors：ffmpeg 输出可能含非 GBK 字节，text=True 默认 gbk 解码会抛
        # UnicodeDecodeError（reader 线程里崩溃 → 时长解析失败/日志噪音）
        r = _sp.run([find_ffmpeg(), "-i", video_path],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=30)
        m = _re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr or "")
        if m:
            h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            return h * 3600 + mi * 60 + s
    except Exception:
        pass
    return 0.0


def extract_video_frames(video_path: str, n: int = 3):
    """抽 n 帧（均匀分布：起点附近/中部/靠后），返回帧文件路径列表；失败返回 []"""
    import subprocess as _sp
    import uuid as _uuid
    frames = []
    try:
        dur = _video_duration_sec(video_path)
        if dur <= 0:
            dur = 5.0  # 解析失败按 5 秒处理：只抽起点/0.5s
        times = []
        if n <= 1 or dur <= 1:
            times = [min(0.3, dur / 2)]
        else:
            # 起点附近 + 均分中段 + 尾部略提前（避免黑场结尾）
            times = [0.3]
            for i in range(1, n - 1):
                times.append(dur * i / n)
            times.append(max(0.1, dur - 0.8))
        tmp_dir = os.path.join(BASE_DIR, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        tag = _uuid.uuid4().hex[:8]
        for idx, t in enumerate(times):
            out = os.path.join(tmp_dir, f"qq_vision_frame_{tag}_{idx}.jpg")
            # 同上：ffmpeg 输出非 UTF-8/GBK 字节时，捕获解码必须容错，
            # 否则 reader 线程 UnicodeDecodeError（此前日志里的崩溃来源）
            r = _sp.run(
                [find_ffmpeg(), "-y", "-ss", f"{t:.2f}", "-i", video_path,
                 "-frames:v", "1", "-q:v", "3", out],
                capture_output=True, encoding="utf-8", errors="replace", timeout=60)
            if os.path.exists(out) and os.path.getsize(out) > 0:
                frames.append(out)
        print(f"[QQVision] 🎬 抽帧完成: {len(frames)}/{len(times)} 帧")
    except Exception as e:
        print(f"[QQVision] ⚠ 视频抽帧失败: {e}")
    return frames


def describe_video(video_path: str) -> str:
    """
    识别视频：抽 3 帧 → 一次请求送入视觉模型 → 返回画面内容描述。
    返回: 描述文本；失败返回空字符串。
    """
    if not video_path or not os.path.exists(video_path):
        print(f"[QQVision] ⚠ 视频不存在: {video_path}")
        return ""
    pet_name = _get_pet_name()
    frames = extract_video_frames(video_path)
    if not frames:
        return ""
    try:
        identity = (
            "你是一个AI桌宠的助手，主人给你发来了一段视频，下面是按时间顺序抽取的"
            f"几帧画面。请你综合这些画面，以{pet_name}的口吻简要描述视频里发生的内容"
            "（画面主体、动作、场景、字幕等），像在给没看视频的人转述一样。"
            "只输出描述内容，不要有任何前后缀或客套话，控制在 120 字以内。"
        )
        return _vision_request(identity, frames)
    finally:
        # 清理抽出的帧
        try:
            for fp in frames:
                if os.path.exists(fp):
                    os.remove(fp)
        except Exception:
            pass


def describe_sticker(image_path: str) -> str:
    """给收藏表情生成短标签：用不超过12字短语描述内容与情绪（供自主发图识别用）"""
    if not image_path or not os.path.exists(image_path):
        return ""
    identity = (
        "这是一张表情包/图片，请用不超过12个字的短语概括它的内容与情绪"
        "（例如：开心小猫、生气跺脚、委屈大哭、得意洋洋、无语翻白眼）。"
        "只输出短语本身，不要解释、不要加引号。"
    )
    return _vision_request(identity, [image_path])


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