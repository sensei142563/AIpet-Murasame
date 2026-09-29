# -*- coding: utf-8 -*-
"""插件系统：让主人自己给她加本事，不用改核心代码。

插件放在项目根目录的 `plugins/<插件名>/`，两个文件：

    plugin.json
        { "name": "天气", "description": "查今天天气", "marker": "天气",
          "version": "1.0", "author": "你", "enabled": true }
    main.py
        def handle(arg: str = "") -> str:   # 必需：她说【插件:天气】北京 时传进来，返回一句结果
        def rules() -> str:                 # 可选：注入提示词，告诉她这个能力怎么用
        def schedule() -> list:             # 可选：[(间隔秒, 无参回调)]，桌宠定期帮你调
        def on_load() / on_unload()         # 可选

她写「【插件:天气】北京」时：那一行不会被念出来（clean_for_speech 去掉），框架把它交给
插件的 handle()，返回的文字再交回给她，由她用自己的话讲给主人 —— 和 tool/reminder.py
的【提醒】是同一套标记机制。

⚠ 安全边界：插件就是主人自己放进来的**代码**，以桌宠的权限运行（和装个软件一样，来源
  不明的别放）。开关是 config.json 的 plugins_enabled（右键菜单里能关）。
"""
import importlib.util
import json
import os
import re
import sys
import threading
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PLUGIN_MARK_PREFIX = "【插件:"
# 标记后面最多抓 80 个字符当参数；不允许跨行（一行一个标记）
_MARK_RE = re.compile("[【\\[]\\s*插件\\s*[:：]\\s*([^】\\]]+)[】\\]]\\s*([^\"\\]\\n]{0,80})")
MAX_MARKS_PER_REPLY = 2          # 一句回复最多触发两个插件（不然会连锁喊一串）
MIN_SCHEDULE_SEC = 30.0          # 定时任务的最小间隔（太密会把桌宠拖住）
DEFAULT_TIMEOUT_SEC = 20.0       # 单个插件最多跑多久
CACHE_SEC = 30.0                 # 插件清单缓存多久

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(APP, "config.json")

_loaded = {}          # name -> {"meta":…, "mod":…, "dir":…}
_errors = {}          # 目录名 -> 没加载起来的原因
_load_ts = [0.0]
_last_run = {}        # (插件名, 序号) -> 上次跑的时间
_lock = threading.Lock()


def root() -> str:
    return os.path.join(APP, "plugins")


def _cfg() -> dict:
    """原样读 config.json（**绝对路径**，不看 cwd；读不到给空 dict）"""
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def enabled() -> bool:
    """插件系统总开关（默认开）"""
    try:
        from tool.config import as_bool
        return as_bool(_cfg().get("plugins_enabled", "true"), True)
    except Exception:
        return True


def set_enabled(on: bool) -> bool:
    """写总开关。⚠ 只改这一个键（走 tool.config.set_key），别整份 dump"""
    try:
        from tool.config import set_key
        ok = bool(set_key(CFG_PATH, "plugins_enabled", "true" if on else "false"))
        if ok:
            reset_cache()
            print("[插件] 插件系统 → %s" % ("已开启" if on else "已关闭"))
        return ok
    except Exception as e:
        print("[插件] ⚠ 写开关失败: %s" % e)
        return False


def timeout_sec() -> float:
    try:
        return max(1.0, min(120.0, float(_cfg().get("plugins_timeout_sec")
                                        or DEFAULT_TIMEOUT_SEC)))
    except Exception:
        return DEFAULT_TIMEOUT_SEC


def plugin_dirs() -> list:
    """**可加载**的插件目录（必须同时有 main.py 和 plugin.json）"""
    out = []
    try:
        for n in sorted(os.listdir(root())):
            d = os.path.join(root(), n)
            if not os.path.isdir(d):
                continue
            if os.path.isfile(os.path.join(d, "main.py")) and \
                    os.path.isfile(os.path.join(d, "plugin.json")):
                out.append(d)
    except Exception:
        pass
    return out


