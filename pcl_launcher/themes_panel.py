# -*- coding: utf-8 -*-
"""PCL 主题管理面板 — 切换 / 导入 / 导出 / 删除主题。

- themes/<id>/theme.json：id/name/builtin/accent/colors
- 官方主题（不可删除、可导出）；「我的主题」可自由导入/复制/改名/删除
- 应用主题：写 config.json 的 ui_theme → 由外壳实时换肤（**不重启启动器**）
"""
import os
import io
import sys
import json
import shutil
import zipfile

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QScrollArea,
    QFrame, QFileDialog, QDialog
)
from PyQt5.QtGui import QFont

from .colors import *
from .colors import _list_themes  # 下划线名不随 * 导出，需显式导入


from .silicon_dialog import SiliconDialog, page_msg, page_confirm, ask_text  # noqa: E402


class PCLThemeBgDialog(SiliconDialog):
    """主题背景设置：选择图片或视频作为启动器背景（写入该主题，立即生效）"""

    def __init__(self, meta, parent=None):
        # ⚠ 基类第一个参数是 **title**：以前这里把 parent 传成标题 → 窗口没父级、
        #   而且内容没塞进基类的 content 布局（下面又 QVBoxLayout(self) 建了第二个布局，
        #   Qt 不给已有布局的窗口装第二个）→ 按钮/标签全成孤儿，只剩一个黑窗口。
        super().__init__(f"{meta.get('name', meta.get('id'))} 背景设置", parent)
        try:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        except Exception:
            pass
        self._meta = meta
        self.setWindowTitle(f"{meta.get('name', meta.get('id'))} 背景设置")
        self.setMinimumWidth(int(470 * S))
        lay = self.content                       # ← 用基类的 content 布局（别再新建）
        lay.setContentsMargins(int(0 * S), int(6 * S), int(0 * S), int(6 * S))
        lay.setSpacing(int(10 * S))

        try:
            if current_theme_id() == meta["id"]:
                btype, _bpath, _op = background_info()
            else:
                btype = ""
        except Exception:
            btype = ""
        cur = QLabel("当前背景：" + ("图片" if btype == "image" else
                                     ("视频" if btype == "video" else "无（纯色底）")))
        cur.setStyleSheet(f"color: {Color1.name()}; font-size: {int(13*S)}px;"
                          f"font-family: 'Microsoft YaHei';")
        lay.addWidget(cur)

        info = QLabel("选择后立即应用到该主题并实时生效。\n"
                      "图片支持 jpg/png；视频建议 H.264 编码的 mp4（wmv/avi 视系统解码器而定）。")
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;"
                           f"background: {Color6.name()}; border-radius: {int(4*S)}px;"
                           f"padding: {int(8*S)}px;")
        lay.addWidget(info)

        row = QHBoxLayout()
        btn_img = QPushButton("选择背景图片")
        btn_vid = QPushButton("选择背景视频")
        btn_rm = QPushButton("  移除背景")
        for b in (btn_img, btn_vid, btn_rm):
            b.setStyleSheet(primary_btn_qss(pad_h=12, font_size=12))
        btn_img.clicked.connect(lambda: self._pick("image"))
        btn_vid.clicked.connect(lambda: self._pick("video"))
        btn_rm.clicked.connect(self._remove_bg)
        row.addWidget(btn_img)
        row.addWidget(btn_vid)
        row.addWidget(btn_rm)
        lay.addLayout(row)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("  取消")
        btn_cancel.setStyleSheet(primary_btn_qss(pad_h=18, font_size=13))
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(btn_cancel)
        lay.addLayout(btns)

    def _copy_into_theme(self, src, ext, kind):
        tdir = self._meta["_dir"]
        assets = os.path.join(tdir, "assets")
        os.makedirs(assets, exist_ok=True)
        for old in os.listdir(assets):
            if old.startswith("bg_custom"):
                try:
                    os.remove(os.path.join(assets, old))
                except Exception:
                    pass
        dst = os.path.join(assets, f"bg_custom.{ext}")
        shutil.copy2(src, dst)
        pj = os.path.join(tdir, "theme.json")
        tj = json.load(io.open(pj, encoding="utf-8"))
        tj["background"] = {"type": kind, "source": f"assets/bg_custom.{ext}", "opacity": 1.0}
        with io.open(pj, "w", encoding="utf-8") as f:
            json.dump(tj, f, ensure_ascii=False, indent=2)
        self.accept()

    def _pick(self, kind):
        if kind == "image":
            filt = "图片 (*.jpg *.jpeg *.png *.bmp)"
        else:
            filt = "视频 (*.mp4 *.mov *.wmv *.avi *.mkv)"
        path, _ = QFileDialog.getOpenFileName(self, "选择背景文件", "", filt)
        if not path:
            return
        ext = os.path.splitext(path)[1].lstrip(".").lower() or ("jpg" if kind == "image" else "mp4")
        self._copy_into_theme(path, ext, kind)

    def _remove_bg(self):
        tdir = self._meta["_dir"]
        pj = os.path.join(tdir, "theme.json")
        tj = json.load(io.open(pj, encoding="utf-8"))
        tj.pop("background", None)
        with io.open(pj, "w", encoding="utf-8") as f:
            json.dump(tj, f, ensure_ascii=False, indent=2)
        assets = os.path.join(tdir, "assets")
        if os.path.isdir(assets):
            for old in os.listdir(assets):
                if old.startswith("bg_custom"):
                    try:
                        os.remove(os.path.join(assets, old))
                    except Exception:
                        pass
        self.accept()

