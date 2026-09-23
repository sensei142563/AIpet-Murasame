# -*- coding: utf-8 -*-
"""让桌宠能自己操作键鼠：移动/点击/双击/右键/滚轮/键盘输入/组合键/等待。

开关（默认关闭，安全第一）：
    桌宠右键菜单 →「允许操控电脑（键鼠）」→ 写 config.json 的 pc_control_enabled。
    关掉后立刻停止执行，已排队的动作全部丢弃。
    另有「自主操作（不用主人开口）」→ pc_auto_enabled，允许她自己判断要不要动手。

她怎么表达"要做什么"：回复里带一行动作指令即可（和【看屏幕】同一个套路）：
    【键鼠】移动 800 250
    【键鼠】点击 800 250      【键鼠】双击 800 250      【键鼠】右键 800 250
    【键鼠】滚轮 下 3          （上 / 下）
    【键鼠】输入 你好，世界
    【键鼠】按键 enter        【键鼠】热键 ctrl+s
    【键鼠】等待 0.5

模型实际会写出来的花式写法（云端模型很爱加括号和解释），这里都认：
    【键鼠】点击(800, 250)      【键鼠】点击 800，250     【键鼠】点击 x=800 y=250
    【键鼠】点击 800 250（屏幕中央的弹窗）                [键鼠] click 800 250
    【键鼠】点击 中央 / 左上 / 右上 / 左下 / 右下         （估不准像素时的方位词）
    【键鼠】点击 800 250，然后输入 你好                  （一条写多个动作）

安全限制：
    * 不限制每轮动作条数（限制会让她"做到一半停下"）；只留防跑飞的保险丝
    * 同一个动作 90 秒内重复的会被丢掉（她做过没看到变化时容易反复点同一处）
    * 坐标必须落在屏幕内，越界直接丢弃并记日志
    * 每个动作写一行日志（data/pc_control.log + 控制台），随时可查她做了什么
    * 动作之间留 120ms 间隔，避免鼠标瞬移导致对方程序来不及响应
    * 「移动」只挪鼠标、不产生任何实际效果；只有点击/双击/右键/滚轮/输入/按键/热键
      才算"真的做了事"，自主行动的间隔也只被这些动作消耗。
"""
import os
import re
import time

# 安全限制
# ⚠ 不再限制每轮动作条数：限制会让她"做到一半停下"（用户反馈）。
#   这里只留一个防跑飞的保险丝（正常一轮几十条都用不到）。
SAFETY_MAX = 500
# 重复抑制窗口（秒）：同一个地方连续点超过 DUP_ATTEMPTS 次才判为"卡在重复"
# ⚠ 不能一重复就挡：按两次 win 是"开开始菜单再关掉"、点两下同一个按钮可能是正常的
#   （实测一刀切把她的合法重试也挡死了，任务直接卡住）。
DUP_WINDOW = 90
DUP_ATTEMPTS = 2
_recent_acts = []          # [(指纹, 时间, 次数)]
_dup_hits = [0]
# 立刻停手的开关（主人喊停 / 任务中止）：每个动作执行前都要检查
_abort = ["", 0.0]


def set_abort(reason: str = "主人喊停"):
    """立刻停手：正在执行的动作做完当前这一个就停，后面的全部丢弃。

    8 秒后自动失效——避免这个标记留着，把主人之后让她做的事也一起挡掉。
    """
    _abort[0] = str(reason or "停")
    _abort[1] = time.time()
    _log_line(f"⛔ 收到停止请求（{_abort[0]}）→ 后续动作不再执行")


def clear_abort():
    _abort[0] = ""
    _abort[1] = 0.0


def abort_requested() -> str:
    if _abort[0] and (time.time() - float(_abort[1] or 0)) > 8:
        clear_abort()
    return _abort[0]
# 做完之后的"说一句"回调（桌宠注册，用来让她汇报自己干了什么；Worker 线程里调用）
_narrator = [None]


def set_narrator(fn):
    """桌宠注册：动作真正做完后回调 done 列表，用来让她说一句"我做了什么/接下来想干什么"。"""
    _narrator[0] = fn


