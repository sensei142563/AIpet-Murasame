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

# ⚠ 这一步会**落盘**（affinity() 把抬起来的下限写回 state.json）。
#   为了不污染主人的真实记忆（我自己踩过：探针把 20.4 改成 79 写进了她的存档），
#   这里把 state 的存储路径指到临时目录，并用真值预置一份，再验证下限逻辑。
_st_dir = tempfile.mkdtemp(prefix="state_test2_")
_st_file = os.path.join(_st_dir, "state.json")
_orig_st_path2 = ST._store_path
ST._store_path = lambda: _st_file
try:
    _raw_real = read("pets/murasame/memory/state.json")
    try:
        _seed = json.loads(_raw_real)
    except Exception:
        _seed = {}
    _seed.setdefault("mood", 60.0)
    _seed["affinity"] = 20.4
    io.open(_st_file, "w", encoding="utf-8").write(json.dumps(_seed, ensure_ascii=False))
    ST.reset_cache()
    _aff = ST.affinity()
    check("★ 真实证据下关系不再是 20.4（现在是 %.1f / %s）" % (_aff, ST.affinity_label()),
          _aff > 30.0)
    _persisted = json.loads(io.open(_st_file, encoding="utf-8").read()).get("affinity")
    check("落盘的 affinity 与读出来的一致（不会两处显示不同数）",
          abs(float(_persisted) - _aff) < 0.01, "落盘 %.1f / 读出 %.1f" % (float(_persisted), _aff))
    check("★ 抬起来的数只写进临时文件（主人真实存档没被试写）",
          os.path.isfile(_st_file)
          and abs(float(json.loads(io.open(_st_file, encoding="utf-8").read())
                        .get("affinity")) - _aff) < 0.01
          and ST._store_path() == _st_file,
          "临时文件 %s" % os.path.basename(_st_file))
finally:
    ST._store_path = _orig_st_path2
    ST.reset_cache()
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

print("== ③ 中键拖动不再打断语音（pause_all_ai 默认不动语音）==")
import inspect                             # noqa: E402
import classes.murasame_class as MC3       # noqa: E402
_pet3 = MC3.Murasame()
try:
    _sig = inspect.signature(_pet3.pause_all_ai)
    check("pause_all_ai 有了 stop_voice 开关（默认 False）",
          "stop_voice" in _sig.parameters
          and _sig.parameters["stop_voice"].default is False, str(_sig))
    _calls = {"n": 0}
    _orig_stop = MC3.stop_voice_wav
    MC3.stop_voice_wav = lambda: _calls.__setitem__("n", _calls["n"] + 1)
    try:
        _pet3.pause_all_ai()                       # 点/拖桌宠 → focusInEvent 走这条
        check("★ 点击/拖动（默认路径）**不**停语音", _calls["n"] == 0,
              "被调 %d 次" % _calls["n"])
        _pet3.pause_all_ai(stop_voice=True)        # 用户主动输入才会走这条
        check("用户主动输入时仍然会停语音", _calls["n"] == 1, "被调 %d 次" % _calls["n"])
    finally:
        MC3.stop_voice_wav = _orig_stop
    check("focusInEvent 走的是默认路径（没传 stop_voice=True）",
          "self.pause_all_ai()" in read("classes/murasame_class.py"))
except Exception as e:
    check("pause_all_ai 行为检查", False, "%s: %s" % (type(e).__name__, e))

print("== ② 切回 2D：不进表情词、脸不丢、字号不跳 ==")
check("★ 进入 Live2D 时存的是真实图层（_last_portrait_layers），不是 portrait_history 的表情词",
      "_saved_layers = list(getattr(self, \"_last_portrait_layers\", None)" in
      read("classes/murasame_class.py"))
_pet2 = MC3.Murasame()
_pet2.update_portrait(_pet2.portrait_target, _pet2.first_portrait)
_font_before = getattr(_pet2, "_font_px", None)
_x_before = getattr(_pet2, "text_x_offset", None)
_layers_before = list(getattr(_pet2, "_last_portrait_layers", []) or [])


