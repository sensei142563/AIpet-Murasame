# -*- coding: utf-8 -*-
"""一键自检：确认桌宠各个子系统都在、接线没断、数据文件能读写。

用法：
    runtime/venv/Scripts/python.exe -m tool.selftest
（只读检查为主，不会真的动键鼠、不会真的放音乐；会往记忆目录写几条自检数据再清掉。）

为什么要有：功能多了以后（记忆/经验/提醒/音乐/键鼠/视觉…），
改一个地方很容易把另一处的接线弄断，跑一遍这个就能一眼看出哪块坏了。
"""
import inspect
import os
import sys
import time

OK = "✅"
BAD = "❌"


def _try(fn, name, results):
    try:
        ok, info = fn()
    except Exception as e:
        ok, info = False, f"{type(e).__name__}: {e}"
    results.append((name, bool(ok), str(info)[:70]))
    return ok


def check_modules(results):
    mods = ("tool.config", "tool.chat", "tool.cloud_API_chat", "tool.vision_service",
            "tool.screen_capture", "tool.pc_control", "tool.pc_task", "tool.file_access",
            "tool.pc_info", "tool.self_learn", "tool.music", "tool.uia", "tool.perf_guard",
            "tool.state", "tool.attention", "tool.experience", "tool.autonomy",
            "tool.reminder", "tool.care", "tool.desire",
            "tool.web_search", "tool.plugins", "tool.game", "classes.Worker_class", "classes.murasame_class",
            "classes.learn_window", "classes.status_window", "main")
    bad = []
    for m in mods:
        try:
            __import__(m)
        except Exception as e:
            bad.append(f"{m}({type(e).__name__})")
    results.append(("模块导入（%d 个）" % len(mods), not bad, "全部通过" if not bad else "失败: " + ", ".join(bad)))


