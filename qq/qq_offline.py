# -*- coding: utf-8 -*-
"""
QQ 离线消息补拉 — 启动后主动拉取大号离线期间的消息并补回复。

原理：
- NapCat 的 enableForcePushEvent 在当前版本并未真正在 WS 连接后补推离线消息
- 改用 NapCat 扩展 API get_friend_msg_history 主动拉取与大号的聊天记录
- 记录"上次退出时间"，只处理退出期间到达的消息（time > last_exit_time）
- 已处理过的 message_id 记录到 qq_processed_ids.json（防重复回复）

三层防护（防"上线机枪回复"）：
A. 方向过滤：跳过 bot 自己发的消息（self_id 匹配），防自我对话
B. message_id 去重：已处理过的消息不再回复
C. 首次运行只补最近若干条：防把历史记录全刷一遍
"""

import os
import json
import time
import uuid
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(BASE_DIR, "data", "qq_offline_state.json")
PROCESSED_IDS_FILE = os.path.join(BASE_DIR, "data", "qq_processed_ids.json")

POLL_INTERVAL = 60  # 每秒轮询兜底

# 首次运行（无 last_exit_time）时最多补拉条数，防止把历史记录全刷一遍
FIRST_RUN_MAX = 10
# 去重记录最多保留数量（防止文件无限膨胀）
PROCESSED_IDS_MAX = 5000
# 好友离线补拉：最多拉取前 N 个好友的历史（NapCat 无"最近联系人"接口，只能全量好友逐个拉）
MAX_FRIEND_PULLS = 30
# 好友补拉总时长预算（秒）——超过即停止，避免好友多时启动过慢
FRIEND_PULL_BUDGET = 30


