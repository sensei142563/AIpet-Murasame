# -*- coding: utf-8 -*-
"""PCL 插件管理面板 — 集中管控程序全部功能插件（桌宠侧 + QQ 侧）。

- 每个功能 = plugins/<id>/ 目录（plugin.json 元数据 + 说明.md）
- feature 插件：开关直接读写 config.json 对应键（如 qq_lively_enable）
- tool 插件：开关直接启停对应进程（如时间同步守护）
- 支持：导入插件包(zip)、删除插件、打开插件目录、启用/停用
"""
import os
import io
import json
import sys
import shutil
import zipfile
import subprocess

from PyQt5.QtCore import QObject, pyqtSignal, Qt, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QScrollArea,
    QCheckBox, QFrame, QMessageBox, QFileDialog, QSizePolicy, QDialog,
    QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit, QButtonGroup,
    QGraphicsOpacityEffect
)
from PyQt5.QtGui import QFont

from .colors import *

S = 1.0


def _app_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _plugins_dir() -> str:
    return os.path.join(_app_base_dir(), "plugins")


def _config_path() -> str:
    try:
        from tool.paths import data_path
        return data_path("config.json")
    except Exception:
        return os.path.join(_app_base_dir(), "config.json")


def _load_config():
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(cfg, toast=True):
    """写配置；toast=True 时在屏幕中央弹保存成功/失败提示"""
    try:
        p = _config_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        if toast:
            try:
                from pcl_launcher.widgets import show_save_toast
                show_save_toast(True)
            except Exception:
                pass
        return True
    except Exception as e:
        print(f"[Plugins] 保存配置失败: {e}")
        if toast:
            try:
                from pcl_launcher.widgets import show_save_toast
                show_save_toast(False)
            except Exception:
                pass
        return False


def _bool_of(value, default=False) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true" if value is not None else default


def scan_plugins():
    """扫描 plugins/ 目录，返回插件元数据列表（带目录路径）"""
    result = []
    root = _plugins_dir()
    if not os.path.isdir(root):
        return result
    try:
        for name in sorted(os.listdir(root)):
            d = os.path.join(root, name)
            pj = os.path.join(d, "plugin.json")
            if not os.path.isdir(d) or not os.path.exists(pj):
                continue
            try:
                with io.open(pj, encoding="utf-8") as f:
                    meta = json.load(f)
                if isinstance(meta, dict) and meta.get("id"):
                    meta.setdefault("name", meta["id"])
                    meta.setdefault("desc", "")
                    meta.setdefault("version", "1.0.0")
                    meta.setdefault("kind", "feature")
                    meta.setdefault("config_key", None)
                    meta.setdefault("extra_keys", [])
                    meta.setdefault("default", True)
                    # 官方插件（随包自带）= builtin true；导入的第三方插件导入时写 false
                    meta.setdefault("builtin", True)
                    meta["_dir"] = d
                    result.append(meta)
            except Exception as e:
                print(f"[Plugins] 读取 {name} 失败: {e}")
    except Exception:
        pass
    return result


def is_enabled(meta, cfg=None) -> bool:
    """读取插件当前启用状态"""
    if cfg is None:
        cfg = _load_config()
    if meta.get("kind") == "tool":
        return _tool_running(meta) if meta.get("id") == "time_guard" else True
    key = meta.get("config_key")
    if not key:
        return bool(meta.get("default", True))
    return _bool_of(cfg.get(key), bool(meta.get("default", True)))


def set_enabled(meta, enabled: bool) -> bool:
    """设置插件启用状态。feature → config 键；tool → 启停进程。返回是否成功"""
    if meta.get("kind") == "tool":
        if meta.get("id") == "time_guard":
            return _time_guard_set(bool(enabled))
        return True
    key = meta.get("config_key")
    if not key:
        return False
    cfg = _load_config()
    cfg[key] = "true" if enabled else "false"
    _save_config(cfg)
    print(f"[Plugins] {meta.get('id')} -> {'启用' if enabled else '停用'}（{key}={cfg[key]}）")
    return True


