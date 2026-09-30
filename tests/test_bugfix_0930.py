# -*- coding: utf-8 -*-
"""2026-09-30 用户报的一批缺陷的回归体检（⑤ 勾选对比度 / ⑥ 陪伴天数 / ⑩ 形象切换菜单 / ⑪ 前端备注）。

每条都对应一个**真实撞到过**的现象，不是凭空写的：

⑤ 用户："插件页是否打勾的对比度太小，完全看不清，还是颜色没有随着主题变。"
   根因：① 插件设置项的 QCheckBox 没套 `enabled_check_qss`，退回全局那套 `:checked{background:accent}`
        实心块；② 对勾图 `_check_png("#ffffff")` 写死白色 → 浅色主题（千恋万花 / 沫子的日常）上白勾看不见。
⑥ 用户："陪伴天数等等完完全全是不知道从哪里编的"，界面上写着「在一起第 1756 天」。
   根因：`_touch_first_seen()` 按"角色包里最老文件"回填，挑到从压缩包导入、mtime 停在 2021-12-10 的
   资源文件 → first_seen=2021；而 `companion_days()` 写回 `max(旧值, 新值)` → 错误值**永久固化**。
⑩ 用户："右键的更换为 live2D/2D 形象不见了"。
   根因：切换功能一直在（长按 Shift 2 秒），但 `_show_outfit_menu` 里从来没有这个菜单项。
⑪ 用户："任务经验（下次先查这个）里的括号内容不该显示在前端。"
   根因：卡片标题里混进了给开发看的备注。

用法：`python tests/test_bugfix_0930.py`
"""
import io
import json
import os
import re
import sys
import tempfile
import time

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


print("== ⑤ 勾选：颜色随主题明暗走，且插件页设置项套上了带对勾的样式 ==")
from PyQt5.QtWidgets import QApplication   # noqa: E402
app = QApplication(sys.argv[:1])
import pcl_launcher.colors as C            # noqa: E402
import pcl_launcher.silicon_ui as SU       # noqa: E402

_old_theme = getattr(C, "_ACTIVE_THEME_ID", "")
try:
    # ⚠ 只改 _ACTIVE_THEME_ID 不够：颜色对象是模块级 QColor，得用 apply_theme_live() 原地改值
    #   （这正是启动器切主题走的那条路，测试就该走同一条）
    C.apply_theme_live("senrenbanka_copy")           # 浅色主题（沫子的日常）
    light_col = SU._check_color()
    light_dark = SU._is_dark_theme()
    C.apply_theme_live("silicon")                    # 深色主题
    dark_col = SU._check_color()
    dark_dark = SU._is_dark_theme()
finally:
    try:
        C.apply_theme_live(_old_theme or "senrenbanka_copy")
    except Exception:
        C._ACTIVE_THEME_ID = _old_theme
check("浅色主题判定为浅色", light_dark is False, "light_col=%s" % light_col)
check("深色主题判定为深色", dark_dark is True, "dark_col=%s" % dark_col)
check("两种主题的勾色不一样（原来都写死 #ffffff）", light_col != dark_col,
      "%s vs %s" % (light_col, dark_col))
check("浅色主题用深勾（不是白勾）",
      light_col.lower() != "#ffffff" and int(light_col[1:3], 16) < 0x80, light_col)
check("深色主题用白勾", dark_col.lower() == "#ffffff", dark_col)


def _lum(hexs):
    r, g, b = (int(hexs[i:i + 2], 16) for i in (1, 3, 5))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


_c = SU._check_color()
check("勾色与浅色底板的亮度差够大（≥0.35）", abs(_lum(_c) - _lum("#f4eef2")) >= 0.35,
      "勾=%s 亮度差=%.2f" % (_c, abs(_lum(_c) - _lum("#f4eef2"))))
png = SU._check_png(SU._check_color())
check("对勾 PNG 真生成出来了", bool(png) and os.path.isfile(png), os.path.basename(png or ""))
qss = SU.silicon_qss()
check("全局 QSS 的勾选态带对勾图", "QCheckBox::indicator:checked" in qss
      and "image: url(" in qss.split("QCheckBox::indicator:checked")[1][:220])
src_pp = read("pcl_launcher/plugins_panel.py")
check("插件页设置项勾选框套了 enabled_check_qss",
      'w.setStyleSheet(enabled_check_qss(Color1.name()))' in src_pp)
check("enabled_check_qss 用主题感知勾色（不再是写死白）",
      "img = _check_png(_check_color())" in read("pcl_launcher/silicon_ui.py"))

