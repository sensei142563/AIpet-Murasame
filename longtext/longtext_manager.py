# -*- coding: utf-8 -*-
"""
长文本模式核心 — 流式 AI + 标点切句 + TTS 队列 + 播放管理

防卡死设计（基于上次调试经验）：
- QThread 流式生成，主线程零阻塞
- TTS 合成后台线程串行（RLock 防死锁）
- pygame.mixer 播放线程只创建一次（pause() 替代销毁重建）
- 采样率 24000Hz（F5-TTS 输出）
"""

import os
import re
import time
import threading
from queue import Queue
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal, QObject

import pygame

from pets.pet_registry import get_prompt_path, get_pet_config

# ── 路径 ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── 切句配置（参考 TTS调试总结 第8节）──────────────────
# 强断句：句号/问号/感叹号/省略号/分号/换行（无条件切断）
STRONG_BREAKS = "。！？…；;\n"
# 弱断句：逗号（中英文都支持）
SOFT_BREAKS   = "，,"
MIN_CLAUSE_LEN = 4         # 最短子句（小于此长度继续等待）
MAX_CLAUSE_LEN = 30        # 兜底强制切（防止 buffer 无限膨胀）
LONG_THRESHOLD = 40        # 只有逗号的超长句阈值
SOFT_AFTER = 20            # 超长句 20 字后找第一个逗号切
# 右引号/闭标点（断句符后紧跟这些 → 并入前句，避免引号被单独切出）
# 用 Unicode 转义避免引号字符歧义（中文右引号 / ASCII 引号 / 方引号）
RIGHT_QUOTES = {
    "\u201d",  # ” 中文右双引号
    "\u2019",  # ’ 中文右单引号
    "\u300d",  # 」 右方引号
    "\u300f",  # 』 右角引号
    "\u0022",  # " ASCII 双引号
    "\u0027",  # ' ASCII 单引号
    "\u0060",  # ` 反引号（markdown 代码标记闭合）
}


# ══════════════════════════════════════════════════════════
# 流式 AI 线程（QThread）
# ══════════════════════════════════════════════════════════