_TOOL_STATE = {}          # 工具型插件运行状态缓存（后台探测）
_TOOL_BUSY = set()


class _ToolProbe(QObject):
    """探测完成后通知界面刷新（免得一直显示旧状态）"""
    done = pyqtSignal()


tool_probe = _ToolProbe()


def _probe_tool_state(pid: str):
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python(w)?.exe' -and "
             "$_.CommandLine -like '*time_sync_guard.py*' } | Measure-Object).Count"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))   # ★ 别弹终端窗口
        _TOOL_STATE[pid] = out.stdout.strip().startswith(("1", "2", "3"))
    except Exception:
        _TOOL_STATE[pid] = False
    finally:
        _TOOL_BUSY.discard(pid)
    try:
        tool_probe.done.emit()
    except Exception:
        pass


def _tool_running(meta, sync: bool = False) -> bool:
    """工具型插件是否在运行（time_guard = 时间同步守护）。

    ★ 以前这里是**同步**跑 powershell 查进程，而且没带 CREATE_NO_WINDOW →
      点「插件」目录必弹一个终端窗口、界面还要卡半秒以上（用户反馈）。
      现在：界面刷新只读缓存，没缓存就丢后台线程去探（探完发信号刷新）；
      只有"启停"这种需要立即拿准结果的操作才同步等（同样不弹窗口）。
    """
    if meta.get("id") != "time_guard":
        return True
    pid = str(meta.get("id"))
    if pid in _TOOL_STATE:
        return _TOOL_STATE[pid]
    if sync:
        _TOOL_BUSY.add(pid)
        _probe_tool_state(pid)
        return _TOOL_STATE.get(pid, False)
    if pid not in _TOOL_BUSY:
        _TOOL_BUSY.add(pid)
        import threading
        threading.Thread(target=_probe_tool_state, args=(pid,), daemon=True).start()
    return False          # 首次先按"未运行"显示，后台探完会自动刷新