print("== ⑥ 陪伴天数：脏数据会被修掉，且不再被旧值永久固化 ==")
import tool.care as care   # noqa: E402

tmpdir = tempfile.mkdtemp(prefix="care_test_")
_fake = os.path.join(tmpdir, "care.json")
_orig_path = care._path
care._path = lambda: _fake
try:
    check("_plausible：2021 年那种脏值判为不合理",
          care._plausible(1639068862.0) is False)
    check("_plausible：今天判为合理", care._plausible(time.time()) is True)
    check("_plausible：未来时间判为不合理",
          care._plausible(time.time() + 10 * 86400) is False)

    io.open(_fake, "w", encoding="utf-8").write(
        json.dumps({"first_seen": 1639068862.0, "days": 1756}))
    n = care.companion_days()
    check("★ 脏数据下不再返回 1756 天", n < 400, "返回 %d 天" % n)
    d = json.load(io.open(_fake, encoding="utf-8"))
    check("脏 first_seen 被重写为合理值",
          care._plausible(d.get("first_seen")), str(d.get("first_seen")))
    check("存下来的 days 与返回一致", int(d.get("days")) == n, str(d))
    check("_touch_first_seen 直接调用也不返回 2021",
          care._touch_first_seen() > care._FLOOR)

    io.open(_fake, "w", encoding="utf-8").write(
        json.dumps({"first_seen": time.time() - 10 * 86400}))
    check("★ 10 天前的起点 → 第 11 天", care.companion_days() == 11,
          "返回 %d" % care.companion_days())
    io.open(_fake, "w", encoding="utf-8").write(
        json.dumps({"first_seen": time.time() - 10 * 86400, "days": 9999}))
    check("★ 旧值再离谱也压不过现算结果（原来 max() 会留着 9999）",
          care.companion_days() == 11, "返回 %d" % care.companion_days())
finally:
    care._path = _orig_path
    try:
        os.remove(_fake)
    except Exception:
        pass

care_src = read("tool/care.py")
check("companion_days 里不再有 max(int(d.get(\"days\")…)) 那种固化写法",
      'd["days"] = max(int(d.get("days") or 1), n)' not in care_src)

print("== ⑩ 右键菜单里有「换成 Live2D / 2D 形象」，且点了会调回调 ==")
from PyQt5.QtCore import QPoint            # noqa: E402
from PyQt5.QtWidgets import QMenu          # noqa: E402
from classes.murasame_class import Murasame   # noqa: E402

pet = Murasame()
calls = []
pet.toggle_live2d_form = lambda: calls.append("toggle")
captured = {}
_real_exec = QMenu.exec_
QMenu.exec_ = lambda self, *a, **k: captured.setdefault("menu", self) or None


def _patch_exec():
    QMenu.exec_ = lambda self, *a, **k: captured.setdefault("menu", self) or None


def _unpatch_exec():
    QMenu.exec_ = lambda self, *a, **k: None      # 别真弹菜单（offscreen 下会报参数不匹配）
try:
    pet._show_outfit_menu(QPoint(50, 50))
finally:
    QMenu.exec_ = _real_exec
menu = captured.get("menu")
acts = [a.text() for a in menu.actions()] if menu is not None else []
print("      菜单项：%s" % " | ".join(acts)[:150])
check("菜单能构建出来", menu is not None)
check("★ 有「Live2D / 2D 形象」切换项", any("Live2D" in a or "2D 立绘" in a for a in acts),
      str(acts)[:90])
target = next((a for a in menu.actions() if "Live2D" in a.text() or "2D 立绘" in a.text()),
              None) if menu else None
if target is not None:
    target.trigger()
    check("点它会调 main.py 挂上的切换回调", calls == ["toggle"], str(calls))
else:
    check("点它会调 main.py 挂上的切换回调", False, "没找到菜单项")
check("main.py 确实把回调挂到 pet 上",
      "pet.toggle_live2d_form = _on_shift_held" in read("main.py"))
check("没有回调时菜单也不会崩（老角色/未挂载）",
      (lambda: (_patch_exec(), setattr(pet, "toggle_live2d_form", None),
                pet._show_outfit_menu(QPoint(1, 1)), _unpatch_exec(), True)[-1])())

print("== ⑨ 从 Live2D 切回 2D：窗口几何/字号必须还原 ==")
print("   （根因：Live2D 模式下 _ensure_live2d_overlay() 把桌宠窗口本身撑成"
      "「与模型同位置同尺寸」并重算字号，\n"
      "     而 _exit_live2d_mode() 原来只恢复立绘 → 退出后剩一个全屏透明文字层）")
