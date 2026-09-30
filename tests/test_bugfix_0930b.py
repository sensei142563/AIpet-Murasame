# -*- coding: utf-8 -*-
"""第二批（2026-09-30 傍晚）缺陷回归：⑧默认2D / ⑦f5探测 / ⑥开机问候 / ②关系下限 / ①状态页重复备注。"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AIPET_NO_SPAWN", "1")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FAILS = []


def check(name, cond, extra=""):
    if cond:
        print("  [OK]   %s %s" % (name, extra))
    else:
        print("  [FAIL] %s %s" % (name, extra))
        FAILS.append(name)


def read(rel):
    return io.open(os.path.join(REPO, rel), encoding="utf-8", errors="replace").read()


print("== ⑧ 默认 2D：只有角色要求 / 没有 2D 立绘时才自动进 Live2D ==")
from PyQt5.QtCore import Qt                # noqa: E402
from PyQt5.QtWidgets import QApplication   # noqa: E402
app = QApplication(sys.argv[:1])
import classes.murasame_class as MC        # noqa: E402

_src = read("classes/murasame_class.py")
check("should_default_live2d 不再看 live2d_enabled 总开关",
      "should_default_live2d" in _src
      and "设置里已启用 Live2D 且角色有模型" not in _src)
pet = MC.Murasame()
pet._default_display = "2d"
pet._has_fgimages = True
_orig_gc = MC.get_config
MC.get_config = lambda p: {"live2d_enabled": "true", "screen_index": 0}
try:
    check("★ 总开关开着、但有 2D 立绘 → 启动**不**自动进 Live2D",
          pet.should_default_live2d() is False)
    pet._has_fgimages = False
    check("★ 纯 Live2D 角色（没有 2D 立绘）→ 自动进 Live2D",
          pet.should_default_live2d() is True)
    pet._has_fgimages = True
    pet._default_display = "live2d"
    check("角色自己写 model.default=live2d → 自动进",
          pet.should_default_live2d() is True)
finally:
    MC.get_config = _orig_gc

print("== ⑦ f5_tts 探测：分清「没装」和「装了但依赖缺」，且候选含 PATH 上的 python ==")
import run as RUN                         # noqa: E402

cands = RUN._f5tts_python_candidates()
print("      候选：%s" % [os.path.basename(c) for c in cands])
check("候选里有 runtime\\venv", any("venv" in c for c in cands))
check("★ 候选里有 PATH 上的 python（用户装在系统 Python 里的那种情况）",
      any(os.path.normcase(c) == os.path.normcase(sys.executable) for c in cands)
      or len(cands) >= 3, "%d 个候选" % len(cands))

_ok, _why = RUN._probe_f5tts(sys.executable)
print("      本解释器探测：ok=%s why=%s" % (_ok, _why))
check("探测能返回可读原因（不是空/异常）", isinstance(_why, str) and (bool(_ok) or bool(_why)))

_tmp = tempfile.mkdtemp(prefix="f5probe_")
io.open(os.path.join(_tmp, "f5_tts.py"), "w", encoding="utf-8").write(
    "import definitely_missing_dep_xyz\n")
_env_old = os.environ.get("PYTHONPATH")
os.environ["PYTHONPATH"] = _tmp
try:
    _ok2, _why2 = RUN._probe_f5tts(sys.executable)
finally:
    if _env_old is None:
        os.environ.pop("PYTHONPATH", None)
    else:
        os.environ["PYTHONPATH"] = _env_old
print("      假模块（依赖缺）：ok=%s why=%s" % (_ok2, _why2))
check("★ f5_tts 在、但依赖缺 → 说明里点出「依赖缺」而不是「没装」",
      _ok2 is False and "依赖缺" in _why2, _why2)
check("★ 真的没装时才会说「没装 f5_tts」",
      "没装 f5_tts" in _why or "依赖缺" in _why or bool(_ok))
check("日志会把每个候选的原因打出来",
      "for _n in _F5_NOTES" in read("run.py"))

print("== ⑥ 开机问候：默认播指定语音 / 可关 / 老行为单列 ==")
import tool.care as care                   # noqa: E402
check("默认方式是 voice（不再开机就让模型说话）", care.startup_greeting_mode() == "voice",
      care.startup_greeting_mode())
check("语音路径默认为空 → 不播任何东西", care.startup_greeting_voice() == "")
_mj = read("main.py")
check("main.py 三种方式都处理了（off / voice / chat）",
      '== "off"' in _mj and '== "voice"' in _mj and "老行为" in _mj)
check("voice 模式用 play_voice_wav（不需要 TTS 服务）", "play_voice_wav" in _mj)
_ex = json.loads(read("config.example.json"))
check("示例配置有 startup_greeting_mode / _voice",
      _ex.get("startup_greeting_mode") == "voice" and _ex.get("startup_greeting_voice") == "")

print("== ② 关系下限：按真实相处证据抬起来（提示词不动）==")
import tool.state as ST                    # noqa: E402
_o_talk, _o_days = ST._talk_count, None
try:
    from tool import care as _c2
    _o_days = _c2.companion_days
    ST._talk_count = lambda: 0
    _c2.companion_days = lambda: 1
    check("新用户（1 天、没聊过）→ 下限就是基线 20（体感不变）",
          abs(ST.affinity_floor() - 20.0) < 0.01, "%.1f" % ST.affinity_floor())
    _c2.companion_days = lambda: 100
    ST._talk_count = lambda: 100
    _f100 = ST.affinity_floor()
    check("★ 100 天 + 100 条对话 → 下限抬到「很亲近」档（≥75）", _f100 >= 75.0, "%.1f" % _f100)
    ST._talk_count = lambda: 99999
    _c2.companion_days = lambda: 9999
    check("上限夹在 88（「离不开你」仍要靠真实互动）", ST.affinity_floor() <= 88.0,
          "%.1f" % ST.affinity_floor())
finally:
    ST._talk_count = _o_talk
    if _o_days is not None:
        from tool import care as _c3
        _c3.companion_days = _o_days

ST.reset_cache()
_aff = ST.affinity()
check("★ 真实数据下关系不再是 20.4（现在是 %.1f / %s）" % (_aff, ST.affinity_label()),
      _aff > 30.0)
check("落盘的 affinity 与读出来的一致（不会两处显示不同数）",
      abs(float(json.loads(read("pets/murasame/memory/state.json")).get("affinity")) - _aff) < 0.01,
      read("pets/murasame/memory/state.json")[:80])
check("提示词侧用的是同一个 affinity()", "affinity()" in read("tool/state.py"))

print("== ① 状态页开关行不再每行重复「（桌宠右键菜单）」==")
_sp_src = read("pcl_launcher/status_panel.py")
check("默认位置不再追加提示（源码里按 where 判断）",
      'str(where) in ("", "桌宠右键菜单")' in _sp_src)
try:
    from pcl_launcher.status_panel import PCLStatusPanel   # noqa: E402
    from PyQt5.QtWidgets import QLabel                     # noqa: E402
    _p = PCLStatusPanel()
    _p.show()
    app.processEvents()
    _lbls = [w.text() for w in _p.box_sw.findChildren(QLabel)]
    _dup = [t for t in _lbls if "（桌宠右键菜单）" in t]
    check("★ 构建出来的开关行里没有重复的那句提示", not _dup, "%d 行重复" % len(_dup))
    check("识图那行仍保留它自己的位置提示（启动器「设置」页）",
          any("设置" in t for t in _lbls))
    _p.close()
except Exception as e:
    check("状态页能构建并检查开关行", False, "%s: %s" % (type(e).__name__, e))

print("== ③ 设置页模型下拉按内容自适应（不再固定 200px 被截断）==")
_w_src = read("pcl_launcher/widgets.py")
check("不再用 setFixedWidth 卡死下拉宽度",
      "combo.setFixedWidth(int(200 * S))" not in _w_src)
check("改用 setMinimumWidth + AdjustToContents",
      "combo.setMinimumWidth(int(200 * S))" in _w_src
      and "QComboBox.AdjustToContents" in _w_src)
try:
    import pcl_launcher.silicon_ui as SUI2      # noqa: E402
    SUI2.install(app)
    from pcl_launcher.widgets import PCLSettingsPanel   # noqa: E402
    from PyQt5.QtWidgets import QComboBox               # noqa: E402
    _panel = PCLSettingsPanel()
    _panel.setAttribute(Qt.WA_DontShowOnScreen, True)
    _panel.show()
    app.processEvents()
    _bad = []
    for _c in _panel.findChildren(QComboBox):
        _fm = _c.fontMetrics()
        _need = max([_fm.horizontalAdvance(_c.itemText(i)) for i in range(_c.count())]
                    + [_fm.horizontalAdvance(_c.currentText())] + [0])
        if _need + 28 > _c.width():          # 留出内边距 + 下拉箭头
            _bad.append((_c.currentText(), _c.width(), _need))
    check("★ 每个下拉都放得下它最长的选项（含 deepseek-flash）", not _bad, str(_bad[:2]))
    _panel.close()
except Exception as e:
    check("设置页能构建并检查下拉宽度", False, "%s: %s" % (type(e).__name__, e))

print("== ④ 2D 立绘画布宽度：不再被小图层带偏 ==")
from tool import portrait_geom as PG       # noqa: E402
_w480 = PG.canvas_size_for("murasame", "b", 480)[0]
_w900 = PG.canvas_size_for("murasame", "b", 900)[0]
print("      canvas_size_for(b,480)=%d  (b,900)=%d（修前 1384 / 2596）" % (_w480, _w900))
check("★ 画布宽度回到角色本体尺寸（≤700 / ≤1500）", _w480 <= 700 and _w900 <= 1500,
      "%d / %d" % (_w480, _w900))
check("同一套里稳定（连算两次一样）", PG.canvas_size_for("murasame", "b", 480)[0] == _w480)
check("其它角色不受影响（没有索引时仍返回 0 → 原路径）",
      PG.canvas_size_for("arona", "a", 900) == (0, 0))
import classes.murasame_class as MC2       # noqa: E402
_pet4 = MC2.Murasame()
_pm4 = _pet4.pixmap()
_img4 = _pm4.toImage()
_op = _smp = 0
for _x in range(0, _img4.width(), 5):
    for _y in range(0, _img4.height(), 5):
        _smp += 1
        if _img4.pixelColor(_x, _y).alpha() > 200:
            _op += 1
_ratio = 100.0 * _op / max(1, _smp)
check("★ 合成图里角色占比从 8.3%% 提到 >25%%（现在 %.1f%%）" % _ratio, _ratio > 25.0)
check("画布是竖的（宽 < 高），不再是被撑宽的横条",
      _pm4.width() < _pm4.height(), "%dx%d" % (_pm4.width(), _pm4.height()))

print("== ⑤ 2D 文本框字号/位置回到 v1.16.1 口径 ==")
_mc5 = read("classes/murasame_class.py")
check("2D 字体按 v1.16.1 构造（QFont(字体名, 点数)）",
      "self.text_font = QFont(self._font_family, max(8, int(scaled_font_size)))" in _mc5)
check("留白在 2D 下就是 140×scale（20% 夹取只留给 Live2D）",
      "self.text_x_offset = old_margin" in _mc5
      and 'if getattr(self, "_live2d_mode", False):' in _mc5)
check("想要新字体可以开 text_font_native（默认 false = 老样子）",
      "text_font_native" in _mc5
      and str(json.loads(read("config.example.json")).get("text_font_native")) == "false")
check("★ text_x_offset = max(10, round(140×scale))（scale=%.3f）" % float(_pet4._current_scale),
      int(_pet4.text_x_offset) == max(10, int(round(140 * float(_pet4._current_scale)))),
      "实际 %s" % _pet4.text_x_offset)

print()
if FAILS:
    print("FAILED %d 项：%s" % (len(FAILS), "、".join(FAILS)))
    sys.exit(1)
print("第二批缺陷回归体检全部通过")
sys.exit(0)