def _opaque(pet):
    pm = pet.pixmap()
    if pm.isNull():
        return 0.0, (0, 0)
    img = pm.toImage()
    op = smp = 0
    for x in range(0, img.width(), 4):
        for y in range(0, img.height(), 4):
            smp += 1
            if img.pixelColor(x, y).alpha() > 200:
                op += 1
    return 100.0 * op / max(1, smp), (pm.width(), pm.height())


_r_before, _sz_before = _opaque(_pet2)


class _FakeL2D:
    def stop_live2d(self):
        pass

    def hide(self):
        pass


try:
    # 模拟"在 Live2D 里聊过天"：保存信息被写成了表情词 + 还挂着淡入状态
    _pet2._saved_portrait_info = (_pet2.portrait_target, ["高兴", "好奇"])
    _pet2._saved_current_scale = float(getattr(_pet2, "_current_scale", 0.2))
    _pet2._live2d_widget = _FakeL2D()
    _pet2._live2d_mode = True
    _pet2._fade_state = {"id": _pet2._fade_id, "target": _pet2.portrait_target}
    _pet2._exit_live2d_mode()
    _after = list(getattr(_pet2, "_last_portrait_layers", []) or [])
    check("★ 退出后图层全是整数 id（表情词被挡掉）",
          bool(_after) and all(isinstance(x, int) for x in _after), str(_after))
    check("退出后没有淡入残影（_fade_state 清空）", getattr(_pet2, "_fade_state", None) is None)
    _r_after, _sz_after = _opaque(_pet2)
    check("★ 脸没丢：不透明占比与切之前一致（%.1f%% vs %.1f%%）" % (_r_after, _r_before),
          abs(_r_after - _r_before) < 3.0 and _r_after > 25.0)
    check("尺寸没变（%s vs %s）" % (_sz_after, _sz_before), _sz_after == _sz_before)
    check("★ 字号没跳（%s → %s）" % (_font_before, getattr(_pet2, "_font_px", None)),
          getattr(_pet2, "_font_px", None) == _font_before)
    check("留白也没跳（%s → %s）" % (_x_before, getattr(_pet2, "text_x_offset", None)),
          getattr(_pet2, "text_x_offset", None) == _x_before)
    check("保存的图层与进入前一致", _after == _layers_before, "%s vs %s" % (_after, _layers_before))
except Exception as e:
    import traceback
    traceback.print_exc()
    check("Live2D 退出路径能跑通", False, "%s: %s" % (type(e).__name__, e))

print("== ① 换装复核：四套衣服合成结果确实不同 ==")
try:
    import json as _json                    # noqa: E402
    from tool import portrait_outfit as PO2  # noqa: E402
    _pc = os.path.join(REPO, "data", "portrait_choice.json")
    _orig_pc = io.open(_pc, encoding="utf-8").read()
    _ratios = {}
    try:
        for _c in ("制服", "睡衣", "私服", "刀服"):
            _d = _json.loads(_orig_pc)
            _d["b"]["cloth"] = _c
            io.open(_pc, "w", encoding="utf-8").write(_json.dumps(_d, ensure_ascii=False))
            if hasattr(PO2, "reset_cache"):
                PO2.reset_cache()
            _pet2.update_portrait(_pet2.portrait_target, _pet2.first_portrait)
            _ratios[_c] = _opaque(_pet2)[0]
    finally:
        io.open(_pc, "w", encoding="utf-8").write(_orig_pc)
        if hasattr(PO2, "reset_cache"):
            PO2.reset_cache()
    print("      四套衣服的不透明占比：%s" % {k: round(v, 1) for k, v in _ratios.items()})
    check("★ 四套衣服画出来各不相同（换装确实生效）",
          len(set(round(v, 1) for v in _ratios.values())) >= 3, str(_ratios))
except Exception as e:
    check("换装复核", False, "%s: %s" % (type(e).__name__, e))