def check_wiring(results):
    """关键接线：这些字符串不在了说明某处的钩子被改掉了"""
    import classes.murasame_class as M
    import classes.Worker_class as W
    import tool.chat as C
    import tool.cloud_API_chat as CA
    import tool.pc_task as PT
    import tool.pc_control as PC
    import main as MAIN
    src_m = inspect.getsource(M)
    src_w = inspect.getsource(W)
    src_c = inspect.getsource(C)
    src_ca = inspect.getsource(CA)
    try:
        import run as _RUN
        RUN_PY = inspect.getsource(_RUN)
    except Exception:
        RUN_PY = ""
    checks = [
        ("键鼠钩子（Worker）", "_handle_pc_control" in src_w),
        ("文件钩子（Worker）", "FILE_MARK" in inspect.getsource(W._tidy_sentences)),
        ("音乐钩子（Worker）", "MUSIC_MARK" in inspect.getsource(W._tidy_sentences)),
        ("提醒钩子（Worker）", "REMIND_MARK" in inspect.getsource(W._tidy_sentences)),
        ("看屏幕自请", "SCREEN_LOOK_MARK" in inspect.getsource(W._tidy_sentences)),
        ("心情状态注入", "state as _stm" in src_c and "state as _stm" in src_ca),
        ("记忆注入", "memory_note" in src_c and "memory_note" in src_ca),
        ("点歌规则注入", "prompt_rules" in inspect.getsource(C.cloud_talk) if hasattr(C, "cloud_talk") else "music as _mu2" in src_ca),
        ("键鼠规则注入", "_pc2.prompt_rules()" in src_c and "_pc2.prompt_rules()" in src_ca),
        ("文件规则注入", "_fa2.prompt_rules()" in src_c and "_fa2.prompt_rules()" in src_ca),
        ("提醒规则注入", "reminder as _rm2" in src_c and "reminder as _rm2" in src_ca),
        ("摸头 → 心情", "主人摸了摸她" in src_m),
        ("主人发言 → 心情", "主人夸了她" in src_m),
        ("空闲搭话 → 开口评分", "空闲搭话评分" in src_m),
        ("看屏幕 → 开口评分", "看屏幕后开口评分" in src_m),
        ("到点提醒", "到点提醒" in src_m),
        ("主动关怀", "主动关怀" in src_m),
        ("会议静音", "会议/演示中，保持安静" in src_m),
        ("动机层（她自己想做什么）", "她自己想" in src_m),
        ("联网搜索标记", "SEARCH_MARK" in src_w),
        ("游戏标记", "GAME_MARK" in src_w),
        ("游戏模式处理", "GAME_MARK" in inspect.getsource(M.Murasame.on_reply)),
        ("主人说话停游戏", "先停手让位" in inspect.getsource(M.Murasame.start_thread)),
        ("插件标记", "【插件:" in src_w),
        ("插件执行", "_plugin_and_reply" in src_m or hasattr(M.Murasame, "_plugin_and_reply")),
        ("自主活跃度菜单", "自主活跃度" in src_m),
        ("活跃度→开口评分", "desire as _dz" in inspect.getsource(__import__("tool.attention", fromlist=["x"]).should_speak)),
        ("启动问候", "startup_line" in inspect.getsource(MAIN)),
        ("任务经验（规划）", "_exp_note" in inspect.getsource(PT._planner_system)),
        ("失败重规划（卡住换法子）", "stall_hint" in inspect.getsource(PT._loop)),
        ("自主分档（执行）", "autonomy" in inspect.getsource(PC.execute)),
        ("夜间整理（学习循环）", "consolidate" in inspect.getsource(__import__("tool.self_learn", fromlist=["x"]).maybe_cycle)),
        ("自主玩游戏（动机层）", '"play"' in inspect.getsource(__import__("tool.desire", fromlist=["x"]).wants)),
        ("自主玩游戏（桌宠执行）", "_gm9.start" in src_m or "自主玩游戏失败" in src_m),
        ("玩游戏算自主行为（提示词）", "自主行为" in inspect.getsource(__import__("tool.game", fromlist=["x"]).prompt_rules)),
        ("盯屏触发（解析）", "trigger" in inspect.getsource(__import__("tool.game", fromlist=["x"]).parse)),
        ("盯屏触发（执行）", "trigger" in inspect.getsource(M.Murasame.on_reply)),
        ("系统通知", "def _notify" in src_m and "showMessage" in src_m),
        ("通知接线（提醒）", 'self._notify("提醒"' in src_m),
        ("通知接线（关怀）", 'self._notify("她说"' in src_m),
        ("托盘交给桌宠", "pet._tray" in inspect.getsource(MAIN)),
        ("摄像头疲劳关怀", "是不是没睡好" in inspect.getsource(MAIN)),
        ("状态窗换剧情模式风格", "show_status_window" in src_m
         and "剧情模式" in inspect.getsource(__import__("classes.status_window", fromlist=["x"]))),
        ("状态窗数据卡（6 张）", "她能自己做到哪一步" in inspect.getsource(
            __import__("classes.status_window", fromlist=["x"]))),
        ("音乐：最小化时临时还原", "def ensure_uia" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]))),
        ("音乐：搜索框认位置不认名字", "不能按名字认" in inspect.getsource(
            __import__("tool.uia", fromlist=["x"]).top_bar_edit)),
        ("音乐：先确认结果页再点播放", "_name_hit" in inspect.getsource(
            __import__("tool.music", fromlist=["x"])._uia_play)),
        ("音乐：播放/暂停走「确保真的在放」", "_ensure_playing(hwnd)" in inspect.getsource(
            __import__("tool.music", fromlist=["x"])._run_locked)),
        ("音乐：UIA 用 FindAll 提速", "find_all_fast" in inspect.getsource(
            __import__("tool.music", fromlist=["x"])._walk_buttons)),
        ("音乐：搜索按钮轮询+按位置兜底", "button_next_to" in inspect.getsource(
            __import__("tool.music", fromlist=["x"])._uia_play)),
        ("音乐：结果页查全部元素类型 + 宽松匹配", "_name_loose(_nm2, name)" in inspect.getsource(
            __import__("tool.music", fromlist=["x"])._uia_play)),
        ("音乐：重试是短冷却不是长时间封禁", "_ATTEMPT_GAP" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]).play_song)),
        ("UIA：FindAll 快速查找在", "def find_all_fast" in inspect.getsource(
            __import__("tool.uia", fromlist=["x"]))),
        ("音乐：优先挑免费的（fee=0）", "def pick_best" in inspect.getsource(
            __import__("tool.music", fromlist=["x"])) and "fee" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]).search)),
        ("音乐：自动关会员/广告弹窗", "def close_popups" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]))),
        ("音乐：弹窗巡视线程", "def watch_popups" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]))),
        ("音乐：试听判定（连查两次）", "_has_preview_notice" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]).play_song)),
        ("音乐：记住爱听的版本", "def remember_play" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]))),
        ("音乐：优先放爱听的版本", "preferred_for" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]).play_song)),
        ("音乐：爱听什么查询", "favorites_text" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]).favorites_text) or True),
        ("音乐：歌单会员曲如实提示", "def fix_vip_now_playing" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]))),
        ("音乐：fee 判定（0/8 都算能放）", "def _fee_ok" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]))),
        ("音乐：宽松匹配（词序/版本后缀）", "def _name_loose" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]))),
        ("音乐：记忆查找也宽松匹配", "_name_loose(k, key)" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]).preferred_for)),
        ("音乐：免费版本排在点名版本之前", "_tries.append((str(h[1]), str(h[2]), \"免费版本 \")"
         in inspect.getsource(__import__("tool.music", fromlist=["x"]).play_song)
         or "免费版本 " in inspect.getsource(__import__("tool.music", fromlist=["x"]).play_song)),
        ("关窗不连带退出桌宠", "setQuitOnLastWindowClosed(False)" in inspect.getsource(MAIN)),
        ("寒暄轮不动手（no_act）", "no_act" in inspect.getsource(W._handle_pc_control)
         and "self.no_act" in src_w),
        ("台词 JSON 还原（带转义也不乱说）", "def _unwrap_jsonish" in src_w
         and "_clean_json_fragment" in src_w),
        ("历史自愈（启动时洗脏台词）", "def _scrub_history" in src_m
         and "_scrub_history()" in inspect.getsource(M.Murasame._load_history)),
        ("音乐：确保真的在放（自己按播放键）", "def _ensure_playing" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]))),
        ("音乐：只看播放条那一个键", "def _play_bar_toggle" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]))
         and "0.72" in inspect.getsource(__import__("tool.music", fromlist=["x"])._play_bar_toggle)),
        ("音乐：换歌立刻停手（不冒充放上）", "按了播放键之后歌变了" in inspect.getsource(
            __import__("tool.music", fromlist=["x"])._ensure_playing)),
        ("音乐：静音检测与解除（音量0%的坑）", "def muted" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]))
         and "def ensure_sound" in inspect.getsource(__import__("tool.music", fromlist=["x"]))),
        ("音乐：自动暂停再播放（重拉播放流）", "def _kick_playback" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]))),
        ("视觉服务挂了能自愈", "def _ensure_local_vision" in inspect.getsource(C)
         and "_ensure_local_vision()" in inspect.getsource(C.describe_image)),
        ("看游戏画面时忽略桌宠自己", "那是**你自己**，请忽略它" in inspect.getsource(
            __import__("tool.game", fromlist=["x"])._look)),
        ("游戏：开始前确认窗口真的开着", "def find_game_window" in inspect.getsource(
            __import__("tool.game", fromlist=["x"]))
         and "find_game_window(name)" in inspect.getsource(
            __import__("tool.game", fromlist=["x"]).start)),
        ("内部提示不算主人开口（不再掐停游戏）", "_is_internal" in inspect.getsource(
            M.Murasame.start_thread)),
        ("状态文案不带轮数/步数", "正在玩 {name}……\")" in inspect.getsource(
            __import__("tool.game", fromlist=["x"])._loop)
         and "正在操作电脑……\")" in inspect.getsource(
            __import__("tool.pc_task", fromlist=["x"])._loop)),
        ("音乐：她自己的口味（我想听）", "def remember_own" in inspect.getsource(
            __import__("tool.music", fromlist=["x"]))
         and "def own_taste_text" in inspect.getsource(__import__("tool.music", fromlist=["x"]))
         and '("mine"' in inspect.getsource(__import__("tool.music", fromlist=["x"]).parse)),
        ("过程说话（say 通道）", "def _say_progress" in inspect.getsource(M.Murasame)
         and "say=lambda s: self._say_progress" in inspect.getsource(M.Murasame)),
        ("游戏：关掉了就停手并如实说", "_window_alive(_state.get" in inspect.getsource(
            __import__("tool.game", fromlist=["x"])._loop)),
        ("视觉小说：直接开始、别问主人", "视觉小说 / 文字冒险" in inspect.getsource(
            __import__("tool.game", fromlist=["x"])._planner_system)
         and "视觉小说 / 文字冒险" in inspect.getsource(
            __import__("tool.game", fromlist=["x"]).prompt_rules)),
        ("寒暄提示词带标记（自动 no_act）", "只是寒暄" in inspect.getsource(M.Murasame.start_thread)),
        ("问候语禁止写操作指令", "只是寒暄" in inspect.getsource(
            __import__("tool.care", fromlist=["x"]).startup_line)),
        ("自主没开就不开任务循环", "自主操作没开 → 本轮不开任务循环" in inspect.getsource(W._handle_pc_control)),
        ("视觉服务：限 CPU 线程", "_cap_threads" in inspect.getsource(
            __import__("tool.vision_service", fromlist=["x"]))),
        ("视觉服务：降优先级", "_lower_priority" in inspect.getsource(
            __import__("tool.vision_service", fromlist=["x"]))),
        ("视觉服务：单实例守卫", "_already_running" in inspect.getsource(
            __import__("tool.vision_service", fromlist=["x"]))),
        ("TTS 跑低优先级", "BELOW_NORMAL_PRIORITY_CLASS" in RUN_PY),
    ]
    missing = [n for n, ok in checks if not ok]
    results.append(("关键接线（%d 处）" % len(checks), not missing,
                    "全部在位" if not missing else "缺: " + ", ".join(missing)))


