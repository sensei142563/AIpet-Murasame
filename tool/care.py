# -*- coding: utf-8 -*-
"""主动关怀：熬夜、久坐、离开太久 —— 她会主动说一句（参考 Mitra / OpenPets / HealthMate）。

和"提醒"的区别：提醒是主人让她记的事；关怀是**她自己**看时间与状态决定的，
带冷却，不会反复唠叨。触发条件（都会写日志，方便回看）：

    深夜还在用（23:30 之后）        → 催睡觉（一晚最多一次）
    连续用电脑超过 2 小时           → 起来动动、看看远处（每 2 小时最多一次）
    离开很久（>90 分钟没输入）后回来  → 欢迎回来（交给空闲问候那套，这里不重复）
    演示/会议模式（Windows 判定）    → 保持安静，不主动开口

另外记着"在一起多少天"（第一次见到主人那天起），启动时可以打个招呼。
存储：pets/<角色>/memory/care.json
"""
import json
import os
import time

# 冷却（秒）
NIGHT_COOLDOWN = 8 * 3600
SIT_COOLDOWN = 2 * 3600
NIGHT_HOURS = (23, 0, 1, 2, 3, 4)      # 23:00 ~ 04:59 算深夜
SIT_LIMIT_SEC = 2 * 3600


def _say(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        pass


def _cfg(key, default):
    try:
        from tool.config import get_config
        return get_config("./config.json").get(key, default)
    except Exception:
        return default


def _cfg_bool(key, default=True) -> bool:
    try:
        from tool.config import as_bool
        return as_bool(_cfg(key, default), default)
    except Exception:
        return bool(default)


def enabled() -> bool:
    return _cfg_bool("care_enabled", True)


def startup_greeting_enabled() -> bool:
    return _cfg_bool("care_startup_greeting", True)


def startup_greeting_mode() -> str:
    """开机问候怎么出声（用户 2026-09-30：「播放指定的一条语音或者不播放」）。

    voice = 播 startup_greeting_voice 指定的那条语音（**默认**，不需要 TTS 服务）
    off   = 不播（只留启动日志）
    chat  = 老行为：让模型自己说一句 —— ⚠ 需要短语音 TTS 服务已就绪，
            而 GPT-SoVITS 启动要 1~2 分钟，所以开机那一下必然失败（用户报的就是这个）
    """
    try:
        from tool.config import enum_of
        return enum_of(_cfg("startup_greeting_mode", "voice"), ("voice", "off", "chat"),
                       "voice", "startup_greeting_mode")
    except Exception:
        return "voice"


def startup_greeting_voice() -> str:
    """要播的那条语音文件（config：startup_greeting_voice；空 = 不播任何语音）"""
    try:
        return str(_cfg("startup_greeting_voice", "") or "").strip()
    except Exception:
        return ""


def meeting_quiet_enabled() -> bool:
    return _cfg_bool("care_meeting_quiet", True)


def _path() -> str:
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
    except Exception:
        d = "memory"
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "care.json")


# 合理性下限：本项目 2026 年才有；比这更早的 first_seen 一定是脏数据
# （真实案例：按「角色包里最老文件」回填时挑到从压缩包导入、mtime 停在 2021-12-10 的
#   资源文件 → first_seen=2021 年 → 陪伴天数算出 1756 天，被 max() 固化后再也回不去）
_FLOOR = time.mktime((2026, 1, 1, 0, 0, 0, 0, 0, -1))


def _plausible(ts) -> bool:
    """这个时间戳像不像「真的第一次见到主人」：不许早于 _FLOOR，也不许是未来。"""
    try:
        v = float(ts)
    except Exception:
        return False
    return _FLOOR <= v <= time.time() + 86400