def _time_guard_set(enabled: bool) -> bool:
    """启停时间同步守护进程（计划任务每 3 分钟也会拉起，若已装任务则以任务为准）"""
    try:
        if enabled:
            if _tool_running({"id": "time_guard"}, sync=True):
                return True
            pyw = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python310\pythonw.exe"
            base = _app_base_dir()
            if not os.path.exists(pyw):
                pyw = os.path.join(base, "runtime", "venv", "Scripts", "pythonw.exe")
            if not os.path.exists(pyw):
                return False
            subprocess.Popen([pyw, os.path.join(base, "time_sync_guard.py")],
                             cwd=base, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return True
        # 停用：结束守护进程
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python(w)?.exe' -and "
             "$_.CommandLine -like '*time_sync_guard.py*' } | "
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
            capture_output=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False


from .silicon_dialog import SiliconDialog  # noqa: E402


class PCLPluginSettingsDialog(SiliconDialog):
    """插件设置对话框：按 plugin.json 的 settings 声明渲染表单并写回 config.json"""

    def __init__(self, meta, parent=None):
        super().__init__(parent)
        # 去掉标题栏右上角那个点了没反应的「?」帮助按钮（Qt 默认给 QDialog 加）
        try:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        except Exception:
            pass
        _title = f" {meta.get('name', meta.get('id', '插件'))} 设置"
        super().__init__(_title, parent, width=560, height=620)
        self.setWindowTitle(_title)
        self._meta = meta
        self._widgets = {}

        lay = self.content
        lay.setContentsMargins(int(20 * S), int(16 * S), int(20 * S), int(16 * S))
        lay.setSpacing(int(10 * S))

        cfg = _load_config()
        settings = meta.get("settings") or []
        if not settings:
            info = QLabel("该插件没有可调节参数。\n详情见插件目录内的 说明.md。")
            info.setWordWrap(True)
            info.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
            lay.addWidget(info)

        for item in settings:
            itype = item.get("type", "info")
            if itype == "info":
                lbl = QLabel(item.get("text", ""))
                lbl.setWordWrap(True)
                lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px; "
                                  f"background: {Color6.name()}; border-radius: {int(4*S)}px;"
                                  f"padding: {int(8*S)}px;")
                lay.addWidget(lbl)
                continue
            key = item.get("key")
            label = item.get("label", key or "")
            row = QHBoxLayout()
            cap = QLabel(f"  {label}")
            cap.setStyleSheet(f"color: {Color1.name()}; font-size: {int(13*S)}px;"
                              f"font-family: 'Microsoft YaHei';")
            row.addWidget(cap)
            if itype == "checkbox":
                w = QCheckBox()
                w.setChecked(_bool_of(cfg.get(key), bool(item.get("default", True))))
                row.addWidget(w)
            elif itype == "spin":
                w = QSpinBox()
                w.setRange(int(item.get("min", 0)), int(item.get("max", 999)))
                w.setSingleStep(int(item.get("step", 1)))
                try:
                    w.setValue(int(cfg.get(key, item.get("default", 0))))
                except Exception:
                    w.setValue(int(item.get("default", 0)))
                w.setFixedWidth(int(100 * S))
                row.addWidget(w)
            elif itype == "double":
                w = QDoubleSpinBox()
                w.setRange(float(item.get("min", 0)), float(item.get("max", 999)))
                w.setSingleStep(float(item.get("step", 0.05)))
                try:
                    w.setValue(float(cfg.get(key, item.get("default", 0))))
                except Exception:
                    w.setValue(float(item.get("default", 0)))
                w.setFixedWidth(int(110 * S))
                row.addWidget(w)
            elif itype == "combo":
                w = QComboBox()
                w.addItems([str(o) for o in item.get("options", [])])
                cur = str(cfg.get(key, item.get("default", "")))
                if cur in [str(o) for o in item.get("options", [])]:
                    w.setCurrentText(cur)
                row.addWidget(w)
            else:  # text
                w = QLineEdit()
                w.setText(str(cfg.get(key, item.get("default", ""))))
                w.setFixedWidth(int(180 * S))
                row.addWidget(w)
            row.addStretch()
            self._widgets[key] = (w, itype)
            lay.addLayout(row)

        # 底部按钮
        btns = QHBoxLayout()
        btn_save = QPushButton("   保存")
        btn_cancel = QPushButton("  取消")
        for b in (btn_save, btn_cancel):
            b.setStyleSheet(f"""
                QPushButton {{ background: {Color3.name()}; color: white; border: none;
                    padding: {int(8*S)}px {int(18*S)}px; font-size: {int(13*S)}px;
                    border-radius: {btn_radius()}px; font-family: 'Microsoft YaHei'; }}
                QPushButton:hover {{ background: {Color4.name()}; }}
            """)
        btn_cancel.setStyleSheet(btn_cancel.styleSheet() +
                                f"QPushButton {{ background: {Gray4.name()}; }}")
        btn_save.clicked.connect(self._on_save_clicked)
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(btn_save)
        btns.addWidget(btn_cancel)
        lay.addLayout(btns)

        # 人脸识别插件：照片库直接内嵌在本设置对话框里（原来的顶部「人脸」目录已移除）
        if meta.get("id") == "face":
            info = QLabel(" 主人 / 其他人的照片在这里添加、删除；下面是识别参数。")
            info.setWordWrap(True)
            info.setStyleSheet(f"color: {Color3.name()}; font-size: {int(12*S)}px;"
                               f"background: {Color6.name()}; border-radius: {int(4*S)}px;"
                               f"padding: {int(8*S)}px;")
            lay.addWidget(info)
            # 内嵌照片管理面板（复用原「人脸」页的控件：添加主人/添加其他人/删除）
            try:
                from .widgets import PCLFaceManager
                fm = PCLFaceManager(self)
                fm.setMinimumHeight(300)
                lay.addWidget(fm)
                self._face_manager = fm
            except Exception as e:
                print(f"[Plugins] 内嵌人脸管理面板失败: {e}")
                err = QLabel("（人脸管理面板加载失败，可在插件目录用脚本管理照片）")
                err.setWordWrap(True)
                lay.addWidget(err)
            self.setMinimumWidth(int(480 * S))
        else:
            self.setMinimumWidth(int(480 * S))

    def _on_save_clicked(self):
        """保存按钮：写配置成功后关闭对话框并标记为「已保存」(Accepted)"""
        try:
            self._save()
        except Exception as e:
            print(f"[Plugins] 保存失败: {e}")
        try:
            self.accept()
        except Exception:
            pass

    def _save(self):
        cfg = _load_config()
        for key, (w, itype) in self._widgets.items():
            if itype == "checkbox":
                cfg[key] = "true" if w.isChecked() else "false"
            elif itype == "spin":
                cfg[key] = int(w.value())
            elif itype == "double":
                cfg[key] = float(w.value())
            elif itype == "combo":
                cfg[key] = w.currentText().strip()
            else:
                cfg[key] = w.text().strip()
        _save_config(cfg)
        print(f"[Plugins] 已保存 {self._meta.get('id')} 的设置")
        self.accept()