import classes.murasame_class as MC            # noqa: E402
from PyQt5.QtCore import QSize                 # noqa: E402


class _FakeL2D:
    def __init__(self, pos, size):
        self._pos, self._size = pos, size
        self.started = self.stopped = 0

    def pos(self):
        return self._pos

    def size(self):
        return self._size

    def height(self):
        return self._size.height()

    def width(self):
        return self._size.width()

    def lower(self):
        pass

    def resize_to_screen(self, idx):
        pass

    def move(self, *a):
        pass

    def start_live2d(self):
        self.started += 1

    def stop_live2d(self):
        self.stopped += 1


pet2 = Murasame()
pet2._has_fgimages = True
pet2._live2d_initialized = True
_fake = _FakeL2D(QPoint(0, 0), QSize(1920, 1080))
pet2._live2d_widget = _fake
geo0 = (pet2.pos(), pet2.size())
scale0 = float(pet2._current_scale)
_orig_get_config = MC.get_config
MC.get_config = lambda p: {"live2d_enabled": "true", "screen_index": 0}
try:
    pet2._toggle_live2d_mode()
finally:
    MC.get_config = _orig_get_config
check("进入了 Live2D 模式", pet2.is_live2d_mode() is True and _fake.started == 1)
check("★ 进模式时记下了 2D 的几何与字号",
      getattr(pet2, "_saved_window_geo", None) == geo0
      and getattr(pet2, "_saved_current_scale", None) is not None,
      str(getattr(pet2, "_saved_window_geo", None)))
# 模拟 overlay：把窗口撑成模型那么大 + 重算字号（这正是 Live2D 模式下发生的事）
pet2.move(QPoint(0, 0))
pet2.resize(QSize(1600, 900))
pet2._current_scale = 1.9
pet2._exit_live2d_mode()
check("★ 退出后窗口尺寸还原", pet2.size() == geo0[1],
      "%s → %s" % (geo0[1], pet2.size()))
check("★ 退出后窗口位置还原", pet2.pos() == geo0[0],
      "%s → %s" % (geo0[0], pet2.pos()))
check("★ 退出后字号缩放还原（不再是 Live2D 的 1.9）",
      abs(float(pet2._current_scale) - scale0) < 0.35,
      "%.2f → %.2f" % (1.9, float(pet2._current_scale)))
check("Live2D 控件已被停掉（hide）", _fake.stopped == 1)
check("★ 2D 立绘重新合成出来了（不是空白窗）", not pet2.pixmap().isNull(),
      "pixmap=%sx%s" % (pet2.pixmap().width(), pet2.pixmap().height()))
check("已退出 Live2D 模式", pet2.is_live2d_mode() is False)
check("文字层标记已复位", getattr(pet2, "_overlay_visible", None) is False)

print("== ⑪ 前端卡片标题不再带开发备注 ==")
snap_src = read("tool/status_snapshot.py")
check("没有「（下次先查这个）」了", "下次先查这个" not in snap_src)
check("标题就是「任务经验」", '_card("任务经验"' in snap_src)
_bad = [ln.strip()[:70] for ln in snap_src.splitlines()
        if "_card(" in ln and re.search(r"（[^）]*(下次|TODO|待办|先查|暂时|临时)[^）]*）", ln)]
check("没有别的卡片标题夹带开发备注", not _bad, str(_bad[:2]))

print("== ⑦ 桌宠进程不会自己拉起 QQ 桥接 ==")
print("   （用户报「打开桌宠以后连带把 QQAIpet 也启动了」；查证：代码里只有启动器的"
      "「启动QQ」按钮会起它，\n"
      "     系统 HKCU\\Run 里有 QQ 自己的 QQNT /background 自启项 —— 那是 QQ 自己起来的）")
main_src, run_src = read("main.py"), read("run.py")
check("main.py 里没有 QQ 桥接启动入口",
      "run_qq" not in main_src and "QQBotBridge" not in main_src)
check("run.py 里同样没有",
      "run_qq" not in run_src and "QQBotBridge" not in run_src)
sw_src = read("pcl_launcher/silicon_window.py")
check("★ 全仓只有「启动QQ」流程会起桥接（_do_start_qq 恰好 1 个调用点）",
      sw_src.count("self._do_start_qq()") == 1, str(sw_src.count("self._do_start_qq()")))
check("QQ 桥接只在 run_qq.py 里实例化（桌宠进程里连类都不 import）",
      "class QQBotBridge" in read("qq/qq_bridge.py")
      and "QQBotBridge()" in read("run_qq.py")
      and "QQBotBridge" not in main_src)