def _act_key(a: dict) -> str:
    """动作指纹：用来判断"她是不是又在重复同一件事"（坐标抖动 20px 以内算同一处）"""
    t = str(a.get("type") or "")
    if t in ("move", "click", "double", "right"):
        return "%s@%d,%d" % (t, int(a.get("x", 0)) // 20, int(a.get("y", 0)) // 20)
    if t == "type":
        return "type:" + str(a.get("text") or "")[:40]
    if t == "key":
        return "key:" + str(a.get("key") or "")
    if t == "hotkey":
        return "hotkey:" + "+".join(a.get("keys") or [])
    if t == "scroll":
        return "scroll:" + ("up" if a.get("up") else "down")
    return t


def _is_dup(a: dict) -> bool:
    """这个点击是不是"卡住重复了"→ True 表示应当跳过。

    只对"点哪里"这类做抑制（click/double/right），而且同一个地方**允许连做两次**，
    第三次起才判为卡住——按两次 win 是开关开始菜单、点两下同一个按钮也常常是正常的，
    一刀切会把合法的重试也挡掉（实测她就此卡死）。坐标按 ±24px 容差算同一处。
    """
    try:
        t = str(a.get("type") or "")
        if t not in ("click", "double", "right"):
            return False
        x, y = int(a.get("x", 0)), int(a.get("y", 0))
        now = time.time()
        _recent_acts[:] = [r for r in _recent_acts if now - r[1] < DUP_WINDOW]
        for i, (kk, _ts, cnt) in enumerate(_recent_acts):
            try:
                kt, pos = kk.split("@", 1)
                px, py = pos.split(",")
                if kt == t and abs(int(px) - x) <= 24 and abs(int(py) - y) <= 24:
                    if cnt >= DUP_ATTEMPTS:
                        return True
                    _recent_acts[i] = (kk, now, cnt + 1)
                    return False
            except Exception:
                continue
        _recent_acts.append(("%s@%d,%d" % (t, x, y), now, 1))
        return False
    except Exception:
        return False


def describe(actions: list) -> str:
    """把动作列表说成人话（给她汇报 / 给日志用）"""
    _names = {"move": "移动鼠标", "click": "点击", "double": "双击", "right": "右键单击",
              "scroll": "滚轮", "type": "输入文字", "key": "按键", "hotkey": "按组合键",
              "wait": "等待"}
    out = []
    for a in (actions or [])[:12]:
        t = str(a.get("type") or "")
        n = _names.get(t, t)
        if t in ("move", "click", "double", "right"):
            n += " (%s,%s)" % (a.get("x"), a.get("y"))
        elif t == "type":
            n += "「%s」" % str(a.get("text") or "")[:20]
        elif t == "key":
            n += " %s" % a.get("key")
        elif t == "hotkey":
            n += " %s" % "+".join(a.get("keys") or [])
        elif t == "scroll":
            n += " %s %s 下" % ("上" if a.get("up") else "下", a.get("n", 1))
        out.append(n)
    return "、".join(out) if out else "（什么都没做）"
# 动作间隔（秒）
STEP_DELAY = 0.12
# 日志文件
_LOG = os.path.join("data", "pc_control.log")

# 自主行动的最小间隔（分钟）：她"自己想动手"时，两次之间至少要隔这么久。
# 以前默认 3 分钟——她看到弹窗想点掉，被间隔拦下来就成了"只说不做"（用户反馈）。
DEFAULT_AUTO_MINUTES = 1

# ⚠ 参数部分遇到 引号 / 右方括号 / 换行 就停 —— 云端回复是 ["句子"] 这种 JSON 文本，
#   贪婪匹配会把结尾的引号和括号一起吃掉，破坏 JSON。
_MARK = re.compile("[【\\[（(]\\s*(?:键鼠|鼠标|电脑)\\s*[】\\]）)]\\s*[:：]?\\s*([^\"\\]\\n]{1,160})")

# 动作关键字（长的写在前面：左键单击要能被拆成「左键」+「单击」两段）
# ⚠ 别加光秃秃的「按」——「右上角关闭按钮」会被拆出一个「按键 钮」的假动作
_OP_RE = re.compile(
    "(双击|输入文字|组合键|点击|单击|左键|右键|右击|移动|移到|滚轮|滚动|点一下|"
    "输入|打字|键入|按键|按下|热键|等待|暂停|"
    "double|click|right|move|scroll|type|press|hotkey|wait)",
    re.I,
)
_KW_TYPE = {
    "移动": "move", "移到": "move", "move": "move",
    "点击": "click", "单击": "click", "左键": "click", "点一下": "click", "click": "click",
    "双击": "double", "double": "double",
    "右键": "right", "右击": "right", "right": "right",
    "滚轮": "scroll", "滚动": "scroll", "scroll": "scroll",
    "输入": "type", "输入文字": "type", "打字": "type", "键入": "type", "type": "type",
    "按键": "key", "按下": "key", "key": "key", "press": "key",
    "热键": "hotkey", "组合键": "hotkey", "hotkey": "hotkey",
    "等待": "wait", "暂停": "wait", "wait": "wait",
}
# 会产生实际效果的动作（自主间隔只被这些消耗）
_REAL_TYPES = ("click", "double", "right", "scroll", "type", "key", "hotkey")

_NUM = re.compile("-?\\d+(?:\\.\\d+)?")
# 取数字前先把全角标点/括号/等号统一成空格，这样 800，250 / (800,250) / x=800 都能取到
_NORM = re.compile("[，,、;；()（）\\[\\]【】=＝:：/]")
_CN = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
       "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
# 方位词 → 屏幕相对位置（她估不准像素时的兜底，比"什么都不做"强）
# ⚠ 顺序有意义：先匹配到的赢，所以「右上角关闭按钮」要命中「右上」而不是「上」
_ANCHORS = (("左上", 0.06, 0.06), ("右上", 0.94, 0.06),
            ("左下", 0.06, 0.94), ("右下", 0.94, 0.94),
            ("中央", 0.5, 0.5), ("中间", 0.5, 0.5), ("中心", 0.5, 0.5),
            # 桌面常见目标（模型很爱写「点击 底部任务栏 哔哩哔哩图标」这种没坐标的描述）
            ("任务栏", 0.5, 0.97), ("开始菜单", 0.025, 0.97), ("开始按钮", 0.025, 0.97),
            ("托盘", 0.97, 0.97), ("桌面", 0.5, 0.45),
            ("顶部", 0.5, 0.06), ("上方", 0.5, 0.06),
            ("底部", 0.5, 0.94), ("下方", 0.5, 0.94))

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

# 上次自主行动的时间戳（内存记录，重启后重置）
_last_auto_ts = [0.0]
# pynput 的鼠标控制器（只建一次：导入要一两百毫秒，每轮都导会拖慢对话）
_mouse_c = [None, False]


# 给模型的说明（开启时才注入提示词）
PROMPT_RULES = (
    "【电脑操作能力（已开启）】你可以直接操作主人的键鼠。需要动手时，在回复里单独写一行指令，"
    "格式是「【键鼠】动作 参数」，例如：\n"
    "【键鼠】点击 800 250（把鼠标移过去并左键单击一下）、【键鼠】双击 800 250、【键鼠】右键 800 250、"
    "【键鼠】移动 800 250、【键鼠】滚轮 下 3、【键鼠】输入 你好、【键鼠】按键 enter、"
    "【键鼠】热键 ctrl+s、【键鼠】等待 0.5。\n"
    "★★ 主人明确让你做事时（打开某个软件、点掉什么、输入什么），你的回复里**必须**至少带一条"
    "「【键鼠】…」或「【看屏幕】」指令。只回一句「行」「这就去」「这次真给你开」等于没做——"
    "他等的不是你答应，是你动手。\n"
    "★★ 坐标只能写「两个数字」或方位词，不许写「任务栏里那个哔哩哔哩图标」这种没有坐标的描述，"
    "那样执行不了。方位词：中央／左上／右上／左下／右下／顶部／底部／任务栏／开始菜单／托盘／桌面。\n"
    "★ 位置估不准时的正确做法：先「【键鼠】移动 800 250」把鼠标挪过去，再「【看屏幕】」"
    "看清鼠标底下是什么，确认后再「【键鼠】点击 800 250」。\n"
    "★ 边说话边动手：动手那一轮也要说一句人话（例如「好，我来点」「点掉了，你看看」），"
    "不能只留一行指令——只发指令的回合主人什么都听不到，会以为你哑了。\n"
    "★ 一次把整件事写完：一件事要几步就一次写几行指令（点完等界面反应就写「【键鼠】等待 0.8」），"
    "别一步一条回复慢慢磨——那样一步要等半分钟，主人会等到发火。\n"
    "★ 看屏幕很慢（一次十几秒），同一次动手最多看一次；能靠已知位置判断就别看。\n"
    "★★ 分清「陪你玩」和「帮你操作」：\n"
    "   · 「陪我打火影」「陪我玩」「一起玩」「陪我聊聊天」这类，是**要你陪着说话**，"
    "不是你该去开程序——绝对不要输出【键鼠】指令，用话回应他（例如「好啊，你打我看」）；\n"
    "   · 只有明确的操作要求（「帮我打开火影」「把那个窗口关掉」「点一下确定」「帮我下载…」）"
    "才是让你动手；\n"
    "   · 拿不准就先问一句「要我帮你打开吗？」——宁可不做，也别做错。\n"
    "★ 同一个地方别连着点三次（重复的会被丢掉）。做过没变化就换个办法，"
    "或者直接告诉主人你做不了、让他自己来。\n"
    "★ 宁可多用键盘、少猜坐标：打开软件用「【键鼠】热键 win」→「【键鼠】输入 软件名」"
    "→「【键鼠】按键 enter」；搜东西用「【键鼠】热键 ctrl+f」再输入；切换窗口用 alt+tab。"
    "这些不会点到别的窗口上去（用户反馈过'点击点到别的窗口上'）。\n"
    "★ 要点击某个东西之前，先确认它在最前面（不确定就【看屏幕】看一眼）；"
    "看不准就改用键盘，或者直接跟主人说做不到。\n"
    "★ 只写「移动」等于什么都没做（那只是把鼠标挪过去），不许拿它敷衍。"
    "指令那一行不会被念出来。"
)

AUTO_RULES = (
    "【自主行动的权限（已开启）】主人没有开口时，你也可以**自己判断**要不要动手，"
    "不必每次等主人吩咐。看到屏幕上明显的弹窗、报错、广告、需要点掉的按钮，"
    "就该动手点掉，别只在嘴上说。判断依据是你最近看到的画面描述；"
    "拿不准就先输出「【看屏幕】」看清再决定，一次动手最多看一次。"
    "动手时照旧用「【键鼠】动作 参数」指令；确实没什么可做的就正常说话，别硬找事做。"
    "主人明确让你做事时不受此限制，直接动手即可。"
    "★ 但主人正在玩的游戏、正在看的视频、正在聊天的窗口，绝不要自己去点（那是他要用，不是挡路的）。"
    "★ 主人说「陪我玩/陪我打/一起玩」时，他要的是你陪着说话，不是让你动手。"
    "★ 主人中途喊停（停、别动、算了…）时，你已经停手了，如实回他一句就好，别再动手。"
)

# 「陪我玩」和「帮我打开」要分清楚：只有出现明确的操作词，才允许动手（用户反馈：
# 他说"陪我打火影"，桌宠却去操作电脑想打开火影）。
_EXPLICIT_ACTION = (
    "打开", "开一下", "开下", "关掉", "关闭", "关一下", "点一下", "点开", "点击", "双击",
    "输入", "打字", "下载", "搜索", "搜一下", "安装", "切到", "切一下", "返回", "刷新",
    "保存", "发送", "发个", "登录", "帮我", "替我", "替我点", "调出", "最小化", "最大化",
    "把那个", "给我开", "给我点",
)
_CHAT_ONLY = ("陪我", "一起玩", "一起打", "陪你", "聊聊天", "说说话", "陪我聊", "陪我玩",
              "一起看", "看着我", "看你打")


def looks_like_chat_only(text: str) -> bool:
    """主人这句话是不是只是"想让你陪着"（而不是让你操作电脑）。

    没有明确的操作词、又出现「陪我/一起玩/陪我聊」这类 → 判定为陪聊。
    有明确操作词（帮我打开、点一下、下载…）一律放行，避免误拦真正的要求。
    """
    try:
        t = str(text or "").strip()
        if not t:
            return False
        if any(w in t for w in _EXPLICIT_ACTION):
            return False
        return any(w in t for w in _CHAT_ONLY)
    except Exception:
        return False


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


# ─────────────────────────── 开关 ───────────────────────────

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
    return _write_flag("pc_control_enabled", on, "操控电脑")


def auto_enabled() -> bool:
    """是否允许她**自己主动**操作电脑（不等主人开口）：config.json 的 pc_auto_enabled"""
    try:
        from tool.config import get_config
        v = get_config("./config.json").get("pc_auto_enabled", "false")
        return str(v).strip().lower() in ("true", "1", "yes", "on")
    except Exception:
        return False


def set_auto_enabled(on: bool) -> bool:
    return _write_flag("pc_auto_enabled", on, "自主操作")


def _write_flag(key: str, on: bool, label: str) -> bool:
    try:
        from tool.config import get_config
        import json
        cfg = dict(get_config("./config.json") or {})
        cfg[key] = "true" if on else "false"
        p = _cfg_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        _log_line(f"{label} → {'已开启' if on else '已关闭'}")
        return True
    except Exception as e:
        _log_line(f"⚠ {label}开关写入失败: {e}")
        return False


def auto_minutes() -> float:
    try:
        from tool.config import get_config
        return max(0.2, float(get_config("./config.json").get("pc_auto_minutes") or DEFAULT_AUTO_MINUTES))
    except Exception:
        return float(DEFAULT_AUTO_MINUTES)


def auto_cooldown_left() -> float:
    """距离下次可以自主行动还剩几秒（0 = 可以动手）"""
    try:
        gap = auto_minutes() * 60.0
        left = gap - (time.time() - float(_last_auto_ts[0] or 0.0))
        return max(0.0, left)
    except Exception:
        return 0.0


# ─────────────────────── 屏幕信息 / 提示词 ───────────────────────

def _screen_size():
    try:
        from PyQt5.QtGui import QGuiApplication
        g = QGuiApplication.primaryScreen().availableGeometry()
        return int(g.x()), int(g.y()), int(g.width()), int(g.height())
    except Exception:
        return 0, 0, 1920, 1080


def _mouse_pos():
    """当前鼠标位置（拿不到返回 None）"""
    try:
        if _mouse_c[0] is None and not _mouse_c[1]:
            try:
                from pynput.mouse import Controller
                _mouse_c[0] = Controller()
            except Exception:
                _mouse_c[1] = True          # 记下失败，别每次都重试
        if _mouse_c[0] is not None:
            return int(_mouse_c[0].position[0]), int(_mouse_c[0].position[1])
    except Exception:
        pass
    return None


def screen_brief() -> str:
    """把屏幕尺寸和鼠标当前位置写给她 —— 坐标全靠猜是点不准的最大原因。"""
    try:
        x0, y0, w, h = _screen_size()
        s = ("【当前屏幕】%d×%d 像素（左上角 0,0；中央 %d,%d；右下角 %d,%d）。"
             % (w, h, x0 + w // 2, y0 + h // 2, x0 + w - 1, y0 + h - 1))
        p = _mouse_pos()
        if p:
            s += "你的鼠标此刻停在 (%d, %d)。" % (p[0], p[1])
        return s
    except Exception:
        return ""


_FLAG_SEEN = [None]


def turn_reminder() -> str:
    """每轮贴在主人那句话后面的「现在就动手」提醒。

    为什么需要（实测）：系统提示词离得太远，长对话里她的老习惯会盖过规则——
    真实历史 406 条时，主人说「帮我打开哔哩哔哩」，她只回
    「白天说了一遍，晚上又一遍。这次真给你开。」一条指令都没有；
    同一句话放在干净历史下，她会正常输出【键鼠】+【看屏幕】。
    贴在最后一条消息上（模型最近看到的），她才会当真。
    """
    if not enabled():
        return ""
    s = (chr(10) + chr(10) + "（系统提醒｜必须遵守：主人这句话如果是让你做事，你现在就要真的动手——"
         "回复里必须带上「【键鼠】动作 参数」指令；只回一句「行/好的/这次真给你开」等于没做。"
         "不知道东西在哪就先「【键鼠】移动 <x> <y>」再「【看屏幕】」，看清了再点；"
         "坐标只写数字或方位词（中央／左上／右上／任务栏／底部…），别写文字描述。）")
    if auto_enabled():
        s += "（你自己想动手时也一样，看准了就直接动手。）"
    return s


def prompt_rules() -> str:
    """按开关拼出要给模型的说明（允许操控 + 是否自主）"""
    _on = enabled()
    if _FLAG_SEEN[0] != _on:
        _FLAG_SEEN[0] = _on
        _log_line("键鼠规则已交给模型（她能自己动手了）" if _on else
                  "键鼠规则未注入：菜单里的「允许操控电脑（键鼠）」没开 → 她只会嘴上答应")
    if not _on:
        return ""
    txt = PROMPT_RULES + chr(10) + screen_brief()
    if auto_enabled():
        txt = txt + chr(10) + AUTO_RULES
    return txt


# ─────────────────────── 解析（她说了什么动作）───────────────────────

def _norm(s: str) -> str:
    return _NORM.sub(" ", str(s or ""))


def _to_int(tok):
    try:
        return int(float(tok))
    except Exception:
        return None


def _cn_count(s: str) -> int:
    for ch, v in _CN.items():
        if ch in str(s or ""):
            return v
    return 0


def _anchor_xy(s: str):
    for w, fx, fy in _ANCHORS:
        if w in s:
            x0, y0, sw, sh = _screen_size()
            return int(x0 + sw * fx), int(y0 + sh * fy)
    return None


def _pos_of(s: str):
    """从参数里取坐标：数字优先，取不到就用方位词/桌面目标词"""
    nums = _NUM.findall(_norm(s))
    if len(nums) >= 2:
        x, y = _to_int(nums[0]), _to_int(nums[1])
        if x is not None and y is not None:
            return x, y
    a = _anchor_xy(s)
    if a:
        _log_line("⚠ 指令里没有坐标，按方位词估了个位置 (%d,%d)：%s" % (a[0], a[1], str(s).strip()[:40]))
    return a


def _text_of(s: str) -> str:
    """「输入」后面要打的字：去掉「文字/文本/内容」这类前缀、去掉解释性括注"""
    t = str(s or "").strip()
    t = re.sub("^(?:文字|文本|内容|这串字|这一串|这样写)", "", t).strip()
    t = re.sub("^[:：]", "", t).strip()
    for cut in ("（", "(", "【", "["):
        i = t.find(cut)
        if i > 0:
            t = t[:i]
    return t.strip().strip("\"'“”「」『』").strip()[:200]


def _key_of(s: str) -> str:
    parts = re.split("[\\s，,;；/、]+", str(s or "").strip())
    tok = parts[0] if parts and parts[0] else ""
    return tok.strip("：:。.、\"'“”「」()（）").lower()


def _keys_of(s: str) -> list:
    t = str(s or "").replace("＋", "+").replace("加", "+")
    toks = re.split("[\\s，,、+\\-]+", t)
    out = []
    for k in toks:
        k = k.strip("：:。.\"'“”「」()（）").lower()
        if k:
            out.append(k)
    return out[:4]


def _split_ops(seg: str) -> list:
    """把一段指令按动作关键字拆开（她可能在一行里写了「点击…然后输入…」）"""
    ms = list(_OP_RE.finditer(seg))
    out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(seg)
        out.append((m.group(1), seg[m.end():end]))
    return out


def _make_action(kw: str, rest: str):
    kind = _KW_TYPE.get(str(kw).lower())
    if not kind:
        return None
    if kind in ("move", "click", "double", "right"):
        xy = _pos_of(rest)
        if not xy:
            return None
        return {"type": kind, "x": xy[0], "y": xy[1]}
    if kind == "scroll":
        low = str(rest).lower()
        up = any(w in low for w in ("上", "up", "往上", "向前", "前"))
        m = re.search("-?\\d+", _norm(rest))
        n = _to_int(m.group(0)) if m else None
        if n is None:
            n = _cn_count(rest) or 1
        if n < 0:
            up, n = False, -n
        return {"type": "scroll", "up": bool(up), "n": max(1, min(20, n or 1))}
    if kind == "type":
        txt = _text_of(rest)
        return {"type": "type", "text": txt} if txt else None
    if kind == "key":
        k = _key_of(rest)
        return {"type": "key", "key": k} if k else None
    if kind == "hotkey":
        ks = _keys_of(rest)
        return {"type": "hotkey", "keys": ks} if ks else None
    if kind == "wait":
        m = re.search("\\d+(?:\\.\\d+)?", _norm(rest))
        if m:
            try:
                s = float(m.group(0))
            except Exception:
                s = 1.0
        else:
            s = float(_cn_count(rest) or 1)
        return {"type": "wait", "s": max(0.0, min(5.0, s))}
    return None


def _parse_seg(seg: str) -> list:
    out = []
    for kw, rest in _split_ops(seg):
        a = _make_action(kw, rest)
        if a:
            out.append(a)
    return out


_SCAN_CACHE = {"src": None, "val": None}


def scan(text: str):
    """返回 (动作列表, 要删掉的字符区间)。

    只有带标记的行才算指令；解析不出来也照样删掉（那种半截指令念出来更糟），
    并写一条日志方便排查——"她好像说了要做什么但没做"时先看 data/pc_control.log。
    """
    src = str(text or "")
    if _SCAN_CACHE["src"] == src and _SCAN_CACHE["val"] is not None:
        return _SCAN_CACHE["val"]
    acts, spans = [], []
    for m in _MARK.finditer(src):
        seg = m.group(1)
        spans.append((m.start(), m.end()))
        got = _parse_seg(seg)
        if got:
            acts.extend(got)
        elif str(seg).strip():
            _log_line(f"⚠ 这条指令看不懂，已跳过: {str(seg).strip()[:60]}")
    val = (acts[:SAFETY_MAX] if SAFETY_MAX else acts, spans)
    _SCAN_CACHE["src"] = src
    _SCAN_CACHE["val"] = val
    return val


def parse(text: str) -> list:
    """从回复里解析出动作列表（解析不出来就返回空）"""
    try:
        return scan(text)[0]
    except Exception:
        return []


def strip(text: str) -> str:
    """把指令行从要显示/朗读的文字里去掉（她只动手，不念指令）。

    云端回复是 ["句子"] 这种 JSON 文本：指令整句被删掉后会留下一个空串
    （实测出现过 ["", "弹窗还开着…"] → 空句子会浪费一次翻译/TTS），这里顺手清掉。
    """
    src = str(text or "")
    try:
        _acts, spans = scan(src)
        if not spans:
            return src
        out, last = [], 0
        for a, b in spans:
            out.append(src[last:a])
            last = b
        out.append(src[last:])
        txt = "".join(out)
        s = txt.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                import json
                data = json.loads(s)
            except Exception:
                data = None
            if isinstance(data, list):
                data = [d for d in data if not (isinstance(d, str) and not d.strip())]
                if not data:
                    return ""
                return json.dumps(data, ensure_ascii=False)
        txt = re.sub("\\n{2,}", chr(10), txt)
        return txt.strip()
    except Exception:
        return src


# ─────────────────────────── 执行 ───────────────────────────

def _resolve_key(name: str):
    """把「enter」「a」「5」这类名字解析成 pynput 能按的东西"""
    from pynput.keyboard import Key
    n = str(name or "").strip().lower()
    if not n:
        return None
    if n in _KEYMAP:
        return getattr(Key, _KEYMAP[n], None)
    if n in _MODMAP:
        return getattr(Key, _MODMAP[n], None)
    if len(n) == 1:
        return n
    return getattr(Key, n, None)


def execute(actions: list, dry_run: bool = False, auto: bool = False, notify=None,
            no_dup: bool = False) -> list:
    """执行动作。dry_run=True 只做校验和日志，不动真实键鼠（自测用）。

    auto=True 表示这是**她自己主动**要动手（主人没开口）：
      * 需要在菜单里额外打开「自主操作」
      * 有最小间隔（config 的 pc_auto_minutes，默认 1 分钟），避免她自己反复点
      * 只有点击/输入这类真动作才消耗间隔；单纯"移动鼠标"不算
    notify：动作被拦下来时回调一段说明，让桌宠能把"没做成"记进对话，
            免得她下一轮还嘴硬说自己做过了。
    返回实际执行成功的动作列表。
    """
    done = []

    def _drop(reason: str):
        _log_line(reason)
        if notify:
            try:
                notify(reason)
            except Exception:
                pass

    if not actions:
        return []
    if not dry_run and not enabled():
        _drop("操控电脑没开（右键菜单 →「允许操控电脑（键鼠）」）→ 本轮动作已忽略")
        return []
    if not dry_run and auto:
        if not auto_enabled():
            _drop("她想自己动手，但菜单里的「自主操作（不用主人开口）」没开 → 本轮动作已忽略")
            return []
        left = auto_cooldown_left()
        if left > 0:
            _drop("她想自己动手，但距离上次自主动手还差 %.0f 秒（防止她自己反复点）→ 本轮动作已忽略" % left)
            return []
        if any(str(a.get("type")) in _REAL_TYPES for a in actions):
            _last_auto_ts[0] = time.time()
        _log_line("⭐ 她主自动手（主人没开口）")

    x0, y0, sw, sh = _screen_size()
    try:
        from pynput.mouse import Controller as _M, Button
        from pynput.keyboard import Controller as _K
        _mouse, _kb = _M(), _K()
    except Exception as e:
        _drop(f"键鼠控制不可用（pynput: {e}）→ 本轮动作已忽略")
        return []

    _acts = list(actions)
    if SAFETY_MAX and len(_acts) > SAFETY_MAX:
        _acts = _acts[:SAFETY_MAX]
    # ── 自主行动分档：打字/按键这类只在主人开口时做（见 tool/autonomy.py）──
    if not dry_run and auto:
        try:
            from tool import autonomy as _au
            _kept = []
            for _a in _acts:
                _ok, _why = _au.allowed(_a, True)
                if _ok:
                    _kept.append(_a)
                else:
                    _log_line(f"🛡 自主模式下拦下这个动作（{_a.get('type')}）：{_why}")
                    if notify:
                        try:
                            notify(_why)
                        except Exception:
                            pass
            if len(_kept) != len(_acts):
                _acts = _kept
                if not _acts:
                    return []
        except Exception as _ea:
            _log_line(f"⚠ 分档检查失败（照常执行）: {_ea}")
    for a in _acts:
        t = a.get("type")
        # ── 立刻停手：主人喊停 / 任务中止 ──
        if not dry_run and abort_requested():
            _log_line(f"⛔ 已停止（{_abort[0]}）→ 丢弃剩下的动作")
            _drop(f"主人叫停了（{_abort[0]}），剩下的动作我没做")
            break
        # ── 重复抑制：同一个地方连着点太多次才算"卡住"（允许两次） ──
        if not dry_run and not no_dup and _is_dup(a):
            _dup_hits[0] += 1
            _log_line(f"⏭ 这个地方已经点过两次了（{_act_key(a)}）→ 跳过，别再重复")
            _drop("你在反复点同一个地方（%s）。它已经点过了，再点也不会有变化——"
                  "换个办法（比如【看屏幕】看清位置再点），或者直接跟主人说你做不了。"
                  % _act_key(a))
            continue
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
                    _log_line(f"⚠ 不认识的组合键: {a.get('keys')}")
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
    if not dry_run and len(done) < len(_acts):
        _log_line(f"⚠ 本轮 {len(_acts)} 个动作里只做成了 {len(done)} 个"
                  f"（有重复的、坐标越界的或没做成的）")
    # 做完了 → 让桌宠给她一次"说一句"的机会（我做了什么 / 接下来想干什么）
    if not dry_run and done and _narrator[0]:
        try:
            _narrator[0](done)
        except Exception:
            pass
    return done


if __name__ == "__main__":
    # 自测：只解析 + 演练，不动真实键鼠
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    demos = [
        # 云端模型真实会写出来的各种花样
        "【键鼠】移动 960 540",
        "【键鼠】点击 800 250",
        "【键鼠】点击(800, 250)",
        "【键鼠】点击（800，250）",
        "【键鼠】点击 x=800 y=250",
        "【键鼠】双击 800 250（屏幕中央的弹窗）",
        "【键鼠】点击 中央",
        "【键鼠】点击 800 250，然后输入 你好",
        "[键鼠] click 800 250",
        "【键鼠】右键 800 250",
        "【键鼠】滚轮 下 3",
        "【键鼠】滚轮 向上 五",
        "【键鼠】输入文字：你好，世界",
        "【键鼠】输入 你好（在搜索框里）",
        "【键鼠】按键 enter",
        "【键鼠】热键 ctrl+s",
        "【键鼠】等待 0.5",
        "【键鼠】等待一秒",
        "【键鼠】晃动鼠标",                       # 解析不出来 → 只写日志
    ]
    print("=== 逐条解析 ===")
    for d in demos:
        print("  %-38s → %s" % (d, parse(d)))
    print()
    print("=== 云端 JSON 回复（整句被删后不留空串）===")
    raw = '["【键鼠】点击 800 250","弹窗还开着，先给你点掉。","哔哩哔哩在任务栏吧，自己找一下。"]'
    print("  原文 :", raw)
    print("  解析 :", parse(raw))
    print("  剥离 :", strip(raw))
    print()
    print("=== 普通聊天不该被动过 ===")
    plain = '["今天天气不错呢。","要不要一起看视频？"]'
    print("  %s → %s" % (plain, strip(plain)))
    print()
    print("=== 演练执行（不动真键鼠）===")
    execute([{"type": "click", "x": 800, "y": 250}, {"type": "scroll", "up": False, "n": 3},
             {"type": "type", "text": "你好"}, {"type": "hotkey", "keys": ["ctrl", "s"]}],
            dry_run=True)
