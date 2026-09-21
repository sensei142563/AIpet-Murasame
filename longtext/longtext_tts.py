# -*- coding: utf-8 -*-
"""
F5-TTS 客户端 — 长文本模式中文语音合成
统一接口: say(text, save_path, callback)
"""

import io
import os
import json
import time
import uuid
import threading
import requests

# F5-TTS HTTP 服务地址
F5TTS_URL = os.getenv("F5TTS_URL", "http://127.0.0.1:9881/infer")
# GPT-SoVITS API（默认 9880）。A 卡/无 N 卡机器上它比 F5-TTS 快几十倍
GSV_URL = os.getenv("GSV_URL", "http://127.0.0.1:9880/")

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

    @staticmethod
    def _cfg(key, default):
        try:
            with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as fh:
                return json.load(fh).get(key, default)
        except Exception:
            return default

    def _unified_ref(self):
        """短语音包里的默认情绪参考（和日常说话同一个音色）"""
        try:
            from pets.pet_registry import (get_pet_config, get_short_emotion_dirs,
                                           get_short_voices_dir)
            base = get_short_voices_dir()
            emo = str(((get_pet_config().get("voices") or {}).get("default_emotion") or "")).strip()
            cand = [emo] if emo else []
            cand += [e for e in (get_short_emotion_dirs() or []) if e != emo]
            for e in cand:
                d = os.path.join(base, str(e))
                if not os.path.isdir(d):
                    continue
                txt = ""
                try:
                    txt = io.open(os.path.join(d, "asr.txt"), encoding="utf-8").read().strip()
                except Exception:
                    txt = ""
                for f in sorted(os.listdir(d)):
                    if f.lower().endswith((".wav", ".mp3", ".flac", ".ogg")):
                        return os.path.join(d, f), txt
        except Exception:
            pass
        return "", ""

    def __init__(self, ref_audio=None, ref_text=None):
        self.ref_audio = ref_audio or DEFAULT_REF_AUDIO
        self.ref_text = ref_text or DEFAULT_REF_TEXT
        # ① 先用"设置里指定的语音包文件"（启动器设置界面写的就是这一项）
        if not ref_audio:
            try:
                _sv = str(self._cfg("longtext_ref_voice", "") or "").strip()
            except Exception:
                _sv = ""
            if _sv:
                _sp = _sv if os.path.isabs(_sv) else os.path.join(BASE_DIR, _sv)
                if os.path.isfile(_sp):
                    self.ref_audio = os.path.abspath(_sp)
        # ② 只有显式打开 gsv_unified_ref 时，才改用短语音包那套参考
        try:
            _u = self._cfg("gsv_unified_ref", False)
        except Exception:
            _u = False
        if str(_u).lower() in ("true", "1", "yes") and not ref_audio:
            _a, _t = self._unified_ref()
            if _a:
                self.ref_audio, self.ref_text = _a, _t
        # 引擎：默认优先 GPT-SoVITS（同样 CPU 上比 F5-TTS 快两个数量级）；
        # 只有它不在线时才退回 F5-TTS。可用 LONGTEXT_TTS_BACKEND=f5tts 强制旧引擎。
        want = (os.getenv("LONGTEXT_TTS_BACKEND", "").strip().lower()
                or str(self._cfg("longtext_tts_type", "gpt_sovits")).strip().lower())
        self.backend = "f5tts" if want == "f5tts" else "gpt_sovits"
        self.gsv_steps = str(self._cfg("gsv_sample_steps", 16))
        # 语速：默认略快（丛雨是活泼元气的角色，语速太慢会显得冷淡）
        # 角色包 pet.json 里 voices.long_speed 可覆盖
        try:
            from pets.pet_registry import get_pet_config
            self._speed = float((get_pet_config().get("voices", {}) or {}).get("long_speed", 1.06))
        except Exception:
            self._speed = 1.06

    def is_available(self) -> bool:
        """GPT-SoVITS 在线就用它（快得多），否则退 F5-TTS"""
        gsv = self._ping(self._gsv_health())
        if gsv:
            if self.backend != "f5tts":
                self.backend = "gpt_sovits"
            elif os.getenv("LONGTEXT_TTS_BACKEND", "").strip().lower() != "f5tts":
                self.backend = "gpt_sovits"      # 配置写了 f5tts 但 GSV 在线 → 还是用快的
            return True
        if self._ping(self._health_url()):
            self.backend = "f5tts"
            return True
        return False

    @staticmethod
    def _ping(url: str) -> bool:
        try:
            return requests.get(url, timeout=3).status_code == 200
        except Exception:
            return False

    @staticmethod
    def _health_url() -> str:
        base = F5TTS_URL.rsplit("/", 1)[0]
        return base + "/health"

    @staticmethod
    def _gsv_health() -> str:
        return GSV_URL.rstrip("/") + "/docs"

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

        # 缓存：同样的文本+音色+语速 → 直接用上次的成品
        try:
            import hashlib
            try:
                _ref_t = self._effective_ref(msg.strip()) if self.backend == "gpt_sovits" else None
            except Exception:
                _ref_t = None
            _eff = _ref_t[0] if _ref_t else self.ref_audio
            _tl = _ref_t[3] if _ref_t else "zh"
            self._cache_ref = _eff
            _fp2 = ""
            try:
                _st2 = os.stat(_eff)
                _fp2 = "%d_%d" % (int(_st2.st_mtime), int(_st2.st_size))
            except Exception:
                pass
            self._model_tag = ""
            try:
                _gsv2 = os.path.join(BASE_DIR, "GPT-SoVITS")
                for _rel2 in ("GPT_weights/murasame-gpt.ckpt", "SoVITS_weights/murasame-sovits.pth"):
                    _f2 = os.path.join(_gsv2, _rel2)
                    if os.path.isfile(_f2):
                        _s2 = os.stat(_f2)
                        self._model_tag += "%s@%d_%d;" % (os.path.basename(_f2), int(_s2.st_mtime), int(_s2.st_size))
            except Exception:
                pass
            _ck = hashlib.md5(("%s|%s|%s|%.2f|%s|%s|%s|%s|v4" % (msg.strip(), _eff, self.backend,
                                                          self._speed, self.gsv_steps, _fp2,
                                                          self._model_tag, _tl)).encode("utf-8")).hexdigest()[:16]
            self._cache_path = os.path.join(BASE_DIR, "tmp", "tts_cache", _ck + ".wav")
            if os.path.isfile(self._cache_path):
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                import shutil as _sh
                _sh.copy2(self._cache_path, save_path)
                print("[LongTextTTS] ⚡ 命中缓存，直接用已合成的语音")
                if callback:
                    callback()
                return
        except Exception:
            self._cache_path = ""

        def _synthesize():
            try:
                if self.backend == "gpt_sovits" and self._say_gsv(msg.strip(), save_path):
                    self._save_cache(save_path)
                    if callback:
                        callback()
                    return
                payload = {
                    "text": msg.strip(),
                    "ref_audio": self.ref_audio,
                    "ref_text": self.ref_text,
                    "speed": self._speed,
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

                if os.path.isfile(save_path):
                    self._save_cache(save_path)
            except Exception as e:
                print(f"[LongTextTTS] ⚠ 请求异常: {e}")

            if callback:
                callback()

        # 异步线程合成，不阻塞调用方
        threading.Thread(target=_synthesize, daemon=True).start()

    def _save_cache(self, save_path: str):
        try:
            import shutil
            _cp = getattr(self, "_cache_path", "")
            if _cp:
                os.makedirs(os.path.dirname(_cp), exist_ok=True)
                shutil.copy2(save_path, _cp)
            _cd = os.path.dirname(_cp) if _cp else ""
            if _cd and os.path.isdir(_cd):                 # 缓存别无限涨：3 天前的删掉
                for f in os.listdir(_cd):
                    fp = os.path.join(_cd, f)
                    try:
                        if os.path.getmtime(fp) < time.time() - 86400 * 3:
                            os.remove(fp)
                    except Exception:
                        pass
        except Exception:
            pass

    def _ja_ref(self):
        """日语文本找一个日语参考：优先角色包的短语音包（句子短 → 合成更快、音色更贴）"""
        try:
            from pets.pet_registry import get_short_emotion_dirs, get_short_voices_dir
            base = get_short_voices_dir()
            dirs = get_short_emotion_dirs() or []
            for emo in ("高兴", "平静", "害羞") + tuple(dirs):
                d = os.path.join(base, str(emo))
                if not os.path.isdir(d):
                    continue
                tr = os.path.join(d, "asr.txt")
                if not os.path.isfile(tr):
                    continue
                try:
                    txt = io.open(tr, encoding="utf-8").read().strip()
                except Exception:
                    txt = ""
                for f in sorted(os.listdir(d)):
                    if f.lower().endswith((".wav", ".mp3", ".flac", ".ogg")):
                        return os.path.join(d, f), txt
        except Exception:
            pass
        return "", ""

    def _effective_ref(self, text: str):
        """返回本次实际要用的 (参考音频, 参考台词, 参考语言, 文本语言)"""
        # ★ 语言判定统一走 tool/chat._tts_text_lang：带假名 → 日语；纯汉字
        #   （「了解」「大丈夫」这类）→ 跟随当前语言模式，不能一律当中文念
        #   （那正是用户反馈的"日语模式却合成出中文"）。
        try:
            from tool.chat import _tts_text_lang as _lang
        except Exception:
            import re as _re
            _kana = lambda t: bool(_re.search(r"[\u3040-\u30ff]", str(t or "")))
            _lang = lambda t: ("ja" if _kana(t) else "zh")
        prompt_lang = _lang(self.ref_text)     # 参考音频那条台词的语言
        text_lang = _lang(text)                # 要念的这段话的语言
        # ⚠ 长语音只用长语音包（用短语音的样例会让音色变味，用户明确要求不要混用）；
        #   但"文本语言"必须跟着文本走：音色由参考音频决定，语言由文本决定，
        #   两者混用会把中文台词按日文念（听着像换了个人）。跨语言合成是正常用法。
        return self.ref_audio, self.ref_text, prompt_lang, text_lang

    def _say_gsv(self, text: str, save_path: str) -> bool:
        """走 GPT-SoVITS API（VITS 系模型，CPU 上比 F5-TTS 快几十倍）"""
        try:
            ref_audio, ref_text, prompt_lang, text_lang = self._effective_ref(text)
            params = {
                "refer_wav_path": ref_audio,
                "prompt_text": ref_text or ("こんにちは。" if prompt_lang == "ja" else "你好。"),
                "prompt_language": prompt_lang,
                "text": text,
                "text_language": text_lang,
                "top_k": 15, "top_p": 1, "temperature": 1,
                "speed": self._speed,
                "sample_steps": self.gsv_steps,      # 步数越少越快（8~16 够用）
                "if_sr": "false",                    # 关超分，省一大截
            }
            t0 = time.time()
            resp = requests.get(GSV_URL, params=params, timeout=(10, 600))
            if resp.status_code == 200 and resp.content[:4] == b"RIFF":
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                try:
                    if os.path.exists(save_path):
                        os.remove(save_path)
                except Exception:
                    pass
                _audio = resp.content
                try:
                    from tool.audio_polish import polish_wav_bytes
                    _audio = polish_wav_bytes(_audio)      # 统一响度 + 偏闷时提亮
                except Exception:
                    pass
                with open(save_path, "wb") as f:
                    f.write(_audio)
                el = time.time() - t0
                try:
                    import wave as _w
                    with _w.open(save_path) as wf:
                        dur = wf.getnframes() / float(wf.getframerate() or 1)
                    print("[LongTextTTS] ✅ GPT-SoVITS 合成 %.1fs 音频用了 %.1fs（RTF=%.2f）"
                          % (dur, el, el / max(dur, 1e-6)))
                except Exception:
                    print("[LongTextTTS] ✅ GPT-SoVITS 合成完成（%.1fs）" % el)
                return True
            print("[LongTextTTS] ⚠ GPT-SoVITS 返回异常：HTTP %s" % resp.status_code)
        except Exception as e:
            print("[LongTextTTS] ⚠ GPT-SoVITS 请求失败：%s" % str(e)[:120])
        self.backend = "f5tts"          # 失败就回退 F5
        return False


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