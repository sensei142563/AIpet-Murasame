# -*- coding: utf-8 -*-
"""改 run.py：起 TTS 服务时改为经 tool/tts_console.py 外壳，并写外壳配置。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
RUN = os.path.join(ROOT, "run.py")

t = io.open(RUN, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

ANCHOR = """            _flags = _console_flags() | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000)
            proc = subprocess.Popen(
                [python_path, script_path] + _extra,
                cwd=work_dir,
                env=_pop_env,
                creationflags=_flags
            )"""
print("=== 锚点是否命中（原文）===")
print(repr(ANCHOR[:90]))
print("命中:", ANCHOR in t)

NEW = '''            _flags = _console_flags() | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000)
            # ★ 2026-10-13：不再直接把 api.py 丢进新控制台 —— 它会刷一整屏日志，看着乱
            #   （旧版起的是 api_v2.py，本来就安静，所以主人会觉得"以前不长这样"）。
            #   改成经 tool/tts_console.py 外壳：
            #     · 窗口有明确标题（"AIpet 语音服务 · 丛雨（GPT-SoVITS 9880）"）
            #     · 窗口里只打一个整齐横幅，服务本体输出全部写进 data/tts_service.log
            #     · 外壳被 taskkill /T 收掉时，服务本体跟着走（不留孤儿进程）
            _wrap = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "tool", "tts_console.py")
            _pet_label = _pid or ""
            try:
                _pj = os.path.join("pets", str(_pid or ""), "pet.json")
                if _pid and os.path.isfile(_pj):
                    import json as _json_p
                    with open(_pj, encoding="utf-8", errors="replace") as _fp:
                        _pet_label = (_json_p.load(_fp) or {}).get("name") or _pid
            except Exception:
                pass
            _console_cfg = os.path.abspath(os.path.join("data", "tts_console.json"))
            try:
                import json as _json_c
                os.makedirs("data", exist_ok=True)
                with open(_console_cfg, "w", encoding="utf-8") as _fc:
                    _json_c.dump({
                        "title": "AIpet 语音服务 · %s（GPT-SoVITS 9880）" % (_pet_label or "桌宠"),
                        "log": os.path.abspath(os.path.join("data", "tts_service.log")),
                        "lines": [
                            "AIpet 语音服务 · %s" % (_pet_label or "桌宠"),
                            "GPT-SoVITS  ·  服务端口 9880  ·  模型：%s / %s"
                            % (_flag_arg(_extra, "-g") or "-", _flag_arg(_extra, "-s") or "-"),
                            "详细日志写在 data\\\\tts_service.log（本窗口故意保持安静）",
                            "关闭本窗口 = 停止语音服务；不需要语音时可在设置里关掉「短语音」。",
                        ],
                    }, _fc, ensure_ascii=False, indent=1)
            except Exception as _ec:
                print(f"[TTS] ⚠ 写外壳配置失败（将直接启动服务）: {_ec}")
                _console_cfg = ""
            if _console_cfg and os.path.isfile(_wrap):
                _launch = [python_path, _wrap, _console_cfg, "--", script_path] + list(_extra)
            else:
                _launch = [python_path, script_path] + list(_extra)
            proc = subprocess.Popen(
                _launch,
                cwd=work_dir,
                env=_pop_env,
                creationflags=_flags
            )'''

if ANCHOR in t:
    t = t.replace(ANCHOR, NEW, 1)
    io.open(RUN, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已改：经外壳启动 + 写外壳配置（失败则回落直接启动）")
else:
    print("✗ 锚点未命中，未改动")
    sys.exit(1)

import py_compile  # noqa: E402
try:
    py_compile.compile(RUN, doraise=True)
    print("✓ py_compile OK")
except Exception as e:
    print("✗ py_compile:", e)
    sys.exit(1)

print()
print("=== 复核关键行 ===")
for i, l in enumerate(io.open(RUN, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if "tts_console" in l or "tts_console.json" in l or "_launch = " in l:
        print("   %5d| %s" % (i, l.strip()[:104]))
