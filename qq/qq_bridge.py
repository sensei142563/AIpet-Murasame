# -*- coding: utf-8 -*-
"""
NapCat WebSocket 桥 — 连接 OneBot11 协议，收发 QQ 消息。

- 正向 WS（ws://127.0.0.1:3001）：接收 QQ 事件上报（消息/群@等）
- HTTP API（http://127.0.0.1:6099）：发送消息/图片/语音
  注意：6099 是 NapCat WebUI 面板端口，OneBot API 与 WS 同端。
  实际发消息通过 WS 发送 API 调用（send_msg 等），HTTP 备用。

实际实现：
- 连接正向 WebSocket 3001（OneBot11 事件上报 + API 调用共用）
- 收到私聊消息 → chat_once → 发文字 + 可选表情包 + 可选语音
  - 私聊：按标点切句逐条发送（模拟真人打字节奏）
  - 群聊：一次性发送完整回复
- 收到图片消息（私聊）→ qwen3-vl-plus 识别 → 注入对话回复
"""

import json
import os
import re
import time
import uuid
import threading
import requests
import websocket  # pip install websocket-client

from qq.qq_config import get_qq_config, STICKER_DIR, check_port_open, F5TTS_PORT
from qq.qq_chat import chat_once
from qq.qq_scheduler import MessageScheduler


def send_text(ws, text: str, message_type: str, target_id: int, self_id: int):
    """通过 WS 发送消息（正向 WebSocket 调用 API）"""
    payload = {
        "action": "send_msg",
        "params": {
            "message_type": message_type,
            "user_id" if message_type == "private" else "group_id": target_id,
            "message": text,
            "auto_escape": False,
        },
        "echo": f"send_{uuid.uuid4().hex[:8]}",
    }
    ws.send(json.dumps(payload, ensure_ascii=False))
    print(f"[QQBridge] → 发送文本到 {message_type}:{target_id}: {text[:40]}...")


def send_image(ws, image_path: str, message_type: str, target_id: int, self_id: int):
    """通过 WS 发送图片（本地文件路径）"""
    try:
        # 本地上传：NapCat 需要文件路径（绝对路径）
        payload = {
            "action": "send_msg",
            "params": {
                "message_type": message_type,
                "user_id" if message_type == "private" else "group_id": target_id,
                "message": [{"type": "image", "data": {"file": image_path}}],
            },
            "echo": f"send_img_{uuid.uuid4().hex[:8]}",
        }
        ws.send(json.dumps(payload, ensure_ascii=False))
        print(f"[QQBridge] → 发送图片: {os.path.basename(image_path)}")
    except Exception as e:
        print(f"[QQBridge] ⚠ 发送图片失败: {e}")


def send_voice(ws, voice_path: str, message_type: str, target_id: int, self_id: int):
    """通过 WS 发送语音（需 silk 格式；若为 wav 会尝试 NapCat 自动转换）"""
    try:
        payload = {
            "action": "send_msg",
            "params": {
                "message_type": message_type,
                "user_id" if message_type == "private" else "group_id": target_id,
                "message": [{"type": "record", "data": {"file": voice_path}}],
            },
            "echo": f"send_voice_{uuid.uuid4().hex[:8]}",
        }
        ws.send(json.dumps(payload, ensure_ascii=False))
        print(f"[QQBridge] → 发送语音: {os.path.basename(voice_path)}")
    except Exception as e:
        print(f"[QQBridge] ⚠ 发送语音失败: {e}")


def get_sticker_path(sticker_name: str):
    """根据表情包名返回文件路径（支持 gif/png/jpg；NapCat 富媒体不支持 avif）"""
    if not sticker_name:
        return None
    for ext in (".gif", ".png", ".jpg", ".jpeg"):
        p = os.path.join(STICKER_DIR, f"{sticker_name}{ext}")
        if os.path.exists(p):
            return p
    return None