class PCLPluginsPanel(QScrollArea):
    """插件管理页：列表 + 启用开关 + 导入/删除/打开位置"""

    # 插件启用状态变化（plugin_id, enabled）——主窗口据此联动（如人脸导航显隐）
    plugin_toggled = pyqtSignal(str, bool)

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

        title = QLabel("   插件管理")
        title.setFont(QFont("Microsoft YaHei", int(16 * S), QFont.Bold))
        title.setStyleSheet(f"color: {Color1.name()};")
        self._layout.addWidget(title)

        hint = QLabel("集中管控程序全部功能的插件：桌宠与 QQ 的新增功能都在此统一启用/停用、"
                      "删除或打开文件位置；导入插件包(zip)可扩展新功能。\n"
                      "官方插件随程序自带；「我的插件」为导入的第三方插件，可自由删除。")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        self._layout.addWidget(hint)

        # 分类筛选：全部 / 官方 / 我的（我的 = 导入的第三方插件）
        self._filter = "all"  # all | official | mine
        filt_row = QHBoxLayout()
        filt_row.setSpacing(int(6 * S))
        chip_style = f"""
            QPushButton {{ background: rgba(255,255,255,150); color: {Color1.name()};
                border: 1px solid {Gray5.name()}; padding: {int(5*S)}px {int(14*S)}px;
                font-size: {int(12*S)}px; border-radius: {btn_radius()}px;
                font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ background: rgba(255,255,255,220); }}
            QPushButton:checked {{ background: {Color3.name()}; color: white;
                border-color: {Color3.name()}; font-weight: bold; }}
        """
        self._grp_filt = QButtonGroup(self)
        self._grp_filt.setExclusive(True)
        self._btn_filt_all = QPushButton("全部插件"); self._btn_filt_all.setCheckable(True)
        self._btn_filt_official = QPushButton("官方插件"); self._btn_filt_official.setCheckable(True)
        self._btn_filt_mine = QPushButton("我的插件"); self._btn_filt_mine.setCheckable(True)
        for _b in (self._btn_filt_all, self._btn_filt_official, self._btn_filt_mine):
            _b.setStyleSheet(chip_style)
            _b.setCursor(Qt.PointingHandCursor)
            self._grp_filt.addButton(_b)
        self._btn_filt_all.setChecked(True)
        self._btn_filt_all.clicked.connect(lambda: self._set_filter("all"))
        self._btn_filt_official.clicked.connect(lambda: self._set_filter("official"))
        self._btn_filt_mine.clicked.connect(lambda: self._set_filter("mine"))
        filt_row.addWidget(self._btn_filt_all)
        filt_row.addWidget(self._btn_filt_official)
        filt_row.addWidget(self._btn_filt_mine)
        filt_row.addStretch()
        self._layout.addLayout(filt_row)

        # 顶部操作行
        top = QHBoxLayout()
        btn_import = QPushButton("   导入插件 (zip)")
        btn_refresh = QPushButton("   刷新")
        for b in (btn_import, btn_refresh):
            b.setStyleSheet(f"""
                QPushButton {{ background: {Color3.name()}; color: white; border: none;
                    padding: {int(8*S)}px {int(16*S)}px; font-size: {int(13*S)}px;
                    border-radius: {btn_radius()}px; font-family: 'Microsoft YaHei'; }}
                QPushButton:hover {{ background: {Color4.name()}; }}
            """)
        btn_import.clicked.connect(self._import_plugin)
        btn_refresh.clicked.connect(self._reload)
        top.addWidget(btn_import)
        top.addWidget(btn_refresh)
        top.addStretch()
        self._layout.addLayout(top)

        # 插件列表容器（每次刷新重建）
        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(int(8 * S))
        self._layout.addWidget(self._list_widget)

        path_lbl = QLabel(f"插件目录：{_plugins_dir()}")
        path_lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11*S)}px;")
        self._layout.addWidget(path_lbl)
        self._layout.addStretch()

        self._reload()

    # ---- 列表 ----
    def _set_filter(self, key):
        """切换分类：只改显隐不重建卡片，附带淡入动画，切换不卡顿"""
        if key == self._filter:
            return
        self._filter = key
        self._update_visible_cards()
        self._fade_list()

    def _filter_match(self, meta) -> bool:
        if self._filter == "official":
            return bool(meta.get("builtin", True))
        if self._filter == "mine":
            return not bool(meta.get("builtin", True))
        return True

    def _fade_list(self):
        """列表容器淡入动画（快速柔和，隐藏掉切换重建的突兀感）"""
        try:
            eff = QGraphicsOpacityEffect(self._list_widget)
            eff.setOpacity(0.35)
            self._list_widget.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(160)
            anim.setStartValue(0.35)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.finished.connect(lambda: self._list_widget.setGraphicsEffect(None))
            anim.start(QPropertyAnimation.DeleteWhenStopped)
            self._fade_anim = anim
        except Exception:
            pass

    def _reload(self):
        # 后台探测完成后自动刷新一次（插件运行状态）
        try:
            tool_probe.done.connect(self._reload)
        except Exception:
            pass
        """从磁盘扫描重建全部卡片（导入/删除/刷新/设置关闭时调用；切分类不走这里）"""
        # 清空旧列表
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        plugins = scan_plugins()
        # 分类计数（官方 = builtin；我的 = 导入）
        n_all = len(plugins)
        n_off = sum(1 for p in plugins if p.get("builtin", True))
        n_mine = n_all - n_off
        self._btn_filt_all.setText(f"全部插件（{n_all}）")
        self._btn_filt_official.setText(f"官方插件（{n_off}）")
        self._btn_filt_mine.setText(f"我的插件（{n_mine}）")
        cfg = _load_config()
        self._cards = []
        for meta in plugins:
            card = self._make_card(meta, cfg)
            self._cards.append((meta, card))
            self._list_layout.addWidget(card)
        self._empty_lbl = QLabel("")
        self._empty_lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(13*S)}px; "
                                      f"padding: {int(16*S)}px;")
        self._list_layout.addWidget(self._empty_lbl)
        self._update_visible_cards()
        self._fade_list()

    def _update_visible_cards(self):
        """按当前分类显示/隐藏卡片（不重建，切分类秒切）"""
        vis = 0
        for meta, card in self._cards:
            show = self._filter_match(meta)
            card.setVisible(show)
            vis += int(show)
        if getattr(self, "_empty_lbl", None) is not None:
            if vis == 0:
                texts = {
                    "all": "  该分类下暂无插件。可点击上方「导入插件」添加。",
                    "official": "  该分类下暂无官方插件。",
                    "mine": "  该分类下暂无我的插件。可点击上方「导入插件」添加。",
                }
                self._empty_lbl.setText(texts.get(self._filter, ""))
                self._empty_lbl.setVisible(True)
            else:
                self._empty_lbl.setVisible(False)

    def _make_card(self, meta, cfg):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{ background: rgba(255,255,255,150); border: 1px solid {Gray5.name()};
                border-radius: {int(8*S)}px; }}
        """)
        row = QHBoxLayout(frame)
        row.setContentsMargins(int(12*S), int(10*S), int(12*S), int(10*S))
        row.setSpacing(int(10*S))

        left = QVBoxLayout()
        left.setSpacing(int(2*S))
        _official = bool(meta.get("builtin", True))
        _tag = (f"<span style='color:{Color3.name()};font-size:{int(10*S)}px;'>官方</span>"
                if _official else
                f"<span style='color:#c98a1e;font-size:{int(10*S)}px;'>我的</span>")
        name_lbl = QLabel(f"{meta.get('name', meta['id'])}  {_tag}  "
                          f"<span style='color:{Gray3.name()};font-size:{int(10*S)}px;'>v{meta.get('version','1.0.0')}"
                          f" · {'功能' if meta.get('kind')=='feature' else '工具'}</span>")
        name_lbl.setFont(QFont("Microsoft YaHei", int(14*S), QFont.Bold))
        name_lbl.setStyleSheet(f"color: {Color1.name()}; background: transparent; border: none;")
        left.addWidget(name_lbl)
        desc_lbl = QLabel(meta.get("desc", ""))
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {Color1.name()}; font-size: {int(12*S)}px; background: transparent; border: none;")
        left.addWidget(desc_lbl)
        key_hint = meta.get("config_key") or ("进程/任务" if meta.get("kind") == "tool" else "")
        if key_hint:
            k = QLabel(f"配置键：{key_hint}")
            k.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(10*S)}px; background: transparent; border: none;")
            left.addWidget(k)
        row.addLayout(left, 1)

        # 右侧：启用开关 + 按钮
        right = QVBoxLayout()
        right.setSpacing(int(6*S))
        chk = QCheckBox("启用")
        try:
            from .silicon_ui import enabled_check_qss
            chk.setStyleSheet(enabled_check_qss(Color1.name()))
        except Exception:
            pass
        chk.setChecked(is_enabled(meta, cfg))
        chk.setStyleSheet(f"QCheckBox {{ color: {Color1.name()}; font-size: {int(13*S)}px; "
                          f"font-family: 'Microsoft YaHei'; background: transparent; }}"
                          f"QCheckBox::indicator {{ width: {int(16*S)}px; height: {int(16*S)}px; }}")
        chk.stateChanged.connect(lambda st, m=meta: self._on_toggle(m, st))
        right.addWidget(chk)

        btn_cfg = QPushButton(" 设置")
        btn_open = QPushButton(" 打开位置")
        # 官方内置插件不可删除；仅第三方（我的插件）显示删除按钮
        btn_del = None if _official else QPushButton(" 删除")
        small_style = f"""
            QPushButton {{ background: {Color6.name()}; color: {Color1.name()};
                border: 1px solid {Color5.name()}; padding: {int(4*S)}px {int(8*S)}px;
                font-size: {int(11*S)}px; border-radius: {int(4*S)}px;
                font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ background: {Color4.name()}; color: white; }}
        """
        for b in (btn_cfg, btn_open):
            b.setStyleSheet(small_style)
        if btn_del is not None:
            btn_del.setStyleSheet(small_style)
        btn_cfg.clicked.connect(lambda: self._open_settings(meta))
        btn_open.clicked.connect(lambda: self._open_dir(meta))
        if btn_del is not None:
            btn_del.clicked.connect(lambda: self._delete_plugin(meta))
        right.addWidget(btn_cfg)
        right.addWidget(btn_open)
        if btn_del is not None:
            right.addWidget(btn_del)
        row.addLayout(right)
        return frame

    def _open_settings(self, meta):
        dlg = PCLPluginSettingsDialog(meta, self)
        accepted = dlg.exec_()
        #  只有真正保存过才重建整个插件列表；「取消」直接返回（原来无条件 _reload 会卡一下）
        if accepted == QDialog.Accepted:
            self._reload()

    # ---- 动作 ----
    def _on_toggle(self, meta, state):
        ok = set_enabled(meta, bool(state))
        if not ok:
            QMessageBox.information(self, "插件",
                                    f"「{meta.get('name')}」切换失败（可能缺少运行环境）")
            self._reload()
            return
        self.plugin_toggled.emit(str(meta.get("id", "")), bool(state))

    def _open_dir(self, meta):
        try:
            d = meta.get("_dir")
            if d and os.path.isdir(d):
                os.startfile(d)  # noqa
        except Exception as e:
            print(f"[Plugins] 打开目录失败: {e}")

    def _delete_plugin(self, meta):
        if bool(meta.get("builtin", True)):
            msg = "这是随程序自带的官方内置插件，不可删除。" + chr(10) + "不需要时可在列表里关闭它的开关即可。"
            QMessageBox.information(self, "删除插件", msg)
            return
        if meta.get("id") in ("auto_offline", "lively", "adult_mode", "galgame",
                              "slang_search", "time_guard", "auto_learning",
                              "request_music"):
            QMessageBox.information(self, "删除插件",
                                    "这是内置插件。删除后该功能将失去管控入口："
                                    "功能类会同时被停用（config 键置 false）。\n"
                                    "如误删可重新生成，或联系开发者恢复。")
        ret = QMessageBox.question(
            self, "确认删除",
            f"确定要删除插件「{meta.get('name')}」吗？\n（目录：{meta.get('_dir')}）",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        try:
            # feature 插件删除 → 停用对应功能
            if meta.get("config_key"):
                cfg = _load_config()
                cfg[meta["config_key"]] = "false"
                _save_config(cfg)
            if meta.get("kind") == "tool":
                set_enabled(meta, False)
            d = meta.get("_dir")
            if d and os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
            self.plugin_toggled.emit(str(meta.get("id", "")), False)
            self._reload()
        except Exception as e:
            QMessageBox.warning(self, "删除失败", str(e))

    def _import_plugin(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择插件包 (zip)", "",
                                              "插件包 (*.zip);;所有文件 (*.*)")
        if not path:
            return
        try:
            with zipfile.ZipFile(path) as zf:
                # 定位 plugin.json
                names = zf.namelist()
                target = None
                for n in names:
                    if n.replace("\\", "/").endswith("plugin.json"):
                        target = n
                        break
                if target is None:
                    QMessageBox.warning(self, "导入失败", "压缩包内未找到 plugin.json")
                    return
                base_dir = target.replace("\\", "/").rsplit("/", 1)[0]
                meta = json.loads(zf.read(target).decode("utf-8"))
                pid = str(meta.get("id", "")).strip()
                if not pid or not str(pid).replace("_", "").isalnum():
                    QMessageBox.warning(self, "导入失败", "plugin.json 缺少合法 id")
                    return
                dst = os.path.join(_plugins_dir(), pid)
                if os.path.exists(dst):
                    QMessageBox.warning(self, "导入失败", f"插件 {pid} 已存在，请先删除旧版本")
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
                # 导入的插件一律标记为「我的插件」（非官方）
                _pj = os.path.join(dst, "plugin.json")
                if os.path.isfile(_pj):
                    try:
                        with io.open(_pj, encoding="utf-8") as f:
                            _m2 = json.load(f)
                        if isinstance(_m2, dict):
                            _m2["builtin"] = False
                            with io.open(_pj, "w", encoding="utf-8") as f:
                                json.dump(_m2, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
            QMessageBox.information(self, "导入成功", f"插件「{meta.get('name', pid)}」已导入（我的插件）")
            self._reload()
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"导入出错：{e}")