def manifest_dirs() -> list:
    """所有带 plugin.json 的目录 —— **包括缺 main.py 的**。

    为什么要分开：本仓库的 plugins/ 里有一批**只有 plugin.json、没有 main.py** 的目录
    （face / galgame / lively / request_music / slang_search / auto_offline /
    auto_learning / time_guard）。它们的定位是**启动器插件页里的开关面板** ——
    功能本身在别处实现（`qq/qq_learn.py`、`qq/qq_music.py`、`qq/qq_slang.py`、
    `qq/qq_galgame.py`、`qq/qq_offline.py`、`tool/face_recognition*.py`、
    `time_sync_guard.py`），配置键也确实被 `qq/qq_config.py` 与
    `classes/murasame_class.py` 读取。

    ⚠ 所以缺 main.py **不等于"功能没做"**（这里原来的注释就是这么写的，是错的）——
      它只意味着**她不能自己写【插件:xxx】喊它**。`plugin_dirs()` 会把它们当"不存在"跳过，
      于是清单里凭空少了 8 项，主人只会以为插件丢了。清单要如实说明它们的状态。
    """
    out = []
    try:
        for n in sorted(os.listdir(root())):
            d = os.path.join(root(), n)
            if os.path.isdir(d) and os.path.isfile(os.path.join(d, "plugin.json")):
                out.append(d)
    except Exception:
        pass
    return out


def _is_off(v) -> bool:
    return str(v).strip().lower() in ("false", "0", "no", "off", "关", "关闭")


