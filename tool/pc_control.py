# -*- coding: utf-8 -*-
"""让桌宠能自己操作键鼠：移动/点击/双击/右键/滚轮/键盘输入/组合键/等待。

开关（默认关闭，安全第一）：
    桌宠右键菜单 →「允许操控电脑（键鼠）」→ 写 config.json 的 pc_control_enabled。
    关掉后立刻停止执行，已排队的动作全部丢弃。

她怎么表达"要做什么"：回复里带一行动作指令即可（和【看屏幕】同一个套路）：
    【键鼠】移动 800 250
    【键鼠】点击 800 250      【键鼠】双击 800 250      【键鼠】右键 800 250
    【键鼠】滚轮 下 3          （上 / 下）
    【键鼠】输入 你好，世界
    【键鼠】按键 enter        【键鼠】热键 ctrl+s
    【键鼠】等待 0.5

安全限制：
    * 每轮最多 8 个动作（防止模型跑飞反复点击）
    * 坐标必须落在屏幕内，越界直接丢弃并记日志
    * 每个动作写一行日志（data/pc_control.log + 控制台），随时可查她做了什么
    * 动作之间留 120ms 间隔，避免鼠标瞬移导致对方程序来不及响应
"""
import os
import re
import time

# 每轮动作上限
MAX_ACTIONS = 8
# 动作间隔（秒）
STEP_DELAY = 0.12
# 日志文件
_LOG = os.path.join("data", "pc_control.log")

# 指令：允许【键鼠】或 [键鼠] 两种写法。
# ⚠ 参数部分遇到 引号 / 右方括号 / 换行 就停 —— 云端回复是 ["句子"] 这种 JSON 文本，
#   贪婪匹配会把结尾的引号和括号一起吃掉，破坏 JSON。
_LINE = re.compile("[【\\[]\\s*键鼠\\s*[】\\]]\\s*([^\"\\]\\n]{1,120})")

# 给模型的说明（开启时才注入提示词）
PROMPT_RULES = (
    "【电脑操作能力（已开启）】你可以自己操作主人的键鼠。需要动手时，在回复里单独写一行指令，"
    "格式是「【键鼠】动作 参数」，例如：\n"
    "【键鼠】点击 800 250（先移动再左键单击）、【键鼠】双击 800 250、【键鼠】右键 800 250、"
    "【键鼠】移动 800 250、【键鼠】滚轮 下 3、【键鼠】输入 你好、【键鼠】按键 enter、"
    "【键鼠】热键 ctrl+s、【键鼠】等待 0.5。\n"
    "坐标是屏幕像素（左上角为 0 0），看不准就先输出「【看屏幕】」看清画面再动手。"
    "括号里的指令不会念出来，只会保留给它自己执行；不需要动手时不要输出这类指令。"
)

_KEYMAP = {
    "enter": "enter", "回车": "enter", "esc": "esc", "escape": "esc", "退出": "esc",
    "tab": "tab", "空格": "space", "space": "space", "退格": "backspace", "backspace": "backspace",
    "delete": "delete", "del": "delete", "删除": "delete", "ins": "insert", "insert": "insert",
    "上": "up", "up": "up", "下": "down", "down": "down",
    "左": "left", "left": "left", "右": "right", "right": "right",
    "home": "home", "end": "end", "pgup": "page_up", "pgdn": "page_down",
    "pageup": "page_up", "pagedown": "page_down",
    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4", "f5": "f5", "f6": "f6",
    "f7": "f7", "f8": "f8", "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
}
_MODMAP = {"ctrl": "ctrl", "control": "ctrl", "shift": "shift", "alt": "alt",
           "win": "cmd", "cmd": "cmd", "super": "cmd"}


# 自主行动的最小间隔（分钟）：她"自己想动手"时，两次之间至少要隔这么久
DEFAULT_AUTO_MINUTES = 3
# 上次自主行动的时间戳（内存记录，重启后重置）
_last_auto_ts = [0.0]

AUTO_RULES = (
    "【自主行动的权限（已开启）】主人没有开口时，你也可以**自己判断**要不要动手，"
    "不必每次等主人吩咐；但只在确实能帮上忙的时候动手，不要为了动而动。例如："
    "屏幕上有个明显的报错/弹窗需要点掉、主人正要把东西拖来拖去、聊天窗口空着可以帮他打句招呼。"
    "动手前如果不确定画面，先输出「【看屏幕】」看清再决定。"
    "动手时照旧用「【键鼠】动作 参数」指令；不需要动手就正常说话，别硬找事做。"
    "主人明确让你做事时不受此限制，直接动手即可。"
)


def _cfg_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def _log_line(msg: str):
    try:
        print(f"[PC] {msg}")
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(_LOG) or ".", exist_ok=True)
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def enabled() -> bool:
    """是否允许操控电脑（config.json 的 pc_control_enabled，默认关闭）"""
    try:
        from tool.config import get_config
        v = get_config("./config.json").get("pc_control_enabled", "false")
        return str(v).strip().lower() in ("true", "1", "yes", "on")
    except Exception:
        return False