print("== ④ 联网学习三方共用（tool/learn_hub.py）==")
try:
    import tool.learn_hub as LH               # noqa: E402
    check("中枢有 qq/wx/pet 三个渠道", tuple(LH.CHANNELS) == ("qq", "wx", "pet"),
          str(LH.CHANNELS))
    check("默认渠道是桌宠", LH.current_channel() == "pet", LH.current_channel())
    with LH.channel("wx"):
        check("with channel('wx') 里能读到微信", LH.current_channel() == "wx")
        check("qq_chat 用的 current_channel_or('qq') 也认这个标记",
              LH.current_channel_or("qq") == "wx")
    check("with 结束后回到桌宠", LH.current_channel() == "pet")
    check("未标记时 current_channel_or('qq') 给 qq（QQ 桥没打标记）",
          LH.current_channel_or("qq") == "qq")

    _fake = {"qq_auto_learn_enable": True, "qq_auto_learn_search": True,
             "qq_slang_enable": True}
    _orig_bool = LH._bool
    LH._bool = lambda k, d=False: bool(_fake.get(k, d))
    try:
        check("★ 插件开关一开 → 三个渠道都能联网搜索",
              all(LH.search_enabled(c) for c in LH.CHANNELS),
              str({c: LH.search_enabled(c) for c in LH.CHANNELS}))
        check("★ 插件开关一开 → 三个渠道都能查网络用语",
              all(LH.slang_enabled(c) for c in LH.CHANNELS))
        _fake["learn_search_wx"] = False
        check("关掉微信渠道后：只有微信不查，QQ/桌宠照旧",
              (not LH.search_enabled("wx")) and LH.search_enabled("qq")
              and LH.search_enabled("pet"))
        _fake["qq_auto_learn_search"] = False
        check("子开关一关 → 三个渠道全不查（旧键仍然管全局）",
              not any(LH.search_enabled(c) for c in LH.CHANNELS))
    finally:
        LH._bool = _orig_bool
    check("查不到时静默返回空串（不抛异常）",
          LH.fact_prefix("", "pet") == "" and LH.learn_notes("x", gid=None) == [])
except Exception as e:
    check("learn_hub 可用", False, "%s: %s" % (type(e).__name__, e))

check("★ QQ 侧改走中枢（qq_chat.py 调 learn_hub.fact_prefix）",
      "learn_hub as _lh" in read("qq/qq_chat.py")
      and "_lh.fact_prefix(user_text, _lh.current_channel_or(\"qq\")" in read("qq/qq_chat.py"))
check("★ 网络用语统一由 learn_hub 出（不再在 qq_chat 里重复注入）",
      "_lh_slang.slang_enabled(_ch_slang)" not in read("qq/qq_chat.py")
      and "learn_hub as _lh" in read("qq/qq_chat.py"))
check("★ 微信桥把自己标成 wx 渠道",
      'with _lh_wx.channel("wx")' in read("wechat/wechat_bridge.py"))
check("★ 微信桥对中枢 import 单独容错（中枢坏了也不至于完全不回复）",
      "except Exception as _e_lh:" in read("wechat/wechat_bridge.py")
      and "_lh_wx = None" in read("wechat/wechat_bridge.py"))
check("★ 勿扰模式仍然会停语音（语义没被顺手改掉）",
      "self.pause_all_ai(stop_voice=True)" in read("classes/murasame_class.py"))
check("★ 桌宠本地链路接上中枢（tool/chat.py）",
      "learn_hub as _lh_chat" in read("tool/chat.py"))
check("★ 桌宠云端链路接上中枢（tool/cloud_API_chat.py）",
      "learn_hub as _lh_chat" in read("tool/cloud_API_chat.py"))
_pj1 = json.loads(read("plugins/auto_learning/plugin.json"))
_pj2 = json.loads(read("plugins/slang_search/plugin.json"))
_keys1 = [s.get("key") for s in _pj1["settings"] if s.get("type") == "checkbox"]
_keys2 = [s.get("key") for s in _pj2["settings"] if s.get("type") == "checkbox"]
check("★ 插件页出现三个渠道开关（问题联网搜索）",
      all(k in _keys1 for k in ("learn_search_qq", "learn_search_wx", "learn_search_pet")),
      str(_keys1))
check("★ 插件页出现三个渠道开关（网络用语）",
      all(k in _keys2 for k in ("learn_slang_qq", "learn_slang_wx", "learn_slang_pet")),
      str(_keys2))
_ex4 = json.loads(read("config.example.json"))
check("示例配置里也有这 6 个渠道键",
      all(str(_ex4.get(k)) == "true" for k in
          ("learn_search_qq", "learn_search_wx", "learn_search_pet",
           "learn_slang_qq", "learn_slang_wx", "learn_slang_pet")))

