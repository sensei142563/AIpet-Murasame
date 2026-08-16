# -*- coding: utf-8 -*-
"""
F5-TTS 客户端 — 长文本模式中文语音合成
统一接口: say(text, save_path, callback)
"""

import os
import json
import time
import uuid
import threading
import requests

# F5-TTS HTTP 服务地址
F5TTS_URL = os.getenv("F5TTS_URL", "http://127.0.0.1:9881/infer")

# 默认参考音频（短参考，音色克隆更稳定）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 角色语音包优先，全局兜底 —— 由 pet_registry.get_long_ref() 动态解析
from pets.pet_registry import get_long_ref
DEFAULT_REF_AUDIO, DEFAULT_REF_TEXT = get_long_ref()


class LongTextVoice:
    """
    F5-TTS 引擎封装。
    核心接口：say(text, save_path, callback) — 与流式提示词完全一致。
    替换引擎只需要改这一个类。
    """

    def __init__(self, ref_audio=None, ref_text=None):
        self.ref_audio = ref_audio or DEFAULT_REF_AUDIO
        self.ref_text = ref_text or DEFAULT_REF_TEXT

    def is_available(self) -> bool:
        """检查 F5-TTS 服务是否在线"""
        try:
            resp = requests.get(
                self._health_url(),
                timeout=3,
            )
            return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _health_url() -> str:
        base = F5TTS_URL.rsplit("/", 1)[0]
        return base + "/health"

    def say(self, msg: str, save_path: str = None, callback=None):
        """
        异步合成语音。

        msg:       要合成的文本
        save_path: 输出 wav 路径 (None 则自动生成临时路径)
        callback:  合成完成后回调 (无参数)
        """
        if not msg or not msg.strip():
            if callback:
                callback()
            return

        if save_path is None:
            save_path = os.path.join(
                os.path.dirname(__file__), "..", "tmp",
                f"longtext_{int(time.time() * 1000)}.wav"
            )
            save_path = os.path.abspath(save_path)

        def _synthesize():
            try:
                payload = {
                    "text": msg.strip(),
                    "ref_audio": self.ref_audio,
                    "ref_text": self.ref_text,
                    "speed": 1.0,
                }
                resp = requests.post(
                    F5TTS_URL,
                    json=payload,
                    timeout=(15, 300),  # (连接超时, 读取超时)
                )
                if resp.status_code == 200 and resp.headers.get("Content-Type", "").startswith("audio/"):
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    # 写入前先删除旧文件（避免 Permission denied）
                    try:
                        if os.path.exists(save_path):
                            os.remove(save_path)
                    except Exception:
                        pass
                    with open(save_path, "wb") as f:
                        f.write(resp.content)
                else:
                    try:
                        err = resp.json().get("error", resp.text[:200])
                    except Exception:
                        err = resp.text[:200]
                    print(f"[LongTextTTS] ⚠ 合成失败: {err}")

            except Exception as e:
                print(f"[LongTextTTS] ⚠ 请求异常: {e}")

            if callback:
                callback()

        # 异步线程合成，不阻塞调用方
        threading.Thread(target=_synthesize, daemon=True).start()


class LongTextTTSManager:
    """
    串行 TTS 合成+播放队列管理器。
    1. 调用 voice.say() 异步合成 .wav
    2. 合成完成后 callback → tts.play_audio() 加入播放队列
    3. 播放完毕后处理下一条
    """
    def __init__(self, voice, tts_playback):
        self.voice = voice
        self.tts = tts_playback
        self.queue = []               # [(text, path), ...]
        self.is_generating = False

    def add(self, text):
        """外部调用：加入合成队列"""
        import re
        text = re.sub(r'[^\u4e00-\u9fff\u3000-\u303f，。！？、；：""''（）,.?!;:()a-zA-Z0-9\s]', '', text).strip()
        if not text:
            return

        # 临时目录（用完即删），时间戳 + 随机后缀确保文件名唯一
        timestamp = int(time.time() * 1000)
        unique = uuid.uuid4().hex[:8]
        audio_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tmp",
            f"longtext_{timestamp}_{unique}.wav",
        )
        self.queue.append((text, audio_path))
        if not self.is_generating:
            self._process_next()

    def _process_next(self):
        """处理队列中的下一个"""
        if not self.queue:
            self.is_generating = False
            return
        self.is_generating = True
        text, path = self.queue.pop(0)
        # 异步合成，完成后自动播放
        self.voice.say(text, save_path=path, callback=lambda: self._on_done(path))

    def _on_done(self, path):
        """合成完成 → 加入播放队列 → 处理下一个"""
        self.tts.play_audio(path)
        self._process_next()

    def is_idle(self):
        """合成队列空闲（无待合成文本 且 当前不在合成）→ True"""
        return not self.queue and not self.is_generating

    def clear(self):
        """清空队列（新对话开始时调用）"""
        self.queue.clear()
        self.is_generating = False