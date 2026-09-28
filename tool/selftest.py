# -*- coding: utf-8 -*-
"""一键自检：确认桌宠各个子系统都在、接线没断、数据文件能读写。

用法：
    runtime\\venv\\Scripts\\python.exe -m tool.selftest          # 人看的表格
    runtime\\venv\\Scripts\\python.exe -m tool.selftest --json   # 机器读的 JSON

检查四类（只读为主，只在 tmp/ 与 data/ 写一条探针文件再删掉）：

  1. 模块导入 / 入口语法：该在的模块都在、入口脚本能编译
  2. 关键接线：那些"删掉一行就悄悄坏掉、跑起来看不出来"的钩子（用源码断言钉住）
     —— 包括本项目已经修过的坑：MSVC 自愈顺序、本机代理绕过、立绘稳定/裁切、
        语音响度、性能守卫、云对话直连回落 …
  3. 运行时：config 能读、数据目录能写、角色包装得对（pet.json / 头像 / 2D 素材）
  4. 可选依赖：装了没有（缺了只提示，不算失败）

为什么要有：功能一多，改 A 处很容易把 B 处的接线弄断，而且**运行时不一定立刻暴露**。
跑一遍这个能一眼看出哪块坏了；也可以给启动器做成一个「自检」按钮。
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── 1. 该能导入的模块 ────────────────────────────────────────────────
CORE_MODULES = (
    "tool.config", "tool.paths", "tool.net_env", "tool.perf_guard", "tool.audio_polish",
    "tool.msvc_runtime", "tool.napcat_version", "tool.portrait_geom", "tool.portrait_outfit",
    "tool.portrait_cli", "tool.generate", "tool.chat", "tool.cloud_API_chat", "tool.api_server",
    "tool.stt", "tool.camera", "tool.face_recognition", "tool.touch_areas",
    "tool.voice_trigger", "tool.time_utils", "tool.weather_utils",
    "pets.pet_registry", "classes.Worker_class", "classes.murasame_class",
    "pcl_launcher.colors", "pcl_launcher.widgets",
)
# 只做语法检查（导入会拉起 torch/Qt 或产生副作用）
COMPILE_ONLY = (
    "run.py", "main.py", "run_launcher.py", "run_qq.py", "run_wechat.py", "api.py",
    "build_launcher.py", "download.py", "download_stt.py", "time_sync_guard.py",
    "tool/pack/build_installer.py", "tool/pack/installer_main.py", "tool/pack/verify_installer.py",
    "longtext/longtext_tts.py", "longtext/f5tts_server.py", "qq/qq_bridge.py",
    "wechat/ilink_client.py",
)

# ── 2. 关键接线（源码断言）─────────────────────────────────────────
# (文件, 必须出现的片段, 说明)
WIRING = (
    ("run.py", "from tool.msvc_runtime import", "run.py 缺 MSVC 运行时自愈入口"),
    ("run.py", "import torch as _early_torch", "run.py 缺「提前加载 torch」（否则先 Qt 后 torch 会崩）"),
    ("run.py", "import PyQt5", "run.py 里 Qt 的首次导入不见了"),
    ("run.py", "from tool.net_env import bypass_proxy_for_local", "run.py 缺本机绕过系统代理"),
    ("main.py", "from tool.net_env import bypass_proxy_for_local", "main.py 缺本机绕过系统代理"),
    ("run_launcher.py", "from tool.net_env import bypass_proxy_for_local", "run_launcher.py 缺本机绕过系统代理"),
    ("run_qq.py", "from tool.net_env import bypass_proxy_for_local", "run_qq.py 缺本机绕过系统代理"),
    ("run_wechat.py", "from tool.net_env import bypass_proxy_for_local", "run_wechat.py 缺本机绕过系统代理"),
    ("tool/net_env.py", "def bypass_proxy_for_local", "net_env 少了本机绕过函数"),
    ("tool/net_env.py", "def post_with_direct_fallback", "net_env 少了直连回落函数"),
    ("tool/cloud_API_chat.py", "post_with_direct_fallback", "云对话没走「代理挂了自动直连」"),
    ("tool/generate.py", "_pos_of", "立绘合成少了「图层↔坐标一一对应」表"),
    ("tool/generate.py", "画布就地长大", "立绘合成少了「画布长大而不是裁人」"),
    ("classes/murasame_class.py", "def _stabilize_portrait_canvas", "桌宠少了稳定画布"),
    ("classes/murasame_class.py", "self._stabilize_portrait_canvas(self._scale_portrait_pixmap",
     "稳定画布没接在合成出口上"),
    ("classes/murasame_class.py", "def _pad_pixmap(pm, size, center_x=False)",
     "_pad_pixmap 少了 center_x（过渡会左移）"),
    ("classes/murasame_class.py", "def _perf_tick", "桌宠少了性能守卫 tick"),
    ("classes/murasame_class.py", "set_process_priority(False)", "启动时没把进程优先级降到 BelowNormal"),
    ("tool/chat.py", "polish_wav_bytes", "短语音没做响度统一"),
    ("longtext/longtext_tts.py", "polish_wav_bytes", "长语音没做响度统一"),
    ("pcl_launcher/portrait_studio.py", "stable_canvas_width", "工坊预览没和桌面共用几何"),
    ("tool/portrait_geom.py", "def canvas_size_for", "立绘几何模块少了算法入口"),
    ("build_launcher.py", "AIPET_QT_PATHFIX",
     "打包没注入「非 ASCII 路径」修复（中文目录下会缺整个 PyQt5）"),
    ("tool/pyinstaller_qtfix/sitecustomize.py", "_repair",
     "非 ASCII 路径修复模块缺 _repair（或文件被删）"),
)
# 绝不能出现的（历史坑，回来就是 bug 复发）—— **正则**，只扫非注释行：
#   注释里写着"原来写死了 infos[57:65]"是对的（解释历史），不能算复发（自测自己踩过这个误报）
FORBIDDEN = (
    (r"infos\[57:65\]", "立绘合成又把丛雨索引行号写死了（会裁人）"),
    (r"infos\[47:51\]", "立绘合成又把丛雨索引行号写死了（会裁人）"),
)
FORBIDDEN_FILES = ("tool/generate.py",)


def _src(rel: str) -> str:
    """读仓库里某个文件的源码（检查器与被检查对象分开，便于测试替换）"""
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return ""
    return io.open(p, encoding="utf-8", errors="replace").read()


def _code_lines(rel: str):
    """只取**非注释、非空**的代码行（注释里的历史说明不算问题）"""
    out = []
    for ln in _src(rel).splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def _try(fn, name, results):
    try:
        ok, info = fn()
    except Exception as e:
        ok, info = False, "%s: %s" % (type(e).__name__, e)
    results.append((name, bool(ok), str(info)[:90]))
    return ok


def check_modules(results):
    bad = []
    for m in CORE_MODULES:
        try:
            __import__(m)
        except Exception as e:
            bad.append("%s(%s)" % (m, type(e).__name__))
    results.append(("核心模块导入（%d 个）" % len(CORE_MODULES), not bad,
                    "全部通过" if not bad else "失败: " + ", ".join(bad)))
    # ⚠ 不要用 py_compile + cfile=os.devnull：Windows 上 "nul" 会被当普通文件，
    #   报 FileExistsError（自测自己踩过）。直接在内存里 compile()，还不会产生 .pyc 垃圾。
    bad2 = []
    for rel in COMPILE_ONLY:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            bad2.append("%s(缺失)" % rel)
            continue
        try:
            src = io.open(p, encoding="utf-8", errors="replace").read()
            compile(src, p, "exec")
        except Exception as e:
            bad2.append("%s(%s)" % (rel, type(e).__name__))
    results.append(("入口/重模块语法（%d 个）" % len(COMPILE_ONLY), not bad2,
                    "全部通过" if not bad2 else "失败: " + ", ".join(bad2)))


def check_wiring(results):
    missing = []
    for rel, needle, why in WIRING:
        if needle not in _src(rel):
            missing.append("%s ← %s" % (why, rel))
    results.append(("关键接线（%d 处）" % len(WIRING), not missing,
                    "全部通过" if not missing else "断了 %d 处: %s"
                    % (len(missing), " | ".join(missing[:3]))))
    bad = []
    for pat, why in FORBIDDEN:
        rx = re.compile(pat)
        for rel in FORBIDDEN_FILES:
            hit = next((ln for ln in _code_lines(rel) if rx.search(ln)), None)
            if hit:
                bad.append("%s（%s: %s）" % (why, rel, hit[:44]))
    results.append(("历史坑未复发（%d 条）" % len(FORBIDDEN), not bad,
                    "干净" if not bad else "复发: " + " | ".join(bad)))


def check_runtime(results):
    # config：能读（读不到会自动回落到 config.example.json，也算通过但要说明）
    def _cfg():
        from tool.config import get_config
        c = get_config(os.path.join(ROOT, "config.json"))
        if not isinstance(c, dict) or not c:
            return False, "读不到配置"
        from pets.pet_registry import get_active_pet_id
        return True, "角色=%s，键 %d 个" % (get_active_pet_id(), len(c))
    _try(_cfg, "config 可读", results)

    # 数据目录可写（写一条探针再删）
    def _writable():
        import tempfile
        done = []
        for d in ("tmp", "data"):
            p = os.path.join(ROOT, d)
            os.makedirs(p, exist_ok=True)
            fd, f = tempfile.mkstemp(prefix=".selftest_", dir=p)
            os.close(fd)
            os.remove(f)
            done.append(d)
        return True, "可写: " + ", ".join(done)
    _try(_writable, "数据目录可写（tmp/data）", results)

    # 角色包：pet_list 可解析、active 角色存在、pet.json 与头像都在
    def _pets():
        pj = os.path.join(ROOT, "pets", "pet_list.json")
        data = json.load(io.open(pj, encoding="utf-8"))
        ids = [p.get("id") for p in data.get("pets", [])]
        act = str(data.get("active") or "")
        if act not in ids:
            return False, "active=%r 不在列表 %s 里" % (act, ids)
        bad = []
        for pid in ids:
            d = os.path.join(ROOT, "pets", pid)
            pj2 = os.path.join(d, "pet.json")
            if not os.path.isfile(pj2):
                bad.append("%s 缺 pet.json" % pid)
                continue
            cfg = json.load(io.open(pj2, encoding="utf-8"))
            av = cfg.get("avatar") or ""
            if av and not os.path.isfile(os.path.join(d, av)):
                bad.append("%s 头像缺失(%s)" % (pid, av))
        return (not bad), ("角色 %d 个，active=%s%s" % (len(ids), act,
                                                     "" if not bad else "；问题: " + ", ".join(bad)))
    _try(_pets, "角色包完整（pet_list / pet.json / 头像）", results)

    # 立绘几何：当前角色有 2D 素材时应该算得出画布
    def _geom():
        from pets.pet_registry import get_active_pet_id, has_fgimages
        pid = get_active_pet_id()
        if not has_fgimages(pid):
            return True, "%s 没有 2D 素材（跳过）" % pid
        from tool.portrait_geom import stable_canvas_width
        w = stable_canvas_width(pid, "a", 900)
        return (w > 0), ("%s a 套 900px → 宽 %d" % (pid, w))
    _try(_geom, "立绘几何可算", results)


def check_optional(results):
    mods = ("numpy", "requests", "cv2", "PyQt5", "torch", "sounddevice", "soundfile",
            "websocket", "Crypto", "qrcode", "pilk", "live2d", "OpenGL")
    import importlib.util
    missing = [m for m in mods if importlib.util.find_spec(m) is None]
    results.append(("可选依赖（%d 个）" % len(mods), True,
                    "全部在" if not missing else "缺: " + ", ".join(missing)
                    + "（对应功能不可用，不算失败）"))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    results = []
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)
    if as_json:
        # ⚠ JSON 消费者的 stdout 必须是**干净**的：被导入的模块会自己打印横幅
        #   （实测 pygame 会往 stdout 打两行）→ 检查阶段先把 stdout 收走，最后只输出 JSON。
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            check_modules(results)
            check_wiring(results)
            check_runtime(results)
            check_optional(results)
    else:
        check_modules(results)
        check_wiring(results)
        check_runtime(results)
        check_optional(results)
    fails = [(n, i) for n, ok, i in results if not ok]
    if as_json:
        print(json.dumps({"ok": not fails, "checks": [
            {"name": n, "ok": ok, "info": i} for n, ok, i in results]},
            ensure_ascii=False, indent=2))
    else:
        print("=== AIpet 自检（%d 项）===" % len(results))
        for n, ok, info in results:
            print("  %s %-28s %s" % ("✓" if ok else "✗", n, info))
        print("")
        if fails:
            print("失败 %d 项：" % len(fails))
            for n, i in fails:
                print("  ✗ %s —— %s" % (n, i))
        else:
            print("全部通过：模块/接线/运行时/依赖四项都正常（%d 项）" % len(results))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