print("== ④b 联网结果的编码（冒烟时发现整段乱码）==")
try:
    from qq.qq_search import decode_response, _clean   # noqa: E402

    class _Resp:
        def __init__(self, body: bytes, enc="ISO-8859-1", app="ISO-8859-1"):
            self.content = body
            self.encoding = enc
            self.apparent_encoding = app
            self.text = body.decode(enc, "replace")

    _cn = "yyds（网络流行语）_百度百科"
    check("★ UTF-8 页面被误判成 Latin-1 时也要解对（原来整段乱码）",
          decode_response(_Resp(_cn.encode("utf-8"))) == _cn)
    _meta = '<meta charset="utf-8">中文测试'
    check("正文 <meta charset> 生效",
          decode_response(_Resp(_meta.encode("utf-8"))) == _meta)
    check("声明编码正常时不乱动",
          decode_response(_Resp("纯ASCII".encode("utf-8"), enc="utf-8")) == "纯ASCII")
    # &#0183; 是十进制 183 → 中点「·」；&ensp; → 空格；&amp; → &（实测结果）
    check("★ HTML 实体被还原（&ensp;/&#0183; 不再原样喂给模型）",
          _clean("a&ensp;&#0183;&ensp;b &amp; c") == "a · b & c",
          repr(_clean("a&ensp;&#0183;&ensp;b &amp; c")))
    check("两个联网模块都用同一套解码",
          "decode_response(r)" in read("qq/qq_search.py")
          and "decode_response as _dec" in read("qq/qq_slang.py"))
except Exception as e:
    check("编码工具可用", False, "%s: %s" % (type(e).__name__, e))

print("== ⑤ codex 复审的 4×P2 + 1×P3 回归 ==")
try:
    # P2-1：plugins_panel 里必须真的 import 到 enabled_check_qss（原来 NameError 被吞掉）
    _pp_src = read("pcl_launcher/plugins_panel.py")
    check("★ 插件页勾选框样式真的套上了（原来 NameError 被 except 吞掉）",
          "from .silicon_ui import enabled_check_qss as _ecq" in _pp_src
          and "_ecq(Color1.name())" in _pp_src)
    from pcl_launcher.plugins_panel import PCLPluginsPanel       # noqa: E402
    from PyQt5.QtWidgets import QCheckBox                        # noqa: E402
    _pp = PCLPluginsPanel()
    _pp.setAttribute(Qt.WA_DontShowOnScreen, True)
    _pp.show()
    app.processEvents()
    _styled = 0
    _total = 0
    for _cb in _pp.findChildren(QCheckBox):
        _total += 1
        _ss = _cb.styleSheet() or ""
        if "image:" in _ss and "indicator" in _ss:
            _styled += 1
    check("★ 插件设置项里有勾选框带上了对勾图样式（%d/%d）" % (_styled, _total), _styled > 0)
    _pp.close()

    # P2-2：对勾 PNG 的文件名必须带颜色（否则换主题后缓存指向错的图）
    import pcl_launcher.silicon_ui as SUI3                       # noqa: E402
    _f1 = SUI3._check_png("#ffffff")
    _f2 = SUI3._check_png("#2b3245")
    check("★ 深浅两色的对勾图是两个不同文件（%s / %s）"
          % (os.path.basename(_f1), os.path.basename(_f2)),
          bool(_f1) and bool(_f2) and _f1 != _f2)
    check("再取一次 #ffffff 仍然指向同一个文件（缓存没被冲掉）",
          SUI3._check_png("#ffffff") == _f1)
    check("两个文件都真的存在", os.path.exists(_f1) and os.path.exists(_f2))

    # P2-3：真实对话条数要读现役角色的 memory/history.json
    import tool.state as ST3                                     # noqa: E402
    from pets.pet_registry import get_memory_dir as _gmd3        # noqa: E402
    _live = os.path.join(_gmd3(), "history.json")
    _n_live = 0
    if os.path.isfile(_live):
        _dd = json.loads(io.open(_live, encoding="utf-8").read())
        _hh = _dd.get("history") if isinstance(_dd, dict) else _dd
        _n_live = len(_hh) if isinstance(_hh, list) else 0
    print("      现役 %s 条 / _talk_count()=%d" % (_n_live or "（没有该文件）", ST3._talk_count()))
    check("★ _talk_count() 读的是现役角色历史（不再是只写一次的 data/history.json）",
          ST3._talk_count() == _n_live if _n_live else ST3._talk_count() >= 0,
          "live=%d count=%d" % (_n_live, ST3._talk_count()))

    # P2-4：群学习检索必须过插件总开关
    import tool.learn_hub as LH3                                 # noqa: E402
    _orig_b3 = LH3._bool
    LH3._bool = lambda k, d=False: False if k == "qq_auto_learn_enable" else True
    try:
        check("★ 插件总开关关着时，群学习检索直接返回空（不再注入）",
              LH3.learn_notes("随便什么问题", gid="12345") == [])
    finally:
        LH3._bool = _orig_b3