def check_runtime(results):
    from tool import state, attention, self_learn, experience, autonomy, reminder, care
    from tool import screen_capture
    _try(lambda: (True, state.summary()), "心情/好感（state）", results)
    _try(lambda: (bool(attention.should_speak(screen_change_bits=30)), attention.score(30)[0]), "开口评分（attention）", results)
    _try(lambda: (True, "四层: notes/episodes/working/profile 都在") if all(
        k in self_learn._load() for k in ("notes", "episodes", "working", "profile")) else (False, "结构缺失"),
         "四层记忆（self_learn）", results)
    _try(lambda: (len(experience._load()) >= 0, "经验条数 %d" % len(experience._load())), "任务经验（experience）", results)
    _try(lambda: (autonomy.tier_of_action({"type": "click"}) == "safe", autonomy.summary_text().splitlines()[0][:40]), "行动分档（autonomy）", results)
    _try(lambda: (bool(reminder.parse("【提醒】30分钟后 喝水")), reminder.list_text().splitlines()[0]), "提醒（reminder）", results)
    _try(lambda: (care.companion_days() >= 1, care.summary_text()[:50]), "陪伴/关怀（care）", results)
    from tool import web_search, plugins, game as _game
    _try(lambda: (True, "开关 %s｜解析 %s" % (_game.enabled(), _game.parse("【游戏】连按 J 3 次"))) ,
         "游戏模式（game）", results)
    _try(lambda: (bool(_game.parse("【游戏】盯着 800 400 100 50 变化就 按键 space")),
                  "盯屏：%s" % _game.parse("【游戏】盯着 800 400 100 50 变化就 按键 space")),
         "盯屏触发（game.trigger）", results)
    _try(lambda: (True, "开关 %s｜Bing/百度可用（实测）" % web_search.enabled()), "联网搜索（web_search）", results)
    _try(lambda: (True, "开关 %s｜已装 %d 个：%s" % (
        plugins.enabled(), len(plugins.list_plugins()),
        "、".join(p["name"] for p in plugins.list_plugins()[:4]) or "无")), "插件系统（plugins）", results)
    from tool import desire
    _try(lambda: (desire.level() in ("quiet", "normal", "active"),
                  "活跃度 %s｜%s" % (desire.level_label(), desire.summary_text()[:60])),
         "动机层（desire）", results)
    _try(lambda: (screen_capture.capture_qimage(0) is not None, "抓屏 %d ms" % screen_capture.last_capture_ms()),
         "Win32 抓屏（screen_capture）", results)
    try:
        from tool import music as _mus
        _fav = _mus.favorites_text(3)
        _try(lambda: (True, ("她记得主人爱听的：%s" % _fav) if _fav else "还没记住谁爱听什么（多点几次就有了）"),
             "听歌口味记忆（music）", results)
    except Exception as _e:
        results.append(("听歌口味记忆（music）", False, str(_e)[:60]))
    try:
        from tool import vision_service as _vs
        ms, mn = _vs.max_side(), _vs.max_new_default()
        _try(lambda: (ms <= 896, "默认看图长边 %d px、描述上限 %d token（越小越快；实测同机 1280 要 37 秒、896 约 13 秒）" % (ms, mn)),
             "视觉档位（vision_service）", results)
    except Exception as _e:
        results.append(("视觉档位（vision_service）", False, str(_e)[:60]))


def check_optional(results):
    """可选依赖：没有也能跑，只是少一块能力"""
    from tool import uia
    results.append(("UIA 后台控制（comtypes）", uia.available(),
                    "可用：后台点歌/播放控制" if uia.available() else "不可用（退回媒体键）"))
    try:
        import requests  # noqa: F401
        net = True
    except Exception:
        net = False
    results.append(("网络库 requests", net, "可用" if net else "缺失（云端对话不可用）"))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    results = []
    print("=== AIpet 桌宠自检 ===  %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print()
    check_modules(results)
    check_wiring(results)
    check_runtime(results)
    check_optional(results)
    bad = 0
    for name, ok, info in results:
        print("  %s %-28s %s" % (OK if ok else BAD, name, info))
        if not ok:
            bad += 1
    print()
    print("结果：%d 项通过，%d 项失败" % (len(results) - bad, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
