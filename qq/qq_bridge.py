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
- 收到图片消息（私聊）→ 视觉模型识别（vision_model_name 配置）→ 注入对话回复
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

_RECENT_CUSTOM_STICKERS = []  # 最近发送过的自存表情文件（防连续重复发同一张）


def resolve_sticker_files(stickers):
    """解析表情发送文件列表：自存表情与默认表情随机混合（默认表情选择逻辑不变）。

    - 模型点名自存表情（[表情:自存名]）→ 直接发自存（原逻辑，不变）；
    - 模型点名默认表情 → 按名取默认文件（原逻辑，不变）；
    - 但自存池非空时，本轮以约 1/2 概率改成"从自存池随机挑"发送
      （群里学来的表情与默认表情随机混着用，增加灵动性、防呆板重复）；
    - 自存池随机时避开最近发过的，防同一张连发。
    返回 (文件路径列表, 是否含自定义)。"""
    import random as _rnd
    custom_files = []
    default_files = []
    custom_used = False
    try:
        from qq.qq_saved import sticker_file as _sf
        for name in (stickers or []):
            cp = _sf(name)
            if cp and os.path.exists(cp):
                custom_files.append(cp)
                custom_used = True
    except Exception:
        pass
    if custom_used:
        # 本轮含模型点名的自存表情 → 只发自存（防止刷屏；不影响以后轮次）
        return custom_files, True
    for name in (stickers or []):
        p = get_sticker_path(name)
        if p:
            default_files.append(p)
    # ── 随机混合：自存池非空时，一半概率改发自存池随机表情 ──
    try:
        from qq.qq_saved import names as _names, sticker_file as _sf2
        pool = []
        for _n in (_names("stickers") or []):
            _p = _sf2(_n)
            if _p and os.path.exists(_p):
                pool.append(_p)
        if pool and _rnd.random() < 0.5:
            fresh = [p for p in pool if p not in _RECENT_CUSTOM_STICKERS] or pool
            _rnd.shuffle(fresh)
            n = min(max(1, len(stickers or []) or 1), 2)  # 1~2 张，与原上限一致
            picked = fresh[:n]
            for p in picked:
                _RECENT_CUSTOM_STICKERS.append(p)
            del _RECENT_CUSTOM_STICKERS[:-10]
            return picked, True
    except Exception:
        pass
    return default_files, False




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


def cap_clauses_count(clauses, max_msgs):
    """单次回复最多发送条数（0=不限）：

    切句后条数超过 max_msgs 时，前 max_msgs-1 条原样逐条发送，
    其余句子全部合并进最后一条一起发——内容不丢失，且一次回复
    发出的消息条数不会超过配置的「每次对话最多回复次数」，
    避免"一次回复被拆成 5 句 = 用户看到回了好几次"。"""
    try:
        m = int(max_msgs or 0)
    except Exception:
        m = 0
    if m <= 0 or not clauses or len(clauses) <= m:
        return clauses
    return clauses[:m - 1] + ["".join(clauses[m - 1:])]


