# -*- coding: utf-8 -*-
"""插件系统：让主人自己给她加本事，不用改核心代码（参考 OpenPets / N.E.K.O 的插件思路）。

插件放在项目根目录的 `plugins/<插件名>/` 里，两个文件：

    plugin.json
        {
          "name": "天气",
          "description": "查今天天气",
          "marker": "天气",          ← 她会写【插件:天气】北京
          "version": "1.0",
          "author": "你",
          "enabled": true            ← 设成 false 就不加载
        }
    main.py
        def rules() -> str:            # 可选：注入提示词，告诉她这个能力怎么用
            return "【天气】你可以查天气，写一行【插件:天气】城市名。"
        def handle(arg: str) -> str:   # 必需：收到【插件:天气】后面的内容，返回一句结果
            return f"{arg}今天晴，20~28 度。"
        def schedule() -> list:        # 可选：[(间隔秒数, 无参回调)]
            return []
        def on_load() / on_unload():   # 可选

她说「【插件:天气】北京」时，桌宠会：
    1) 从 Worker 的句子整理里把这一行留住（不当成台词念出来）
    2) 交给我们这个加载器 → 找到插件 → 调它的 handle()
    3) 把返回的文字交回给她，由她用自己的话讲给主人听

安全边界：插件是主人自己放进来的代码，会以桌宠的权限运行（和装个软件一样要自己确认）。
开关：config 的 plugins_enabled（菜单里可以关）。
"""
import importlib.util
import json
import os
import re
import sys
import threading
import time

PLUGIN_MARK_PREFIX = "【插件:"
_MARK_RE = re.compile("[【\\[]\\s*插件\\s*[:：]\\s*([^】\\]]+)[】\\]]\\s*([^\"\\]\\n]{0,80})")

_loaded = {}          # name -> {"meta":…, "mod":…, "dir":…}
_load_ts = [0.0]
_lock = threading.Lock()


def _root() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins")


def enabled() -> bool:
    try:
        from tool.config import get_config
        v = get_config("./config.json").get("plugins_enabled", "true")
        return str(v).strip().lower() in ("true", "1", "yes", "on")
    except Exception:
        return True


def set_enabled(on: bool) -> bool:
    try:
        from tool.config import get_config
        cfg = dict(get_config("./config.json") or {})
        cfg["plugins_enabled"] = "true" if on else "false"
        p = os.path.join("config.json")
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        print(f"[插件] 插件系统 → {'已开启' if on else '已关闭'}")
        if on:
            _load_ts[0] = 0.0        # 立即重新加载
        return True
    except Exception as e:
        print(f"[插件] ⚠ 写开关失败: {e}")
        return False


def plugin_dirs() -> list:
    r = _root()
    out = []
    try:
        for n in sorted(os.listdir(r)):
            d = os.path.join(r, n)
            if os.path.isdir(d) and os.path.exists(os.path.join(d, "main.py")):
                out.append(d)
    except Exception:
        pass
    return out