def load_plugin(d: str):
    """加载单个插件目录 → (name, entry_or_None, 原因)。

    ⚠ 插件写坏了只影响它自己：这里把所有异常都收成"原因"字符串返回，绝不上抛。
    """
    meta = {}
    try:
        with open(os.path.join(d, "plugin.json"), encoding="utf-8") as f:
            meta = json.load(f)
        if not isinstance(meta, dict):
            return os.path.basename(d), None, "plugin.json 不是一个对象"
    except Exception as e:
        return os.path.basename(d), None, "plugin.json 读不了（%s: %s）" % (type(e).__name__, e)
    name = str(meta.get("name") or os.path.basename(d)).strip() or os.path.basename(d)
    if _is_off(meta.get("enabled", True)):
        return name, None, "plugin.json 里标了 enabled=false"
    try:
        spec = importlib.util.spec_from_file_location(
            "aiplug_%s" % re.sub(r"\W+", "_", os.path.basename(d)), os.path.join(d, "main.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
    except Exception as e:
        return name, None, "main.py 加载失败（%s: %s）" % (type(e).__name__, str(e)[:120])
    if not hasattr(mod, "handle"):
        return name, None, "main.py 里没有 handle(arg) 函数（必需）"
    try:
        if hasattr(mod, "on_load"):
            mod.on_load()
    except Exception as e:
        # on_load 出错不算加载失败（她照样能用），但要说出来
        print("[插件] ⚠ %s.on_load 出错: %s: %s" % (name, type(e).__name__, e))
    return name, {"meta": meta, "mod": mod, "dir": d}, ""


def load_all(force: bool = False) -> dict:
    """加载全部插件（结果缓存 CACHE_SEC 秒）"""
    with _lock:
        now = time.time()
        if not force and _loaded and (now - float(_load_ts[0] or 0) < CACHE_SEC):
            return _loaded
        _loaded.clear()
        _errors.clear()
        _load_ts[0] = now
        if not enabled():
            return _loaded
        for d in plugin_dirs():
            name, entry, why = load_plugin(d)
            if entry:
                _loaded[name] = entry
                print("[插件] ✅ 已加载：%s（%s）" % (name, entry["meta"].get("description") or "无说明"))
            else:
                _errors[os.path.basename(d)] = "%s：%s" % (name, why)
                print("[插件] ⚠ 跳过 %s：%s" % (os.path.basename(d), why))
        return _loaded


def reset_cache() -> None:
    """下次访问重新扫盘（装/删插件、改开关后调）"""
    _load_ts[0] = 0.0


def list_plugins() -> list:
    """清单（给菜单/状态窗看）：每个目录都给状态，**包括**没加载成功的原因。

    对端只给一个 ok 布尔且跳过缺 main.py 的目录；那样主人看到"少了几项"却不知道为什么。
    """
    out = []
    alive = load_all()
    for d in manifest_dirs():
        meta = {}
        try:
            with open(os.path.join(d, "plugin.json"), encoding="utf-8") as f:
                meta = json.load(f) or {}
        except Exception:
            pass
        base = os.path.basename(d)
        nm = str(meta.get("name") or base)
        has_main = os.path.isfile(os.path.join(d, "main.py"))
        if nm in alive:
            why = ""
        elif not has_main:
            # ⚠ 措辞要对："缺 main.py"**不是**"功能没做" —— 这些目录是启动器插件页的
            #   开关面板，功能在 qq/ 或桌宠那边实现；缺的只是"她能自己喊它"那部分。
            why = ("缺 main.py：她不能自己写【插件:%s】喊它"
                   "（这类目录是启动器里的开关面板，功能在 QQ / 桌宠那边实现）"
                   % str(meta.get("marker") or nm))
        else:
            why = _errors.get(base, "未加载")
        out.append({"name": nm,
                    "desc": str(meta.get("description") or ""),
                    "marker": str(meta.get("marker") or "") or nm,
                    "version": str(meta.get("version") or ""),
                    "ok": nm in alive,
                    "error": why,
                    "dir": base,
                    # 给前端用：能不能被她自己喊（False = 只是开关面板）
                    "callable": bool(has_main)})
    return out


def markers() -> list:
    """[(标记, 插件名, 说明)] —— 写进提示词，她就知道能用【插件:xxx】"""
    out = []
    for name, e in load_all().items():
        meta = e.get("meta") or {}
        out.append((str(meta.get("marker") or "").strip() or name, name,
                    str(meta.get("description") or "")))
    return out


def rules_text() -> str:
    """把所有插件的能力说明拼成一段交给模型（开关关了/没插件就返回空串）"""
    if not enabled():
        return ""
    ms = markers()
    if not ms:
        return ""
    lines = ["【插件能力（主人给你装的）】下面这些是你额外会做的事，"
             "需要时写一行「【插件:标记】参数」就能用："]
    for mk, name, desc in ms[:12]:
        lines.append("· 【插件:%s】%s" % (mk, ("——" + desc) if desc else ("（%s）" % name)))
    try:
        for _name, e in load_all().items():
            mod = e.get("mod")
            if mod is not None and hasattr(mod, "rules"):
                r = str(mod.rules() or "").strip()
                if r:
                    lines.append(r[:300])
    except Exception:
        pass
    lines.append("标记那一行不会被念出来；插件返回的结果会交给你，"
                 "你用自己的话讲给主人，不要念标记本身。")
    return "\n".join(lines)


def parse(text: str) -> list:
    """从回复里解析【插件:标记】参数 → [(标记, 参数)]（最多 MAX_MARKS_PER_REPLY 个）"""
    out = []
    for m in _MARK_RE.finditer(str(text or "")):
        mk = str(m.group(1)).strip()
        arg = str(m.group(2)).strip("：:，,。\"'「」")
        if mk:
            out.append((mk, arg))
    return out[:MAX_MARKS_PER_REPLY]


def clean_for_speech(text: str) -> str:
    """把标记那一行去掉再念（不然她会把「【插件:天气】北京」当台词念出来）"""
    src = str(text or "")
    try:
        if not _MARK_RE.search(src):
            return src
        return re.sub("\\n{2,}", "\n", _MARK_RE.sub("", src)).strip()
    except Exception:
        return src


def _find(marker: str):
    mk = str(marker or "").strip()
    for name, e in load_all().items():
        meta = e.get("meta") or {}
        if (str(meta.get("marker") or "").strip() or name) == mk:
            return name, e
    return "", None


def run_one(marker: str, arg: str = "", timeout: float = 0.0) -> str:
    """执行一个插件，返回它给的一句话（拿不到就返回**空串**）。

    ⚠ 两条口径（都和对端的做法不同）：
      1) 插件抛异常时返回**空串**，不是"（插件「X」出错了：ValueError）" —— 那句人话会被
         当成插件结果交给她，她就照着念（第 22 步识图那边踩过同一个坑）。
      2) handle() 有超时：插件是自己写的代码，可能卡在网络请求上；超时就放弃这一次，
         不能把桌宠的说话线程一起拖住。
    """
    if not enabled():
        return ""
    name, e = _find(marker)
    if not e:
        print("[插件] ⚠ 没有叫「%s」的插件（没装、被关掉，或名字写错了）" % str(marker).strip())
        return ""
    limit = float(timeout or timeout_sec())
    box = {}

    def _work():
        try:
            box["out"] = str(e["mod"].handle(str(arg or "")) or "").strip()
        except Exception as ex:
            box["err"] = "%s: %s" % (type(ex).__name__, ex)

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    t.join(max(0.5, limit))
    if t.is_alive():
        print("[插件] ⚠ %s 超过 %.0f 秒没返回 → 放弃这一次" % (name, limit))
        return ""
    if box.get("err"):
        print("[插件] ⚠ %s.handle 出错: %s" % (name, box["err"]))
        return ""
    txt = box.get("out") or ""
    print("[插件] %s → %s" % (name, txt[:60]))
    return txt


def schedules() -> list:
    """所有插件声明的定时任务 → [(间隔秒, 回调, 插件名, 序号)]"""
    out = []
    for name, e in load_all().items():
        mod = e.get("mod")
        try:
            if mod is None or not hasattr(mod, "schedule"):
                continue
            for i, it in enumerate(mod.schedule() or []):
                try:
                    iv, cb = it
                    out.append((max(MIN_SCHEDULE_SEC, float(iv)), cb, name, i))
                except Exception:
                    continue
        except Exception as ex:
            print("[插件] ⚠ %s.schedule 出错: %s" % (name, ex))
    return out


def due_schedules(now: float = 0.0, run: bool = False) -> list:
    """到点了的定时任务 → [(间隔秒, 回调, 插件名)]。

    run=True 时顺手记下"这次跑过了"，并**真的调用**那些回调（异常单独吞掉，
    一个插件的定时任务炸了不影响别的）。
    """
    t = float(now or time.time())
    out = []
    for iv, cb, name, i in schedules():
        key = (name, i)
        last = float(_last_run.get(key) or 0.0)
        if last and (t - last) < iv:
            continue
        _last_run[key] = t
        out.append((iv, cb, name))
    if run:
        for _iv, cb, name in out:
            try:
                cb()
            except Exception as e:
                print("[插件] ⚠ %s 的定时任务出错: %s: %s" % (name, type(e).__name__, e))
    return out


_pending = []      # 最近一次插件调用的结果 [(插件名, 结果)]，供二次润色/状态窗看


def handle_reply(reply: str) -> str:
    """处理回复里的【插件:xxx】标记（和 reminder.handle_reply 同一个位置调用）。

    做三件事：
      1) 执行插件（最多 MAX_MARKS_PER_REPLY 个）
      2) 把标记那一行从"要念出口的话"里去掉
      3) 插件返回的话**接在后面说**

    为什么第 3 步是直接接上去、而不是再问一次模型润色：她这一轮的回复已经发出去了，
      补一轮对话要动到句子流水线（classes/Worker_class.py）；而且插件返回的本来就是
      给主人看的话（"内存用了 12.3G / 共 16G（77%）"），直接说并不别扭。
      想让措辞更口语的话，用 results_note() 把结果塞进下一轮 system 再问一次即可。
    """
    global _pending
    src = str(reply or "")
    try:
        if not _MARK_RE.search(src):
            return src
    except Exception:
        return src
    got = []
    for mk, arg in parse(src):
        name, e = _find(mk)
        txt = run_one(mk, arg)
        if txt:
            got.append((name or mk, txt))
    _pending = got
    clean = clean_for_speech(src)
    if got:
        clean = (clean + "\n" + "\n".join(t for _n, t in got)).strip()
    return clean


def pending_results() -> list:
    """最近一次插件调用的结果 [(插件名, 结果)]"""
    return list(_pending)


def results_note(results=None) -> str:
    """「二次润色」用的提示段：想让插件结果更口语时，追加进下一轮 system 再问一次。"""
    rs = list(results) if results is not None else list(_pending)
    if not rs:
        return ""
    return ("【插件刚查到的结果】" + "；".join("%s：%s" % (n, t) for n, t in rs) +
            "。请用你自己的话自然地讲给主人，不要提「插件」这两个字。")


def summary_text() -> str:
    """一段话概括插件现状（状态窗/自检用）"""
    if not enabled():
        return "插件系统：关着（右键「🧩 插件」可以打开）"
    ps = list_plugins()
    if not ps:
        return "插件系统：开着，但 plugins/ 里还没有插件（复制 _模板 那份改改就有）"
    ok = [p for p in ps if p["ok"]]
    lines = ["插件系统：开着，%d/%d 个可用" % (len(ok), len(ps))]
    for p in ps:
        lines.append("· %s%s" % (p["name"], "" if p["ok"] else "（%s）" % p["error"]))
    return "\n".join(lines)


if __name__ == "__main__":
    # 手动体检：python -m tool.plugins
    print("插件目录:", root())
    print("开关:", enabled(), "超时: %.0fs" % timeout_sec())
    print()
    print("加载:", sorted(load_all(force=True).keys()))
    print()
    for p in list_plugins():
        print("  · %-10s 标记=%-8s %s %s" % (p["name"], p["marker"],
                                            "已加载" if p["ok"] else "未加载", p["error"]))
    print()
    print("解析:", parse("好，我看看。【插件:例子】随便什么"))
    print("去掉标记后要念的:", repr(clean_for_speech("好，我看看。\n【插件:例子】随便什么\n")))
    print("执行:", run_one("例子", "测试")[:120])
    print()
    print(summary_text())