def load_last_exit_time():
    """读取上次退出时间（字符串，无则返回 None）"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("last_exit_time")
    except Exception:
        pass
    return None


def save_last_exit_time(timestamp=None):
    """记录退出时间（默认当前时间）"""
    try:
        ts = timestamp or time.strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_exit_time": ts}, f, ensure_ascii=False, indent=2)
        print(f"[QQOffline] ✅ 已记录退出时间: {ts}")
    except Exception as e:
        print(f"[QQOffline] ⚠ 保存退出时间失败: {e}")


def _parse_time(msg_time):
    """把 NapCat 消息 time（Unix 秒）转成 'YYYY-MM-DD HH:MM:SS'"""
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(msg_time)))
    except Exception:
        return None


# 已处理消息 ID 文件读写锁（调度线程 mark_processed 与 WS 线程离线补拉并发，须串行）
_IDS_LOCK = threading.Lock()


def _load_processed_ids():
    """读取已处理过的消息 ID（保持插入序的有序列表，尾部=最新）。"""
    with _IDS_LOCK:
        try:
            if os.path.exists(PROCESSED_IDS_FILE):
                with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items = data.get("ids", [])
                # 兼容旧格式（可能存成 set/list 混合）→ 归一化去重保序
                seen = set()
                ordered = []
                for i in items:
                    s = str(i)
                    if s not in seen:
                        seen.add(s)
                        ordered.append(s)
                return ordered
        except Exception:
            pass
        return []


def _save_processed_ids(ordered_ids):
    """保存已处理的消息 ID（有序，保留尾部最新 PROCESSED_IDS_MAX 条）"""
    with _IDS_LOCK:
        try:
            tail = ordered_ids[-PROCESSED_IDS_MAX:]
            os.makedirs(os.path.dirname(PROCESSED_IDS_FILE), exist_ok=True)
            tmp = PROCESSED_IDS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"ids": tail}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, PROCESSED_IDS_FILE)  # 原子写
        except Exception as e:
            print(f"[QQOffline] ⚠ 保存已处理 ID 失败: {e}")


def _append_processed_ids(new_ids) -> bool:
    """把新 ID 追加到已处理列表尾部（保持插入序；重复的跳过）。加锁防并发。"""
    if not new_ids:
        return False
    new_clean = []
    seen_new = set()
    for i in new_ids:
        s = str(i)
        if i is not None and s not in seen_new:
            seen_new.add(s)
            new_clean.append(s)
    if not new_clean:
        return False
    with _IDS_LOCK:
        try:
            ordered = []
            try:
                if os.path.exists(PROCESSED_IDS_FILE):
                    with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    ordered = [str(i) for i in data.get("ids", [])]
            except Exception:
                ordered = []
            existing = set(ordered)
            added = False
            for s in new_clean:
                if s not in existing:
                    ordered.append(s)
                    existing.add(s)
                    added = True
            if added:
                tail = ordered[-PROCESSED_IDS_MAX:]
                os.makedirs(os.path.dirname(PROCESSED_IDS_FILE), exist_ok=True)
                tmp = PROCESSED_IDS_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump({"ids": tail}, f, ensure_ascii=False, indent=2)
                os.replace(tmp, PROCESSED_IDS_FILE)
            return True
        except Exception as e:
            print(f"[QQOffline] ⚠ 追加已处理 ID 失败: {e}")
            return False


def mark_processed(message_ids):
    """公开入口：实时回复成功后调用，记录该消息 ID（防下次离线补拉重复回复）。

    关键：实时路径回复的消息若不记录，下次启动离线补拉会把它当"离线期间消息"
    再补回复一次 → 主人被重复回复（用户实测 bug）。锁内追加，保持插入序。
    """
    try:
        _append_processed_ids(message_ids)
    except Exception as e:
        print(f"[QQOffline] ⚠ 记录已处理 ID 失败: {e}")


def _fetch_login_info(ws, timeout=3):
    """
    主动请求 get_login_info 并返回 (bot 自己的 QQ 号, 期间收到的实时事件)。
    connect() 里的 login_info 响应可能已被其它 recv 消费，这里独立再请求一次，
    确保拿到 self_id（用于方向过滤）。期间到达的实时消息事件一并收集返回，不能丢弃。
    """
    echo = f"offline_login_{uuid.uuid4().hex[:6]}"
    stray_events = []
    try:
        ws.send(json.dumps({"action": "get_login_info", "echo": echo}))
        import websocket
        deadline = time.time() + timeout
        while True:
            remain = deadline - time.time()
            if remain <= 0:
                break
            try:
                # 单次 recv 阻塞受 socket 超时支配 → 临时收紧到剩余时间
                ws.settimeout(min(remain + 0.2, timeout + 0.2))
                raw = ws.recv()
                if not raw:
                    continue
                data = json.loads(raw)
                if data.get("echo") == echo and data.get("data"):
                    return data["data"].get("user_id"), stray_events
                # 非本次请求的响应（实时消息事件）→ 收集待补处理
                print(f"[QQOffline] login_info recv: echo={data.get('echo')} post_type={data.get('post_type')} → 收集待补处理")
                stray_events.append(raw)
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                break
    except Exception:
        pass
    finally:
        try:
            ws.settimeout(30)
        except Exception:
            pass
    return None, stray_events


def _normalize_messages(data):
    """兼容多种返回结构 → 消息列表"""
    if isinstance(data, dict):
        return data.get("messages") or data.get("message") or []
    if isinstance(data, list):
        return data
    return []


def _request_and_wait(ws, action, params=None, timeout=2, label=""):
    """
    发送 NapCat API 请求并等待 echo 响应。
    期间收到的非 echo 消息（实时事件）收集返回，不能丢弃。
    返回 (data, stray_events)；超时返回 (None, stray_events)。

    超时语义（关键）：deadline 之外必须真正限制单次 recv 的阻塞。websocket 的 socket
    超时由 create_connection(timeout=30) 决定，若 NapCat 对某 API 完全不响应，裸
    ws.recv() 会阻塞约 30s 才抛超时——名义上的"2 秒"根本不会生效。这里在每次 recv 前
    临时 settimeout(剩余时间)，保证单次调用总阻塞 ≈ timeout 级，不拖垮启动/主 WS。
    """
    import websocket
    echo = f"{label}_{uuid.uuid4().hex[:8]}"
    payload = {"action": action, "echo": echo}
    if params:
        payload["params"] = params
    stray_events = []
    try:
        ws.send(json.dumps(payload, ensure_ascii=False))
        deadline = time.time() + timeout
        while True:
            remain = deadline - time.time()
            if remain <= 0:
                break
            try:
                # 单次 recv 阻塞上限 = 剩余时间（含少量余量防抖动）
                ws.settimeout(min(remain + 0.2, timeout + 0.2))
                raw = ws.recv()
                if not raw:
                    continue
                data = json.loads(raw)
                if data.get("echo") != echo:
                    print(f"[QQOffline] recv: echo={data.get('echo')} post_type={data.get('post_type')} → 收集待补处理")
                    stray_events.append(raw)
                    continue
                return data.get("data"), stray_events
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                break
    except Exception as e:
        print(f"[QQOffline] ⚠ 请求 {action} 失败: {e}")
    finally:
        # 恢复 socket 超时（离线拉取是启动期一次性操作；主循环心跳依赖 30s 超时）
        try:
            ws.settimeout(30)
        except Exception:
            pass
    return None, stray_events


def _extract_vision_desc(message, ws=None, stray_out=None):
    """离线消息识图：提取图片并调用视觉识别（与实时路径同一套实现）。
    NapCat file 是 file_id 时走 get_image；期间收到的实时事件归入 stray_out（不能丢）。
    返回图片内容描述；无图片/未启用/失败 → None。"""
    try:
        from qq.qq_config import get_qq_config
        if not get_qq_config().get("vision_enabled"):
            return None
        from qq.qq_vision import (
            extract_image_path, describe_image, clean_vision_tmp,
            napcat_get_image, find_image_file_id,
        )
        img_path = extract_image_path(message)
        stray = []
        if not img_path and ws:
            fid = find_image_file_id(message)
            if fid:
                print(f"[QQOffline] 本地无此文件，改用 NapCat get_image: {fid}")
                img_path, stray = napcat_get_image(ws, fid)
        if stray_out is not None:
            stray_out.extend(stray)
        if not img_path:
            return None
        desc = describe_image(img_path)
        clean_vision_tmp()
        return desc or None
    except Exception as e:
        print(f"[QQOffline] ⚠ 离线识图异常: {e}")
        return None


def _process_history(messages, owner_id, self_id, last_exit_time,
                     prev_processed, processed_this_run, out_msgs, default_sender=None,
                     ws=None, stray_out=None):
    """处理一批历史消息（三层防护 + 按真实发送者构造条目）

    顺序优化（防浪费）：先做所有无 IO 过滤（自己发的消息 / 窗口外 / 已处理），
    只有真正需要回复的消息才走识图——旧实现先识图再过滤，
    导致 bot 自己发的历史图片也被下载+识图，纯浪费 token（实测日志可见）。
    """
    for m in messages:
        if not isinstance(m, dict):
            continue
        msg_time = _parse_time(m.get("time"))
        if not msg_time:
            continue
        msg_id = m.get("message_id")
        msg_user_id = m.get("user_id")
        message = m.get("message")
        text_raw = _extract_msg_text(message)

        # ===== 防护 A：跳过 bot 自己发的消息（防自我对话机枪）=====
        # 必须在任何 IO（识图/下载）之前——自己发的图片无需识别
        if self_id is not None and msg_user_id is not None:
            if str(msg_user_id) == str(self_id):
                print(f"[QQOffline]     ↘ 跳过自己发的消息（self_id={self_id}）")
                continue

        # 过滤窗口外的消息。注意：窗口外的消息**不**记入已处理——
        # 之前"先标记后过滤"会把窗口外消息毒化为已处理，导致放宽窗口后也永远补不回。
        if msg_time <= last_exit_time:
            continue

        # 窗口内消息记入已处理（防下次重复；文本为空无法回复的也标记，避免反复拉取）
        if msg_id is not None:
            processed_this_run.add(str(msg_id))

        # ===== 防护 B：本次拉取前已处理过的消息 → 跳过 =====
        if msg_id is not None and str(msg_id) in prev_processed:
            print(f"[QQOffline]     ↘ 跳过已处理消息 mid={msg_id}")
            continue

        # 真正要回复的消息才识图（此时已排除自己发的 + 窗口外 + 已处理）
        vision_desc = _extract_vision_desc(message, ws=ws, stray_out=stray_out)
        text = text_raw.strip()
        print(f"[QQOffline]   # time={msg_time} user_id={msg_user_id} mid={msg_id} text='{text[:30]}' vision={'Y' if vision_desc else '-'}")

        if not text and not vision_desc:
            continue
        # 实际发送者：消息自带的 user_id 优先；保底用该聊天对象/大号
        sender_id = msg_user_id or default_sender or owner_id
        if self_id is not None and str(sender_id) == str(self_id):
            sender_id = owner_id
        out_msgs.append({
            "session_key": f"private_{sender_id}",
            "text": text,
            "vision_desc": vision_desc,
            "user_id": sender_id,
            "message_type": "private",
            "message_id": msg_id,
        })


def fetch_offline_messages(ws, owner_id, last_exit_time, self_id=None):
    """
    离线补拉：
    1. 大号（主人）的聊天历史 get_friend_msg_history
    2. 最近联系人里离线期间有消息的其他好友（逐个补拉历史）——
       修复"bot 连接晚于消息到达时，其他好友的离线消息无法恢复"的问题

    - self_id: bot 自己的 QQ 号（过滤自己发出的消息，防自我对话机枪）
    - 已处理过的 message_id 会跳过（防重复回复）
    - 首次运行（last_exit_time=None）只补大号且仅保留最近 FIRST_RUN_MAX 条（防刷屏）

    返回: (msgs, stray_events, seen_ids)  msg 按时间升序
    """
    if not ws or not owner_id:
        return [], [], set()

    prev_processed = set(_load_processed_ids())  # list → set，供 O(1) 归属/去重查询
    processed_this_run = set()
    msgs = []
    stray_events = []

    # ===== 离线窗口 =====
    # 基线（上次启动时间）向前放宽 24 小时：
    # 覆盖「隔一天才开 QQ 补回消息」的需求，也补回老版本漏掉的历史消息；
    # processed_ids 去重保证每条消息一生只回一次。首次运行（无基线）用最近 10 分钟窗口防刷历史。
    if last_exit_time:
        try:
            base_ts = time.mktime(time.strptime(last_exit_time, "%Y-%m-%d %H:%M:%S")) - 86400
            window_start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(base_ts))
        except Exception:
            window_start = last_exit_time
    else:
        window_start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 600))
    print(f"[QQOffline] 离线窗口起点: {window_start}（基线 {last_exit_time or '首次运行'} 放宽 24 小时）")

    # ===== 1. 大号历史 =====
    data, stray = _request_and_wait(ws, "get_friend_msg_history",
                                    {"user_id": int(owner_id), "count": 50}, label="history")
    stray_events.extend(stray)
    if data is not None:
        messages = _normalize_messages(data)
        print(f"[QQOffline] 🔎 大号历史 {len(messages)} 条")
        _process_history(messages, owner_id, self_id, window_start,
                         prev_processed, processed_this_run, msgs, default_sender=owner_id,
                         ws=ws, stray_out=stray_events)
    else:
        print("[QQOffline] ⚠ 未等到 get_friend_msg_history 响应（NapCat 可能不支持该 API，跳过）")

    # ===== 2. 其他好友的离线消息 =====
    # NapCat OneBot11 WS 不支持 get_recent_contacts（报"不支持的API"），
    # 改用 get_friend_list 拿全量好友列表，对每个好友拉历史，靠时间窗口过滤。
    data2, stray2 = _request_and_wait(ws, "get_friend_list", None, timeout=2, label="friends")
    stray_events.extend(stray2)
    friends = _normalize_messages(data2)
    print(f"[QQOffline] 🔎 好友列表 {len(friends)} 人")
    friend_pulls = 0
    friend_budget_start = time.time()
    for friend in friends[:MAX_FRIEND_PULLS]:
        if not isinstance(friend, dict):
            continue
        peer = friend.get("user_id") or friend.get("uin")
        if not peer or str(peer) == str(owner_id):
            continue
        if self_id is not None and str(peer) == str(self_id):
            continue
        # 总时长预算：好友多时避免启动过慢
        if time.time() - friend_budget_start > FRIEND_PULL_BUDGET:
            print("[QQOffline] 🔍 好友补拉达到时长预算，停止")
            break
        friend_pulls += 1
        # 拉取条数：好友会话常被 bot 自己的长回复占满（一条回复可能切成 10+ 条历史），
        # count=20 会把好友离线期间的消息挤出拉取窗口 → 好友消息永远补不回来。
        # 提高到 50（NapCat 上限内），且只保留离线窗口内的，多拉不影响。
        data3, stray3 = _request_and_wait(ws, "get_friend_msg_history",
                                          {"user_id": int(peer), "count": 50}, timeout=2, label="history_f")
        stray_events.extend(stray3)
        if data3 is None:
            print(f"[QQOffline] ⚠ 好友 {peer} 历史拉取超时，跳过")
            continue
        messages3 = _normalize_messages(data3)
        print(f"[QQOffline] 🔎 好友 {peer} 历史 {len(messages3)} 条")
        _process_history(messages3, owner_id, self_id, window_start,
                         prev_processed, processed_this_run, msgs, default_sender=peer,
                         ws=ws, stray_out=stray_events)

    # 按时间升序（各次拉取通常是倒序，整体翻转）
    msgs = list(reversed(msgs))

    # ===== 防护 C：首次运行只补最近几条（防刷屏）=====
    if not last_exit_time and len(msgs) > FIRST_RUN_MAX:
        print(f"[QQOffline] 🔍 首次运行，仅保留最近 {FIRST_RUN_MAX} 条（共 {len(msgs)} 条）")
        msgs = msgs[-FIRST_RUN_MAX:]

    # 把本次看到的消息 ID 全部记录（含旧消息）→ 下次启动跳过所有历史
    # 用保序追加（_append_processed_ids 内部去重 + 锁 + 截断尾部最新）
    if processed_this_run:
        _append_processed_ids(list(processed_this_run))
        total = len(set(_load_processed_ids()))
        print(f"[QQOffline] 📝 已记录已处理消息 ID（当前共 {total} 条，防下次重复）")

    # 返回本次历史里见过的 message_id（bridge 补处理实时事件时据此去重，
    # 防止同一消息既走离线回复又被实时补处理导致重复回复）
    return msgs, stray_events, processed_this_run


def _extract_msg_text(message):
    """从 OneBot11 message 段提取纯文本（过滤 CQ 码）"""
    import re
    texts = []
    if isinstance(message, list):
        for seg in message:
            if isinstance(seg, dict) and seg.get("type") == "text":
                texts.append(seg.get("data", {}).get("text", ""))
    if texts:
        return "".join(texts)
    if isinstance(message, str):
        return re.sub(r"\[CQ:[^\]]*\]", "", message).strip()
    return ""


def fetch_before_loop(ws, owner_id, scheduler, self_id=None):
    """
    同步拉取离线消息（在 connect() 的 while 循环前调用）。
    单线程 recv，避免与主循环线程竞争 WS 响应。

    - ws: NapCat WebSocket
    - owner_id: 大号 QQ 号
    - scheduler: MessageScheduler 实例（消息入队）
    - self_id: 丛雨自己的 QQ 号（可选；若未传则主动请求 get_login_info 获取）

    默认开启（qq_offline_enable=true）；NapCat 不支持 get_friend_msg_history 时可在
    PCL 设置关闭。即便开启，任何请求失败/超时也绝不上抛、极短超时，
    避免拖断主 WebSocket（否则表现成"连上就断、QQ 不回复"）。
    """
    # 开关（默认开）：未开启时跳过整个离线补拉
    try:
        from qq.qq_config import get_qq_config
        if not get_qq_config().get("offline_enabled"):
            print("[QQOffline] ℹ️ 离线补拉已关闭（qq_offline_enable=false，可在 PCL 设置开启）。")
            save_last_exit_time()  # 仍记录基线，避免下次误判"首次运行"
            return [], set()
    except Exception:
        pass

    last = load_last_exit_time()
    print(f"[QQOffline] 上次退出时间: {last or '首次运行'}")
    # 立刻记录本次启动时间作为下次离线窗口的基线：
    # 进程被强杀（如 PCL taskkill）时退出钩子不执行，不记基线会导致每次都是"首次运行"，
    # 且其他好友的离线补拉永远被跳过。首次运行（无基线）除外。
    save_last_exit_time()

    stray_events = []
    # 若外部没传 self_id（或因时序没拿到），主动请求一次 get_login_info
    if not self_id:
        self_id, login_stray = _fetch_login_info(ws)
        stray_events.extend(login_stray)
        if self_id:
            print(f"[QQOffline] 主动获取到丛雨 self_id: {self_id}")
    print(f"[QQOffline] 丛雨 self_id: {self_id or '未知（方向过滤降级）'}")

    seen_ids = set()
    try:
        offline, history_stray, seen_ids = fetch_offline_messages(ws, owner_id, last, self_id=self_id)
        stray_events.extend(history_stray)
        if offline:
            print(f"[QQOffline] 🔄 发现 {len(offline)} 条离线消息，逐条补回复...")
            for msg in offline:
                scheduler.enqueue(msg)
        else:
            print(f"[QQOffline] 📭 无离线消息（或 get_friend_msg_history 不可用）")
    except Exception as e:
        print(f"[QQOffline] ⚠ 离线补拉异常（不影响主连接）: {e}")
    # 返回 (拉取期间收到的实时事件, 历史里见过的 message_id) 由 bridge 补处理/去重
    return stray_events, seen_ids