class LongTextStreamThread(QThread):
    """
    长文本流式生成线程（支持 qwen / deepseek）：
    - 逐 token 接收 AI 回复
    - 遇到标点(。！？)切句，且长度在 [MIN, MAX] 之间
    - clause_ready 信号 → 主线程显示 + 加入 TTS 队列
    - ai_done 信号 → 保存历史 + 恢复 UI
    """
    clause_ready = pyqtSignal(str)
    ai_done = pyqtSignal(str)
    ai_error = pyqtSignal(str)

    def __init__(self, history, user_input, api_key, chat_model="qwen-plus",
                 api_url=None, parent=None):
        super().__init__(parent)
        self.history = history or []
        self.user_input = user_input
        self.api_key = api_key
        self.chat_model = chat_model
        self.api_url = api_url or "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

        # 加载长文本专属 prompt（文件读取失败则用默认）
        self.system_prompt = self._load_system_prompt()

        self._force_stop = False

    def _load_system_prompt(self):
        prompt_path = get_prompt_path("long")
        try:
            if prompt_path and os.path.exists(prompt_path):
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
        except Exception as e:
            print(f"[LongText] 读取 prompt 失败: {e}")
        pet_cfg = get_pet_config()
        pet_name = pet_cfg.get("display_name") or pet_cfg.get("name") or "桌宠"
        return (
            f"你是一个住在用户身边的人工智能桌宠角色——{pet_name}。"
            "请像真正的人类一样自然对话，不要机械重复设定词汇。"
            "直接说出你想说的话，不要有任何背景描写或动作描写。"
        )

    def stop(self):
        self._force_stop = True

    def run(self):
        try:
            buffer = ""
            full_text = ""
            for token in self._chat_stream():
                if self._force_stop:
                    self.ai_done.emit(full_text)
                    return
                full_text += token
                buffer += token
                # 提前清洗：仅丢弃"断句符+紧跟孤立引号"的闭合残引（上一句完整收尾）
                # 流式场景右引号在断句之后才到达；引号后跟普通文字 → 视为新句左引号保留
                while (
                    buffer
                    and buffer[0] in RIGHT_QUOTES
                    and len(buffer) >= 2
                    and buffer[1] in STRONG_BREAKS
                ):
                    buffer = buffer[1:]
                # 切句循环
                while True:
                    clause = self._extract_clause(buffer)
                    if clause is None:
                        break
                    buffer = buffer[len(clause):]
                    print(f"[切句] 输出: {clause.strip()[:40]}... ({len(clause.strip())}字)")
                    self.clause_ready.emit(clause.strip())

            # 流结束后处理剩余文本
            if buffer.strip() and not self._force_stop:
                # 流末清理纯符号残留（引号/省略号/标点/空白）→ 不输出 1 字垃圾 clause
                while buffer and (
                    buffer[0] in RIGHT_QUOTES
                    or buffer[0] in "\u2026\n\t "
                    or buffer[0] in "，,、；;：:.)）]】》"
                ):
                    buffer = buffer[1:]
                if buffer.strip():
                    self.clause_ready.emit(buffer.strip())

            self.ai_done.emit(full_text)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.ai_error.emit(str(e))
            self.ai_done.emit("")

    def _extract_clause(self, buffer: str):
        """
        从 buffer 中提取一个完整短句。

        策略：
        1. 优先找强断句符（。！？…；;换行）→ 直接切
        2. 强断句太远 → 找逗号：
           - 短文本（≤40字）：逗号处直接切
           - 超长文本（>40字）：20 字后的第一个逗号切（避免切成碎片）
        3. 都没有 → 兜底按 MAX_CLAUSE_LEN 强制切
        中英文标点都支持（。vs . / ，vs ,）。
        """
        if not buffer:
            return None

        # 1️⃣ 优先找强断句符（。！？…；;换行）
        # 改进：取第一个满足 MIN_CLAUSE_LEN 的断点
        # （跳过 buffer 开头过短的残段（如换行/孤立标点），避免卡死等待超长兜底）
        break_points = []
        for p in STRONG_BREAKS:
            pos = buffer.find(p)
            if pos != -1:
                end_idx = pos + 1
                # 连续省略号（……）合并：避免第二个 … 残留成 1 字垃圾 clause
                while end_idx < len(buffer) and buffer[end_idx] == "\u2026":
                    end_idx += 1
                # 断句符后连续右引号/闭标点（如 ’” 嵌套引语收尾）→ 全部并入，避免残留 1 字垃圾
                while end_idx < len(buffer) and buffer[end_idx] in RIGHT_QUOTES:
                    end_idx += 1
                break_points.append(end_idx)
        if break_points:
            for end_idx in sorted(break_points):
                if end_idx >= MIN_CLAUSE_LEN:
                    # 断句符恰在 buffer 末尾 → 延迟切句（右引号可能还未到达）
                    # 下一 token 到达后断句符不再是末尾 → 立即切出（含右引号）
                    # 若流就此结束，流末处理会整体输出，不会丢内容
                    if end_idx == len(buffer):
                        return None
                    return buffer[:end_idx]
            # 所有强断句点都太短（<MIN）→ 放弃强断句，走逗号/兜底
            # 注意：不返回，继续下面的逗号策略

        # 2️⃣ 强断句太远 → 逗号策略
        if len(buffer) > MIN_CLAUSE_LEN:
            # 超长文本（>40字）：从 20 字后开始找逗号，避免切成碎片
            search_start = SOFT_AFTER if len(buffer) > LONG_THRESHOLD else 0
            for p in SOFT_BREAKS:
                pos = buffer.find(p, search_start)
                if pos != -1:
                    clause = buffer[:pos + 1]
                    if len(clause) >= MIN_CLAUSE_LEN:
                        return clause

        # 3️⃣ 兜底：强制 MAX_CLAUSE_LEN 切（防止 buffer 无限膨胀）
        if len(buffer) >= MAX_CLAUSE_LEN:
            return buffer[:MAX_CLAUSE_LEN]

        return None

    def _chat_stream(self):
        """
        流式调用对话模型（qwen-plus / deepseek-chat），逐 token yield。
        URL / Key / 模型名均由 model_config 在构造时传入。

        优先级记忆处理：
        - priority=high: 提取为 system 级「最近的观察」强注入（高权重）
        - priority=low:  完全过滤（权重≈0，不再送入 API）
        """
        import requests as req

        url = self.api_url

        messages = []
        # 系统提示词
        messages.append({"role": "system", "content": self.system_prompt})

        # 处理带 priority 字段的记忆（与 cloud_API_chat / chat 同逻辑）
        high_observations = []
        for msg in (self.history or []):
            if not isinstance(msg, dict):
                messages.append(msg)
                continue
            pri = msg.get("priority")
            if pri == "high" and msg.get("content"):
                high_observations.append(msg.get("content", "").strip())
                continue  # 高权重消息不放进正常序列（单独强注入）
            if pri == "low":
                continue  # 低权重消息完全过滤
            messages.append(msg)

        # 高权重「最近的观察」强注入（仅本轮有高权重）
        if high_observations:
            obs_text = "\n".join(f"- {obs}" for obs in high_observations[-5:])
            messages.append({
                "role": "system",
                "content": (
                    "【最近的观察】你刚刚通过摄像头或屏幕看到了以下内容，"
                    "这是你亲眼所见的事实，请自然地融入接下来的对话：\n"
                    f"{obs_text}"
                ),
            })

        # 当前用户消息
        messages.append({"role": "user", "content": self.user_input})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.chat_model,
            "messages": messages,
            "max_tokens": 4096,
            "stream": True,
        }

        try:
            with req.post(url, json=payload, headers=headers, stream=True, timeout=(15, 300)) as resp:
                if resp.status_code != 200:
                    err_text = resp.text[:300]
                    print(f"[LongText] ⚠ API 错误 {resp.status_code}: {err_text}")
                    raise RuntimeError(f"API {resp.status_code}: {err_text}")

                # 逐行解析 SSE
                for line in resp.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break

                    import json as _json
                    try:
                        chunk = _json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        # 跳过 reasoning_content（思考过程）
                        if delta.get("reasoning_content"):
                            continue
                        content = delta.get("content")
                        if content:
                            yield content
                    except Exception:
                        continue

        except Exception as e:
            print(f"[LongText] ⚠ 流式请求异常: {e}")
            raise


