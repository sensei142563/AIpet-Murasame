"""
摄像头拍照识别模块
- 摄像头线程持续采集帧
- AI 视觉识别（云端 Qwen VL / 本地 Ollama）
- 对外接口：take_photo → AI 描述 → 返回文本
"""

import os
import sys
import base64
import threading
import time
from typing import Optional, Callable

import cv2

from tool.config import get_config

# ==================== 摄像头采集线程 ====================

class CameraCapture:
    """摄像头采集器 — 后台线程连续采集，主线程随时取帧"""

    def __init__(self, camera_id: int = 0):
        self.camera_id = camera_id
        self.frame: Optional[any] = None  # cv2 BGR 帧
        self._lock = threading.Lock()
        self._running = True
        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._init_camera()
        self._thread = threading.Thread(target=self._update, daemon=True)
        self._thread.start()

    def _init_camera(self):
        """打开摄像头，DSHOW 优先"""
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY]
        for backend in backends:
            try:
                cap = cv2.VideoCapture(self.camera_id, backend)
                if cap.isOpened():
                    self._cap = cap
                    break
            except Exception:
                continue
        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError(f"无法打开摄像头 (id={self.camera_id})")

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        # 预热
        for _ in range(5):
            self._cap.read()

    def _update(self):
        while self._running:
            if self._cap and self._cap.isOpened():
                ret, frame = self._cap.read()
                if ret:
                    with self._lock:
                        self.frame = frame.copy()
            time.sleep(1 / 30)

    def get_frame(self):
        """线程安全获取当前帧（BGR）"""
        with self._lock:
            return self.frame.copy() if self.frame is not None else None

    def close(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._cap:
            self._cap.release()


# ==================== AI 视觉分析 ====================

def _encode_frame(frame) -> str:
    """OpenCV 帧 → JPEG base64 data URL"""
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 75]
    _, buffer = cv2.imencode('.jpg', frame, encode_param)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/jpeg;base64,{img_base64}"


def _qwen_vision(image_b64_url: str, prompt: str) -> str:
    """通过云端 Qwen VL 模型分析图像"""
    import requests
    cfg = get_config("./config.json")
    api_key = cfg.get("APIKEY", {}).get("qwen", "")
    if not api_key:
        return "错误：未配置 Qwen API Key"

    payload = {
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_b64_url}},
                {"type": "text", "text": prompt},
            ]
        }],
        "model": "qwen-vl-plus",
        "max_tokens": 512,
        "stream": False,
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        url = cfg["local_api"]["cloud_api"]
        resp = requests.post(url, json={"payload": payload, "headers": headers}, timeout=30)
        data = resp.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"].strip()
        print(f"[camera] API错误: {data}")
        return f"识别失败: {data.get('error', '未知错误')}"
    except Exception as e:
        return f"识别失败: {str(e)[:80]}"


# ==================== 全局单例 ====================

_camera_cap: Optional[CameraCapture] = None


def init_camera(camera_id: int = 0):
    """初始化摄像头（全局单例）"""
    global _camera_cap
    if _camera_cap is not None:
        try:
            _camera_cap.close()
        except Exception:
            pass
    _camera_cap = CameraCapture(camera_id)


def take_photo_and_describe() -> Optional[str]:
    """
    拍照并通过 AI 描述画面内容
    返回：场景描述文本，或 None 表示失败
    """
    global _camera_cap
    if _camera_cap is None:
        print("[camera] 摄像头未初始化")
        return None

    frame = None
    for _ in range(10):
        frame = _camera_cap.get_frame()
        if frame is not None:
            break
        time.sleep(0.1)
    if frame is None:
        print("[camera] 摄像头预热超时，无法获取画面")
        return "无法获取摄像头画面"

    try:
        img_url = _encode_frame(frame)
        prompt = "请用简短的中文描述这张照片中的场景、人物和主要活动，不超过50个字。如果画面很暗看不清，也请如实描述。"
        result = _qwen_vision(img_url, prompt)
        print(f"[camera] 识别结果: {result}")
        return result
    except Exception as e:
        print(f"[camera] 识别异常: {e}")
        return None


def get_camera_frame():
    """获取摄像头当前帧（用于人脸识别等额外处理）"""
    global _camera_cap
    if _camera_cap is None:
        print("[camera] CameraCapture 未初始化")
        return None
    # 重试最多 10 次（约 1 秒），确保摄像头已预热
    for _ in range(10):
        frame = _camera_cap.get_frame()
        if frame is not None:
            return frame
        time.sleep(0.1)
    print("[camera] 摄像头预热超时，未能获取帧")
    return None


def close_camera():
    global _camera_cap
    if _camera_cap:
        _camera_cap.close()
        _camera_cap = None