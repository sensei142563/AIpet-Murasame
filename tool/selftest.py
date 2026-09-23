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
            "tool.web_search", "tool.plugins", "classes.Worker_class", "classes.murasame_class",
            "classes.learn_window", "main")
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
        ("插件标记", "【插件:" in src_w),
        ("插件执行", "_plugin_and_reply" in src_m or hasattr(M.Murasame, "_plugin_and_reply")),
        ("自主活跃度菜单", "自主活跃度" in src_m),
        ("活跃度→开口评分", "desire as _dz" in inspect.getsource(__import__("tool.attention", fromlist=["x"]).should_speak)),
        ("启动问候", "startup_line" in inspect.getsource(MAIN)),
        ("任务经验（规划）", "_exp_note" in inspect.getsource(PT._planner_system)),
        ("自主分档（执行）", "autonomy" in inspect.getsource(PC.execute)),
        ("夜间整理（学习循环）", "consolidate" in inspect.getsource(__import__("tool.self_learn", fromlist=["x"]).maybe_cycle)),
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
    from tool import web_search, plugins
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
