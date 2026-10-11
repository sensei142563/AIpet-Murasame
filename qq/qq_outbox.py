# -*- coding: utf-8 -*-
"""发送队列消费者（手机 → 电脑 → QQ）。

手机端（App 里的 QQ 页）把要发的话 POST 到 api.py 的 /qq/queue/send，
api.py 追加一行 JSON 到 data/qq_outbox.jsonl。本模块由桌面端进程（握着 OneBot11 WS 的那个）
在后台线程里轮询该文件，把新行经 WS 发出去，并把结果写进 data/qq_outbox_ack.jsonl。

为什么单独成文件：
  · 零重依赖（不 import qq_bridge/qq_chat/LLM 客户端），可以被**离线单测**直接加载；
  · senders 可注入 → 测试时传一个"假 ws"，断言它收到的 OneBot11 payload。
"""
import json
import os
import threading
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUTBOX = os.path.join(BASE_DIR, "data", "qq_outbox.jsonl")
DEFAULT_OFFSET = os.path.join(BASE_DIR, "data", "qq_outbox.offset")
DEFAULT_ACK = os.path.join(BASE_DIR, "data", "qq_outbox_ack.jsonl")

_worker_started = False
_worker_lock = threading.Lock()
_send_lock = threading.Lock()   # 与 enable_multithread 一起保证帧不被写串


def _default_senders():
    """默认发送实现：复用 qq_bridge 里现成的三个函数（延迟 import，避免循环依赖）。"""
    from qq.qq_bridge import send_text, send_image, send_voice
    return {"text": send_text, "image": send_image, "voice": send_voice}


def _read_offset(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int((f.read() or "0").strip() or 0)
    except Exception:
        return 0


def _write_offset(path, n):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(int(n)))
    except Exception:
        pass


def _append(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception:
        pass


def drain(ws, self_id, outbox=None, offset_path=None, ack_path=None, senders=None, max_items=20):
    """把 outbox 里**尚未处理**的行发出去。返回处理结果列表。

    返回项：{"ok": bool, "item": {...}, "error": str|None, "echo": str|None}
    用 offset 记录已消费字节数（不重写文件，避免与手机端并发追加打架）。
    """
    outbox = outbox or DEFAULT_OUTBOX
    offset_path = offset_path or DEFAULT_OFFSET
    ack_path = ack_path or DEFAULT_ACK
    if ws is None:
        return []
    if not os.path.isfile(outbox):
        return []
    senders = senders or _default_senders()
    off = _read_offset(offset_path)
    size = os.path.getsize(outbox)
    if off > size:            # 文件被截断/重建 → 从头开始
        off = 0
    if off == size:
        return []
    results = []
    try:
        with open(outbox, "r", encoding="utf-8") as f:
            f.seek(off)
            for _ in range(max_items):
                line = f.readline()
                if not line:
                    break
                # **只消费完整行**：手机端是并发追加的（api.py 的 /qq/queue/send 用 "a" 模式
                # 写 json+"\n"），所以 readline() 很可能读到"写到一半、还没有换行"的半行。
                # 原实现在判断完整性之前就记下 consumed 并推进 offset ⇒ 半行被当成已消费，
                # 等后半截到来时会被当作新的垃圾行读掉 ⇒ **这条消息永远不会发出**（静默丢消息）。
                # 对抗测试已复现：半行场景下 offset=87（应 67），补完后该条一条都发不出去。
                if not line.endswith("\n"):
                    break
                consumed = f.tell()
                line = line.strip()
                if not line:
                    off = consumed          # 空行直接跳过（不产生 ack 噪音）
                    continue
                res = {"ok": False, "item": None, "error": None, "echo": None}
                try:
                    item = json.loads(line)
                    res["item"] = item
                    ttype = str(item.get("target_type") or "private")
                    tid = item.get("target_id")
                    text = item.get("text")
                    image = item.get("image")
                    sticker = item.get("sticker")
                    voice = item.get("voice")
                    if not tid:
                        raise ValueError("target_id 缺失")
                    with _send_lock:
                        if voice:
                            senders["voice"](ws, voice, ttype, int(tid), self_id or 0)
                            res["echo"] = "voice"
                        elif image or sticker:
                            path = image
                            if sticker and not path:
                                try:
                                    from qq.qq_bridge import get_sticker_path
                                    path = get_sticker_path(sticker)
                                except Exception:
                                    path = None
                            if not path:
                                raise ValueError("找不到要发的图片/表情包文件")
                            senders["image"](ws, path, ttype, int(tid), self_id or 0)
                            res["echo"] = "image"
                        elif text:
                            senders["text"](ws, str(text), ttype, int(tid), self_id or 0)
                            res["echo"] = "text"
                        else:
                            raise ValueError("text/image/sticker/voice 至少要有一个")
                    res["ok"] = True
                except Exception as e:
                    res["error"] = "%s: %s" % (type(e).__name__, e)
                res["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                _append(ack_path, res)
                results.append(res)
                off = consumed
    finally:
        _write_offset(offset_path, off)
    return results


def ack_tail(n=20, ack_path=None):
    ack_path = ack_path or DEFAULT_ACK
    if not os.path.isfile(ack_path):
        return []
    out = []
    try:
        with open(ack_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    return out[-max(1, int(n)):]


def start_worker(get_ws, get_self_id, interval=1.5, outbox=None):
    """起后台线程消费队列（幂等）。get_ws/get_self_id 是取当前连接的回调。"""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return False
        _worker_started = True

    def loop():
        while True:
            try:
                ws = get_ws()
                if ws is not None:
                    drain(ws, get_self_id(), outbox=outbox)
            except Exception as e:
                print("[QQOutbox] 轮询异常: %s: %s" % (type(e).__name__, e))
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True, name="qq-outbox")
    t.start()
    print("[QQOutbox] 发送队列线程已启动（每 %.1fs 检查一次 data/qq_outbox.jsonl）" % interval)
    return True