def split_sentences(reply: str):
    """只按【完整句子】边界切分（不切逗号/顿号，绝不把一句话拆到两条消息里）。

    规则：
    - 强断句：。！？…；; 换行（无条件切断）
    - 右引号/省略号随断句符并入前句
    - 不足 4 字的残段并入上一句（避免发出"嗯。"这种碎片单独成条）
    返回: [完整句子, ...]
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
        if ch in _PRIVATE_STRONG_BREAKS:
            j = i + 1
            while j < len(reply) and reply[j] in _PRIVATE_RIGHT_QUOTES:
                buffer += reply[j]
                j += 1
            while j < len(reply) and reply[j] == "\u2026":
                buffer += reply[j]
                j += 1
            i = j - 1
            clause = buffer.strip()
            if clause:
                if len(clause) < 4 and clauses:
                    clauses[-1] = clauses[-1] + clause
                else:
                    clauses.append(clause)
            buffer = ""
        i += 1
    rest = buffer.strip()
    if rest:
        if len(rest) < 4 and clauses:
            clauses[-1] = clauses[-1] + rest
        else:
            clauses.append(rest)
    return clauses


def split_by_char_limit(text, limit, max_parts=3):
    """按「单次回复字数上限」把回复切成若干条短消息。

    设计原则（用户要求）：
    - 只按【完整句子】边界切分，绝不把一句话拆成两条消息（不出现断句）；
    - 每条尽量不超过 limit 字（limit<=0 表示不限，原样返回）；
    - 条数不超过 max_parts（=「单条回复最多发几条消息」这个硬上限），
      超出时把句子并入相邻条（内容不丢），绝不为了凑条数把句子切开。
    """
    text = (text or "").strip()
    if not text:
        return []
    try:
        lim = int(limit or 0)
    except Exception:
        lim = 0
    if lim <= 0:
        return [text]
    clauses = split_sentences(text) or [text]
    # ① 贪心打包：每段尽量贴近但不超过 limit
    parts = []
    for c in clauses:
        if parts and len(parts[-1]) + len(c) <= lim:
            parts[-1] = parts[-1] + c
        else:
            parts.append(c)
    try:
        mp = max(1, int(max_parts or 1))
    except Exception:
        mp = 1
    if len(parts) <= mp:
        return [p for p in parts if p]
    # ② 条数超上限（硬限制）：按句子边界合并到 mp 条以内，长度按剩余内容均摊。
    #    合并后单条可能超过 limit 字 —— 这是"字数上限"与"条数上限"冲突时的
    #    必要取舍：宁可单条长一点，也不断句、不少说（模型侧已按 条数×字数
    #    的总预算要求表达，实际很少触发）。
    merged = []
    i, remaining, left = 0, mp, sum(len(c) for c in clauses)
    while i < len(clauses) and len(merged) < mp:
        target = max(lim, -(-left // max(1, remaining)))
        cur = clauses[i]
        i += 1
        while i < len(clauses) and len(cur) + len(clauses[i]) <= target:
            cur += clauses[i]
            i += 1
        merged.append(cur)
        left -= len(cur)
        remaining -= 1
    if i < len(clauses):                      # 兜底：剩余句子并入最后一条
        merged[-1] = merged[-1] + "".join(clauses[i:])
    return [p for p in merged if p]


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
        self.self_nick = ""  # 登录昵称（让 AI 记住"自己是谁"，防止认不出自己）
        self._lock = threading.Lock()
        self._send_fail_count = 0  # 断线窗口内发送失败计数（重连成功后清零）
        self._stt_warm_started = False  # 语音模型预热只做一次（重连循环避免反复下载/刷屏）

        # 消息调度器：FIFO 队列 + 串行处理 + 会话合并
        self.scheduler = MessageScheduler(handler=self._handle_queued_message)

        # ===== 空闲自动离线（PCL 设置开关，默认关 = 始终活跃）=====
        # 主人白名单（qq_owner_id + qq_master_ids，最多 5 个）；第一位 = 主主人
        self._master_ids = []
        try:
            from qq.qq_config import get_qq_config as _gqc
            self._master_ids = list(_gqc().get("master_ids") or [])
        except Exception:
            self._master_ids = []
        self._owner_id = self._master_ids[0] if self._master_ids else None
        self._activity_lock = threading.Lock()
        self._last_activity = time.time()  # 最近一次有效对话时间（收到消息/发出回复）
        self._offline_mode = False         # 当前是否处于自动离线（离开）状态
        self._watcher_started = False

        # ===== 活泼模式（群聊间歇接话，活跃群气氛）=====
        self._groups_lock = threading.Lock()
        self._group_buf = {}               # group_id -> {last_others, last_bot_talk, recent[]}
        self._lively_last_global = 0.0     # 全局最近一次活泼发言时间（防刷屏）
        # ===== QQ 会话活性自愈（防"平台下线但 NapCat 无感"的假死）=====
        self._health_seq = 0               # 探针序号
        self._health_pending = 0.0         # 最近一次探针发出时间(0=无在途)
        self._health_fail = 0              # 连续失败次数
        self._last_recover_ts = 0.0        # 上次自动重启 NapCat 时间（冷却防循环）
        self._last_scan_hint_ts = 0.0      # 上次扫码提示时间（防刷屏）
        self._napcat_log_pos = {}          # NapCat 日志已扫描到的字节偏移（只看新增内容）
        # ===== 自主学习（官方插件）限流状态 =====
        self._learn_media_ts = {}   # gid -> 上次学习群媒体时间
        self._learn_link_ts = {}    # gid -> 上次学习链接时间

        # ===== 对话调节（设置 → QQ配置）=====
        # （单条回复条数/字数限制见 _reply_limits/_cap_reply 与发送层 cap_clauses_count；
        #   无"N轮后静默"——那会导致聊几句后 bot 不再回话，用户明确不需要）
        self._seen_msg = {}    # message_id -> 到达时间（活消息去重，防重复回复）

        # ===== 群名缓存（get_group_info 异步查询，供身份标识使用）=====
        self._group_names_lock = threading.Lock()
        self._group_names = {}             # str(group_id) -> group_name
        self._group_names_pending = set()  # 已请求过、等待响应的群（防止重复请求）

        # ===== 主人昵称学习（识别"有人喊主人的 QQ 名字"场景，防认不出主人）=====
        self._master_nicks_lock = threading.Lock()
        self._master_nicks = {}            # str(QQ号) -> {昵称/群名片, ...}

    def connect(self):
        """建立 WebSocket 连接并进入事件循环（阻塞）。

        关键健壮性（面向 A 卡/NapCat 未熟配置的用户）：
        - 连接前先等待 NapCat WS 端口就绪（不 ready 则提示并重试，而非直接 Connection refused）
        - 主循环因任何原因断开后自动重连（不再一断就静默退出）
        """
        self.running = True  # 先置 running，_reconnect_loop 的 while 才会进入
        # 后台守护线程：空闲自动离线 + 活泼模式（只启动一次，重连期间持续运行）
        if not self._watcher_started:
            self._watcher_started = True
            threading.Thread(target=self._background_watcher, daemon=True,
                             name="QQBackgroundWatcher").start()
        host, port = self._ws_url_parts()
        if port and not self._napcat_ready(port, host=host):
            print(f"[QQBridge] ⏳ 等待 NapCat 就绪（{host}:{port}）..."
                  "若一直卡在这里，说明 NapCat 未正常启动/扫码，请运行 start_napcat.bat 并扫码登录。")
        self._reconnect_loop()

    @staticmethod
    def _ws_url_parts():
        """从 ws_url 解析 (host, port)（默认 127.0.0.1:3001）"""
        try:
            import urllib.parse as up
            u = up.urlparse(get_qq_config()["ws_url"])
            return (u.hostname or "127.0.0.1"), (u.port or 3001)
        except Exception:
            return "127.0.0.1", 3001

    @staticmethod
    def _ws_port():
        """从 ws_url 提取端口（默认 3001）"""
        return QQBotBridge._ws_url_parts()[1]

    @staticmethod
    def _napcat_ready(port, host="127.0.0.1", timeout=2, max_wait=30):
        """等待 NapCat WS 端口可连接（最多 max_wait 秒；host 跟随 ws_url，支持局域网部署）"""
        import socket as _sock
        import time as _t
        t0 = _t.time()
        while _t.time() - t0 < max_wait:
            try:
                with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as s:
                    s.settimeout(timeout)
                    return s.connect_ex((host, port)) == 0
            except Exception:
                pass
            _t.sleep(1)
        return False

    def _ws_auth_headers(self):
        """NapCat 正向 WS 开启 token 鉴权时的握手头。

        token 来源：config.json 的 qq_napcat_token；**没配就自动去 NapCat 自己的
        onebot11_*.json 里读**（仅本机地址）——NapCat 重装/重置会随机换 token，
        自动读取可以免掉"连上就断"这类故障。未拿到 token 时返回 None（兼容未开鉴权的 NapCat）。
        """
        token = str(self.cfg.get("napcat_token", "") or "").strip()
        if not token:
            try:
                from qq.qq_config import discover_ws_token
                token = discover_ws_token(self.ws_url) or ""
                if token:
                    self._auto_token = token
                    self.cfg["napcat_token"] = token      # 本次运行内复用
            except Exception as e:
                print(f"[QQBridge] ⚠ 自动获取 token 失败: {e}")
        if token:
            return [f"Authorization: Bearer {token}"]
        return None

    def _warn_auth_failed(self, raw: str = ""):
        """识别 NapCat 的 token 鉴权失败（retcode 1403）并说清楚怎么修。

        NapCat 开启 token 后，握手不带/带错 token 时它**不是拒绝连接**，而是先接受、
        再回一帧 {"status":"failed","retcode":1403,"message":"token验证失败"} 然后断开 →
        以前只会看到「接收异常: Connection is closed」，完全看不出原因。
        """
        try:
            from qq.qq_config import discover_ws_token
            good = discover_ws_token(self.ws_url) or ""
        except Exception:
            good = ""
        print("[QQBridge] ❌ NapCat 返回 retcode 1403：WS token 验证失败（连接被立即关闭）")
        if good:
            print(f"[QQBridge] 🔑 从 NapCat 配置里读到正确 token：{good}")
            print("[QQBridge] → 已自动切换使用该 token（下一次重连生效）；"
                  "如需固定，可写入 config.json: \"qq_napcat_token\": \"" + good + "\"")
        else:
            print("[QQBridge] → 请在 config.json 里配置 qq_napcat_token，"
                  "或确认 NapCat 的 onebot11_*.json 里的 websocketServers.token")
        # 丢掉可能过期的 token，下次重连重新发现（NapCat 换 token 后能自愈）
        try:
            self.cfg["napcat_token"] = ""
            self._auto_token = ""
        except Exception:
            pass
        if raw:
            print(f"[QQBridge] 原始响应: {str(raw)[:200]}")

    def _reconnect_loop(self):
        """断开后自动重连（不退出），给用户 NapCat 就绪时间窗口"""
        delay = 5
        while self.running:
            try:
                print(f"[QQBridge] 连接 NapCat: {self.ws_url}")
                self.ws = websocket.create_connection(
                    self.ws_url, timeout=30, enable_multithread=True,
                    header=self._ws_auth_headers(),
                )
                self._on_connected()   # 内部处理 login_info + 离线补拉 + 进入事件循环（阻塞）
                # 正常走到这里说明事件循环因断开退出 → 重置 delay 后重连
                if not self.running:
                    break
                print("[QQBridge] 连接断开，5 秒后自动重连...")
                delay = 5
                time.sleep(delay)
            except Exception as e:
                print(f"[QQBridge] ⚠ 连接失败: {e}")
                if not self._sleep(delay):
                    break
                # 指数退避，最多 30 秒
                delay = min(30, delay * 2)

    def _sleep(self, secs):
        import time as _t
        t0 = _t.time()
        while self.running and _t.time() - t0 < secs:
            _t.sleep(0.5)
        return self.running

    # ===== 空闲自动离线 + 活泼模式 =====

    def _is_owner(self, user_id) -> bool:
        """该消息是否来自主人白名单成员（自动离线的唤醒入口、主人功能判定）"""
        return bool(self._master_ids) and user_id is not None and str(user_id) in self._master_ids

    def _learn_master_nick(self, user_id, nick):
        """记录主人名单成员的昵称/群名片（有人喊主人的 QQ 名字时要认得出）"""
        try:
            qq = str(user_id or "").strip()
            n = str(nick or "").strip()
            if not qq or not n or n in ("未知", "群友", "对方"):
                return
            with self._master_nicks_lock:
                s = self._master_nicks.setdefault(qq, set())
                s.add(n)
        except Exception:
            pass

    def _master_nicks_snapshot(self):
        """主人昵称映射快照 {QQ: [昵称,...]}（供 chat_once 注入对照表）"""
        try:
            with self._master_nicks_lock:
                return {k: sorted(v) for k, v in self._master_nicks.items() if v}
        except Exception:
            return None

    def _master_mention_note(self, text):
        """消息文本里提到主人昵称时给出对照注记（防认不出主人）。
        返回如：『（注：「申余不是鱼」是主人 QQ 1851959578 的名字，提到 ta 就是在说你的主人）』"""
        try:
            t = str(text or "")
            if not t:
                return ""
            hits = []
            with self._master_nicks_lock:
                for qq, nicks in self._master_nicks.items():
                    for n in nicks:
                        if n and n in t:
                            hits.append(f"「{n}」是主人 QQ {qq} 的名字")
                            break
            if hits:
                return "（注：" + "；".join(hits) + "，提到 ta 就是在说你的主人）"
        except Exception:
            pass
        return ""

    @staticmethod
    def _media_from_speaker(item, user_id) -> bool:
        """媒体条目是否由该发言者本人发出（who 形如『（主人）@昵称(QQ号)』）。
        用于收紧"群最近媒体"注入：只注入发言者自己发的图/视频，
        避免把别人发的表情包算到当前说话人头上（用户反馈的"回错人"问题）。"""
        try:
            who = (item or {}).get("who") or ""
            m = re.search(r"\((\d+)\)\s*$", who)
            if not m:
                return False
            return str(m.group(1)) == str(user_id)
        except Exception:
            return False

    def _touch_activity(self):
        """记录一次有效活动（收到主人消息/正常对话）——空闲计时据此重置"""
        with self._activity_lock:
            self._last_activity = time.time()

    # ================= 对话调节（设置 → QQ配置） =================
    # 「每次对话最多回复次数」= 单条 AI 回复最多拆成几条消息发送
    # （私聊发送层用 cap_clauses_count 合并，见 _send_private_reply）。
    # 注意：不做「N 轮后静默」——那会导致聊几句后 bot 不再回话（用户明确不要）。
    @staticmethod
    def _reply_limits():
        """实时读取对话调节配置（运行中修改即时生效，不依赖启动快照）。
        返回 (max_replies_per_conversation, max_reply_chars)，0=不限。"""
        try:
            from qq.qq_config import get_qq_config as _gqc
            c = _gqc()
            return (int(c.get("max_replies_per_conversation") or 0),
                    int(c.get("max_reply_chars") or 0))
        except Exception:
            return 0, 0

    def _reply_parts(self, reply, max_parts=3, hard_limit=None):
        """把回复按「单次回复字数上限」拆成若干条短消息（不砍半句话，内容不丢）。

        - 字数在限制内：原样一条发出（模型被要求"在限制内把意思表达完整"）；
        - 超限：按句子边界拆成最多 max_parts 条（默认 2~3 条），逐条发送；
        - 限制为 0（不限）：原样一条；
        - 「每次对话最多回复次数」配置了条数上限时，分条数不超过它（多出的并入最后一条）；
        - hard_limit：强制上限（活泼模式防刷屏用，与配置上限取较小值）。"""
        try:
            _msgs, m = self._reply_limits()
        except Exception:
            _msgs, m = 0, 0
        if hard_limit:
            try:
                m = min(m, int(hard_limit)) if m > 0 else int(hard_limit)
            except Exception:
                m = int(hard_limit)
        mp = max(1, int(max_parts or 1))
        try:
            if _msgs and int(_msgs) > 0:
                mp = min(mp, int(_msgs))
        except Exception:
            pass
        try:
            return split_by_char_limit(reply, m, mp) or ([reply] if reply else [])
        except Exception:
            return [reply] if reply else []

    def _private_reply_allowed(self, user_id, sub_type=None) -> bool:
        """私信回复范围（启动器 设置→QQ；改动即时生效，无需重启 QQ）：

        - qq_private_enable         总开关（false = 完全不回私信，含主人）
        - qq_private_master_only    true = 只回主人私信（覆盖下面两项）
        - qq_private_reply_friend   是否回好友私信（sub_type=friend/group 视为好友）
        - qq_private_reply_stranger 是否回陌生人私信（非好友/临时会话）
        主人始终在允许范围内（除非总开关关闭）。"""
        try:
            from qq.qq_config import get_qq_config
            c = get_qq_config()
            if not c.get("private_enable", True):
                return False
            if self._is_owner(user_id):
                return True
            if c.get("private_master_only"):
                return False
            is_friend = str(sub_type or "").strip().lower() in ("friend", "group")
            if is_friend:
                return bool(c.get("private_reply_friend", True))
            return bool(c.get("private_reply_stranger", True))
        except Exception as e:
            print(f"[QQBridge] ⚠ 私信范围判定失败（按允许处理）: {e}")
            return True

    def _cap_reply(self, reply):
        """（保留旧接口）单次回复字数上限：不再硬截断句子——
        实际发送由 _reply_parts / 发送层按句子边界分条，内容不丢。"""
        return reply

    def _apply_cloth_marker(self, reply):
        """解析 AI 回复里的 [换装:制服|睡衣|私服|刀服] 标记：
        保存装扮到【当前立绘类型（a/b）】（桌宠 + QQ 立绘同步生效、持久化），
        并从文本中移除标记。仅当标记里的服装可识别时才处理，避免误删正常文本。"""
        try:
            import re as _re
            text = str(reply or "")
            m = _re.search(r"[\[【]\s*换装\s*[:：]\s*([^\]】]{1,8})\s*[\]】]", text)
            if not m:
                return reply
            from tool.portrait_outfit import resolve_cloth, save_outfit, active_set
            name = resolve_cloth(m.group(1))
            if name and save_outfit(name, set_name=active_set()):
                print(f"[QQBridge] 👗 AI 自主换装: {name}（{active_set()} 立绘 · 桌宠同步）")
                text = _re.sub(r"[\[【]\s*换装\s*[:：]\s*[^\]】]{1,8}\s*[\]】]", "", text).strip()
                return text
        except Exception as e:
            print(f"[QQBridge] ⚠ 换装标记处理失败: {e}")
        return reply

    def _dedupe_msg(self, message_id) -> bool:
        """活消息去重：NapCat 偶发同一条消息上报两次（或与补拉撞车）。
        返回 True = 该 message_id 近期已见过（应跳过，防止重复回复）。"""
        if message_id is None:
            return False
        now = time.time()
        prev = self._seen_msg.get(message_id)
        if prev is not None and now - prev < 120:
            return True
        self._seen_msg[message_id] = now
        if len(self._seen_msg) > 1000:
            for k in [k for k, v in self._seen_msg.items() if now - v > 300]:
                self._seen_msg.pop(k, None)
        return False

    def _set_qq_online_status(self, status) -> bool:
        """把 QQ 在线状态设为 status（10=在线 30=离开 40=隐身 60=Q我吧 等）。
        仅作展示状态切换，不改变 WS 连接。"""
        return self._safe_send({
            "action": "set_online_status",
            "params": {"status": int(status), "ext_status": 0, "battery_status": 0},
            "echo": f"status_{uuid.uuid4().hex[:8]}",
        }, label="状态设置 ")

    def _wake_from_offline(self):
        """主人来消息 → 恢复在线状态并清除离线标志"""
        if not self._offline_mode:
            return
        self._offline_mode = False
        print("[QQBridge] 🌞 主人来消息了，已恢复在线状态")
        self._set_qq_online_status(10)

    def _enter_auto_offline(self):
        """空闲超时 → 自动进入离线（离开）模式：暂停自动回复，主人消息可唤醒"""
        self._offline_mode = True
        minutes = self.cfg.get("auto_offline_minutes", 30)
        print(f"[QQBridge] 🌙 已空闲 {minutes} 分钟，自动进入离线模式"
              "（QQ 状态=离开，暂停自动回复；主人发消息立即恢复在线）")
        self._set_qq_online_status(30)

    @staticmethod
    def _message_has_image(message) -> bool:
        """消息段是否含图片（仅判断类型，不下载不识别）"""
        if not isinstance(message, list):
            return False
        return any(isinstance(s, dict) and s.get("type") == "image" for s in message)

    @staticmethod
    def _message_has_video(message) -> bool:
        """消息段是否含视频（仅判断类型，不下载不识别）"""
        if not isinstance(message, list):
            return False
        return any(isinstance(s, dict) and s.get("type") == "video" for s in message)

    def _extract_private_video(self, message, allow_ws=False):
        """
        提取视频并识别（下载 → 抽帧 → 视觉模型描述）。
        与图片不同：视频文件大、抽帧耗时，URL 下载线程安全；
        无本地文件且无 URL（file_id-only）时跳过（不占用 WS）。"""
        try:
            from qq.qq_vision import extract_video_path, describe_video, clean_vision_tmp
            if not self._message_has_video(message):
                return None
            print("[QQBridge] 🎬 视频消息，开始识别...")
            vpath = extract_video_path(message)
            if not vpath:
                print("[QQBridge] ⚠ 视频无本地文件且无下载 URL，跳过识别")
                return None
            print(f"[QQBridge] 🎬 视频文件: {vpath}")
            desc = describe_video(vpath)
            clean_vision_tmp()
            # 清理下载的视频本体（帧已在 describe_video 内清理）
            try:
                if vpath and os.path.exists(vpath):
                    os.remove(vpath)
            except Exception:
                pass
            return desc or None
        except Exception as e:
            print(f"[QQBridge] ⚠ 视频识别异常: {e}")
            return None

    def _note_group_media(self, group_id, message, user_id=None, nickname=None):
        """记录某群最近一条图片/视频消息段（供回复前识图/识视频注入）。

        只保存消息段元数据(体积小)，识别在调度线程延迟执行；
        图/视频分别记录 last_img 与 last_video，互不覆盖；
        同时记录发送者身份（昵称+是否主人）——回复注入时带上"谁发的"，
        防止模型把别人发的图当成主人发的而叫错人。"""
        try:
            if not isinstance(message, list):
                return
            # 防御：绝不记录 bot 自己发的图/表情包（否则后续回复会"识别到自己发的表情包"）
            if user_id is not None and self.self_id is not None \
                    and str(user_id) == str(self.self_id):
                return
            with self._groups_lock:
                g = self._group_buf.setdefault(str(group_id), {
                    "last_others": 0.0,
                    "last_bot_talk": 0.0,
                    "recent": [],          # 最近若干条他人文本（带 @QQ号 硬标识）
                    "name": self._group_display_name(group_id),
                })
                now = time.time()
                # 发送者标注：与 recent 硬标识风格一致 → 模型不会叫错主人
                who = None
                is_master = False
                if user_id is not None:
                    try:
                        uin = str(user_id)
                        nick = (nickname or "") or f"QQ {uin}"
                        who = f"{nick}({uin})"
                        is_master = self._is_owner(user_id)
                    except Exception:
                        pass
                media = {"t": now, "message": message, "who": who, "is_master": is_master}
                if self._message_has_image(message):
                    g["last_img"] = dict(media)
                if self._message_has_video(message):
                    g["last_video"] = dict(media)
        except Exception as e:
            print(f"[QQBridge] ⚠ 记录群媒体失败: {e}")

    def _media_note_sentence(self, kind, desc, item):
        """构造注入附注：识别结果 + 发送者身份（防叫错人/混淆）。
        kind: "image"/"video"；item 含 who/is_master（可为 None → 泛称"有人"）。
        例：（群里 @阿明(123) 发了一张图片，内容大概是：…）/（群里（主人）@小鱼(456) 发了一段视频…）"""
        verb = "发了一张图片" if kind == "image" else "发了一段视频"
        sender = self._media_sender_label(item)
        subj = f"{sender} " if sender else "有人 "
        return f"（群里{subj}{verb}，内容大概是：{desc}）"

    @staticmethod
    def _media_sender_label(item) -> str:
        """媒体发送者的模型可读标注（与群聊 recent 的「主人」硬标识风格一致）。
        返回如「（主人）@昵称(QQ号)」或「@昵称(QQ号)」；无发送者信息返回空串。"""
        try:
            who = (item or {}).get("who")
            if not who:
                return ""
            master_tag = "（主人）" if (item or {}).get("is_master") else ""
            return f"{master_tag}@{who}"
        except Exception:
            return ""

    # ================= 自主学习（官方插件）辅助 =================
    def _maybe_learn_group_link(self, group_id, user_id, nickname, text):
        """群链接学习：打开链接提取内容入库(每群 5 分钟限流, 异步)"""
        import urllib.parse as _up
        m_url = None
        try:
            import re as _re
            m_url = _re.search(r"https?://[^\s，。、；：！？（）<一-鿿]+", text)
        except Exception:
            return
        if not m_url:
            return
        now = time.time()
        if now - self._learn_link_ts.get(str(group_id), 0) < 300:
            return
        self._learn_link_ts[str(group_id)] = now
        url = m_url.group(0)
        import threading as _th
        _th.Thread(target=self._learn_link_worker, args=(group_id, user_id, nickname, url),
                   daemon=True).start()

    def _learn_link_worker(self, group_id, user_id, nickname, url):
        try:
            from qq.qq_search import read_link
            from qq.qq_learnstore import add_link
            info = read_link(url) or ""
            title = ""
            for line in (info or "").split(chr(10)):
                if line.startswith("【链接·"):
                    title = line
                    break
            add_link(group_id, f"{nickname}({user_id})", title or url[:60], url, info[:200])
            print(f"[QQBridge] 🧠 已学习群链接: {url[:60]}")
        except Exception:
            pass

    def _maybe_learn_group_media(self, group_id, user_id, nickname, message):
        """群图片/视频学习：异步识别入库(图片每群10分钟限流2次, 视频每15分钟1次)"""
        if not self._message_has_image(message) and not self._message_has_video(message):
            return
        now = time.time()
        key = str(group_id)
        rec = self._learn_media_ts.get(key, [0, 0])  # [图片次数时间, 视频时间]
        try:
            if self._message_has_video(message):
                if now - float(rec[1]) < 900:
                    return
                rec[1] = now
                self._learn_media_ts[key] = rec
            else:
                if now - float(rec[0]) < 300:
                    return
                rec[0] = now
                self._learn_media_ts[key] = rec
        except Exception:
            pass
        import threading as _th
        _th.Thread(target=self._learn_media_worker,
                   args=(group_id, user_id, nickname, message), daemon=True).start()

    def _learn_media_worker(self, group_id, user_id, nickname, message):
        try:
            from qq.qq_learnstore import add_media
            if self._message_has_video(message):
                desc = self._extract_private_video(message, allow_ws=False) or ""
                kind = "video"
            else:
                desc = self._extract_private_image(message, allow_ws=False) or ""
                kind = "image"
            if desc:
                add_media(group_id, f"{nickname}({user_id})", kind, desc)
                print(f"[QQBridge] 🧠 已学习群{kind}: {desc[:40]}")
            # 自主学习·表情收藏：群里的动画表情包 → 自动存入自存表情池，
            # 供以后发送时随机使用（增加灵动性；受开关/限流/总数上限约束）
            if kind == "image" and desc:
                self._maybe_autosave_sticker(message, desc)
        except Exception:
            pass

    @staticmethod
    def _sticker_url_from_seg(message):
        """从消息段取「表情包」图片的 (url, summary)；非表情返回 (None, '')。
        判定：QQ 动画表情/贴纸（sub_type==1、summary 含"表情"或 .gif 结尾）。"""
        try:
            for seg in (message or []):
                if not isinstance(seg, dict) or seg.get("type") != "image":
                    continue
                d = seg.get("data") or {}
                url = str(d.get("url") or "")
                summary = str(d.get("summary") or "")
                sub = str(d.get("sub_type", ""))
                f = str(d.get("file") or "")
                is_sticker = (sub == "1") or ("表情" in summary) \
                    or f.lower().endswith(".gif") \
                    or url.lower().split("?")[0].endswith(".gif")
                if is_sticker and url:
                    return url, summary
        except Exception:
            pass
        return None, ""

    def _maybe_autosave_sticker(self, message, desc):
        """自主学习：把群里的动画表情自动收藏进自存表情池（以后可随机发送）。
        受配置开关（qq_auto_learn_sticker_save，默认开）与 10 个上限约束；
        超限时优先淘汰更早的自动收藏（不挤掉用户手动收藏）。"""
        try:
            from qq.qq_config import get_qq_config as _g
            if not _g().get("auto_learn_sticker_save", True):
                return
            url, _summary = self._sticker_url_from_seg(message)
            if not url:
                return
            from qq.qq_saved import add_sticker
            # 命名简洁（"群表情/群表情2…"），完整描述存 desc 供模型选择发送时机
            item = add_sticker(url=url, name="群表情", desc=(desc or "")[:40], auto=True)
            if item:
                print(f"[QQBridge] 😊 自主学习已收藏表情「{item['name']}」（以后可随机发送）")
            else:
                print(f"[QQBridge] ⚠ 表情收藏失败（下载/保存未成功）: {url[:60]}")
        except Exception as e:
            print(f"[QQBridge] ⚠ 表情收藏异常: {e}")

    def _group_recent_image_desc(self, group_id, img_ref=None, max_age=240):
        """回复群消息前识别一张图（须在调度线程内调用；只走本地路径/URL，线程安全）。

        - img_ref 由入队时快照（该群当时最近一张图）——避免回复排队期间群里
          又有人发新图导致"识别成别人发的图"；None 表示实时取当前最近一张
          （活泼接话等无快照场景）；
        - 图片 4 分钟内有效（太久远不强行关联当前话题）；
        - 识别成功即清理：仅当缓存里仍是同一张图时移除（新图不误删）；
        - 失败/超时/无图返回 (None, None)，不阻塞正常回复。
        返回 (描述文本, 媒体条目含发送者信息 who/is_master)。"""
        try:
            gid = str(group_id)
            if img_ref is None:
                with self._groups_lock:
                    g = self._group_buf.get(gid)
                    if not g or not g.get("last_img"):
                        return None, None
                    item = g["last_img"]
                    if time.time() - item["t"] > max_age:
                        g.pop("last_img", None)
                        return None, None
                print(f"[QQBridge] 👁 群{gid} 近期有人发图，回复前识图...")
            else:
                item = img_ref
                if time.time() - item.get("t", 0) > max_age:
                    return None, None
                print(f"[QQBridge] 👁 群{gid} 入队时快照图片，回复前识图...")
            message = item["message"]
            # 调度线程内不能独占 ws.recv() → 只走本地路径/URL(线程安全)
            desc = self._extract_private_image(message, allow_ws=False)
            if desc:
                with self._groups_lock:
                    g = self._group_buf.get(gid)
                    # 仅当缓存仍是同一张图才清除，避免误删排队期间的新图
                    if g and g.get("last_img") is item:
                        g.pop("last_img", None)  # 已用掉，描述已随回复进记忆
                return desc, item
            return None, None
        except Exception as e:
            print(f"[QQBridge] ⚠ 群图片识别异常: {e}")
            return None, None

    def _group_recent_video_desc(self, group_id, vid_ref=None, max_age=600):
        """回复群消息前识别一段群视频（调度线程内调用；本地/URL 下载，线程安全）。

        - vid_ref 为入队时快照（防排队期间新视频串位），None=实时取（活泼接话）；
        - 视频比图片时效放宽到 10 分钟（大文件下载+抽帧耗时，且话题延续更久）；
        - 识别成功仅当缓存仍是同一段视频时清理；
        - 失败/超时/无视频一律返回 None，不阻塞正常回复。"""
        try:
            gid = str(group_id)
            if vid_ref is None:
                with self._groups_lock:
                    g = self._group_buf.get(gid)
                    if not g or not g.get("last_video"):
                        return None, None
                    item = g["last_video"]
                    if time.time() - item["t"] > max_age:
                        g.pop("last_video", None)
                        return None, None
                print(f"[QQBridge] 🎬 群{gid} 近期有人发视频，回复前识别...")
            else:
                item = vid_ref
                if time.time() - item.get("t", 0) > max_age:
                    return None, None
                print(f"[QQBridge] 🎬 群{gid} 入队时快照视频，回复前识别...")
            message = item["message"]
            desc = self._extract_private_video(message, allow_ws=False)
            if desc:
                with self._groups_lock:
                    g = self._group_buf.get(gid)
                    if g and g.get("last_video") is item:
                        g.pop("last_video", None)
                return desc, item
            return None, None, None
        except Exception as e:
            print(f"[QQBridge] ⚠ 群视频识别异常: {e}")
            return None, None, None

    def _note_group_chat(self, group_id, user_id, nickname, text):
        """记录某群的一条他人消息文本（活泼模式的发言素材）。

        说话人统一硬标识：白名单主人 →「（主人）@昵称(QQ号)」；
        非白名单 →「@昵称(QQ号)」——让模型明确知道说话人身份，不会乱喊主人。"""
        try:
            content = (text or "").strip()
            if not content:
                content = "[图片/表情]"
            if len(content) > 60:
                content = content[:60] + "…"
            with self._groups_lock:
                g = self._group_buf.setdefault(str(group_id), {
                    "last_others": 0.0,    # 群里最近一次他人消息时间
                    "last_bot_talk": 0.0,  # bot 最近一次主动活泼发言时间
                    "recent": [],          # 最近若干条他人文本（带 @QQ号 硬标识）
                    "name": self._group_display_name(group_id),
                })
                g["last_others"] = time.time()
                # 统一「@昵称(QQ号)」标识；白名单主人额外加「（主人）」前缀
                master_tag = "（主人）" if self._is_owner(user_id) else ""
                who = f"{master_tag}@{nickname or '群友'}({user_id})"
                g["recent"].append(f"{who}: {content}")
                g["recent"] = g["recent"][-6:]
        except Exception as e:
            print(f"[QQBridge] ⚠ 记录群聊内容失败: {e}")

    def _ensure_group_name(self, group_id):
        """群名缓存：未知名则向 NapCat 异步查询一次 get_group_info（不阻塞收包线程）"""
        gid = str(group_id)
        with self._group_names_lock:
            if gid in self._group_names or gid in self._group_names_pending:
                return
            self._group_names_pending.add(gid)
        self._safe_send({
            "action": "get_group_info",
            "params": {"group_id": int(group_id)},
            "echo": f"grpname_{gid}",
        }, label="群名查询 ")

    def _group_display_name(self, group_id) -> str:
        """群显示名：缓存群名优先，未知名用群号兜底"""
        gid = str(group_id)
        with self._group_names_lock:
            return self._group_names.get(gid) or f"群{gid}"

    def _lively_tick(self):
        """活泼模式判定：找「最近有人说话 + 冷却已过 + 上次发言后又有人说话」的群，
        把一条主动接话任务交给调度队列（与正常回复完全串行，防记忆并发）"""
        try:
            # 运行中改配置也即时生效（get_qq_config 实时读 config.json）
            from qq.qq_config import get_qq_config as _cfg
            c = _cfg()
            if not (c.get("lively_enabled") and c.get("allow_groups")):
                return
            now = time.time()
            interval = float(c.get("lively_interval", 15)) * 60
            with self._groups_lock:
                candidates = []
                for gid, g in self._group_buf.items():
                    if now - g.get("last_others", 0) > 600:
                        continue  # 该群最近 10 分钟没人说话，不打扰
                    if not g.get("recent"):
                        continue
                    if now - g.get("last_bot_talk", 0) < interval:
                        continue  # 冷却未到
                    if g.get("last_others", 0) <= g.get("last_bot_talk", 0):
                        continue  # bot 上次发言后群里没有新动静（防自言自语）
                    candidates.append((g.get("last_others", 0), gid, g["recent"]))
            if not candidates:
                return
            # 全局防刷屏：两次主动活泼发言至少间隔 3 分钟
            if now - self._lively_last_global < 180:
                return
            # 选最近最热的群
            candidates.sort(key=lambda x: x[0], reverse=True)
            _, gid, recent = candidates[0]
            self._lively_last_global = now
            with self._groups_lock:
                buf = self._group_buf.get(str(gid))
                if buf:
                    buf["last_bot_talk"] = now
            print(f"[QQBridge] 🎉 活泼模式：群 {gid} 有新话题，主动接话")
            self.scheduler.enqueue({
                # 独立会话前缀，不与同群正常 @ 回复合并
                "session_key": f"lively_{gid}",
                "text": "\n".join(recent),
                "group_id": gid,
                "lively": True,
            })
        except Exception as e:
            print(f"[QQBridge] ⚠ 活泼模式判定失败: {e}")

    # ================= QQ 会话活性探测 & 自动自愈 =================
    def _health_tick(self):
        """每 20s 由后台守护调用：探测 QQ 会话活性，检测到平台下线(NapCat 无感)
        时自动重启 NapCat 并（如需要扫码）弹码提示。
        核心判据：get_status 的 online 字段（QQ 真掉线时为 false，
        而 get_login_info 在掉线后仍会成功返回缓存的登录信息，不可靠）。"""
        now = time.time()
        # 无在途探针且距上次 >=50s → 发探针(get_status)
        if self._health_pending == 0 and now - self._last_recover_ts >= 50:
            self._health_seq += 1
            self._health_pending = now
            try:
                _sent = self._safe_send({
                    "action": "get_status",
                    "echo": f"health_{self._health_seq}",
                }, label="活性探测 ")
                if not _sent:
                    # WS 未连接/发送失败(重连中) → 不计失败，等重连后再探
                    self._health_pending = 0
            except Exception:
                self._health_pending = 0
        # 判据A：NapCat 日志出现下线通知(平台踢下线必写) → 立即计数
        if self._scan_napcat_logs():
            self._health_fail += 1
            print(f"[QQBridge] ❤️ 检测到 NapCat 下线通知({self._health_fail}/2)")
            if self._health_fail >= 2:
                self._health_fail = 0
                self._auto_recover_qq()
            return
        # 判据B：在途探针超时(90s 未收到对应 echo) → 失败计数(辅助，防日志漏报)
        if self._health_pending and now - self._health_pending > 90:
            self._health_fail += 1
            print(f"[QQBridge] ❤️ 活性探测超时({self._health_fail}/2)，疑似 QQ 会话失效")
            self._health_pending = 0
            if self._health_fail >= 2:
                self._health_fail = 0
                self._auto_recover_qq()
        # 长时间无任何真实消息事件(30分钟)且探测正常 → 重置计时即可(群静默正常)

    def _scan_napcat_logs(self) -> bool:
        """扫描 NapCat 日志【新增内容】：出现平台下线/登录失效通知 → True。

        这是 QQ 被平台踢下线时 NapCat 必写的日志（实测为中文"账号状态变更为离线"），
        比 API 探针可靠（get_login_info 掉线后仍会成功）。

        ⚠ 只看「上次扫描之后新增的字节」（首次见到某文件时从当前末尾开始）：
        旧实现每次读文件尾部 4KB 做关键词匹配，NapCat 日志里历史的下线/超时行
        会在 65 分钟 mtime 窗口内被反复命中 → 假报"下线"→ 误重启 NapCat
        → 用户白白重新扫码。现在只认新写入的内容，杜绝这种误伤。"""
        import glob as _glob
        try:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            now = time.time()
            kws = ("KickedOffLine", "下线通知", "登录已失效", "身份已失效",
                   "账号当前登录已失效", "请重新登录",
                   "账号状态变更为离线", "变更为离线",
                   # 会话假死伴随错误：QQ 内核已下线时 sendMsg 会超时（NTEvent Timeout）
                   "Timeout: NTEvent", "NodeIKernelMsgService/sendMsg")
            files = (_glob.glob(os.path.join(base, "tmp", "napcat_run*.log"))
                     + _glob.glob(os.path.join(base, "tmp", "napcat_auto.log"))
                     + _glob.glob(os.path.join(base, "tmp", "napcat_manual.log")))
            for fp in files:
                try:
                    st = os.stat(fp)
                    if now - st.st_mtime > 3900:
                        continue  # 65 分钟内无新写入（NapCat 心跳每小时一次）
                    size = st.st_size
                    if fp not in self._napcat_log_pos:
                        # 首次见到：只从当前末尾开始看，忽略历史内容
                        self._napcat_log_pos[fp] = size
                        continue
                    pos = self._napcat_log_pos[fp]
                    if pos > size:      # 日志被重写/轮转 → 从头看
                        pos = 0
                    if size - pos < 8:
                        continue        # 没有新增内容
                    with open(fp, "rb") as f:
                        f.seek(pos)
                        chunk = f.read(200000)
                    self._napcat_log_pos[fp] = pos + len(chunk)
                    text = chunk.decode("utf-8", errors="replace")
                    if any(k in text for k in kws):
                        print(f"[QQBridge] 🔎 {os.path.basename(fp)} 新增日志命中下线特征")
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _health_ok(self, seq, data=None):
        """收到探针响应：online=true 清零失败计数；
        online=false → QQ 已被平台下线(NapCat 进程无感) → 计数触发自愈。"""
        try:
            if int(seq) != self._health_seq:
                return
            self._health_pending = 0
            online = None
            if isinstance(data, dict):
                online = data.get("online")
            if online is False:
                self._health_fail += 1
                print(f"[QQBridge] ❤️ 检测到 QQ 账号离线(online=false，{self._health_fail}/2)")
                if self._health_fail >= 2:
                    self._health_fail = 0
                    self._auto_recover_qq()
                return
            self._health_fail = 0
        except Exception:
            pass

    def _auto_recover_qq(self):
        """QQ 会话死亡自愈：冷却后杀 NapCat 全家 → 重启 launcher-user.bat →
        等待自动登录；若需扫码则自动弹码提示(图片+弹窗)。"""
        now = time.time()
        if now - self._last_recover_ts < 1500:  # 25 分钟冷却，防循环
            print("[QQBridge] ❤️ 距上次自动恢复不足 25 分钟，跳过(避免循环)")
            return
        # 若 NapCat 活着且正在等扫码（端口未就绪 + 二维码近 10 分钟有更新）：
        # 不重启——重启会作废当前二维码，导致用户反复扫到过期码永远登不上。
        if self._napcat_waiting_scan():
            print("[QQBridge] ❤️ NapCat 正在等待扫码（二维码新鲜），跳过重启，仅提示扫码")
            self._prompt_scan()
            return
        self._last_recover_ts = now
        # 备份掉线现场日志（自愈重启会用 'wb' 覆盖日志，导致掉线原因事后不可查）
        self._backup_napcat_logs(tag="offline")
        print("[QQBridge] ❤️ 检测到 QQ 会话失效，开始自动重启 NapCat...")
        import threading as _th
        _th.Thread(target=self._recover_worker, daemon=True,
                   name="QQAutoRecover").start()

    def _napcat_waiting_scan(self) -> bool:
        """NapCat 进程活着、3001 未监听、且二维码文件近 10 分钟刚更新 → 正在等扫码。
        此时不能重启 NapCat（会作废用户正在扫的二维码）。"""
        try:
            import socket as _s
            with _s.socket(_s.AF_INET, _s.SOCK_STREAM) as sd:
                sd.settimeout(1.5)
                if sd.connect_ex(("127.0.0.1", 3001)) == 0:
                    return False  # 端口通 → 已登录，无需扫码
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            qr = os.path.join(base, "NapCat.Shell.Windows.OneKey", "NapCat",
                              "cache", "qrcode.png")
            if not os.path.exists(qr):
                return False
            # NapCat 进程在吗（QQ 是它的子进程，注入启动）
            import subprocess as _sp
            r = _sp.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Process -Filter \"Name='NapCatWinBootMain.exe'\" | Measure-Object).Count"],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
            if (r.stdout or "").strip() in ("", "0"):
                return False
            return (time.time() - os.path.getmtime(qr)) < 600
        except Exception:
            return False

    @staticmethod
    def _backup_napcat_logs(tag="offline"):
        """掉线现场备份：把当前 NapCat 日志复制到 tmp/napcat_crash_backup/（带时间戳）。
        自愈重启会用 'wb' 模式覆盖 napcat_auto.log，导致掉线原因事后不可查。"""
        try:
            import shutil
            import datetime as _dt
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            src_dir = os.path.join(base, "tmp")
            dst_dir = os.path.join(src_dir, "napcat_crash_backup")
            os.makedirs(dst_dir, exist_ok=True)
            ts = _dt.datetime.now().strftime("%m%d_%H%M%S")
            for name in ("napcat_auto.log", "napcat_manual.log"):
                src = os.path.join(src_dir, name)
                try:
                    if os.path.exists(src) and os.path.getsize(src) > 0:
                        shutil.copy2(src, os.path.join(dst_dir, f"{tag}_{ts}_{name}"))
                except Exception:
                    continue
            # 只保留最近 30 个备份，防无限堆积
            try:
                files = sorted(
                    [os.path.join(dst_dir, f) for f in os.listdir(dst_dir)],
                    key=lambda p: os.path.getmtime(p))
                for p in files[:-30]:
                    os.remove(p)
            except Exception:
                pass
        except Exception:
            pass

    def _recover_worker(self):
        """在独立线程执行恢复流程(不阻塞后台守护)"""
        import subprocess as _sp
        import os as _os
        base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        try:
            # 1. 杀 NapCat 全家(D:\QQ 注入链 + 引导器)
            _sp.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process | Where-Object { "
                 "$_.Name -eq 'NapCatWinBootMain.exe' -or "
                 "($_.Name -eq 'QQ.exe' -and $_.ExecutablePath -like 'D:\QQ\*') } | "
                 "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                capture_output=True, timeout=20,
                creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
            time.sleep(4)
        except Exception as e:
            print(f"[QQBridge] ❤️ 停止旧 NapCat 失败: {e}")
        # 2. 启动 launcher-user.bat(隐藏+日志)
        try:
            nc_dir = _os.path.join(base, "NapCat.Shell.Windows.OneKey", "NapCat")
            logf = _os.path.join(base, "tmp", "napcat_auto.log")
            _sp.Popen(["cmd.exe", "/c", "launcher-user.bat"],
                      cwd=nc_dir,
                      creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0),
                      stdout=open(logf, "wb"), stderr=_sp.STDOUT)
            print("[QQBridge] ❤️ 已重启 NapCat，等待自动登录...")
        except Exception as e:
            print(f"[QQBridge] ❤️ 启动 NapCat 失败: {e}")
            return
        # 3. 等待恢复：最多 90s；未登录(在弹码)则提示扫码
        ok = False
        deadline = time.time() + 90
        while time.time() < deadline and not ok:
            time.sleep(5)
            try:
                import socket as _sock
                with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as sd:
                    sd.settimeout(2)
                    if sd.connect_ex(("127.0.0.1", 3001)) != 0:
                        continue
                # 3001 通 → 探测登录态
                import websocket as _ws, json as _json
                w = _ws.create_connection("ws://127.0.0.1:3001",
                                          header=["Authorization: Bearer " + self._napcat_token()],
                                          timeout=5)
                w.send(_json.dumps({"action": "get_login_info", "echo": "h1"}))
                try:
                    m = _json.loads(w.recv())
                    if m.get("echo") == "h1" and m.get("data"):
                        ok = True
                except Exception:
                    pass
                w.close()
            except Exception:
                pass
        if ok:
            print("[QQBridge] ❤️ NapCat 自动恢复成功(已登录)")
            return
        # 未登录 → 弹码提示
        print("[QQBridge] ❤️ NapCat 需要重新扫码授权，弹出二维码提示...")
        self._prompt_scan()
        # 继续等待(10 分钟内每 30s 探测一次，登录成功则结束)
        deadline2 = time.time() + 600
        while time.time() < deadline2 and not ok:
            time.sleep(30)
            try:
                import socket as _sock
                with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as sd:
                    sd.settimeout(2)
                    if sd.connect_ex(("127.0.0.1", 3001)) != 0:
                        continue
                import websocket as _ws, json as _json
                w = _ws.create_connection("ws://127.0.0.1:3001",
                                          header=["Authorization: Bearer " + self._napcat_token()],
                                          timeout=5)
                w.send(_json.dumps({"action": "get_login_info", "echo": "h2"}))
                try:
                    m = _json.loads(w.recv())
                    if m.get("echo") == "h2" and m.get("data"):
                        ok = True
                except Exception:
                    pass
                w.close()
            except Exception:
                pass
            if not ok:
                self._prompt_scan(force=True)
        print("[QQBridge] ❤️ 扫码恢复流程结束" + ("(已登录)" if ok else "(仍未登录，请手动处理)"))

    def _play_music_worker(self, keyword, ctx):
        """点歌线程：网易云搜索 → 下载转wav → 发record(QQ语音) → 文本回执"""
        session_key, user_id, group_id = ctx
        try:
            from qq.qq_music import search as _msearch, download_wav as _mdl
            hits = _msearch(keyword, 3)
            if not hits:
                self._send_music_text("没搜到《" + keyword[:30] + "》相关歌曲，换个歌名试试？", ctx)
                return
            hit = hits[0]
            wav = _mdl(hit["id"])
            if not wav:
                self._send_music_text("歌曲下载失败（可能受版权限制），换一首试试？", ctx)
                return
            title = str(hit.get("name", "")) + " - " + str(hit.get("artists") or "未知")
            try:
                if session_key.startswith("private_"):
                    send_voice(self.ws, wav, "private", int(user_id), self.self_id)
                else:
                    send_voice(self.ws, wav, "group", int(group_id), self.self_id)
            except Exception as e:
                print(f"[QQBridge] ⚠ 点歌语音发送失败: {e}")
                self._send_music_text("语音发送失败，稍后再试试？", ctx)
                self._del_wav(wav)
                return
            # 延迟清理：NapCat 收包后异步读文件转码上传，立即删会让它读不到文件而静默丢弃
            # （点歌语音历史 bug 根因）。成功发送后 90 秒再删，既保发送成功又不留残留。
            try:
                import threading as _th
                _th.Timer(90.0, self._del_wav, args=(wav,)).start()
            except Exception:
                pass
            self._send_music_text("🎵 已为你点播《" + title[:60] + "》", ctx)

        except Exception as e:
            print(f"[QQBridge] ⚠ 点歌失败: {e}")
            self._send_music_text("点歌出了点问题，稍后再试试？", ctx)

    def _del_wav(self, wav):
        """清理点歌临时音频"""
        try:
            if wav and os.path.exists(wav):
                os.remove(wav)
        except Exception:
            pass

    def _send_music_text(self, text, ctx):
        """点歌回执文本(线程内调用)"""
        try:
            session_key, user_id, group_id = ctx
            if session_key.startswith("private_"):
                self._send_command_reply(text, user_id)
            else:
                self._send_group_command_reply(text, user_id, group_id)
        except Exception as e:
            print(f"[QQBridge] ⚠ 点歌回执失败: {e}")

    def _napcat_token(self) -> str:
        """HTTP API 用的同一份 token（config.json 优先，缺省时自动从 NapCat 配置读取）"""
        try:
            tok = str(self.cfg.get("napcat_token", "") or "").strip()
            if tok:
                return tok
            from qq.qq_config import get_qq_token
            return get_qq_token(getattr(self, "ws_url", "") or "") or ""
        except Exception:
            return ""

    def _prompt_scan(self, force=False):
        """弹出二维码提示：打开二维码图片(屏幕可见) + 系统弹窗(防刷屏)"""
        try:
            import subprocess as _sp
            import os as _os
            base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
            qr = _os.path.join(base, "NapCat.Shell.Windows.OneKey", "NapCat",
                               "cache", "qrcode.png")
            now = time.time()
            if now - self._last_scan_hint_ts > 90 or force:
                self._last_scan_hint_ts = now
                if _os.path.exists(qr):
                    _sp.Popen(["cmd.exe", "/c", "start", "", qr],
                              creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
                try:
                    _sp.run(
                        ["powershell", "-NoProfile", "-Command",
                         "Add-Type -AssemblyName System.Windows.Forms;"
                         "[System.Windows.Forms.MessageBox]::Show("
                         "'NapCat 登录失效，已自动重启并弹出二维码，请用手机QQ扫码授权后继续使用。',"
                         "'QQ 需重新扫码')"],
                        capture_output=True, timeout=15,
                        creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
                except Exception:
                    pass
                print("[QQBridge] ❤️ 已提示扫码(二维码图片已打开)")
        except Exception as e:
            print(f"[QQBridge] ❤️ 扫码提示失败: {e}")

    def _background_watcher(self):
        """后台守护线程：空闲自动离线（+活泼模式），每 20 秒轮询一次"""
        print("[QQBridge] 🔧 后台守护已启动（空闲自动离线 / 活泼模式）")
        warned_no_owner = False
        while self.running:
            try:
                from qq.qq_config import get_qq_config as _cfg
                c = _cfg()
                if c.get("auto_offline_enabled"):
                    if not self._offline_mode:
                        if self._owner_id:
                            with self._activity_lock:
                                idle_secs = time.time() - self._last_activity
                            if idle_secs >= float(c.get("auto_offline_minutes", 30)) * 60:
                                self._enter_auto_offline()
                        elif not warned_no_owner:
                            # 未配置主人 QQ 号 → 无唤醒入口，宁可不自动离线
                            warned_no_owner = True
                            print("[QQBridge] ⚠ 未配置主人 QQ 号（qq_owner_id），空闲自动离线已跳过")
                else:
                    # 运行中关闭开关 → 立即恢复在线（不再离线）
                    if self._offline_mode:
                        self._offline_mode = False
                        print("[QQBridge] ☀️ 自动离线已关闭，恢复在线状态")
                        self._set_qq_online_status(10)
                # 活泼模式：离线期间不主动发言
                if not self._offline_mode:
                    self._lively_tick()
            except Exception as e:
                print(f"[QQBridge] ⚠ 后台守护异常: {e}")
            try:
                self._health_tick()
            except Exception as _he:
                print(f"[QQBridge] ⚠ 健康检查异常: {_he}")
            self._sleep(20)

    def _handle_lively(self, msg: dict):
        """活泼模式发言：把群话题交给角色生成一句自然的话，直接发到群里（不带 @）。
        已由调度队列串行执行，不会与正常回复/记忆并发。
        对话调节：发言同样受单次回复字数上限约束（无轮数静默）。"""
        try:
            group_id = msg.get("group_id")
            topic = (msg.get("text") or "").strip()
            if not group_id or not topic:
                return
            # 输入 = 群里刚才的聊天记录（他人所说，带 @QQ号 硬标识）；
            # 「主动接话」情景与自我回顾由 chat_once 的 lively 语境注入（不进记忆）
            group_name = self._group_display_name(group_id)
            user_input = f"（{group_name}里刚才的聊天记录）\n" + topic
            # 群媒体识别：接话前检测本群最近图片/视频（如大家在聊一张图/一段视频），
            # 识别附注带上"谁发的"（主人用（主人）标记，防叫错人）；失败静默不阻塞接话
            try:
                d, item = self._group_recent_image_desc(group_id)
                if d:
                    user_input += "\n" + self._media_note_sentence("image", d, item)
                else:
                    d2, item2 = self._group_recent_video_desc(group_id)
                    if d2:
                        user_input += "\n" + self._media_note_sentence("video", d2, item2)
            except Exception as e:
                print(f"[QQBridge] ⚠ 活泼媒体识别失败(忽略): {e}")
            reply, stickers, portrait_emo = chat_once(
                user_input,
                use_sticker=self.cfg["send_sticker"],
                session_key=f"group_{group_id}",  # 与 @ 回复共用群记忆 → 上下文连贯
                lively=True,
                group_name=group_name,
                master_nicks=self._master_nicks_snapshot(),
                self_id=self.self_id,
                self_nick=self.self_nick,
            )
            if not reply:
                return
            reply = reply.strip()
            # 只过滤 API 失败兜底文案（"（AI 暂时开小差了…）"这类）：整条很短 且 命中兜底特征。
            # 注意此前"长度>200 就丢弃"是误杀——活泼接话正常写超 200 字时发言被吃掉
            # （日志大量"活泼发言异常文案，跳过"的根因）；长文应截断发送而非丢弃。
            _api_fluff = ("（AI", "（网络", "（未配置", "（什么都没说")
            _is_fluff = (len(reply) < 80) and (
                reply.startswith(_api_fluff) or "开小差" in reply)
            if _is_fluff:
                print(f"[QQBridge] ⚠ 活泼发言为 API 兜底文案，跳过: {reply[:30]}")
                return
                # 对话调节：单次回复字数上限（0=不限）；活泼发言额外兜底 200 字防刷屏
                # —— 超限不再硬截断，改为按句子边界拆成至多 2 条短消息发出（内容不丢）
                reply = self._apply_cloth_marker(reply)
                lively_parts = self._reply_parts(reply, 2, hard_limit=200) or [reply]
                ok = True
                for _i, _part in enumerate(lively_parts):
                    ok = self._safe_send({
                        "action": "send_msg",
                        "params": {
                            "message_type": "group",
                            "group_id": int(group_id),
                            "message": _part,
                        },
                        "echo": f"lively_{uuid.uuid4().hex[:8]}",
                    }, label=f"活泼群{group_id} ")
                    if not ok:
                        break
                    _tag = f"（{_i+1}/{len(lively_parts)}）" if len(lively_parts) > 1 else ""
                    print(f"[QQBridge] 🎉 活泼群 {group_id} 发言{_tag}: {_part[:40]}...")
                    if _i < len(lively_parts) - 1:
                        time.sleep(_PRIVATE_SEND_INTERVAL[0])
                if ok:
                    reply = lively_parts[0]
            # ⚠ 表情包开关关闭时不发（连自存池随机逻辑都不执行）——见 _stickers_on()
            for path in (resolve_sticker_files(stickers)[0] if self._stickers_on() else []):
                if path:
                    try:
                        send_image(self.ws, path, "group", int(group_id), self.self_id)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[QQBridge] ⚠ 活泼发言失败: {e}")

    def _on_connected(self):
        """连接建立后的初始化 + 事件循环（原 connect 主体，改为可被重连循环调用）"""
        self.running = True
        # 重连成功：QQ 重新登录默认在线，清除离线模式标记
        if self._offline_mode:
            self._offline_mode = False
            print("[QQBridge] 🔗 重连成功，退出离线模式")
        # 重连成功：若此前有发送失败，提示一次并清零计数
        if self._send_fail_count > 0:
            print(f"[QQBridge] 🔗 已重新连接（此前断线期间 {self._send_fail_count} 次回复未送达，请对方重发）")
            self._send_fail_count = 0

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
                stray_events, seen_ids = fetch_before_loop(self.ws, owner, self.scheduler,
                                                           self_id=self.self_id,
                                                           private_filter=self._private_reply_allowed) or ([], set())
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

        # 语音识别开启 → 后台预加载 Whisper 模型（避免首条语音阻塞收包线程数十秒）。
        # 只预热一次：断线自动重连会反复进入本函数，重复预热会每 5 秒尝试一次模型下载
        # （HuggingFace 不可达时刷屏 + 线程堆积）
        if self.cfg.get("stt_enabled") and not self._stt_warm_started:
            self._stt_warm_started = True
            print("[QQBridge] 🎤 语音识别已开启（qq_stt_enabled=true），后台预加载模型...")
            threading.Thread(target=self._warm_stt, daemon=True).start()

        print("[QQBridge] ✅ WebSocket 已连接，等待消息...")
        while self.running:
            try:
                raw = self.ws.recv()
                if not raw:
                    continue
                # NapCat 鉴权失败：连上后第一帧就是 retcode 1403 → 说清原因再断
                if "1403" in raw and "\"retcode\"" in raw:
                    self._warn_auth_failed(raw)
                    break
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
        # 断开后不置 running=False——由 _reconnect_loop 判断并自动重连。
        # 仅当外部调用 stop()（running=False）时才真正退出。
        try:
            self.ws.close()
        except Exception:
            pass
        print("[QQBridge] 连接已断开（将由重连循环自动恢复）")

    def _warm_stt(self):
        """后台预热 faster-whisper 模型（进程级单例，只加载一次）"""
        try:
            # 模型已本地缓存（首次由镜像下载）：离线模式加载，避免每次联网探测
            # huggingface.co（本机不可达）导致预热失败
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
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

        # 响应（echo 匹配）→ 处理登录信息 / 群名查询结果
        if "echo" in data and "data" in data:
            echo = data.get("echo", "")
            if echo.startswith("health_"):
                # 活性探针响应(get_status) → online 判定 + 清零/计数
                try:
                    self._health_ok(echo[len("health_"):], data.get("data"))
                except Exception:
                    pass
            elif echo == "login_info" and data.get("data"):
                info = data.get("data") or {}
                self.self_id = info.get("user_id")
                self.self_nick = str(info.get("nickname") or "").strip()
                print(f"[QQBridge] 当前登录账号: {self.self_id} ({self.self_nick})")
                # 主动查询主人名单成员的昵称（有人喊主人的 QQ 名字时要认得出，
                # 不必等主人先发言）
                try:
                    for _m in (self._master_ids or []):
                        try:
                            self._safe_send({
                                "action": "get_stranger_info",
                                "params": {"user_id": int(_m)},
                                "echo": f"mstnick_{_m}",
                            }, label="主人昵称查询 ")
                        except Exception:
                            pass
                except Exception:
                    pass
            elif echo.startswith("mstnick_"):
                qq = echo[len("mstnick_"):]
                info = data.get("data") or {}
                nk = info.get("nick") or info.get("nickname") or ""
                if nk:
                    self._learn_master_nick(qq, nk)
                    print(f"[QQBridge] 🏷 主人 QQ {qq} 的昵称: {nk}")
            elif echo.startswith("grpname_"):
                gid = echo[len("grpname_"):]
                info = data.get("data") or {}
                gname = (info or {}).get("group_name") or ""
                with self._group_names_lock:
                    self._group_names_pending.discard(gid)
                    if gname:
                        self._group_names[gid] = gname
                # 同步到活泼群缓冲（后续接话带群名）
                with self._groups_lock:
                    buf = self._group_buf.get(gid)
                    if buf and gname:
                        buf["name"] = gname
                if gname:
                    print(f"[QQBridge] 群名缓存: {gid} -> {gname}")
            return

        # 事件上报
        post_type = data.get("post_type")
        if post_type != "message":
            return

        message_type = data.get("message_type")
        self_id = data.get("self_id")
        user_id = data.get("user_id")
        message_id = data.get("message_id")
        sender = data.get("sender", {})
        nickname = sender.get("nickname", "未知")
        # 群聊中优先用「群名片/群昵称」（card），让 bot 称呼对方时用 ta 在群里的名字，不认错人
        if message_type == "group":
            _card = (sender.get("card") or "").strip()
            if _card:
                nickname = _card
        group_id = data.get("group_id")
        raw_message = data.get("raw_message", "") or ""
        message = data.get("message", [])

        # 忽略自己发的消息（self.self_id 未就绪时用上报自带的 self_id 兜底，
        # 否则启动早期会把自己发的表情包/图片当成他人消息记录并识别 → 回复自己的表情包）
        _self_keys = set()
        for _x in (self.self_id, data.get("self_id")):
            if _x is not None:
                _self_keys.add(str(_x))
        if user_id is not None and str(user_id) in _self_keys:
            return

        # 学习主人名单成员的昵称/群名片（识别"有人喊主人的 QQ 名字"场景）
        if nickname and self._is_owner(user_id):
            self._learn_master_nick(user_id, nickname)

        # 活消息去重：同一条 message_id 短时间内重复上报 → 跳过（防重复回复同一问题）
        if self._dedupe_msg(message_id):
            print(f"[QQBridge] 忽略重复上报 message_id={message_id}（{nickname}）")
            return

        # ===== 空闲自动离线：离线期间只被「主人私聊 / 主人在群里点名 @」唤醒 =====
        if self._offline_mode:
            if message_type == "private":
                if not self._is_owner(user_id):
                    print(f"[QQBridge] 🌙 离线模式中，忽略私聊 {nickname}({user_id})（主人发消息可唤醒）")
                    return
            else:
                # 离线时群聊一律不响应，仅主人 @ 可唤醒
                if not (self._is_owner(user_id) and self._is_at_me(message, self_id)):
                    return
            self._wake_from_offline()

        from qq.qq_config import get_qq_config as _get_cfg
        cfg = _get_cfg()

        if message_type == "private":
            # 私信回复范围（设置→QQ：总开关 / 陌生人 / 好友 / 仅主人）——不在范围内直接忽略
            if not self._private_reply_allowed(user_id, data.get("sub_type")):
                print(f"[QQBridge] 🔕 私信不在回复范围（sub_type={data.get('sub_type')}），忽略 "
                      f"{nickname}({user_id})")
                return
            # 提取纯文本
            text = self._extract_text(message, raw_message)
            # 文字+链接卡片：文本里没有 URL 时把卡片里的链接补进来（触发联网解析）
            text = self._append_url_text(text, message)
            # 图片消息检测（私聊；收包线程内同步识别，与 get_image 兼容）
            vision_desc = None
            if cfg["vision_enabled"]:
                vision_desc = self._extract_private_image(message)
            # 视频消息检测（私聊）：文件大、抽帧耗时 → 交给调度线程识别，不阻塞收包
            video_seg = None
            if not vision_desc and self._message_has_video(message) and cfg.get("vision_enabled"):
                video_seg = message
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
            # 兜底：链接卡片/分享消息没有 text 段 → 从消息段提取链接与标题
            if not text.strip():
                _url_txt = self._extract_url_seg_text(message)
                if _url_txt and not vision_desc and not video_seg:
                    text = _url_txt[:200]
            if not text.strip() and not vision_desc and not video_seg:
                return
            self._touch_activity()  # 有效对话 → 重置空闲计时
            print(f"[QQBridge] 私聊 {nickname}({user_id}): {text[:40]}")
            # 入调度队列（session_key = private_<QQ号>，串行处理不乱）
            self.scheduler.enqueue({
                "session_key": f"private_{user_id}",
                "text": text,
                "user_id": user_id,
                "nickname": nickname,
                "group_id": None,
                "vision_desc": vision_desc,
                "video_seg": video_seg,  # 视频消息段（调度线程内识别）
                "message_id": message_id,  # 回复成功后记录，防离线补拉重复回复
            })
        elif message_type == "group":
            # 群名异步缓存（身份标识需要知道在哪个群）
            self._ensure_group_name(group_id)
            # 活泼模式：先记录本条群聊内容（无论是否 @；供冷却后主动接话）
            group_text = self._extract_text(message, raw_message)
            if cfg.get("lively_enabled") and cfg["allow_groups"]:
                self._note_group_chat(group_id, user_id, nickname, group_text)
            # 记录本条图片/视频（含发送者身份：回复前识图/识视频附注谁发的）
            self._note_group_media(group_id, message, user_id=user_id, nickname=nickname)
            # 自主学习(官方插件)：群对话/链接/媒体学习(异步、限流，不阻塞收包)
            try:
                from qq.qq_config import get_qq_config as _lcfg
                _lc = _lcfg()
                if _lc.get("auto_learn_enable"):
                    if _lc.get("auto_learn_chats") and group_text.strip():
                        from qq.qq_learnstore import add_chat as _achat
                        _achat(group_id, f"{nickname}({user_id})", group_text)
                    if _lc.get("auto_learn_links") and "http" in group_text:
                        self._maybe_learn_group_link(group_id, user_id, nickname, group_text)
                    if _lc.get("auto_learn_media"):
                        self._maybe_learn_group_media(group_id, user_id, nickname, message)
            except Exception:
                pass
            # 群聊：仅 @丛雨 时回复；但玩法口令（galgame 开关/查看好感度）在群里免 @ 也可触发
            if not cfg["allow_groups"]:
                return
            if not self._is_at_me(message, self_id):
                low_t = (group_text or "").lower()
                # 免 @ 口令收紧：只认完整指令短语，避免群里随便提到"galgame/好感度"就误触发
                _nospace = low_t.replace(" ", "").replace("　", "")
                _gal_phrases = (
                    "开启galgame模式", "打开galgame模式", "关闭galgame模式",
                    "结束galgame模式", "开启好感度模式", "关闭好感度模式",
                    "查看好感度", "好感度多少", "我的好感度", "好感度查询", "好感度几分")
                is_cmd_txt = any(k in _nospace for k in _gal_phrases)
                if not is_cmd_txt:
                    return
                print(f"[QQBridge] 玩法口令(免@): {nickname}({user_id}): {group_text[:30]}")
            # 提取纯文本并去掉 @ 前缀后回复
            clean = self._strip_at(group_text)
            if not clean.strip():
                # 兜底1：@ + 链接卡片/分享（无 text 段）→ 提取段内链接让 bot 解析
                _url_txt = self._extract_url_seg_text(message)
                if _url_txt:
                    clean = _url_txt[:200]
                elif self._message_has_image(message):
                    # 兜底2：@ + 纯图片（无文字）→ 允许走识图回复
                    clean = "（图片）"
                else:
                    # @ 且无图无字无链接 → 忽略
                    return
            # 文字+链接卡片：文本里没有 URL 时把卡片里的链接补进来
            clean = self._append_url_text(clean, message)
            self._touch_activity()  # 被点名 → 有效对话，重置空闲计时
            # 立即占用该群活泼冷却位：被 @ 的话题即将由正常回复回答，
            # 防止活泼模式在回复前把同一话题又插嘴一次（重复回复同一问题）
            if cfg.get("lively_enabled") and cfg.get("allow_groups"):
                try:
                    with self._groups_lock:
                        _buf = self._group_buf.get(str(group_id))
                        if _buf:
                            _buf["last_bot_talk"] = time.time()
                except Exception:
                    pass
            print(f"[QQBridge] 群聊 {nickname}({user_id}) @丛雨: {clean[:40]}")
            # 快照"此刻该群最近一张图"：回复任务在调度队列可能排队数秒~数十秒，
            # 若期间群里又有人发新图，处理时再取最新会识别成别人的图 → 入队时定格
            img_ref = None
            vid_ref = None
            try:
                with self._groups_lock:
                    _g = self._group_buf.get(str(group_id))
                    if _g:
                        img_ref = _g.get("last_img")
                        vid_ref = _g.get("last_video")
            except Exception:
                pass
            # 入调度队列（session_key = group_<群号>_u<QQ号>：按人分仓记忆，
            # 跟谁聊就只带谁的上下文，防止群里不同人的对话互相串味/认错人）
            self.scheduler.enqueue({
                "session_key": f"group_{group_id}_u{user_id}",
                "text": clean,
                "user_id": user_id,
                "nickname": nickname,
                "group_id": group_id,
                "vision_desc": None,
                "message_seg": message,  # 消息段（回复前检测本条/群近期媒体用）
                "img_ref": img_ref,      # 入队时刻的群最近图片快照（防识错图）
                "vid_ref": vid_ref,      # 入队时刻的群最近视频快照
                "message_id": message_id,  # 回复成功后记录，防离线补拉重复回复
            })

    def _extract_url_seg_text(self, message) -> str:
        """从消息段兜底提取链接/分享信息（QQ 链接卡片/图文分享没有 text 段时用）。
        返回空格拼接的 URL/标题；无则空串。"""
        import re as _re
        out = []
        try:
            if not isinstance(message, list):
                return ""
            for seg in message:
                if not isinstance(seg, dict):
                    continue
                d = seg.get("data") or {}
                for k in ("url", "file", "title", "desc", "summary", "text"):
                    v = d.get(k)
                    if isinstance(v, str) and v.strip():
                        v = v.strip()
                        if (v.startswith("http") or k in ("title", "desc", "summary"))                                 and v not in out:
                            out.append(v)
                j = d.get("json") or d.get("meta") or d.get("content")
                if isinstance(j, str):
                    for m in _re.findall(r"https?://[^\s\"'、，。]+", j):
                        if m not in out:
                            out.append(m)
        except Exception:
            pass
        return " ".join(out)

    def _append_url_text(self, text, message):
        """把消息段里的链接补进文本(文本已有 URL 则跳过)"""
        try:
            if "http" in (text or ""):
                return text or ""
            u = self._extract_url_seg_text(message)
            if u:
                base = (text or "").strip()
                sep = chr(10)
                return (base + sep + u[:220]).strip() if base else u[:220]
        except Exception:
            pass
        return text or ""

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

    def _extract_private_image(self, message, allow_ws=True):
        """
        提取图片并识别。
        NapCat 的 image 段 file 常是 file_id（非本地路径）→ 可用 get_image API 解析。

        线程安全说明：get_image 需要独占 ws.recv()，只能在收包线程内调用
        （私聊图片识别即收包线程）；群回复/活泼接话在调度线程 → allow_ws=False，
        只走线程安全的本地路径 / 消息自带 URL 下载，file_id-only 图跳过。

        返回: 识别描述文本；无图片/未启用/失败 → None。
        """
        try:
            from qq.qq_vision import (
                extract_image_path, describe_image, clean_vision_tmp,
                napcat_get_image, find_image_file_id,
            )
            # 无图消息不跑识图（消除纯文字消息的"无法取得图片"噪音日志）
            if not self._message_has_image(message):
                return None
            print("[QQBridge] 👁 图片消息，开始识图...")
            img_path = extract_image_path(message)
            stray = []
            if not img_path and allow_ws and self.ws:
                fid = find_image_file_id(message)
                if fid:
                    print(f"[QQBridge] 👁 本地无此文件，改用 NapCat get_image: {fid}")
                    img_path, stray = napcat_get_image(self.ws, fid)
            if not img_path:
                if allow_ws:
                    print("[QQBridge] ⚠ 无法取得图片（本地路径/URL/get_image 均失败），跳过识图")
                else:
                    print("[QQBridge] ⚠ 图片无本地文件且无下载 URL（file_id 需实时获取），本轮跳过识图")
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
        """检查消息中是否 @ 了丛雨（只认 @自己的 QQ 号，@all 不触发回复）"""
        if isinstance(message, list):
            for seg in message:
                if isinstance(seg, dict) and seg.get("type") == "at":
                    qq = seg.get("data", {}).get("qq", "")
                    # 仅当 @ 的是本 bot 时才命中；@all/@everyone 不算（否则全群消息都会触发回复）
                    if qq and str(qq) == str(self_id):
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
        # 活泼模式：主动接话（不带 @ 的独立路径；与正常回复串行，防记忆并发）
        if msg.get("lively"):
            self._handle_lively(msg)
            return
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

            # ── 媒体收藏 / 联网搜图搜视频指令（群/私聊通用）──
            try:
                from qq.qq_learn import handle as _learn_handle
                from qq.qq_learn import is_media_cmd as _is_media_cmd
                if _is_media_cmd(text):
                    _ctx_img = None
                    try:
                        from qq.qq_vision import extract_image_path as _eip
                        # 遍历合并组各消息段取图：多图时取最后一张（避免保存错图）
                        for _sub in (msg.get("merged_msgs") or [msg]):
                            _seg = _sub.get("message_seg")
                            if _seg:
                                _p = _eip(_seg)
                                if _p:
                                    _ctx_img = _p  # 保留最后一张
                        if not _ctx_img:
                            _ref = msg.get("img_ref") or {}
                            _ctx_img = _eip(_ref.get("message"))
                    except Exception:
                        pass
                    _lrep, _lacts = _learn_handle(text, {
                        "cur_image_file": _ctx_img, "last_image_file": _ctx_img})
                    if _lrep is not None:
                        # 先执行发送动作(图/表情/视频封面)
                        for _a in (_lacts or []):
                            try:
                                _at = _a.get("type")
                                _af = _a.get("file")
                                if _at == "video_file" and _af and os.path.exists(_af):
                                    # 发送本地视频文件(与图片同机制, NapCat 读本地路径)
                                    _tgt = int(user_id) if session_key.startswith("private_") else int(group_id)
                                    _mtype = "private" if session_key.startswith("private_") else "group"
                                    try:
                                        self.ws.send(json.dumps({
                                            "action": "send_msg",
                                            "params": {
                                                "message_type": _mtype,
                                                "user_id" if _mtype == "private" else "group_id": _tgt,
                                                "message": [{"type": "video", "data": {"file": _af}}],
                                            },
                                            "echo": f"sendvid_{uuid.uuid4().hex[:8]}",
                                        }, ensure_ascii=False))
                                        print(f"[QQBridge] 🎬 发送视频: {os.path.basename(_af)}")
                                    except Exception as _ve:
                                        print(f"[QQBridge] ⚠ 发送视频失败: {_ve}")
                                elif _at in ("image", "sticker") and _af and os.path.exists(_af):
                                    if session_key.startswith("private_"):
                                        send_image(self.ws, _af, "private", int(user_id), self.self_id)
                                    else:
                                        send_image(self.ws, _af, "group", int(group_id), self.self_id)
                                elif _at == "video":
                                    if _af and os.path.exists(_af) and group_id:
                                        send_image(self.ws, _af, "group", int(group_id), self.self_id)
                                    _xt = _a.get("extra")
                                    if _xt and session_key.startswith("group_"):
                                        self._send_group_command_reply(_xt, user_id, group_id)
                                    elif _xt:
                                        self._send_command_reply(_xt, user_id)
                                elif _at == "music":
                                    # 点歌：搜索+下载+转码耗时 → 独立线程执行，不阻塞调度
                                    _kw = _a.get("keyword") or _a.get("extra")
                                    if _kw:
                                        import threading as _th
                                        _th.Thread(
                                            target=self._play_music_worker,
                                            args=(_kw, (session_key, user_id, group_id)),
                                            daemon=True,
                                        ).start()
                            except Exception as _ae:
                                print(f"[QQBridge] ⚠ 收藏发送失败: {_ae}")
                        # 回执文本
                        if session_key.startswith("private_"):
                            self._send_command_reply(_lrep, user_id)
                        else:
                            self._send_group_command_reply(_lrep, user_id, group_id)
                        return
            except Exception as _le:
                print(f"[QQBridge] ⚠ 媒体指令异常: {_le}")

            if session_key.startswith("private_"):
                user_id = msg["user_id"]
                print(f"[QQBridge] → 回复目标 private {user_id} (session={session_key})")
                # 私聊视频识别（调度线程内执行，避免阻塞收包；本地/URL 下载线程安全）
                vid_desc = None
                try:
                    if msg.get("video_seg"):
                        print("[QQBridge] 🎬 私聊视频消息，开始识别...")
                        vid_desc = self._extract_private_video(msg["video_seg"], allow_ws=False)
                except Exception as e:
                    print(f"[QQBridge] ⚠ 私聊视频识别失败(忽略): {e}")
                if vid_desc:
                    if text and text.strip():
                        text = f"{text}\n（你发来一段视频，内容大概是：{vid_desc}）"
                    else:
                        text = f"（你发来一段视频，内容大概是：{vid_desc}）"
                # 消息里提到主人昵称 → 注入对照注记（防认不出主人）
                _mnote = self._master_mention_note(text)
                if _mnote:
                    text = f"{text}\n{_mnote}"
                reply, stickers, portrait_emo = chat_once(
                    text,
                    use_sticker=self.cfg["send_sticker"],
                    vision_desc=vision_desc,
                    session_key=session_key,
                    speaker={"nick": msg.get("nickname") or "", "uin": user_id},
                    is_master=self._is_owner(user_id),
                    master_nicks=self._master_nicks_snapshot(),
                    self_id=self.self_id,
                    self_nick=self.self_nick,
                )
                if not reply:
                    return
                # 换装标记 + 发送层按「单次回复字数上限」分条（超限拆 2~3 条，不截断）
                reply = self._apply_cloth_marker(reply)
                # 发送层再按「每次对话最多回复次数」控制单条回复拆成几条消息
                # （cap_clauses_count 在 _send_private_reply 内合并，内容不丢）
                sent_ok = self._send_private_reply(reply, stickers, user_id)
                # 仅整条回复发送成功后，才把本组全部 message_id 记为已处理：
                # - 发送失败若标记 → 重连补拉不再回答（漏回）
                # - 只记 first 而漏掉合并的第 2/3 条 → 重连补拉对它们重复回答（重复回）
                if sent_ok:
                    self._mark_replied_msgs(msg)
            elif session_key.startswith("group_"):
                user_id = msg["user_id"]
                # 群媒体识别：本条 @ 消息带媒体 → 优先识别本条（图/视频）；
                # 否则识别"入队时刻"快照的群最近媒体（防排队期间新内容串位）；
                # 都没有才实时取。识别附注会带上"谁发的"（主人用（主人）标记，
                # 防叫错人/混淆），失败静默不阻塞回复
                media_note = None
                try:
                    seg = msg.get("message_seg")
                    cur_item = {"who": f"{msg.get('nickname') or '群友'}({user_id})",
                                "is_master": self._is_owner(user_id)}
                    if self._message_has_image(seg):
                        print(f"[QQBridge] 👁 群{group_id} @消息带图，开始识图...")
                        # 调度线程内不能独占 ws.recv() → 只走本地路径/URL
                        d = self._extract_private_image(seg, allow_ws=False)
                        if d:
                            media_note = self._media_note_sentence("image", d, cur_item)
                    elif self._message_has_video(seg):
                        print(f"[QQBridge] 🎬 群{group_id} @消息带视频，开始识别...")
                        d = self._extract_private_video(seg, allow_ws=False)
                        if d:
                            media_note = self._media_note_sentence("video", d, cur_item)
                    # 收紧：只注入「当前发言者本人刚发的」图/视频——
                    # 防止把别人发的表情包/图算到说话人头上（用户反馈的"回错人"根源）；
                    # 也不再"实时兜底取群最近媒体"（那会把任意旧图塞给任意发言者）
                    if not media_note and msg.get("img_ref") \
                            and self._media_from_speaker(msg["img_ref"], user_id):
                        d, item = self._group_recent_image_desc(group_id, img_ref=msg["img_ref"])
                        if d:
                            media_note = self._media_note_sentence("image", d, item)
                    if not media_note and msg.get("vid_ref") \
                            and self._media_from_speaker(msg["vid_ref"], user_id):
                        d, item = self._group_recent_video_desc(group_id, vid_ref=msg["vid_ref"])
                        if d:
                            media_note = self._media_note_sentence("video", d, item)
                    if media_note:
                        text = f"{text}\n{media_note}"
                    # 消息里提到主人昵称 → 注入对照注记（防认不出主人）
                    _mnote = self._master_mention_note(text)
                    if _mnote:
                        text = f"{text}\n{_mnote}"
                except Exception as e:
                    print(f"[QQBridge] ⚠ 群媒体识别失败(忽略): {e}")
                # 合并消息组里若有链接卡片段（如先文字、后卡片被合并成一组）→ 补 URL 触发解析
                try:
                    for _sub in (msg.get("merged_msgs") or [msg]):
                        text = self._append_url_text(text, _sub.get("message_seg"))
                except Exception:
                    pass
                reply, stickers, portrait_emo = chat_once(
                    text,
                    use_sticker=self.cfg["send_sticker"],
                    session_key=session_key,
                    speaker={"nick": msg.get("nickname") or "", "uin": user_id},
                    is_master=self._is_owner(user_id),
                    group_name=self._group_display_name(group_id),
                    master_nicks=self._master_nicks_snapshot(),
                    self_id=self.self_id,
                    self_nick=self.self_nick,
                )
                if not reply:
                    return
                # 换装标记；字数上限由 _send_group_reply 按句子边界分条处理（超限拆 2~3 条，不截断）
                reply = self._apply_cloth_marker(reply)
                sent_ok = self._send_group_reply(reply, stickers, user_id, group_id)
                if sent_ok:
                    self._mark_replied_msgs(msg)
                # Galgame 立绘：模型给出 [立绘:情绪] → 合成立绘发到群
                if sent_ok and portrait_emo:
                    try:
                        from qq.qq_portrait import build_portrait, extract_bg_kw
                        _pp = build_portrait(portrait_emo, extract_bg_kw(text))
                        if _pp:
                            send_image(self.ws, _pp, "group", int(group_id), self.self_id)
                            print(f"[QQBridge] 🎨 Galgame立绘({portrait_emo}) 已发送到群 {group_id}")
                    except Exception as _e:
                        print(f"[QQBridge] ⚠ 立绘发送失败: {_e}")
                    # 已回应过当前话题 → 清空该群活泼话题缓冲并记冷却，
                    # 防止活泼模式对同一句话再插嘴一次（用户反馈"一句话被回两次"）
                    try:
                        with self._groups_lock:
                            buf = self._group_buf.get(str(group_id))
                            if buf:
                                buf["recent"].clear()
                                buf["last_bot_talk"] = time.time()
                    except Exception:
                        pass
        except Exception as e:
            print(f"[QQBridge] ⚠ 处理消息异常: {e}")

    def _mark_replied_msgs(self, msg):
        """把本条（含合并子消息）的全部 message_id 记为已回复（去重用）。

        合并会话：scheduler 把同一会话连发的消息合并成一组（merged_msgs 含全部），
        必须收集全部 id——只记 first 会导致第 2/3 条被重连后的离线补拉重复回复。
        """
        mids = []
        merged = msg.get("merged_msgs") or [msg]
        for sub in merged:
            mid = (sub or {}).get("message_id")
            if mid is not None and mid not in mids:
                mids.append(mid)
        if not mids:
            return
        try:
            from qq.qq_offline import mark_processed
            mark_processed(mids)
        except Exception as e:
            print(f"[QQBridge] ⚠ 记录已回复 ID 失败: {e}")

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

    # ===== 断线安全的发送 =====
    def _safe_send(self, payload: dict, label: str = "") -> bool:
        """
        向 NapCat 发送一条 API 调用。断线/重连窗口内 self.ws 可能已关闭或为 None：
        发送失败不抛异常冒泡（会被调度线程吞掉造成丢消息），而是提示并计数返回 False。
        """
        if self.ws is None:
            self._send_fail_count += 1
            print(f"[QQBridge] ⚠ {label}发送失败：连接尚未建立（累计 {self._send_fail_count} 次发送失败）")
            return False
        try:
            with self._lock:
                self.ws.send(json.dumps(payload, ensure_ascii=False))
            return True
        except Exception as e:
            self._send_fail_count += 1
            print(f"[QQBridge] ⚠ {label}发送失败（连接可能已断开）: {e}"
                  f"（累计 {self._send_fail_count} 次发送失败，重连后请对方重发）")
            return False

    def _stickers_on(self) -> bool:
        """表情包开关 —— **实时**读 config.json。

        ⚠ 以前读的是进程启动时的 self.cfg 快照：在设置里关掉开关、不重启 QQ 模块
        是不生效的；而且 resolve_sticker_files() 在「模型没点名表情」时仍有约一半概率
        从自存池随机抽一张，导致"开关关了还一直发表情包"。所以每个发送点都要判。
        """
        try:
            from qq.qq_config import _load_config
            v = str(_load_config().get("qq_send_sticker", "true")).strip().lower()
            return v in ("true", "1", "on", "yes")
        except Exception:
            try:
                return bool(self.cfg.get("send_sticker", True))
            except Exception:
                return True

    def _send_private_reply(self, reply, stickers, user_id):
        """私聊回复：按句切分逐条发送 + 可选表情包(0~2个)/语音。
        返回 True = 文字部分完整发送成功（分句全部送达）；
        False = 断线/失败（调用方不应标记为已回复，避免重连补拉漏回）。

        对话调节：
        - 「单次回复字数上限」→ 超限按句子边界拆成 2~3 条（不砍半句话、内容不丢）；
        - 「每次对话最多回复次数」→ 条数超上限时把多余句子合并进最后一条。"""
        # 字数限制：按【完整句子】打包成 ≤ 上限的若干条（永不把一句话拆开）；
        # 未配置字数限制时也按完整句子逐条发送（同样不切逗号）
        try:
            _lim = self._reply_limits()[1]
        except Exception:
            _lim = 0
        clauses = split_by_char_limit(reply, _lim, 3) if _lim > 0 else split_sentences(reply)
        if not clauses:
            return True
        try:
            clauses = cap_clauses_count(clauses, self._reply_limits()[0])
        except Exception:
            pass
        if not clauses:
            return True

        for idx, clause in enumerate(clauses):
            ok = self._safe_send({
                "action": "send_msg",
                "params": {
                    "message_type": "private",
                    "user_id": user_id,
                    "message": clause,
                },
                "echo": f"reply_{uuid.uuid4().hex[:8]}",
            }, label=f"私聊{user_id} ")
            if not ok:
                return False  # 断线：文字未完整送达，不标记已回复
            if idx < len(clauses) - 1:
                print(f"[QQBridge] → 私聊 {user_id} 第{idx+1}/{len(clauses)}句: {clause[:30]}...")
                time.sleep(_PRIVATE_SEND_INTERVAL[0] + (_PRIVATE_SEND_INTERVAL[1] - _PRIVATE_SEND_INTERVAL[0]) * 0.3)
            else:
                print(f"[QQBridge] → 私聊 {user_id} 第{idx+1}/{len(clauses)}句: {clause[:30]}...")

        # 表情包（最后一条文字后发送，0~2 个；失败不影响"已回复"判定）
        # ⚠ 表情包开关关闭时不发（连自存池随机逻辑都不执行）——见 _stickers_on()
        for path in (resolve_sticker_files(stickers)[0] if self._stickers_on() else []):
            if path:
                try:
                    send_image(self.ws, path, "private", user_id, self.self_id)
                except Exception:
                    pass

        # 语音（可选）
        if self.cfg["send_voice"]:
            try:
                self._send_voice(reply, "private", user_id)
            except Exception:
                pass
        return True

    def _send_group_reply(self, reply, stickers, user_id, group_id):
        """群聊回复：发送回复（超字数上限时按句子边界拆成 2~3 条，内容不丢）
        + 可选表情包(0~2个)/语音。返回 True = 发送成功；False = 断线/失败。"""
        # 对话调节：单次回复字数上限 → 分条发送（第一条带 @ 提问者）
        parts = self._reply_parts(reply, 3)
        if not parts:
            parts = [reply]
        ok = True
        for idx, part in enumerate(parts):
            # 群聊回复时加 @ 提问者（仅第一条）
            msg = f"[CQ:at,qq={user_id}] {part}" if idx == 0 else part
            ok = self._safe_send({
                "action": "send_msg",
                "params": {
                    "message_type": "group",
                    "group_id": group_id,
                    "message": msg,
                },
                "echo": f"reply_{uuid.uuid4().hex[:8]}",
            }, label=f"群{group_id} ")
            if not ok:
                return False
            tip = f"→ 群 {group_id} 回复" + (f"（{idx+1}/{len(parts)}）" if len(parts) > 1 else "")
            print(f"[QQBridge] {tip}: {part[:40]}...")
            if idx < len(parts) - 1:
                time.sleep(_PRIVATE_SEND_INTERVAL[0])
        # ⚠ 表情包开关关闭时不发（连自存池随机逻辑都不执行）——见 _stickers_on()
        for path in (resolve_sticker_files(stickers)[0] if self._stickers_on() else []):
            if path:
                try:
                    send_image(self.ws, path, "group", group_id, self.self_id)
                except Exception:
                    pass
        if self.cfg["send_voice"]:
            try:
                self._send_voice(reply, "group", group_id)
            except Exception:
                pass
        return True

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