# ── 私聊切句（按标点逐条发送）─────────────────────────────
# 强断句：句号/问号/感叹号/省略号/分号/换行（无条件切断）
_PRIVATE_STRONG_BREAKS = "。！？…；;\n"
# 右引号/闭标点（断句符后紧跟这些 → 并入前句）
_PRIVATE_RIGHT_QUOTES = {
    "\u201d",  # ” 中文右双引号
    "\u2019",  # ’ 中文右单引号
    "\u300d",  # 」 右方引号
    "\u300f",  # 』 右角引号
    "\u0022",  # " ASCII 双引号
    "\u0027",  # ' ASCII 单引号
}
_PRIVATE_MAX_LEN = 30  # 兜底强制切

# 私聊逐条发送间隔（秒）
_PRIVATE_SEND_INTERVAL = (0.6, 1.2)


def split_private_reply(reply: str):
    """
    将 AI 完整回复按强断句符切分为多条短消息。
    规则：
    - 强断句：。！？…；; 换行
    - 右引号随断句符并入前句
    - 不足 4 字的残段并入最后一条
    - 兜底 30 字强制切
    返回: [str, str, ...]
    """
    reply = (reply or "").strip()
    if not reply:
        return []

    clauses = []
    buffer = ""

    i = 0
    while i < len(reply):
        ch = reply[i]
        buffer += ch

        # 检查强断句符
        if ch in _PRIVATE_STRONG_BREAKS:
            # 并入后续右引号
            j = i + 1
            while j < len(reply) and reply[j] in _PRIVATE_RIGHT_QUOTES:
                buffer += reply[j]
                j += 1
            # 连续省略号
            while j < len(reply) and reply[j] == "\u2026":
                buffer += reply[j]
                j += 1
            i = j - 1
            # 切句（去掉首尾空白）
            clause = buffer.strip()
            if len(clause) >= 4:
                clauses.append(clause)
                buffer = ""
        # 兜底：超长无断句
        elif len(buffer) >= _PRIVATE_MAX_LEN:
            # 找最后一个逗号切（避免硬切）
            last_comma = max(buffer.rfind("，"), buffer.rfind(","), buffer.rfind("、"))
            if last_comma >= 4:
                clause = buffer[:last_comma + 1].strip()
                if clause:
                    clauses.append(clause)
                buffer = buffer[last_comma + 1:]
            else:
                clause = buffer.strip()
                if clause:
                    clauses.append(clause)
                buffer = ""
        i += 1

    # 剩余残段
    tail = buffer.strip()
    if tail:
        # 清理纯符号残留
        while tail and tail[0] in _PRIVATE_RIGHT_QUOTES:
            tail = tail[1:]
        if not tail:
            tail = ""
        if tail:
            if clauses:
                # 残段很短（<4字）→ 并入最后一条
                if len(tail) < 4:
                    clauses[-1] = clauses[-1] + tail
                else:
                    clauses.append(tail)
            else:
                clauses.append(tail)

    return clauses


