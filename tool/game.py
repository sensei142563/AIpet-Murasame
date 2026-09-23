# -*- coding: utf-8 -*-
"""游戏模式：让她自己玩（回合制 / 挂机 / 需要重复刷的游戏）。

⚠ 先说清楚能玩什么、不能玩什么（实测数据）：
    一轮循环 = 抓屏（约 22ms）+ 视觉认画面（**约 5~10 秒**）+ 规划（约 2~4 秒）+ 执行。
    所以一轮要 8~15 秒 —— **动作类/竞技类游戏（火影、无畏契约、FPS）玩不了**，
    但**回合制、战棋、卡牌、挂机、放置、需要反复刷材料**这类完全够用。
    想让动作游戏也能玩，得换成"直接看像素、不走大模型"的方案（那是另一个工程量）。

两种玩法：
    ① 她看着画面想（适合回合制/需要判断的）
       她对主人说：「【游戏】开始 名字：目标 … ；操作 …」
       循环：抓屏 → 视觉描述当前局面 → 规划出 1~3 个动作 → 执行 → 再来一轮
    ② 固定循环（适合刷材料，**不花模型额度、很快**）
       「【游戏】连按 J 30 次 间隔 0.8 秒」/「【游戏】连点 800 250 20 次」

安全（这套默认就有的）：
    * **F12 急停**：玩的时候她挂一个全局热键监听，按 F12 立刻停（她会回一句"好，停了"）
    * 主人一开口说话也会停（让位给他）
    * 有硬上限：默认最多 10 分钟 / 60 轮，到点自己收工
    * 动作全部走键鼠那边同一套保护：坐标必须在屏幕内、重复动作会被抑制、每步写日志
    * 开关：「允许她玩游戏」（菜单里可以关，默认开但只在你明确让她玩时才动）

存档：pets/<角色>/memory/games.json（记住每个游戏的操作方式和战绩，下次不用再说一遍）
"""
import json
import os
import threading
import time

GAME_MARK = "【游戏】"
DEFAULT_MINUTES = 10
MAX_ROUNDS = 60
# 一轮里的上限：不许它在一轮里狂点
_LINE = None          # 延迟编译（避免顶层 re 依赖）

_state = {
    "running": False, "stop": False, "name": "", "goal": "", "controls": "",
    "round": 0, "started": 0.0, "log": [], "reason": "",
}
_lock = threading.Lock()
_ui = {"status": None, "finish": None}
_hotkey = {"listener": None, "active": False}


def _log(msg: str):
    try:
        print(f"[游戏] {msg}")
    except Exception:
        pass


# ─────────────────────── 开关与存档 ───────────────────────

def _cfg_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def enabled() -> bool:
    try:
        from tool.config import get_config
        v = get_config("./config.json").get("game_enabled", "true")
        return str(v).strip().lower() in ("true", "1", "yes", "on")
    except Exception:
        return True


def set_enabled(on: bool) -> bool:
    try:
        from tool.config import get_config
        cfg = dict(get_config("./config.json") or {})
        cfg["game_enabled"] = "true" if on else "false"
        p = _cfg_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        _log(f"允许她玩游戏 → {'已开启' if on else '已关闭'}")
        return True
    except Exception as e:
        _log(f"⚠ 写开关失败: {e}")
        return False


def _store_path() -> str:
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
    except Exception:
        d = "memory"
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "games.json")