check("启动桌宠的按钮处理里没有 QQ 相关调用",
      not re.search(r"def start_pet.*?(?=\n    def )", sw_src, re.S)
      or not re.search(r"qq", re.search(r"def start_pet.*?(?=\n    def )", sw_src, re.S).group(0),
                       re.I))

print("== ⑧ 默认启动 = 2D 桌宠 + b 套立绘 + 平静表情 ==")
pj = json.loads(read("pets/murasame/pet.json"))
check("pet.json 默认显示体系是 2d", (pj.get("model") or {}).get("default") == "2d",
      str((pj.get("model") or {}).get("default")))
check("★ 默认表情是「平静」（原来是「高兴」）",
      (pj.get("voices") or {}).get("default_emotion") == "平静",
      str((pj.get("voices") or {}).get("default_emotion")))
check("「平静」确实在表情表里（否则切过去是空表情）",
      "平静" in ((pj.get("model") or {}).get("emotions") or {}))
ex_cfg = json.loads(read("config.example.json"))
check("示例配置默认不开 Live2D（新用户也是 2D 启动）",
      str(ex_cfg.get("live2d_enabled")).lower() == "false", str(ex_cfg.get("live2d_enabled")))
check("示例配置默认 b 套立绘", ex_cfg.get("portrait") == "b", str(ex_cfg.get("portrait")))

print("== ④ 状态窗/状态页的卡片底色必须真的画出来 ==")
print("   （根因：QSS 里写了 background，但没开 WA_StyledBackground → 首次显示不画底，"
      "要等一次样式 polish；\n"
      "     用户看到的就是「字压在壁纸上看不清，点刷新后那块底色才出现」）")
from classes.status_window import StatusWindow      # noqa: E402
from PyQt5.QtCore import Qt                        # noqa: E402
from PyQt5.QtWidgets import QGroupBox              # noqa: E402

_win = StatusWindow()
_win.show()
app.processEvents()
check("状态窗开了 WA_StyledBackground", _win.testAttribute(Qt.WA_StyledBackground) is True)
check("状态窗自己有不透明底（QSS 里 QDialog#statusWindow background）",
      "QDialog#statusWindow" in _win.styleSheet()
      and "background" in _win.styleSheet().split("QDialog#statusWindow")[1][:80])
_cards = _win.findChildren(QGroupBox)
check("状态窗里的卡片都开了 WA_StyledBackground（%d 张）" % len(_cards),
      bool(_cards) and all(c.testAttribute(Qt.WA_StyledBackground) for c in _cards),
      str([c.objectName() for c in _cards][:4]))
_img = _win.grab().toImage()
_paper = _total = 0
for _x in range(0, _img.width(), 6):
    for _y in range(0, _img.height(), 6):
        _total += 1
        _c = _img.pixelColor(_x, _y)
        if (abs(_c.red() - 0xFB) <= 8 and abs(_c.green() - 0xF9) <= 8
                and abs(_c.blue() - 0xF5) <= 8):
            _paper += 1
check("★ 抓图里确实有纸色底（不是全透明/壁纸透出来）",
      _paper >= max(20, _total // 20), "纸色采样 %d/%d" % (_paper, _total))
_win.close()

try:
    from pcl_launcher.status_panel import PCLStatusPanel   # noqa: E402
    _sp = PCLStatusPanel()
    _sp.show()
    app.processEvents()
    _sc = (_sp.findChildren(QGroupBox, "statusCard")
           + _sp.findChildren(QGroupBox, "statusCardError"))
    check("状态页卡片存在（%d 张）" % len(_sc), bool(_sc))
    check("★ 状态页卡片有主题底（QSS 里 background 不再是空）",
          bool(_sc) and all("background:" in c.styleSheet() for c in _sc),
          str([c.styleSheet()[:44] for c in _sc[:2]]))
    check("状态页卡片开了 WA_StyledBackground",
          bool(_sc) and all(c.testAttribute(Qt.WA_StyledBackground) for c in _sc))
    check("状态页的开关盒也有底",
          "background:" in _sp.box_sw.styleSheet()
          and _sp.box_sw.testAttribute(Qt.WA_StyledBackground) is True)
    _sp.close()
except Exception as e:
    check("状态页能构建并检查卡片底色", False, "%s: %s" % (type(e).__name__, e))

print()
if FAILS:
    print("FAILED %d 项：%s" % (len(FAILS), "、".join(FAILS)))
    sys.exit(1)
print("本轮缺陷回归体检全部通过")
sys.exit(0)