def set_enabled(on: bool) -> bool:
    """菜单开关用：写进 config.json（持久化）"""
    try:
        from tool.config import get_config
        import json
        cfg = dict(get_config("./config.json") or {})
        cfg["pc_control_enabled"] = "true" if on else "false"
        p = _cfg_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        _log_line(f"操控电脑 → {'已开启' if on else '已关闭'}")
        return True
    except Exception as e:
        _log_line(f"⚠ 写入开关失败: {e}")
        return False


def auto_enabled() -> bool:
    """是否允许她**自己主动**操作电脑（不等主人开口）：config.json 的 pc_auto_enabled"""
    try:
        from tool.config import get_config
        v = get_config("./config.json").get("pc_auto_enabled", "false")
        return str(v).strip().lower() in ("true", "1", "yes", "on")
    except Exception:
        return False


def set_auto_enabled(on: bool) -> bool:
    try:
        from tool.config import get_config
        import json
        cfg = dict(get_config("./config.json") or {})
        cfg["pc_auto_enabled"] = "true" if on else "false"
        p = _cfg_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        _log_line(f"自主操作 → {'已开启' if on else '已关闭'}")
        return True
    except Exception as e:
        _log_line(f"⚠ 写入自主开关失败: {e}")
        return False


def auto_minutes() -> float:
    try:
        from tool.config import get_config
        return max(0.5, float(get_config("./config.json").get("pc_auto_minutes") or DEFAULT_AUTO_MINUTES))
    except Exception:
        return float(DEFAULT_AUTO_MINUTES)


def prompt_rules() -> str:
    """按开关拼出要给模型的说明（允许操控 + 是否自主）"""
    if not enabled():
        return ""
    txt = PROMPT_RULES
    if auto_enabled():
        txt = txt + chr(10) + AUTO_RULES
    return txt


def auto_cooldown_left() -> float:
    """距离下次可以自主行动还剩几秒（0 = 可以动手）"""
    try:
        gap = auto_minutes() * 60.0
        left = gap - (time.time() - float(_last_auto_ts[0] or 0.0))
        return max(0.0, left)
    except Exception:
        return 0.0


def parse(text: str) -> list:
    """从回复里解析出动作列表（解析不出来就返回空）"""
    out = []
    for m in _LINE.finditer(str(text or "")):
        raw = m.group(1).strip()
        if not raw:
            continue
        parts = raw.split()
        op = parts[0]
        try:
            if op in ("移动", "移动鼠标", "移动到") and len(parts) >= 3:
                out.append({"type": "move", "x": int(parts[1]), "y": int(parts[2])})
            elif op in ("点击", "单击", "左键") and len(parts) >= 3:
                out.append({"type": "click", "x": int(parts[1]), "y": int(parts[2])})
            elif op == "双击" and len(parts) >= 3:
                out.append({"type": "double", "x": int(parts[1]), "y": int(parts[2])})
            elif op in ("右键", "右击") and len(parts) >= 3:
                out.append({"type": "right", "x": int(parts[1]), "y": int(parts[2])})
            elif op == "滚轮" and len(parts) >= 2:
                _d = parts[1]
                _n = int(parts[2]) if len(parts) >= 3 else 1
                out.append({"type": "scroll", "up": _d not in ("下", "down", "downwards"), "n": abs(_n)})
            elif op in ("输入", "打字", "键入", "输入文字"):
                txt = raw[len(op):].strip().strip("「」\"'")
                if txt:
                    out.append({"type": "type", "text": txt})
            elif op in ("按键", "按"):
                if len(parts) >= 2:
                    out.append({"type": "key", "key": parts[1]})
            elif op in ("热键", "组合键"):
                if len(parts) >= 2:
                    out.append({"type": "hotkey", "keys": parts[1].split("+")})
            elif op in ("等待", "暂停", "sleep"):
                if len(parts) >= 2:
                    out.append({"type": "wait", "s": max(0.0, min(5.0, float(parts[1])))})
        except Exception:
            _log_line(f"⚠ 这条指令看不懂，已跳过: {raw[:40]}")
    return out[:MAX_ACTIONS]


def strip(text: str) -> str:
    """把指令行从要显示/朗读的文字里去掉（她只动手，不念指令）"""
    try:
        return _LINE.sub("", str(text or "")).strip()
    except Exception:
        return text


def _screen_size():
    try:
        from PyQt5.QtGui import QGuiApplication
        g = QGuiApplication.primaryScreen().availableGeometry()
        return int(g.x()), int(g.y()), int(g.width()), int(g.height())
    except Exception:
        return 0, 0, 1920, 1080


def _resolve_key(name: str):
    """把「enter」「a」「5」这类名字解析成 pynput 能按的东西"""
    from pynput.keyboard import Key
    n = str(name or "").strip().lower()
    if not n:
        return None
    if n in _KEYMAP:
        return getattr(Key, _KEYMAP[n], None)
    if len(n) == 1:
        return n
    return getattr(Key, n, None)