def _load_games() -> dict:
    try:
        with open(_store_path(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_games(d: dict):
    try:
        p = _store_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception as e:
        _log(f"⚠ 存档失败: {e}")


def remember(name: str, goal: str = "", controls: str = "", won: bool = None):
    """记住这个游戏怎么玩（下次她说不用主人再讲一遍）"""
    try:
        d = _load_games()
        it = dict(d.get(str(name)) or {})
        if goal:
            it["goal"] = str(goal)[:120]
        if controls:
            it["controls"] = str(controls)[:200]
        it["plays"] = int(it.get("plays") or 0) + 1
        if won is True:
            it["wins"] = int(it.get("wins") or 0) + 1
        it["ts"] = time.time()
        d[str(name)[:24]] = it
        _save_games(d)
    except Exception:
        pass


def known_games() -> dict:
    return _load_games()


def recall(name: str) -> dict:
    return dict(_load_games().get(str(name)) or {})


# ─────────────────────── 运行状态 ───────────────────────

def running() -> bool:
    return bool(_state["running"])


def status() -> dict:
    return dict(_state)


def set_ui(status=None, finish=None):
    _ui["status"] = status
    _ui["finish"] = finish


def _say_status(t: str):
    try:
        if _ui["status"]:
            _ui["status"](str(t))
    except Exception:
        pass


def _say_finish(t: str, ok: bool = True):
    try:
        if _ui["finish"]:
            _ui["finish"](str(t), bool(ok))
    except Exception:
        pass


def stop(reason: str = "主人叫停") -> bool:
    """立刻停手（F12 / 主人说话 / 菜单）"""
    try:
        with _lock:
            if not _state["running"]:
                return False
            _state["stop"] = True
            _state["reason"] = str(reason)
        _log(f"⛔ 停止（{reason}）")
        try:
            from tool import pc_control as _pc
            _pc.set_abort(reason)
        except Exception:
            pass
        return True
    except Exception:
        return False


def _stopped() -> bool:
    return bool(_state["stop"])


# ─────────────────────── 急停热键（F12）───────────────────────

def _start_hotkey():
    """玩的时候挂一个全局监听：按 F12 立刻停"""
    try:
        if _hotkey["active"]:
            return
        from pynput import keyboard
        from pynput.keyboard import Key

        def _on_press(key):
            try:
                if key == Key.f12:
                    stop("按了 F12 急停")
            except Exception:
                pass

        lst = keyboard.Listener(on_press=_on_press, daemon=True)
        lst.start()
        _hotkey["listener"] = lst
        _hotkey["active"] = True
        _log("急停热键已挂上：按 F12 立刻停")
    except Exception as e:
        _log(f"⚠ 急停热键不可用（可以用菜单/说话让她停）：{e}")


def _stop_hotkey():
    try:
        if _hotkey["listener"] is not None:
            _hotkey["listener"].stop()
    except Exception:
        pass
    _hotkey["listener"] = None
    _hotkey["active"] = False


def hotkey_active() -> bool:
    return bool(_hotkey["active"])


# ─────────────────────── 解析 ───────────────────────

def parse(text: str) -> list:
    """解析【游戏】标记 → [(动作, 参数)]"""
    import re
    out = []
    mark = re.compile("[【\\[]\\s*游戏\\s*[】\\]]\\s*([^\"\\]]{0,120})")
    for m in mark.finditer(str(text or "")):
        s = re.sub("\\s+", " ", str(m.group(1) or "")).strip("：:，,。")
        if not s:
            continue
        if any(k in s for k in ("停", "别玩", "stop")):
            out.append(("stop", ""))
            continue
        if any(k in s for k in ("会玩哪些", "玩过什么", "游戏列表", "战绩")):
            out.append(("list", ""))
            continue
        if s.startswith("连按") or s.startswith("连点") or s.startswith("循环"):
            out.append(("macro", s))
            continue
        if s.startswith("开始") or s.startswith("玩") or "：" in s or ":" in s:
            out.append(("start", s))
            continue
        out.append(("start", s))
    return out[:2]


def _parse_start(s: str) -> dict:
    """「开始 名字：目标 … ；操作 …」→ {name, goal, controls, minutes}"""
    import re
    body = re.sub("^(开始玩|开始|玩|帮我玩|你自己玩)", "", str(s or "")).strip("：:，,。 ")
    minutes = None
    m = re.search("(\\d+)\\s*分钟", body)
    if m:
        try:
            minutes = int(m.group(1))
        except Exception:
            minutes = None
        body = body.replace(m.group(0), " ")
    name, goal, controls = body, "", ""
    if "：" in body or ":" in body:
        parts = re.split("[：:]", body, 1)
        name = parts[0].strip()
        rest = parts[1] if len(parts) > 1 else ""
        for seg in re.split("[；;。]", rest):
            seg = seg.strip()
            if not seg:
                continue
            if seg.startswith("操作") or seg.startswith("按键") or seg.startswith("键位"):
                controls = re.sub("^(操作|按键|键位)", "", seg).strip("：: ")
            elif seg.startswith("目标") or seg.startswith("任务"):
                goal = re.sub("^(目标|任务)", "", seg).strip("：: ")
            elif not goal:
                goal = seg
        if not goal and not controls and rest:
            goal = rest.strip()
    return {"name": name.strip()[:24] or "这个游戏", "goal": goal.strip()[:120],
            "controls": controls.strip()[:200], "minutes": minutes}


# ─────────────────────── 固定循环（刷材料用，不花模型额度）───────────────────────

def macro(spec: str) -> str:
    """「连按 J 30 次 间隔 0.8 秒」/「连点 800 250 20 次」→ 直接跑，不经过模型"""
    import re
    s = str(spec or "")
    n = 10
    m = re.search("(\\d+)\\s*次", s)
    if m:
        try:
            n = max(1, min(500, int(m.group(1))))
        except Exception:
            n = 10
    gap = 0.8
    m2 = re.search("(?:间隔|每)\\s*([\\d.]+)\\s*秒", s)
    if m2:
        try:
            gap = max(0.1, min(10.0, float(m2.group(1))))
        except Exception:
            gap = 0.8
    if "连点" in s:
        nums = re.findall("-?\\d+", re.sub("(\\d+)\\s*次|[\\d.]+\\s*秒", "", s))
        if len(nums) >= 2:
            x, y = int(nums[0]), int(nums[1])
            acts = [{"type": "click", "x": x, "y": y}] * n
            what = "连点 (%d,%d) %d 次" % (x, y, n)
        else:
            return "连点要写坐标，比如「【游戏】连点 800 250 20 次」。"
    else:
        m3 = re.search("连按\\s*([A-Za-z0-9]+)", s)
        if not m3:
            return "这个固定循环我没看懂（可以写「【游戏】连按 J 30 次 间隔 0.8 秒」）。"
        key = m3.group(1)
        acts = [{"type": "key", "key": key}] * n
        what = "连按 %s %d 次" % (key, n)
    return _run_macro(acts, gap, what)


def _run_macro(acts: list, gap: float, what: str) -> str:
    with _lock:
        if _state["running"]:
            return "我手上还玩着别的呢，等一下。"
        _state.update({"running": True, "stop": False, "name": what, "goal": "",
                       "controls": "", "round": 0, "started": time.time(),
                       "log": [], "reason": ""})
    _start_hotkey()

    def _work():
        from tool import pc_control as _pc
        done = 0
        try:
            for a in acts:
                if _stopped():
                    break
                try:
                    if _pc.execute([a], notify=None, no_dup=True):
                        done += 1
                except Exception:
                    pass
                _say_status(f"正在操作……（{done}/{len(acts)}）")
                time.sleep(gap)
        finally:
            with _lock:
                _state["running"] = False
            _stop_hotkey()
            _log(f"固定循环结束：{what}（做了 {done} 次）")
            _say_finish(f"{what}，一共 {done} 次。" if done else "没做成。", done > 0)

    threading.Thread(target=_work, daemon=True).start()
    return f"好，{what}，开始（按 F12 或跟我说「停」都能立刻停）。"


# ─────────────────────── 看着画面玩（回合制用）───────────────────────

def _ask(system: str, user: str, max_tokens: int = 300) -> str:
    try:
        from tool.config import get_config
        mt = str(get_config("./config.json").get("model_type", "deepseek")).strip().lower()
    except Exception:
        mt = "deepseek"
    try:
        if mt == "local":
            from tool.chat import ollama_post
            r = ollama_post("qwen3:14b", {"model": "qwen3:14b", "prompt": system + "\n\n" + user,
                                          "stream": False, "options": {"num_predict": max_tokens}})
            try:
                return str((r or {}).get("message", {}).get("content") or r.get("response") or "").strip()
            except Exception:
                return ""
        from tool.cloud_API_chat import post
        from longtext.model_config import get_short_model_config
        cfg = get_short_model_config()
        if not cfg:
            return ""
        payload = {"messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user}],
                   "model": cfg["model"], "max_tokens": max_tokens, "stream": False}
        payload.update(cfg.get("reasoning") or {})
        return str(post("游戏", payload, api_key=cfg["api_key"]) or "").strip()
    except Exception as e:
        _log(f"⚠ 调用失败: {type(e).__name__}: {e}")
        return ""


def _look() -> str:
    """看一眼游戏画面（小图 + 很短的回答，越快越好）"""
    try:
        import tempfile
        from tool.screen_capture import capture_qimage, is_blank
        from tool.chat import describe_image
        img = capture_qimage()
        if img is None:
            return "（看不到画面）"
        os.makedirs("tmp", exist_ok=True)
        p = os.path.join("tmp", "game_shot.png")
        img.save(p, "PNG")
        if is_blank(img):
            return "（屏幕是黑的，可能游戏是独占全屏，看不到内容）"
        desc = describe_image(p, max_side=640, max_new=70)
        return str(desc or "").strip() or "（没看清）"
    except Exception as e:
        return f"（看画面失败：{type(e).__name__}）"


def start(name: str, goal: str = "", controls: str = "", minutes: int = None,
          pet_name: str = "我") -> str:
    """开始看着画面玩"""
    if not enabled():
        return "主人没让我玩游戏（菜单里可以打开「允许她玩游戏」）。"
    if not name:
        return "要玩哪个游戏呀？"
    with _lock:
        if _state["running"]:
            return "我手上还玩着别的呢，等一下。"
        _state.update({"running": True, "stop": False, "name": str(name)[:24],
                       "goal": str(goal or "")[:120], "controls": str(controls or "")[:200],
                       "round": 0, "started": time.time(), "log": [], "reason": ""})
    mins = float(minutes or DEFAULT_MINUTES)
    _start_hotkey()
    threading.Thread(target=_loop, args=(mins, pet_name), daemon=True).start()
    return (f"好，我来玩「{name}」——我大概十几秒动一次手，"
            f"打不过或者你觉得烦就按 F12，或者直接跟我说「停」。")


def _planner_system(name: str, goal: str, controls: str) -> str:
    return (
        f"你正在替主人玩「{name}」。你能看到画面描述，然后决定下一步怎么做。\n"
        f"目标：{goal or '正常往下玩、别输。'}\n"
        f"操作方式（主人教的，按这个来）：{controls or '不确定就先用键盘：空格/回车/数字键，先试着推进。'}\n"
        "每轮只输出 1~3 行动作，格式：\n"
        "【键鼠】点击 800 250 / 【键鼠】按键 space / 【键鼠】按键 1 / 【键鼠】输入 名字 / 【键鼠】等待 1.5\n"
        "★ 一轮动一下就好，别一口气点一堆；不确定就先写「【键鼠】等待 1.5」再看下一轮。\n"
        "★ 这局结束了（赢了/输了/回到主菜单）→ 输出：完成：<一句话>\n"
        "★ 明显玩不动、或者需要主人决定 → 输出：失败：<一句话>"
    )


def _loop(minutes: float, pet_name: str):
    from tool import pc_control as _pc, self_learn as _sl, state as _st
    name = _state["name"]
    goal, controls = _state["goal"], _state["controls"]
    system = _planner_system(name, goal, controls)
    last = "（还没动手）"
    reason = ""
    ok = False
    try:
        for rnd in range(1, MAX_ROUNDS + 1):
            if _stopped():
                reason = "好，停了。"
                break
            if time.time() - float(_state["started"]) > minutes * 60:
                reason = "这局玩得有点久了，我先歇会儿，你想让我接着玩就说一声。"
                break
            _state["round"] = rnd
            _say_status(f"正在玩 {name}……第 {rnd} 轮")
            desc = _look()
            print(f"[游戏] 第 {rnd} 轮画面：{str(desc)[:90]}")
            user = (f"当前画面：{desc}\n"
                    f"上一轮我做了什么：{last}\n"
                    f"（第 {rnd} 轮）现在输出下一步动作（1~3 行）；结束就写「完成：…」，玩不动写「失败：…」")
            reply = _ask(system, user, max_tokens=300)
            if not reply:
                reason = "唔……我这边联系不上模型了。"
                break
            print(f"[游戏] 第 {rnd} 轮决定：{reply[:110].replace(chr(10), ' | ')}")
            _state["log"].append(reply[:200])
            fin = ""
            for k in ("完成：", "完成:", "失败：", "失败:"):
                if k in reply:
                    ok = k.startswith("完成")
                    fin = reply.split(k, 1)[1].strip().strip("「」\"'") or ("打完了。" if ok else "这局我玩不动。")
                    break
            if fin:
                reason = fin
                break
            acts = _pc.parse(reply)
            if not acts:
                last = "（我上一步没写出能执行的动作）"
                time.sleep(1.0)
                continue
            if _stopped():
                reason = "好，停了。"
                break
            print(f"[游戏] 第 {rnd} 轮执行：{_pc.describe(acts)}")
            done = _pc.execute(acts, notify=None, no_dup=True)
            last = _pc.describe(done) if done else "（一个都没做成）"
            time.sleep(0.6)
        else:
            reason = "玩了好多轮了，我先停一下。"
    except Exception as e:
        reason = f"唔……玩着玩着出岔子了（{type(e).__name__}）。"
    finally:
        stopped = _stopped()
        with _lock:
            _state["running"] = False
        _stop_hotkey()
        try:
            _pc.clear_abort()
        except Exception:
            pass
        # 记住这个游戏怎么玩 + 写情节
        try:
            remember(name, goal=goal, controls=controls, won=ok if reason else None)
            _sl.add_episode(("玩过：" if not stopped else "中途停了：") + name
                            + ("（" + str(reason)[:30] + "）" if reason else ""), "game")
            if ok:
                _st.feel(4, 0.3, "替他玩赢了一局")
            elif stopped:
                _st.feel(-1, 0, "玩到一半被叫停")
        except Exception:
            pass
        _log(f"■ 结束（{'完成' if ok else '停/未完成'}）：{reason[:50]}")
        _say_finish(reason or "玩完了。", ok)


def prompt_rules() -> str:
    if not enabled():
        return ""
    games = known_games()
    known = ("、".join(list(games.keys())[:6])) if games else ""
    return (
        "【陪主人玩游戏（已开启）】主人让你玩（「你帮我玩」「你自己打一局」）时，你可以真的上手：\n"
        "【游戏】开始 游戏名：目标 打通这关 ；操作 W 前进、J 攻击、空格 跳\n"
        "（他会告诉你按键怎么操作；没说全也没关系，你可以先试）\n"
        "【游戏】连按 J 30 次 间隔 0.8 秒   /   【游戏】连点 800 250 20 次   ← 刷材料用，很快\n"
        "【游戏】停   /   【游戏】会玩哪些\n"
        + (f"（你玩过的游戏：{known}。玩过的话操作方式你还记得，不用再问一遍。）\n" if known else "")
        + "★ 你大概十几秒才动一次手：**回合制、战棋、卡牌、挂机、需要反复刷的游戏**能玩，"
          "动作类/竞技类（吃鸡、火影、FPS）**玩不了**，这种要老实跟主人说。\n"
        "★ 玩之前先说一句你在干什么；主人按 F12 或者一开口说话你就会停下来。\n"
        "★ 玩完/打不过都要如实告诉他，别硬撑。"
    )


def summary_text() -> str:
    g = known_games()
    if not g:
        return "（还没玩过什么）"
    out = []
    for k, v in list(g.items())[:6]:
        out.append("· %s（玩过 %s 次%s）：%s" % (
            k, v.get("plays") or 0,
            ("，赢 %s 次" % v.get("wins")) if v.get("wins") else "",
            str(v.get("controls") or "没记操作")[:40]))
    return chr(10).join(out)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("开关:", enabled(), "｜存档:", _store_path())
    print()
    print("=== 解析 ===")
    for t in ("【游戏】开始 纸嫁衣：目标 通关第一关 ；操作 空格 推进、数字键 选项",
              "【游戏】连按 J 30 次 间隔 0.8 秒", "【游戏】连点 800 250 20 次",
              "【游戏】停", "【游戏】会玩哪些"):
        print("  %-52s → %s" % (t[:52], parse(t)))
    print()
    st = _parse_start("开始 纸嫁衣：目标 通关第一关 ；操作 空格 推进、数字键 选项")
    print("  解析开始参数:", st)
    print()
    print("  固定循环（不真的执行，只看参数）:")
    import re as _r
    mm = _r.search("(\\d+)\\s*次", "连按 J 30 次 间隔 0.8 秒")
    print("   次数:", mm.group(1) if mm else "-")
    print()
    print("已玩过的游戏:", summary_text())