S = 1.0


def _app_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config_path() -> str:
    return os.path.join(_app_base_dir(), "config.json")


def _load_config():
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(cfg):
    try:
        p = _config_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception as e:
        print(f"[Themes] 保存配置失败: {e}")


class PCLThemesPanel(QScrollArea):
    """主题目录页：内置两套 + 自定义主题的导入/导出/应用/删除"""

    # 应用主题/强调色：由外壳实时换肤（theme_id / accent_key）
    theme_applied = pyqtSignal(str)
    # 强调色（主题色）即时预览切换
    accent_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(int(30 * S), int(30 * S), int(30 * S), int(30 * S))
        self._layout.setSpacing(int(14 * S))
        self.setWidget(self._container)

        title = QLabel("主题目录")
        title.setFont(QFont("Microsoft YaHei", int(16 * S), QFont.Bold))
        title.setStyleSheet(f"color: {Color1.name()};")
        self._layout.addWidget(title)

        hint = QLabel("自由切换启动器样式：官方主题随程序自带、不可删除；所有主题均可重命名与打开目录查看文件。"
                      "想改官方主题的配色/壁纸等细节，可先「复制为我的主题」再自由修改。")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        self._layout.addWidget(hint)
        try:
            self._layout.addWidget(self._build_bg_controls())
        except Exception as _e:
            print(f"[Themes] ⚠ 背景调节控件挂载失败: {_e}")

        # ===== 主题色（强调色）选择：与主题一体管理 =====
        acc_label = QLabel("主题色（强调色，点击即时预览切换）")
        acc_label.setFont(QFont("Microsoft YaHei", int(13 * S), QFont.Bold))
        acc_label.setStyleSheet(
            f"color: {Color3.name()}; margin-top: {int(8*S)}px;"
            f"padding: {int(5*S)}px {int(10*S)}px;"
            f"background: {surface_fill(120, 20)};"
            f"border-left: 4px solid {Color3.name()}; border-radius: {int(4*S)}px;")
        self._layout.addWidget(acc_label)
        acc_row = QHBoxLayout(); acc_row.setSpacing(int(10 * S))
        for key in ["blue", "red", "green", "gold", "dark", "crimson"]:
            abtn = QPushButton()
            abtn.setFixedSize(int(32 * S), int(32 * S))
            abtn.setToolTip(key)
            abtn.setStyleSheet(f"""
                QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {THEME_COLORS[key]['title_start']},stop:1 {THEME_COLORS[key]['title_end']});
                    border: 2px solid {Gray5.name()}; border-radius: {int(16*S)}px; }}
                QPushButton:hover {{ border: 3px solid {Color3.name()}; }}
            """)
            abtn.clicked.connect(lambda checked, k=key: self.accent_changed.emit(k))
            acc_row.addWidget(abtn)
        acc_row.addStretch()
        self._layout.addLayout(acc_row)

        top = QHBoxLayout()
        btn_import = QPushButton("导入主题 (zip)")
        btn_refresh = QPushButton("刷新")
        for b in (btn_import, btn_refresh):
            b.setStyleSheet(f"""
                QPushButton {{ background: {Color3.name()}; color: white; border: none;
                    padding: {int(8*S)}px {int(16*S)}px; font-size: {int(13*S)}px;
                    border-radius: {btn_radius()}px; font-family: 'Microsoft YaHei'; }}
                QPushButton:hover {{ background: {Color4.name()}; }}
            """)
        btn_import.clicked.connect(self._import_theme)
        btn_refresh.clicked.connect(self._reload)
        top.addWidget(btn_import)
        top.addWidget(btn_refresh)
        top.addStretch()
        self._layout.addLayout(top)

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(int(10 * S))
        self._layout.addWidget(self._list_widget)

        path_lbl = QLabel(f"主题目录：{THEME_DIR}")
        path_lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11*S)}px;")
        self._layout.addWidget(path_lbl)
        self._layout.addStretch()

        self._reload()

    # ---------- 列表 ----------
    def _build_bg_controls(self):
        """背景透明度 / 背景模糊度 / 背景底色（滑块与取色器调节，拖动即时生效）"""
        from PyQt5.QtWidgets import QSlider, QFrame, QPushButton
        box = QFrame()
        box.setStyleSheet(
            f"QFrame {{ background: rgba(255,255,255,0.045); border: 1px solid {Color5.name()};"
            f" border-radius: 12px; }}")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(int(16*S), int(12*S), int(16*S), int(12*S))
        lay.setSpacing(int(8*S))

        head = QLabel("背景调节（壁纸 / 背景视频 · 拖动实时生效）")
        head.setStyleSheet(f"color: {Color1.name()}; font-size: {int(13*S)}px; font-weight: bold;")
        lay.addWidget(head)

        cfg_path = _config_path()
        cfg = _load_config() or {}

        def _mk(label_text, key, default):
            row = QHBoxLayout()
            lab = QLabel(label_text)
            lab.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
            lab.setFixedWidth(int(84*S))
            sd = QSlider(Qt.Horizontal)
            sd.setRange(0, 100)
            sd.setValue(int(cfg.get(key, default) or default))
            sd.setMinimumWidth(int(220*S))
            val = QLabel(f"{sd.value()}%")
            val.setStyleSheet(f"color: {Color1.name()}; font-size: {int(12*S)}px;")
            val.setFixedWidth(int(46*S))

            def _chg(v, k=key, vl=val):
                """拖动中：只更新数字 + 内存实时预览（**不写盘**）→ 丝滑不卡"""
                vl.setText(f"{v}%")
                try:
                    win = self.window()
                    fn = getattr(win, "apply_bg_settings", None)
                    if callable(fn):
                        fn({k: int(v)})          # 自带节流：只在值变化时重载背景
                except Exception as e:
                    print(f"[Themes] ⚠ 实时预览失败: {e}")

            def _commit(v, k=key):
                """松手/点箭头后落盘一次（300ms 防抖，避免频繁写盘卡顿）"""
                try:
                    from PyQt5.QtCore import QTimer as _QT
                    if not hasattr(self, "_bg_save_timer"):
                        self._bg_save_timer = _QT(self)
                        self._bg_save_timer.setSingleShot(True)

                        def _flush():
                            try:
                                pend = getattr(self, "_bg_pending", {})
                                if pend:
                                    c = _load_config() or {}
                                    c.update(pend)
                                    _save_config(c)
                                    self._bg_pending = {}
                                    print(f"[Themes] 背景设置已保存（实时生效）: {pend}")
                            except Exception as e:
                                print(f"[Themes] ⚠ 背景设置落盘失败: {e}")
                        self._bg_save_timer.timeout.connect(_flush)
                    self._bg_pending = getattr(self, "_bg_pending", {})
                    self._bg_pending[k] = int(v)
                    self._bg_save_timer.start(300)
                except Exception as e:
                    print(f"[Themes] ⚠ 背景设置提交失败: {e}")

            sd.valueChanged.connect(_chg)
            sd.sliderReleased.connect(lambda k=key, sd=sd: _commit(sd.value(), k))
            sd.valueChanged.connect(lambda v, k=key, sd=sd: (None if sd.isSliderDown() else _commit(v, k)))
            row.addWidget(lab)
            row.addWidget(sd, 1)
            row.addWidget(val)
            lay.addLayout(row)
            return sd

        self._bg_opacity_slider = _mk("背景透明度", "ui_bg_opacity", 100)
        # 背景遮罩：把壁纸/视频朝主题底色混一层 → 保证上层文字看得清。
        # 樱华主题的背景是角色拼贴画，满不透明度时文字完全糊在画面上（用户报的
        # 「看不清字」就是这个），所以默认给 55%。
        self._bg_scrim_slider = _mk("背景遮罩", "ui_bg_scrim", 55)

        # ── 背景底色：壁纸半透明时透出来的那层颜色（默认黑，可自由选色）──
        try:
            from PyQt5.QtWidgets import QColorDialog
            from PyQt5.QtGui import QColor as _QC
            row_c = QHBoxLayout()
            lab_c = QLabel("背景底色")
            lab_c.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
            lab_c.setFixedWidth(int(84*S))
            row_c.addWidget(lab_c)

            _cfg_now = _load_config() or {}
            # 空值 = 跟随主题：色块显示主题自己的底色（以前这里会显示成黑色，
            # 让人以为"已经是黑底"，其实根本没设过）
            _explicit = str(_cfg_now.get("ui_bg_color") or "").strip()
            try:
                from .colors import base_bg_color as _theme_base
                self._bg_color = _QC(_explicit) if _explicit else _theme_base()
            except Exception:
                self._bg_color = _QC(_explicit or "#000000")

            btn_col = QPushButton()
            btn_col.setFixedSize(int(58*S), int(24*S))
            btn_col.setCursor(Qt.PointingHandCursor)

            def _paint_btn():
                c = self._bg_color
                btn_col.setStyleSheet(
                    f"QPushButton {{ background: {c.name()}; border: 1px solid rgba(255,255,255,0.35);"
                    f" border-radius: 6px; }}")

            def _save_color(c, follow=False):
                """follow=True → 清空 ui_bg_color（跟随主题自带配色）"""
                from .colors import base_bg_color as _theme_base2
                self._bg_color = _theme_base2() if follow else c
                _paint_btn()
                cc = _load_config() or {}
                if follow:
                    cc["ui_bg_color"] = ""
                else:
                    cc["ui_bg_color"] = c.name()
                _save_config(cc)
                # 立即应用（无需重启）
                try:
                    win = self.window()
                    fn = getattr(win, "apply_bg_settings", None)
                    if callable(fn):
                        fn({"ui_bg_color": "" if follow else c.name()})
                except Exception as _e:
                    print(f"[Themes] ⚠ 底色实时应用失败: {_e}")
                print(f"[Themes] 背景底色 → {'跟随主题' if follow else c.name()}（已实时生效）")

            def _pick_color():
                c = QColorDialog.getColor(self._bg_color, self, "选择背景底色")
                if c.isValid():
                    _save_color(c)

            # 「跟随主题」放第一位：这是默认状态，也是复现主题原貌的唯一入口
            _b_follow = QPushButton("跟随主题")
            _b_follow.setCursor(Qt.PointingHandCursor)
            _b_follow.setFixedHeight(int(24*S))
            _b_follow.setToolTip("使用主题自带的整套配色（推荐；自定义底色会覆盖主题配色）")
            _b_follow.setStyleSheet(
                f"QPushButton {{ background: rgba(255,255,255,0.10); color: {Color1.name()};"
                f" border: 1px solid {Color3.name()}; border-radius: 6px; padding: 0 10px;"
                f" font-size: {int(11*S)}px; }}"
                f"QPushButton:hover {{ background: {Color3.name()}; color: white; }}")
            _b_follow.clicked.connect(lambda _=False: _save_color(self._bg_color, follow=True))
            btn_col.clicked.connect(_pick_color)
            _paint_btn()
            row_c.addWidget(_b_follow)
            row_c.addWidget(btn_col)
            for _name, _hex in (("黑", "#000000"), ("深灰", "#1b1f2b"), ("白", "#ffffff"),
                                ("米色", "#fdf6ee"), ("暗红", "#2a1418")):
                _b = QPushButton(_name)
                _b.setCursor(Qt.PointingHandCursor)
                _b.setFixedHeight(int(24*S))
                _b.setStyleSheet(
                    f"QPushButton {{ background: rgba(255,255,255,0.10); color: {Color1.name()};"
                    f" border: 1px solid {Color5.name()}; border-radius: 6px; padding: 0 10px;"
                    f" font-size: {int(11*S)}px; }}"
                    f"QPushButton:hover {{ border-color: {Color3.name()}; }}")
                _b.clicked.connect(lambda _=False, h=_hex: _save_color(_QC(h)))
                row_c.addWidget(_b)
            row_c.addStretch()
            lay.addLayout(row_c)
        except Exception as _e:
            print(f"[Themes] ⚠ 背景底色控件构建失败: {_e}")
        # ── 文字颜色：和背景底色一样能选（浅色背景必须能改深色字，否则白底白字看不见）──
        try:
            from PyQt5.QtWidgets import QColorDialog as _QCD2
            from PyQt5.QtGui import QColor as _QC2
            row_t = QHBoxLayout()
            lab_t = QLabel("文字颜色")
            lab_t.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
            lab_t.setFixedWidth(int(84*S))
            row_t.addWidget(lab_t)
            self._text_color = _QC2(str((_load_config() or {}).get("ui_text_color") or "#eef1f7"))
            btn_txt = QPushButton()
            btn_txt.setFixedSize(int(58*S), int(24*S))
            btn_txt.setCursor(Qt.PointingHandCursor)

            def _paint_txt_btn():
                c = self._text_color
                btn_txt.setStyleSheet(
                    f"QPushButton {{ background: {c.name()}; border: 1px solid rgba(255,255,255,0.35);"
                    f" border-radius: 6px; }}")

            def _apply_everywhere(hexv):
                """把文字色应用到界面：先找带 apply_text_color 的窗口（一路往上找），
                找不到就直接重算色板 —— 两条路都走一遍，保证"选了就变"。"""
                done = False
                try:
                    w = self
                    for _ in range(12):                      # 逐级向上找外壳（页面 → 外壳窗口）
                        fn = getattr(w, "apply_text_color", None) if w is not None else None
                        if callable(fn):
                            fn(hexv or "")
                            done = True
                            break
                        nxt = w.parentWidget() if w is not None else None
                        if nxt is None and w is not None and w is not w.window():
                            nxt = w.window()
                        if nxt is None or nxt is w:
                            break
                        w = nxt
                except Exception as _e:
                    print(f"[Themes] ⚠ 找外壳应用文字色失败: {_e}")
                if not done:
                    try:
                        from . import colors as _C
                        _C.apply_theme_live(_C.current_theme_id())
                        from PyQt5.QtWidgets import QApplication as _QA
                        _app = _QA.instance()
                        if _app is not None:                     # 全局样式跟着重刷一遍
                            from . import silicon_ui as _sui
                            _sui.install(_app, accent=_C.accent_hex())
                    except Exception as _e:
                        print(f"[Themes] ⚠ 直接重算色板失败: {_e}")
                try:
                    from .silicon_dialog import refresh_all_dialog_colors
                    refresh_all_dialog_colors()                  # 已打开的二级窗口一起换
                except Exception:
                    pass
                return done

            def _save_text_color(hexv):
                """写 ui_text_color → 立即应用（重算色板 + 重建当前页），不用重启"""
                if hexv:
                    self._text_color = _QC2(hexv)
                _paint_txt_btn()
                cc = _load_config() or {}
                cc["ui_text_color"] = str(hexv or "")
                _save_config(cc)
                ok = _apply_everywhere(hexv)
                try:
                    self._text_hint.setText(
                        ("已应用：文字颜色 %s（立即生效）" % (hexv or "跟随主题")) if hexv
                        else "已切回「跟随主题」自带的文字配色")
                    self._text_hint.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11*S)}px;")
                except Exception:
                    pass
                print(f"[Themes] 文字颜色 → {hexv or '自动'}（应用路径：{'外壳' if ok else '直接重算色板'}）")

            def _pick_text_color():
                c = _QCD2.getColor(self._text_color, self, "选择文字颜色")
                if c.isValid():
                    _save_text_color(c.name())

            btn_txt.clicked.connect(_pick_text_color)
            _paint_txt_btn()
            row_t.addWidget(btn_txt)
            _b_auto = QPushButton("跟随主题")
            _b_auto.setCursor(Qt.PointingHandCursor)
            _b_auto.setFixedHeight(int(24*S))
            _b_auto.setToolTip("清空自定义文字色，回到主题自带的配色")
            _b_auto.setStyleSheet(
                f"QPushButton {{ background: rgba(255,255,255,0.10); color: {Color1.name()};"
                f" border: 1px solid {Color3.name()}; border-radius: 6px; padding: 0 10px;"
                f" font-size: {int(11*S)}px; }}"
                f"QPushButton:hover {{ background: {Color3.name()}; color: white; }}")
            _b_auto.clicked.connect(lambda _=False: _save_text_color(""))
            row_t.addWidget(_b_auto)
            for _tn, _th2 in (("深灰字", "#20242e"), ("黑字", "#111111"), ("白字", "#ffffff"),
                              ("米白字", "#fdf6ee"), ("浅灰字", "#b9c2d6")):
                _tb = QPushButton(_tn)
                _tb.setCursor(Qt.PointingHandCursor)
                _tb.setFixedHeight(int(24*S))
                _tb.setStyleSheet(
                    f"QPushButton {{ background: rgba(255,255,255,0.10); color: {Color1.name()};"
                    f" border: 1px solid {Color5.name()}; border-radius: 6px; padding: 0 10px;"
                    f" font-size: {int(11*S)}px; }}"
                    f"QPushButton:hover {{ border-color: {Color3.name()}; }}")
                _tb.clicked.connect(lambda _=False, h=_th2: _save_text_color(h))
                row_t.addWidget(_tb)
            row_t.addStretch()
            lay.addLayout(row_t)
        except Exception as _e:
            print(f"[Themes] ⚠ 文字颜色控件构建失败: {_e}")
        self._bg_blur_slider = _mk("背景模糊度", "ui_bg_blur", 0)

        btn_reset = QPushButton("恢复默认（100% / 55% / 0%）")
        btn_reset.setCursor(Qt.PointingHandCursor)
        acc = THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#2f6fd0")
        btn_reset.setStyleSheet(f"""
            QPushButton {{ background: {acc}; color: white; border: none; border-radius: 8px;
                padding: 6px 14px; font-size: 12px; }}
            QPushButton:hover {{ background: {QColor(acc).lighter(120).name()}; }}""")

        def _reset():
            for sd, v in ((self._bg_opacity_slider, 100), (self._bg_scrim_slider, 55),
                          (self._bg_blur_slider, 0)):
                try:
                    sd.setValue(v)
                except Exception:
                    pass
        btn_reset.clicked.connect(_reset)
        lay.addWidget(btn_reset)
        return box

    def _section_label(self, text, count):
        lbl = QLabel(f"  {text}  <span style='color:{Gray2.name()};font-size:{int(11*S)}px;'>"
                     f"共 {count} 个</span>")
        lbl.setFont(QFont("Microsoft YaHei", int(13 * S), QFont.Bold))
        lbl.setStyleSheet(f"color: {Color1.name()}; margin-top: {int(8*S)}px;"
                          f"background: transparent; border: none;")
        return lbl

    def _reload(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        themes = _list_themes()
        if not themes:
            empty = QLabel("  暂无主题。可点击上方「导入主题」添加。")
            empty.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(13*S)}px; padding: {int(16*S)}px;")
            self._list_layout.addWidget(empty)
            return
        cur = current_theme_id()
        official = [t for t in themes if t.get("builtin", True)]
        mine = [t for t in themes if not t.get("builtin", True)]

        # —— 官方主题（不可删除/修改）——
        self._list_layout.addWidget(self._section_label("官方主题", len(official)))
        for meta in official:
            self._list_layout.addWidget(self._make_card(meta, cur))
        if not official:
            self._list_layout.addWidget(QLabel("  暂无官方主题。"))

        # —— 我的主题（导入/复制，可删除/修改/重命名）——
        self._list_layout.addWidget(self._section_label("我的主题", len(mine)))
        for meta in mine:
            self._list_layout.addWidget(self._make_card(meta, cur))
        if not mine:
            empty2 = QLabel("  暂无我的主题：可点击上方「导入主题 (zip)」导入，"
                            "或在官方主题卡片上点「复制为我的主题」。")
            empty2.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(13*S)}px; padding: {int(12*S)}px;")
            self._list_layout.addWidget(empty2)

    def _make_card(self, meta, current):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{ background: {Color7.name()}; border: 1px solid {Color5.name()};
                border-radius: {int(8*S)}px; }}
        """)
        row = QHBoxLayout(frame)
        row.setContentsMargins(int(12*S), int(10*S), int(12*S), int(10*S))
        row.setSpacing(int(10*S))

        left = QVBoxLayout()
        left.setSpacing(int(2*S))
        is_cur = meta["id"] == current
        name = meta["name"]
        if is_cur:
            name += "当前使用"
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Microsoft YaHei", int(14*S), QFont.Bold))
        name_lbl.setStyleSheet(f"color: {Color3.name() if is_cur else Color1.name()}; "
                               f"background: transparent; border: none;")
        left.addWidget(name_lbl)
        desc = QLabel(meta["desc"] + ("" if meta["builtin"] else "（我的主题）"))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px; background: transparent; border: none;")
        left.addWidget(desc)
        # 配色预览条
        sw = QHBoxLayout()
        sw.setSpacing(int(4*S))
        try:
            pj = os.path.join(meta["_dir"], "theme.json")
            if os.path.isfile(pj):
                with io.open(pj, encoding="utf-8") as f:
                    tjson = json.load(f)
                cols = tjson.get("colors") or {}
                for key in ("Color8", "Color6", "Color3", "Color2"):
                    if key in cols:
                        c = QLabel()
                        c.setFixedSize(int(26*S), int(14*S))
                        # 配色预览必须显示**真实颜色**：标记一下，让外壳的"整页透明化"
                        # 跳过它。否则会被压到 35% 不透明度 → 几个色块看着都是浅蓝，
                        # 预览等于没用（用户报的"点刷新前后色块不一样"就是这个）。
                        c.setProperty("keep_true_color", True)
                        c.setStyleSheet(f"background: {cols[key]}; border-radius: {int(3*S)}px;")
                        sw.addWidget(c)
        except Exception:
            pass
        sw.addStretch()
        left.addLayout(sw)
        row.addLayout(left, 1)

        right = QHBoxLayout()
        right.setSpacing(int(6*S))
        _official = bool(meta["builtin"])
        small = f"""
            QPushButton {{ background: {Color6.name()}; color: {Color1.name()};
                border: 1px solid {Color5.name()}; padding: {int(4*S)}px {int(8*S)}px;
                font-size: {int(11*S)}px; border-radius: {int(4*S)}px;
                font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ background: {Color4.name()}; color: white; }}
            QPushButton:disabled {{ color: {Gray4.name()}; }}
        """

        def _mk(text, tip=""):
            b = QPushButton(text)
            b.setStyleSheet(small)
            if tip:
                b.setToolTip(tip)
            return b

        # 按钮分两列排布，避免单列过长
        col_a = QVBoxLayout(); col_a.setSpacing(int(6*S))
        col_b = QVBoxLayout(); col_b.setSpacing(int(6*S))

        btn_apply = _mk("应用"if not is_cur else "使用中")
        btn_apply.setEnabled(not is_cur)
        btn_apply.clicked.connect(lambda: self._apply(meta))
        col_a.addWidget(btn_apply)

        btn_export = _mk("导出")
        btn_export.clicked.connect(lambda: self._export(meta))
        col_a.addWidget(btn_export)

        if not _official:
            btn_bg = _mk("背景", "设置该主题的启动器背景图片/视频")
            btn_bg.clicked.connect(lambda: self._bg_setting(meta))
            col_a.addWidget(btn_bg)
        else:
            # 官方主题：改细节先复制为我的主题
            btn_copy = _mk("复制为我的", "复制一份到「我的主题」，之后可自由修改背景、重命名或删除")
            btn_copy.clicked.connect(lambda: self._duplicate(meta))
            col_b.addWidget(btn_copy)

        # 所有主题都支持重命名与打开目录
        btn_rename = _mk("重命名")
        btn_rename.clicked.connect(lambda: self._rename(meta))
        col_b.addWidget(btn_rename)
        btn_open = _mk("打开目录", "打开该主题所在文件夹")
        btn_open.clicked.connect(lambda: self._open_dir(meta))
        col_b.addWidget(btn_open)
        if not _official:
            btn_del = _mk("删除")
            btn_del.clicked.connect(lambda: self._delete(meta))
            col_b.addWidget(btn_del)

        right.addLayout(col_a)
        right.addLayout(col_b)
        row.addLayout(right)
        return frame

    def _bg_setting(self, meta):
        """打开背景设置：选好图片/视频后立即生效（正在使用的主题实时换背景）"""
        dlg = PCLThemeBgDialog(meta, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        # 正在使用的主题（或用户刚编辑的就是当前主题）→ 立刻重建背景，不弹重启提示
        if meta["id"] == current_theme_id():
            self.theme_applied.emit(meta["id"])
        self._reload()

    # ---------- 动作 ----------
    def _apply(self, meta):
        """点「应用」立即换肤（无需确认、无需重启；随时可切回来）"""
        if meta["id"] == current_theme_id():
            return
        cfg = _load_config()
        cfg["ui_theme"] = meta["id"]
        _save_config(cfg)
        self.theme_applied.emit(meta["id"])
        # ⚠ 这里**不要**再自己排一次 _reload()：外壳换肤会把当前页整个重建
        # （旧面板被销毁），而 _reload 被挂钩过、会再排两个延时回调 —— 落在销毁之后就是
        #   `RuntimeError: wrapped C/C++ object of type PCLThemesPanel has been deleted` 刷屏。
        # 「当前使用」标记由重建后的新面板自己读 current_theme_id() 标出来。

    def _export(self, meta):
        path, _ = QFileDialog.getSaveFileName(self, "导出主题", f"{meta['id']}_theme.zip",
                                              "主题包 (*.zip)")
        if not path:
            return
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                base = meta["_dir"]
                for root, dirs, files in os.walk(base):
                    for fn in files:
                        full = os.path.join(root, fn)
                        rel = os.path.relpath(full, base)
                        zf.write(full, os.path.join(meta["id"], rel))
            page_msg(self, "导出成功", f"主题已导出到：\n{path}")
        except Exception as e:
            page_msg(self, "导出失败", str(e))

    def _delete(self, meta):
        if meta["builtin"]:
            page_msg(self, "删除主题", "官方主题不可删除。")
            return
        if not page_confirm(self, "确认删除",
                            f"确定删除自定义主题「{meta['name']}」吗？",
                            "主题目录会被永久删除，无法恢复。",
                            ok_text="删除", danger=True):
            return
        try:
            shutil.rmtree(meta["_dir"], ignore_errors=True)
            # 若删除的是当前主题 → 回退到默认主题（silicon），并实时换肤
            cfg = _load_config()
            if cfg.get("ui_theme") == meta["id"]:
                fallback = "silicon"
                cfg["ui_theme"] = fallback
                _save_config(cfg)
                self.theme_applied.emit(fallback)
            self._reload()
        except Exception as e:
            page_msg(self, "删除失败", str(e))

    def _rename(self, meta):
        """主题重命名（官方/我的均可；仅改显示名 name，主题目录 id 不变）"""
        new_name, ok = ask_text(self, "重命名主题", "输入新的主题名称", text=meta["name"],
                                placeholder="最多 40 字")
        if not ok:
            return
        new_name = (new_name or "").strip()
        if not new_name:
            page_msg(self, "重命名主题", "名称不能为空。")
            return
        if len(new_name) > 40:
            page_msg(self, "重命名主题", "名称过长（最多 40 字）。")
            return
        try:
            pj = os.path.join(meta["_dir"], "theme.json")
            tj = json.load(io.open(pj, encoding="utf-8"))
            tj["name"] = new_name
            with io.open(pj, "w", encoding="utf-8") as f:
                json.dump(tj, f, ensure_ascii=False, indent=2)
            print(f"[Themes] 主题 {meta['id']} 已重命名为: {new_name}")
            self._reload()
        except Exception as e:
            page_msg(self, "重命名失败", str(e))

    def _open_dir(self, meta):
        """打开主题所在目录（资源文件浏览器）"""
        d = meta.get("_dir")
        if not d or not os.path.isdir(d):
            page_msg(self, "打开主题目录", "这个主题没有独立目录（官方内置主题就是程序自带的那份）。",
                     str(d or ""))
            return
        try:
            os.startfile(d)  # noqa
        except Exception as e:
            print(f"[Themes] 打开主题目录失败: {e}")
            page_msg(self, "打开主题目录", "打开失败。", str(e))

    def _duplicate(self, meta):
        """把官方主题复制一份到「我的主题」（id 加 _copy 后缀，builtin=False）"""
        try:
            base = str(meta["id"])
            cand = base + "_copy"
            i = 1
            while os.path.isdir(os.path.join(THEME_DIR, cand)):
                i += 1
                cand = f"{base}_copy{i}"
            dst = os.path.join(THEME_DIR, cand)
            shutil.copytree(meta["_dir"], dst)
            pj = os.path.join(dst, "theme.json")
            tj = json.load(io.open(pj, encoding="utf-8"))
            tj["id"] = cand
            tj["name"] = f"{meta['name']}（我的副本）" if i == 1 else f"{meta['name']}（我的副本{i}）"
            tj["builtin"] = False
            with io.open(pj, "w", encoding="utf-8") as f:
                json.dump(tj, f, ensure_ascii=False, indent=2)
            print(f"[Themes] 已复制为我的主题: {cand}")
            self._reload()
        except Exception as e:
            page_msg(self, "复制失败", str(e))

    def _import_theme(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择主题包 (zip)", "",
                                              "主题包 (*.zip);;所有文件 (*.*)")
        if not path:
            return
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                target = None
                for n in names:
                    if n.replace("\\", "/").endswith("theme.json"):
                        target = n
                        break
                if target is None:
                    page_msg(self, "导入失败", "压缩包内未找到 theme.json")
                    return
                base_dir = target.replace("\\", "/").rsplit("/", 1)[0]
                meta = json.loads(zf.read(target).decode("utf-8"))
                tid = str(meta.get("id", "")).strip()
                if not tid or not str(tid).replace("_", "").isalnum():
                    page_msg(self, "导入失败", "theme.json 缺少合法 id")
                    return
                dst = os.path.join(THEME_DIR, tid)
                if os.path.exists(dst):
                    page_msg(self, "导入失败", f"主题 {tid} 已存在，请先删除旧版本")
                    return
                os.makedirs(dst, exist_ok=True)
                for n in names:
                    if n.endswith("/"):
                        continue
                    rel = os.path.relpath(n.replace("\\", "/"), base_dir) if base_dir else n
                    if rel.startswith(".."):
                        continue
                    out = os.path.join(dst, rel)
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    with open(out, "wb") as f:
                        f.write(zf.read(n))
            # 导入的主题一律标记为「我的主题」（非官方，即使原包是官方导出的）
            _tpj = os.path.join(dst, "theme.json")
            if os.path.isfile(_tpj):
                try:
                    with io.open(_tpj, encoding="utf-8") as f:
                        _m2 = json.load(f)
                    if isinstance(_m2, dict):
                        _m2["builtin"] = False
                        with io.open(_tpj, "w", encoding="utf-8") as f:
                            json.dump(_m2, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            page_msg(self, "导入成功", f"主题「{meta.get('name', tid)}」已导入（我的主题）")
            self._reload()
        except Exception as e:
            page_msg(self, "导入失败", f"导入出错：{e}")