def _load() -> dict:
    try:
        with open(_path(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d: dict):
    try:
        p = _path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        pass


def _touch_first_seen() -> float:
    """第一次见到主人的时间（陪伴天数用它）

    第一次记录时，尽量回填成**记忆目录里最早那个文件**的时间（角色包创建/首次聊天的日子），
    这样"在一起第 N 天"从一开始就是准的，而不是从装这个功能那天算。
    """
    d = _load()
    # 已有的值也不盲信：不合理的（2021 年那种）直接丢掉重算
    if not _plausible(d.get("first_seen")):
        d.pop("first_seen", None)
    if not d.get("first_seen"):
        first = time.time()
        try:
            # 找"这个角色包最老的文件"当起点：立绘/人设这些一装好就不动了，
            # 比记忆文件靠谱（记忆文件每次保存都会更新 mtime）。
            from pets.pet_registry import get_memory_dir
            cands = []
            try:
                from pets.pet_registry import PETS_DIR, get_active_pet_id
                cands.append(os.path.join(PETS_DIR, get_active_pet_id()))
            except Exception:
                pass
            cands.append(get_memory_dir())
            ts = []
            for base in cands:
                if not base or not os.path.isdir(base):
                    continue
                for root, dirs, files in os.walk(base):
                    dirs[:] = [x for x in dirs if x not in ("__pycache__",)]
                    for fn in files[:200]:
                        if fn.startswith(("care", "state", "attention", "learned", "experience")):
                            continue
                        try:
                            ts.append(os.path.getmtime(os.path.join(root, fn)))
                        except Exception:
                            pass
                    if len(ts) > 3000:
                        break
            ts = [t for t in ts if _plausible(t)]      # 过滤掉导入资源那种远古 mtime
            if ts:
                first = min(min(ts), first)
        except Exception:
            pass
        d["first_seen"] = first
        d["days"] = int((time.time() - first) // 86400) + 1
        _save(d)
    return float(d.get("first_seen") or time.time())


def companion_days() -> int:
    """在一起第几天（第一次记录的那天算第 1 天）

    ⚠ 别再写回 max(旧值, 新值)：旧值一旦被错算（例如 2021 年那种 first_seen），
    max() 会让它永远下不来（用户看到的 1756 天就是这么来的）。现在每次由 first_seen
    现算，只有 first_seen 不合理时才回填重算。
    """
    try:
        first = _touch_first_seen()
        if not _plausible(first):
            first = time.time()
        n = int((time.time() - first) // 86400) + 1
        n = max(1, min(n, 36500))          # 100 年上限：再离谱就当第 1 天
        d = _load()
        if int(d.get("days") or 0) != n:
            d["days"] = n
            _save(d)
        return n
    except Exception:
        return 1


def startup_line(pet_name: str = "我") -> str:
    """启动时的一句（陪伴天数 + 今天挂着的提醒）"""
    try:
        days = companion_days()
        txt = f"（系统提示：你刚开机。今天是你们在一起的第 {days} 天。"
        try:
            from tool import reminder as _rm
            its = _rm.items()
            if its:
                txt += "今天挂着这些提醒：" + "、".join(
                    "%s %s" % (_rm._fmt_ts(x.get("at")), x.get("what")) for x in its[:3]) + "。"
        except Exception:
            pass
        txt += ("用你自己的口吻跟主人打个招呼，一句话就行（别提'系统提示'、别报时）。"
                "★ 这一轮只是寒暄：不要输出任何操作指令（【键鼠】等）。）")
        return txt
    except Exception:
        return ""


def meeting_mode() -> bool:
    """Windows 判定是不是在演示/全屏会议（这类场景她应当安静）"""
    try:
        from tool import perf_guard as _pg
        return int(_pg.notification_state()) == 4
    except Exception:
        return False


def quiet_now() -> bool:
    """现在该不该保持安静（会议/演示中）"""
    try:
        return bool(meeting_quiet_enabled()) and meeting_mode()
    except Exception:
        return False


def check(now_ts: float = None, active_sec: float = 0.0) -> str:
    """看看现在要不要主动关怀一句 → 返回一句"为什么说"（不需要就说空）

    active_sec：主人已经连续在用电脑多久（秒）。由桌宠把"这次连续使用时长"传进来。
    """
    try:
        now = float(now_ts if now_ts is not None else time.time())
        if quiet_now():
            return ""
        d = _load()
        lt = time.localtime(now)
        # ① 深夜
        if lt.tm_hour in NIGHT_HOURS:
            last = float(d.get("last_night") or 0)
            if now - last > NIGHT_COOLDOWN:
                d["last_night"] = now
                _save(d)
                return "深夜了，该睡觉了"
        # ② 久坐
        if active_sec >= 2 * 3600:
            last = float(d.get("last_sit") or 0)
            if now - last > SIT_COOLDOWN:
                d["last_sit"] = now
                _save(d)
                return "已经连续用了两小时，该起来动动"
        return ""
    except Exception:
        return ""


def nudge_prompt(reason: str, pet_name: str = "我") -> str:
    """把"为什么说"变成给她的一句话"""
    return ("（系统提示：你自己留意到「%s」。用你的口吻关心主人一句，"
            "一两句话就好，别唠叨、别提系统提示。如果他在忙可以轻轻带过。）" % str(reason)[:60])


def summary_text() -> str:
    try:
        d = _load()
        last_night = d.get("last_night")
        return ("在一起第 %d 天｜最近一次深夜提醒：%s" % (
            companion_days(),
            time.strftime("%m-%d %H:%M", time.localtime(float(last_night))) if last_night else "还没有"))
    except Exception:
        return ""


def set_meeting_quiet(on: bool):
    """会议/演示时保持安静 —— ⚠ 本地原来是往内存字典 `_cfg` 里写（重启就没了，
    而且现在 `_cfg` 已经是「读配置」的函数，按下标写会直接 TypeError）。
    改成写 config.json 的 care_meeting_quiet（走上游的 set_key：只改一个键 + 原子替换）。"""
    try:
        from tool.config import set_key
        set_key("./config.json", "care_meeting_quiet", "true" if on else "false")
    except Exception:
        pass


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("存储:", _path())
    print("摘要:", summary_text())
    print("启动语:", startup_line())
    print()
    print("模拟：把时钟设成 23:40 检查一次 →", check(now_ts=time.time(), active_sec=3 * 3600) or "（这次不用说）")
    t = time.localtime()
    if t.tm_hour not in NIGHT_HOURS:
        print("   （现在不是深夜，所以只可能命中久坐；下面强制模拟）")
    import calendar
    fake = calendar.timegm((t.tm_year, t.tm_mon, t.tm_mday, 23, 40, 0, 0, 0, 0))
    fake = fake - time.timezone
    print("   深夜那次 →", check(now_ts=fake, active_sec=0) or "（这次不用说）")
    print("   再问一次（冷却内）→", check(now_ts=fake + 60, active_sec=0) or "（这次不用说 ✓）")
    print()
    print("在一起第:", companion_days(), "天")