def _load_one(d: str):
    """加载单个插件目录 → (name, entry) 或 (name, None, 错误)"""
    meta = {}
    try:
        with open(os.path.join(d, "plugin.json"), encoding="utf-8") as f:
            meta = json.load(f)
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    name = str(meta.get("name") or os.path.basename(d))
    if str(meta.get("enabled", True)).lower() in ("false", "0", "no", "off"):
        return name, None, "在 plugin.json 里标了 enabled=false"
    path = os.path.join(d, "main.py")
    try:
        spec = importlib.util.spec_from_file_location("aiplug_%s" % abs(hash(d)), path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        if not hasattr(mod, "handle"):
            return name, None, "main.py 里没有 handle(arg) 函数"
        try:
            if hasattr(mod, "on_load"):
                mod.on_load()
        except Exception as e:
            print(f"[插件] ⚠ {name}.on_load 出错: {e}")
        return name, {"meta": meta, "mod": mod, "dir": d}, ""
    except Exception as e:
        return name, None, f"{type(e).__name__}: {e}"


def load_all(force: bool = False) -> dict:
    """加载所有插件（结果缓存 30 秒；force=True 立刻重扫）"""
    with _lock:
        now = time.time()
        if not force and (now - float(_load_ts[0] or 0) < 30) and _loaded:
            return _loaded
        _loaded.clear()
        if not enabled():
            _load_ts[0] = now
            return _loaded
        for d in plugin_dirs():
            name, entry, err = _load_one(d)
            if entry:
                _loaded[name] = entry
                print(f"[插件] ✅ 已加载：{name}（{entry['meta'].get('description') or '无说明'}）")
            elif err:
                print(f"[插件] ⚠ 跳过 {os.path.basename(d)}：{err}")
        _load_ts[0] = now
        return _loaded


def list_plugins() -> list:
    """给窗口/日志看的清单"""
    out = []
    for d in plugin_dirs():
        meta = {}
        try:
            with open(os.path.join(d, "plugin.json"), encoding="utf-8") as f:
                meta = json.load(f) or {}
        except Exception:
            pass
        nm = str(meta.get("name") or os.path.basename(d))
        out.append({"name": nm, "desc": str(meta.get("description") or ""),
                    "marker": str(meta.get("marker") or ""),
                    "ok": nm in load_all(),
                    "dir": os.path.basename(d)})
    return out


def markers() -> list:
    """所有插件的标记名（会写进提示词：她能用【插件:xxx】）"""
    out = []
    for name, e in load_all().items():
        mk = str((e.get("meta") or {}).get("marker") or "").strip()
        out.append((mk or name, name, str((e.get("meta") or {}).get("description") or "")))
    return out


def rules_text() -> str:
    """把所有插件的能力说明拼起来交给模型"""
    if not enabled():
        return ""
    ms = markers()
    if not ms:
        return ""
    lines = ["【插件能力（主人给你装的）】下面这些是你额外会做的事，写一行「【插件:标记】参数」就能用："]
    for mk, name, desc in ms[:12]:
        lines.append(f"· 【插件:{mk}】{('——' + desc) if desc else ''}")
    try:
        for _name, e in load_all().items():
            mod = e.get("mod")
            if mod is not None and hasattr(mod, "rules"):
                r = str(mod.rules() or "").strip()
                if r:
                    lines.append(r[:300])
    except Exception:
        pass
    lines.append("★ 标记那一行不会念出来；插件返回的结果桌宠会交给你，你用自己的话讲给主人。")
    return chr(10).join(lines)


def parse(text: str) -> list:
    """从回复里解析【插件:标记】参数 → [(标记, 参数)]"""
    out = []
    for m in _MARK_RE.finditer(str(text or "")):
        mk = str(m.group(1)).strip()
        arg = str(m.group(2)).strip("：:，,。\"'「」")
        if mk:
            out.append((mk, arg))
    return out[:2]


def clean_for_speech(text: str) -> str:
    src = str(text or "")
    try:
        if not _MARK_RE.search(src):
            return src
        return re.sub("\\n{2,}", chr(10), _MARK_RE.sub("", src)).strip()
    except Exception:
        return src


def run_one(marker: str, arg: str) -> str:
    """执行一个插件（拿不到就返回空）"""
    if not enabled():
        return ""
    mk = str(marker or "").strip()
    for name, e in load_all().items():
        meta = e.get("meta") or {}
        if str(meta.get("marker") or name) == mk:
            try:
                res = e["mod"].handle(str(arg or ""))
                txt = str(res or "").strip()
                print(f"[插件] {name} → {txt[:60]}")
                return txt
            except Exception as ex:
                print(f"[插件] ⚠ {name}.handle 出错: {type(ex).__name__}: {ex}")
                return f"（插件「{name}」出错了：{type(ex).__name__}）"
    print(f"[插件] ⚠ 没有叫「{mk}」的插件（可能没装或已关闭）")
    return ""


def schedules() -> list:
    """所有插件声明的定时任务 → [(间隔秒, 回调, 插件名)]"""
    out = []
    for name, e in load_all().items():
        mod = e.get("mod")
        try:
            if mod is not None and hasattr(mod, "schedule"):
                for it in (mod.schedule() or []):
                    try:
                        iv, cb = it
                        out.append((max(30.0, float(iv)), cb, name))
                    except Exception:
                        continue
        except Exception as ex:
            print(f"[插件] ⚠ {name}.schedule 出错: {ex}")
    return out


if __name__ == "__main__":
    import sys as _s
    try:
        _s.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("插件目录:", _root())
    print("开关:", enabled())
    print("发现:", plugin_dirs())
    print()
    print("加载:", list(load_all(force=True).keys()))
    print()
    print("清单:")
    for p in list_plugins():
        print("  · %-8s %-22s 标记=%-8s %s" % (p["name"], p["desc"][:22], p["marker"],
                                              "已加载" if p["ok"] else "未加载"))
    print()
    print("解析:", parse("好，我看看。【插件:系统信息】"))
    print("执行:", run_one("系统信息", "")[:120])
    print()
    print("规则节选:")
    for ln in rules_text().splitlines()[:4]:
        print("  ", ln[:80])