def execute(actions: list, dry_run: bool = False, auto: bool = False) -> list:
    """执行动作。dry_run=True 只做校验和日志，不动真实键鼠（自测用）。

    auto=True 表示这是**她自己主动**要动手（主人没开口）：
      * 需要在菜单里额外打开「自主操作」
      * 有最小间隔（config 的 pc_auto_minutes，默认 3 分钟），避免她自己反复点
    返回实际执行成功的动作列表。
    """
    if not actions:
        return []
    if not dry_run and not enabled():
        _log_line("操控电脑未开启（右键菜单可打开）→ 本轮动作已忽略")
        return []
    if not dry_run and auto:
        if not auto_enabled():
            _log_line("她主动想动手，但「自主操作」没开 → 已忽略（菜单里可打开）")
            return []
        left = auto_cooldown_left()
        if left > 0:
            _log_line(f"她主动想动手，但距离上次自主行动还差 {left:.0f} 秒 → 已忽略")
            return []
        _last_auto_ts[0] = time.time()
        _log_line("⭐ 她主自动手（主人没开口）")
    x0, y0, sw, sh = _screen_size()
    done = []
    try:
        from pynput.mouse import Controller as _M, Button
        from pynput.keyboard import Controller as _K
        _mouse, _kb = _M(), _K()
    except Exception as e:
        _log_line(f"⚠ 键鼠控制不可用（pynput: {e}）")
        return []

    for a in list(actions)[:MAX_ACTIONS]:
        t = a.get("type")
        try:
            if t in ("move", "click", "double", "right"):
                x, y = int(a["x"]), int(a["y"])
                if not (x0 <= x <= x0 + sw and y0 <= y <= y0 + sh):
                    _log_line(f"⚠ 坐标 ({x},{y}) 超出屏幕 {sw}x{sh} → 丢弃")
                    continue
                if dry_run:
                    _log_line(f"[演练] {t} ({x},{y})")
                    done.append(a)
                    continue
                _mouse.position = (x, y)
                time.sleep(0.05)
                if t == "click":
                    _mouse.click(Button.left, 1)
                elif t == "double":
                    _mouse.click(Button.left, 2)
                elif t == "right":
                    _mouse.click(Button.right, 1)
                _log_line(f"{t} ({x},{y})")
                done.append(a)
            elif t == "scroll":
                n = max(1, min(20, int(a.get("n", 1))))
                step = 1 if a.get("up") else -1
                if dry_run:
                    _log_line(f"[演练] scroll {'上' if step > 0 else '下'} x{n}")
                    done.append(a)
                    continue
                for _ in range(n):
                    _mouse.scroll(0, step)
                    time.sleep(0.03)
                _log_line(f"scroll {'上' if step > 0 else '下'} x{n}")
                done.append(a)
            elif t == "type":
                txt = str(a.get("text") or "")
                if dry_run:
                    _log_line(f"[演练] type {txt[:30]!r}")
                    done.append(a)
                    continue
                _kb.type(txt)
                _log_line(f"type {txt[:30]!r}")
                done.append(a)
            elif t == "key":
                k = _resolve_key(a.get("key"))
                if k is None:
                    _log_line(f"⚠ 不认识的按键: {a.get('key')}")
                    continue
                if dry_run:
                    _log_line(f"[演练] key {a.get('key')}")
                    done.append(a)
                    continue
                _kb.press(k)
                _kb.release(k)
                _log_line(f"key {a.get('key')}")
                done.append(a)
            elif t == "hotkey":
                keys = [_resolve_key(k) for k in (a.get("keys") or [])]
                keys = [k for k in keys if k is not None]
                if not keys:
                    continue
                if dry_run:
                    _log_line(f"[演练] hotkey {'+'.join(a.get('keys') or [])}")
                    done.append(a)
                    continue
                for k in keys:
                    _kb.press(k)
                for k in reversed(keys):
                    _kb.release(k)
                _log_line(f"hotkey {'+'.join(a.get('keys') or [])}")
                done.append(a)
            elif t == "wait":
                s = max(0.0, min(5.0, float(a.get("s", 0.5))))
                if not dry_run:
                    time.sleep(s)
                _log_line(f"wait {s}s")
                done.append(a)
        except Exception as e:
            _log_line(f"⚠ 执行 {t} 失败: {type(e).__name__}: {e}")
        # 动作之间留点间隔，别让鼠标瞬移
        if not dry_run and t not in ("wait",):
            time.sleep(STEP_DELAY)
    return done


if __name__ == "__main__":
    # 自测：只解析 + 演练，不动真实键鼠
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    demo = "好啊，我帮你点一下。【键鼠】点击 800 250\n【键鼠】滚轮 下 3\n【键鼠】输入 你好\n【键鼠】热键 ctrl+s"
    acts = parse(demo)
    print("解析出动作:", acts)
    print("去掉指令后的文字:", strip(demo))
    execute(acts, dry_run=True)