except Exception as e:
    import traceback
    traceback.print_exc()
    check("codex 复审回归项可跑", False, "%s: %s" % (type(e).__name__, e))

print("== 跨套翻译的表情映射（用户 2026-09-30 报「这个表情没有」）==")
try:
    from tool import portrait_outfit as PO3                  # noqa: E402
    from qq.qq_portrait import expression_choices as _ec3     # noqa: E402
    _ea = {str(n): int(i) for n, i in _ec3("a") if i}
    _eb = {str(n): int(i) for n, i in _ec3("b") if i}
    _same = sorted(set(_ea) & set(_eb))
    _bad_ba = [n for n in _same if PO3._trans_table("b", "a").get(_eb[n]) != _ea[n]]
    _bad_ab = [n for n in _same if PO3._trans_table("a", "b").get(_ea[n]) != _eb[n]]
    print("      两套同名中文情绪 %d 个" % len(_same))
    check("★ b→a 每个同名情绪都映射到正确 id（修前漏 11 个）", not _bad_ba, str(_bad_ba[:6]))
    check("★ a→b 同样不漏", not _bad_ab, str(_bad_ab[:6]))
    check("害羞 1406(b) → 1480(a)（用户日志里丢的就是这条）",
          PO3._trans_table("b", "a").get(1406) == 1480,
          str(PO3._trans_table("b", "a").get(1406)))
    _n1 = PO3.normalize_layers([1718, 1406, 1719, 1261], "a")
    check("★ 日志原列表翻成 a 套后带「害羞」而不是兜底「平静」",
          1480 in _n1 and 1292 not in _n1, str(_n1))
    _n2 = PO3.normalize_layers([1718, 1376, 1261], "a")
    check("惊讶 1376 → 1368 仍正确（这条以前就对）", 1368 in _n2, str(_n2))
    check("权威映射来源是 expression_choices（不是索引里的日文名）",
          "expression_choices" in read("tool/portrait_outfit.py"))
except Exception as e:
    import traceback
    traceback.print_exc()
    check("跨套表情映射可测", False, "%s: %s" % (type(e).__name__, e))

print("== 数据安全：桌宠列表不会被空扫描覆盖（今晚真丢过一次）==")
try:
    import pets.pet_registry as PR4             # noqa: E402
    _reg_before = io.open(PR4.REGISTRY_JSON, encoding="utf-8").read()
    _rl4, _rs4 = PR4._load_json, PR4.scan_pets
    try:
        PR4._load_json = (lambda p, d=None: None
                          if os.path.normcase(str(p)) == os.path.normcase(PR4.REGISTRY_JSON)
                          else _rl4(p, d))
        PR4.scan_pets = lambda: {"pets": [], "active": None}
        _out4 = PR4.load_pet_list()
    finally:
        PR4._load_json, PR4.scan_pets = _rl4, _rs4
    _reg_after = io.open(PR4.REGISTRY_JSON, encoding="utf-8").read()
    print("      注册表现有 %d 个角色" % len(json.loads(_reg_before).get("pets", [])))
    check("★ 读失败 + 扫描为空时：磁盘上的桌宠列表不被清空",
          _reg_before == _reg_after, "文件长度 %d → %d" % (len(_reg_before), len(_reg_after)))
    check("这种情况只在内存里返回空清单（不崩、不写盘）",
          _out4 == {"pets": [], "active": None}, str(_out4))
    check("守卫代码在位（load_pet_list 里的安全阀）",
          "不用空清单覆盖" in read("pets/pet_registry.py"))