class QQBotBridge:
    """NapCat 正向 WebSocket 桥接器"""

    def __init__(self):
        self.cfg = get_qq_config()
        self.ws_url = self.cfg["ws_url"]
        self.ws = None
        self.running = False
        self.self_id = None  # 登录的 QQ 号（识别是否自己发的消息）
        self._lock = threading.Lock()

        # 消息调度器：FIFO 队列 + 串行处理 + 会话合并
        self.scheduler = MessageScheduler(handler=self._handle_queued_message)

    def connect(self):
        """建立 WebSocket 连接并进入事件循环（阻塞）"""
        print(f"[QQBridge] 连接 NapCat: {self.ws_url}")
        self.ws = websocket.create_connection(
            self.ws_url, timeout=30, enable_multithread=True
        )
        self.running = True

        # 获取登录信息（确认 self_id）—— 与离线拉取同一线程串行 recv，避免竞争
        try:
            self.ws.send(json.dumps({"action": "get_login_info", "echo": "login_info"}))
        except Exception:
            pass
        # 处理后到达的响应（login_info）
        try:
            raw = self.ws.recv()
            if raw:
                self._handle(raw)
        except Exception:
            pass

        # 同步拉取离线消息（在 while 循环前，单线程 recv 无竞争）
        self._offline_stop = threading.Event()
        stray_events = []
        seen_ids = set()
        try:
            from qq.qq_offline import fetch_before_loop
            from qq.qq_config import load_config as _lc
            owner = str((_lc() or {}).get("qq_owner_id", ""))
            if owner:
                stray_events, seen_ids = fetch_before_loop(self.ws, owner, self.scheduler, self_id=self.self_id) or ([], set())
            else:
                print("[QQBridge] ⚠ 未配置 qq_owner_id，跳过离线拉取")
        except Exception as e:
            print(f"[QQBridge] ⚠ 离线拉取异常: {e}")

        # 离线拉取期间到达的实时消息事件 → 补处理（此前被丢弃导致漏回复/回错人）
        # 与历史里见过的 message_id 去重：同一消息已被离线路径回复过就不再重复处理
        for raw in stray_events:
            try:
                data = json.loads(raw)
                mid = data.get("message_id")
                if mid is not None and str(mid) in seen_ids:
                    print(f"[QQBridge] ↷ 跳过补处理（离线路径已处理）mid={mid}")
                    continue
                self._handle(raw)
            except Exception as e:
                print(f"[QQBridge] ⚠ 补处理离线期间事件失败: {e}")

        # 打印语音服务状态（实时检测，不依赖 __init__ 快照）
        if self.cfg["send_voice"]:
            if check_port_open(F5TTS_PORT):
                self.cfg["f5tts_ready"] = True
                print(f"[QQBridge] 🎙 F5-TTS 服务就绪（端口 {F5TTS_PORT}），语音消息已开启")
            else:
                self.cfg["f5tts_ready"] = False
                print(f"[QQBridge] ⚠ F5-TTS 服务未运行（端口 {F5TTS_PORT}），语音消息将自动跳过")

        if self.cfg["vision_enabled"]:
            print("[QQBridge] 👁 图片识别已开启（qq_vision_enabled=true）")

        # 语音识别开启 → 后台预加载 Whisper 模型（避免首条语音阻塞收包线程数十秒）
        if self.cfg.get("stt_enabled"):
            print("[QQBridge] 🎤 语音识别已开启（qq_stt_enabled=true），后台预加载模型...")
            threading.Thread(target=self._warm_stt, daemon=True).start()

        print("[QQBridge] ✅ WebSocket 已连接，等待消息...")
        while self.running:
            try:
                raw = self.ws.recv()
                if not raw:
                    continue
                self._handle(raw)
            except websocket.WebSocketTimeoutException:
                # 超时保活
                try:
                    self.ws.send(json.dumps({"action": "get_login_info", "echo": "ping"}))
                except Exception:
                    pass
            except Exception as e:
                print(f"[QQBridge] ⚠ 接收异常: {e}")
                break
        self.running = False
        print("[QQBridge] 连接已关闭")

    def _warm_stt(self):
        """后台预热 faster-whisper 模型（进程级单例，只加载一次）"""
        try:
            from tool.stt import warmup
            warmup()
        except Exception as e:
            print(f"[QQBridge] ⚠ 语音识别模型预热失败: {e}")

    def _handle(self, raw: str):
        """处理一条 WS 消息（JSON）"""
        try:
            data = json.loads(raw)
        except Exception:
            return

        # 响应（echo 匹配）→ 处理登录信息
        if "echo" in data and "data" in data:
            echo = data.get("echo", "")
            if echo == "login_info" and data.get("data"):
                info = data.get("data") or {}
                self.self_id = info.get("user_id")
                print(f"[QQBridge] 当前登录账号: {self.self_id} ({info.get('nickname', '')})")
            return

        # 事件上报
        post_type = data.get("post_type")
        if post_type != "message":
            return

        message_type = data.get("message_type")
        self_id = data.get("self_id")
        user_id = data.get("user_id")
        sender = data.get("sender", {})
        nickname = sender.get("nickname", "未知")
        group_id = data.get("group_id")
        raw_message = data.get("raw_message", "") or ""
        message = data.get("message", [])

        # 忽略自己发的消息
        if user_id == self.self_id:
            return

        from qq.qq_config import get_qq_config as _get_cfg
        cfg = _get_cfg()

        if message_type == "private":
            # 提取纯文本
            text = self._extract_text(message, raw_message)
            # 图片消息检测（私聊）
            vision_desc = None
            if cfg["vision_enabled"]:
                vision_desc = self._extract_private_image(message)
            # 语音消息识别（私聊）
            if cfg.get("stt_enabled", False):
                try:
                    from qq.qq_stt import extract_voice_path, transcribe_voice
                    vd = extract_voice_path(message)
                    if vd:
                        stt = transcribe_voice(vd, self.ws)
                        if stt:
                            text = (text + " " + stt).strip() if text.strip() else stt
                except Exception as e:
                    print(f"[QQBridge] ⚠ 语音识别异常: {e}")
            if not text.strip() and not vision_desc:
                return
            print(f"[QQBridge] 私聊 {nickname}({user_id}): {text[:40]}")
            # 入调度队列（session_key = private_<QQ号>，串行处理不乱）
            self.scheduler.enqueue({
                "session_key": f"private_{user_id}",
                "text": text,
                "user_id": user_id,
                "nickname": nickname,
                "group_id": None,
                "vision_desc": vision_desc,
            })
        elif message_type == "group":
            # 群聊：仅 @丛雨 时回复
            if not cfg["allow_groups"]:
                return
            if not self._is_at_me(message, self_id):
                return
            # 提取纯文本并去掉 @ 前缀后回复
            group_text = self._extract_text(message, raw_message)
            clean = self._strip_at(group_text)
            if not clean.strip():
                return
            print(f"[QQBridge] 群聊 {nickname}({user_id}) @丛雨: {clean[:40]}")
            # 入调度队列（session_key = group_<群号>）
            self.scheduler.enqueue({
                "session_key": f"group_{group_id}",
                "text": clean,
                "user_id": user_id,
                "nickname": nickname,
                "group_id": group_id,
                "vision_desc": None,
            })

    def _extract_text(self, message, raw_message):
        """
        从 message 段提取纯文本。
        纯图片/表情消息没有 text 段 → 返回空串（过滤掉所有 [CQ:...] 垃圾码）
        """
        texts = []
        if isinstance(message, list):
            for seg in message:
                if isinstance(seg, dict) and seg.get("type") == "text":
                    texts.append(seg.get("data", {}).get("text", ""))
        if texts:
            return "".join(texts)
        # 无 text 段 → 过滤 CQ 码后返回（避免 [CQ:image,file=...] 被当作对话文本）
        return re.sub(r"\[CQ:[^\]]*\]", "", raw_message or "").strip()

    def _extract_private_image(self, message):
        """
        提取私聊图片并识别。
        NapCat 的 image 段 file 常是 file_id（非本地路径）→ 用 get_image API 解析；
        返回: 识别描述文本；无图片/未启用/失败 → None。
        """
        try:
            from qq.qq_vision import (
                extract_image_path, describe_image, clean_vision_tmp,
                napcat_get_image, find_image_file_id,
            )
            print("[QQBridge] 👁 私聊图片消息，开始识图...")
            img_path = extract_image_path(message)
            stray = []
            if not img_path and self.ws:
                fid = find_image_file_id(message)
                if fid:
                    print(f"[QQBridge] 👁 本地无此文件，改用 NapCat get_image: {fid}")
                    img_path, stray = napcat_get_image(self.ws, fid)
            if not img_path:
                print("[QQBridge] ⚠ 无法取得图片（本地路径/URL/get_image 均失败），跳过识图")
                self._replay_stray(stray)
                return None
            print(f"[QQBridge] 👁 图片文件: {img_path}")
            desc = describe_image(img_path)
            # 清理临时文件（不删本地已有文件，只清我们下载的）
            clean_vision_tmp()
            self._replay_stray(stray)
            return desc or None
        except Exception as e:
            print(f"[QQBridge] ⚠ 图片识别异常: {e}")
            return None

    def _replay_stray(self, stray):
        """get_image 期间收到的实时事件 → 重新交给 _handle，保证不丢消息"""
        for raw in stray or []:
            try:
                self._handle(raw)
            except Exception as e:
                print(f"[QQBridge] ⚠ 补处理实时事件失败: {e}")

    def _is_at_me(self, message, self_id):
        """检查消息中是否 @ 了丛雨"""
        if isinstance(message, list):
            for seg in message:
                if isinstance(seg, dict) and seg.get("type") == "at":
                    qq = seg.get("data", {}).get("qq", "")
                    if qq and (str(qq) == str(self_id) or str(qq) == "all"):
                        return True
        # 兜底：raw_message 里包含 CQ:at 且 qq=self_id
        return False

    def _strip_at(self, text):
        """去除 @ 标记，保留正文"""
        import re
        text = re.sub(r"\[CQ:at[^\]]*\]", "", text)
        return text.strip()

    def _handle_queued_message(self, msg: dict):
        """
        调度器回调：串行处理一条（或合并后的）消息。
        msg 含: session_key / text / user_id / nickname / group_id / vision_desc
        """
        session_key = msg["session_key"]
        text = msg.get("text", "")
        vision_desc = msg.get("vision_desc")
        group_id = msg.get("group_id")
        user_id = msg.get("user_id")

        try:
            # 特殊指令处理（如 /clear 仅大号可用）
            try:
                from qq.qq_commands import handle_qq_command
                cmd_reply = handle_qq_command(text, session_key, user_id)
                if cmd_reply:
                    # 指令回复：一次性整条发送 + 不合成语音
                    if session_key.startswith("private_"):
                        self._send_command_reply(cmd_reply, user_id)
                    else:
                        self._send_group_command_reply(cmd_reply, user_id, group_id)
                    return
            except Exception as e:
                print(f"[QQBridge] ⚠ 指令处理异常: {e}")

            if session_key.startswith("private_"):
                user_id = msg["user_id"]
                print(f"[QQBridge] → 回复目标 private {user_id} (session={session_key})")
                reply, stickers = chat_once(
                    text,
                    use_sticker=self.cfg["send_sticker"],
                    vision_desc=vision_desc,
                    session_key=session_key,
                )
                if not reply:
                    return
                self._send_private_reply(reply, stickers, user_id)
            elif session_key.startswith("group_"):
                user_id = msg["user_id"]
                reply, stickers = chat_once(
                    text,
                    use_sticker=self.cfg["send_sticker"],
                    session_key=session_key,
                )
                if not reply:
                    return
                self._send_group_reply(reply, stickers, user_id, group_id)
        except Exception as e:
            print(f"[QQBridge] ⚠ 处理消息异常: {e}")

    def _send_command_reply(self, text, user_id):
        """指令回复：一次性整条发送（不分条、不语音）"""
        try:
            with self._lock:
                self.ws.send(json.dumps({
                    "action": "send_msg",
                    "params": {
                        "message_type": "private",
                        "user_id": user_id,
                        "message": text,
                    },
                    "echo": f"cmd_{uuid.uuid4().hex[:8]}",
                }, ensure_ascii=False))
                print(f"[QQBridge] → 指令回复 {user_id}: {text[:50]}...")
        except Exception as e:
            print(f"[QQBridge] ⚠ 指令回复失败: {e}")

    def _send_group_command_reply(self, text, user_id, group_id):
        """群聊指令回复：一次性整条发送（带 @）"""
        try:
            at_msg = f"[CQ:at,qq={user_id}] {text}"
            with self._lock:
                self.ws.send(json.dumps({
                    "action": "send_msg",
                    "params": {
                        "message_type": "group",
                        "group_id": group_id,
                        "message": at_msg,
                    },
                    "echo": f"cmd_{uuid.uuid4().hex[:8]}",
                }, ensure_ascii=False))
                print(f"[QQBridge] → 群指令回复 {user_id}: {text[:50]}...")
        except Exception as e:
            print(f"[QQBridge] ⚠ 群指令回复失败: {e}")

    def _send_private_reply(self, reply, stickers, user_id):
        """私聊回复：按标点切句逐条发送 + 可选表情包(0~2个)/语音"""
        clauses = split_private_reply(reply)
        if not clauses:
            return

        for idx, clause in enumerate(clauses):
            with self._lock:
                self.ws.send(json.dumps({
                    "action": "send_msg",
                    "params": {
                        "message_type": "private",
                        "user_id": user_id,
                        "message": clause,
                    },
                    "echo": f"reply_{uuid.uuid4().hex[:8]}",
                }, ensure_ascii=False))
                print(f"[QQBridge] → 私聊 {user_id} 第{idx+1}/{len(clauses)}句: {clause[:30]}...")

            # 句间间隔（模拟打字，最后一句后不需要等待）
            if idx < len(clauses) - 1:
                time.sleep(_PRIVATE_SEND_INTERVAL[0] + (_PRIVATE_SEND_INTERVAL[1] - _PRIVATE_SEND_INTERVAL[0]) * 0.3)

        # 表情包（最后一条文字后发送，0~2 个）
        for sticker in (stickers or []):
            path = get_sticker_path(sticker)
            if path:
                send_image(self.ws, path, "private", user_id, self.self_id)

        # 语音（可选）
        if self.cfg["send_voice"]:
            self._send_voice(reply, "private", user_id)

    def _send_group_reply(self, reply, stickers, user_id, group_id):
        """群聊回复：一次性发送完整回复 + 可选表情包(0~2个)/语音"""
        # 群聊回复时加 @ 提问者（一次性发送）
        at_msg = f"[CQ:at,qq={user_id}] {reply}"
        with self._lock:
            self.ws.send(json.dumps({
                "action": "send_msg",
                "params": {
                    "message_type": "group",
                    "group_id": group_id,
                    "message": at_msg,
                },
                "echo": f"reply_{uuid.uuid4().hex[:8]}",
            }, ensure_ascii=False))
        for sticker in (stickers or []):
            path = get_sticker_path(sticker)
            if path:
                send_image(self.ws, path, "group", group_id, self.self_id)
        if self.cfg["send_voice"]:
            self._send_voice(reply, "group", group_id)

    def _send_voice(self, text, message_type, target_id):
        """合成语音并发送（F5-TTS；服务未就绪自动跳过）"""
        # 实时检测 F5-TTS 服务（避免使用 __init__ 时的旧快照）
        if not check_port_open(F5TTS_PORT):
            self.cfg["f5tts_ready"] = False
            print(f"[QQBridge] ⚠ F5-TTS 服务未运行（端口 {F5TTS_PORT}），跳过语音发送")
            return
        self.cfg["f5tts_ready"] = True
        try:
            from longtext.longtext_tts import LongTextVoice
            import tempfile
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav", dir="tmp")
            path = tmp.name
            tmp.close()
            voice = LongTextVoice()
            # 完整合成整条回复（不截断，QQ 语音无字数限制）
            voice.say(text, save_path=path, callback=lambda: send_voice(
                self.ws, path, message_type, target_id, self.self_id
            ))
        except Exception as e:
            print(f"[QQBridge] ⚠ 语音合成失败（跳过）: {e}")

    def stop(self):
        """停止连接"""
        self.running = False
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        try:
            self.scheduler.stop()
        except Exception:
            pass
        try:
            from qq.qq_offline import save_last_exit_time
            save_last_exit_time()
        except Exception:
            pass