# ══════════════════════════════════════════════════════════
# 播放管理（pygame.mixer 后台线程）
# ══════════════════════════════════════════════════════════

class LongTextPlayer(QObject):
    """
    后台线程持续从队列取 .wav 播放。
    关键：播放器只创建一次，暂停时用 pause() 而非销毁重建。
    """
    sentence_done = pyqtSignal()
    playback_started = pyqtSignal()

    def __init__(self, sample_rate=24000):
        super().__init__()
        self._queue = Queue()
        self._running = True
        self._sample_rate = sample_rate

        # pygame.mixer 只初始化一次
        try:
            pygame.mixer.quit()
        except Exception:
            pass
        pygame.mixer.init(frequency=self._sample_rate, size=-16, channels=2)

        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._thread.start()

    def _play_loop(self):
        while self._running:
            try:
                path = self._queue.get(block=True, timeout=0.5)
                if not os.path.exists(path) or os.path.getsize(path) == 0:
                    print(f"[player] ⚠ 文件不存在或为空，跳过: {path}")
                    # 关键修复：即使文件不存在也要 emit sentence_done，让文字继续推进
                    self.sentence_done.emit()
                    continue

                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                self.playback_started.emit()

                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)

                self.sentence_done.emit()

                # 播完清理
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass

            except Exception:
                pass

    def play_audio(self, path: str):
        self._queue.put(path)

    def pause(self):
        """暂停播放 + 清空队列，但保持线程运行（不销毁播放器）。"""
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        while not self._queue.empty():
            try:
                p = self._queue.get_nowait()
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    def is_idle(self):
        """播放队列空 且 当前没有在播放 → True"""
        try:
            return self._queue.empty() and not pygame.mixer.music.get_busy()
        except Exception:
            return self._queue.empty()

    def stop(self):
        self._running = False
        self.pause()


# ══════════════════════════════════════════════════════════
# 对外统一接口（供 murasame_class.py 使用）
# ══════════════════════════════════════════════════════════

class LongTextManager:
    """
    长文本模式总管理器：
    - 创建/管理 流式AI线程
    - 创建/管理 TTS 合成队列
    - 创建/管理 播放器

    模型来源：config.json 的 "longtext_model"（qwen / deepseek），
    由 longtext.model_config.get_longtext_model_config() 统一获取。
    """

    def __init__(self, api_key=None, chat_model=None, api_url=None):
        # 兼容旧调用：未传参时自动从 config 读取
        from longtext.model_config import get_longtext_model_config
        if api_key is None or chat_model is None or api_url is None:
            cfg = get_longtext_model_config()
            if cfg:
                api_key = cfg["api_key"]
                chat_model = cfg["model"]
                api_url = cfg["url"]
            else:
                api_key = api_key or ""
                chat_model = chat_model or "qwen-plus"
                api_url = api_url or "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

        self.api_key = api_key
        self.chat_model = chat_model
        self.api_url = api_url
        self.player = LongTextPlayer(sample_rate=24000)  # 只创建一次
        self.tts_queue = None  # 由 murasame_class 注入
        self.stream_thread = None

    def start_stream(self, history, user_input):
        """启动流式 AI 线程"""
        self.stop_stream()
        self.stream_thread = LongTextStreamThread(
            history=history,
            user_input=user_input,
            api_key=self.api_key,
            chat_model=self.chat_model,
            api_url=self.api_url,
        )
        return self.stream_thread

    def stop_stream(self):
        if self.stream_thread and self.stream_thread.isRunning():
            self.stream_thread.stop()
            self.stream_thread.wait(2000)
        self.stream_thread = None

    def shutdown(self):
        self.stop_stream()
        self.player.stop()