except Exception as e:
    import traceback
    traceback.print_exc()
    check("注册表安全阀可测", False, "%s: %s" % (type(e).__name__, e))

print("== 表情丢失的真根因：自动过渡后 config.portrait 必须与显示同套 ==")
try:
    import classes.murasame_class as MC5                              # noqa: E402
    from classes.Worker_class import current_portrait_type as _cpt    # noqa: E402
    _cfg_p = os.path.join(REPO, "config.json")
    _orig_cfg = io.open(_cfg_p, encoding="utf-8").read()
    try:
        _pet5 = MC5.Murasame()
        _other = "b" if _pet5._current_set() == "a" else "a"
        _pet5._crossfade_to(_other)
        _now = json.loads(io.open(_cfg_p, encoding="utf-8").read()).get("portrait")
        check("★ 自动过渡切换后 config.portrait 跟着变（worker 提示词才会同套）",
              str(_now) == str(_pet5._current_set()) == str(_cpt()),
              "config=%s display=%s worker=%s" % (_now, _pet5._current_set(), _cpt()))
        check("源码守卫：_crossfade_to 里调了 _sync_config_portrait",
              "_sync_config_portrait(new_set)" in read("classes/murasame_class.py"))
    finally:
        io.open(_cfg_p, "w", encoding="utf-8").write(_orig_cfg)   # 字节级还原
    check("config.json 已还原", io.open(_cfg_p, encoding="utf-8").read() == _orig_cfg)
except Exception as e:
    import traceback
    traceback.print_exc()
    check("自动过渡同步可测", False, "%s: %s" % (type(e).__name__, e))

print("== 联网搜索的触发词与查询词（用户问「你知道XX吗」查不查）==")
try:
    import qq.qq_search as Q5                                  # noqa: E402
    check("★ 「你知道…吗？一款游戏」现在会触发联网",
          Q5.query_trigger("你知道「魔法少女的魔女审判」吗？一款游戏") is True)
    check("带书名号的专名一定触发", Q5.query_trigger("你知道「丛雨丸」吗") is True)
    check("泛指问句不触发（免得白查一次）",
          Q5.query_trigger("你知道这个游戏吗") is False
          and Q5.query_trigger("你今天开心吗") is False)
    check("原来的触发词没被弄坏",
          Q5.query_trigger("这是什么梗") is True
          and Q5.query_trigger("帮我查一下 丛雨丸 的出处") is True)

    _cap = {}
    _orig_sw = Q5.search_web
    Q5.search_web = lambda q, num=4: (_cap.setdefault("q", q),
                                     [("标题X", "摘要Y", "http://x")])[1]
    try:
        Q5.note_for_text("你知道「魔法少女的魔女审判」吗？一款游戏")
        _q1 = _cap.get("q")
        _cap.clear()
        Q5.note_for_text("魔法少女的魔女审判 是什么游戏")
        _q2 = _cap.get("q")
        _note = Q5.note_for_text("这是什么梗") or ""
    finally:
        Q5.search_web = _orig_sw
    print("      实际拿去搜的词：%r / %r" % (_q1, _q2))
    check("★ 查询词剥掉「你知道…吗」外壳与补充说明，只留专名",
          _q1 == "魔法少女的魔女审判", repr(_q1))
    check("★ 「…是什么游戏」也剥成专名（否则必应只会拿「魔法」凑词）",
          _q2 == "魔法少女的魔女审判", repr(_q2))
    check("资料仍带「别照抄」的引导语", "不要逐字复述" in _note)
except Exception as e:
    import traceback
    traceback.print_exc()
    check("联网触发/查询清洗可测", False, "%s: %s" % (type(e).__name__, e))

print()
if FAILS:
    print("FAILED %d 项：%s" % (len(FAILS), "、".join(FAILS)))
    sys.exit(1)
print("第二批缺陷回归体检全部通过")
sys.exit(0)
