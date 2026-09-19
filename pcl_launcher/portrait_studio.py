# -*- coding: utf-8 -*-
"""立绘工坊 — 选择立绘类型（a/b 两套独立素材）+ 服装/表情/装饰/场景，实时预览并保存。

a 套与 b 套的服装、表情图层 ID 完全不同（各自成套），因此这里可以：
- 切换「立绘类型」查看任意一套，并分别为两套保存各自的服装/装饰；
- 预览使用与 QQ 立绘完全相同的合成流程（本地场景背景 + 放大裁剪，无黑边）。

保存后：该套立绘在 QQ 群对话与桌宠模式都用这套装扮
（表情仍按对话情绪自动变化）。

说明：PCL 启动器是纯 UI 壳（不含 cv2 等桌宠依赖），因此选项枚举与图片
合成全部通过 runtime venv 的 Python 以子进程调用 tool/portrait_cli.py 完成。
"""
import json
import os
import subprocess
import threading

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                             QCheckBox, QPushButton, QGroupBox, QWidget,
                             QStackedLayout, QScrollArea)


def _studio_log(msg: str):
    """把工坊的合成/加载情况写进 tmp/portrait_studio.log（用户可直接查看）"""
    try:
        import datetime
        d = os.path.join(_base_dir(), "tmp")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "portrait_studio.log"), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%m-%d %H:%M:%S}] {msg}\n")
    except Exception:
        pass


def _base_dir():
    """项目根目录：打包后用 exe 所在目录（frozen 时 __file__ 在 _internal 里，不能用）"""
    try:
        from .colors import _app_base_dir
        return _app_base_dir()
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _runtime_python():
    """项目自带 runtime venv 的 Python（有 cv2 等依赖）"""
    p = os.path.join(_base_dir(), "runtime", "venv", "Scripts", "python.exe")
    if os.path.exists(p):
        return p
    return os.path.join(_base_dir(), ".venv", "Scripts", "python.exe")


from .silicon_dialog import SiliconDialog, fade_in as _sil_fade  # noqa: E402


def _clean_name(x) -> str:
    """清理图层/表情名里的控制字符与替换符（避免显示成乱码方块）"""
    try:
        t = str(x)
        t = "".join(ch for ch in t if ch == "\n" or ord(ch) >= 32)
        return t.replace("\ufffd", "").strip()
    except Exception:
        return str(x)


class PortraitStudio(SiliconDialog):
    """立绘工坊对话框"""

    preview_ready = pyqtSignal(str)  # 合成完成（图片路径，空串=失败）
    options_ready = pyqtSignal(dict)  # 选项枚举完成

    def __init__(self, parent=None, pet_id=None):
        super().__init__("立绘工坊 — 立绘类型 / 换装 / 表情 / 场景", parent,
                         width=1060, height=720)
        # ★ 按「当前要编辑的角色」工作（以前永远用活动角色 → 编辑别人时显示的是活动角色的立绘）
        self._pet_id = pet_id
        # 内容挂到新外壳的 content 区（自带圆角/亚克力/标题栏/关闭按钮）
        _lay = self.content
        try:
            self.content.setContentsMargins(14, 4, 14, 12)
        except Exception:
            pass
        self.setWindowTitle("立绘工坊 — 立绘类型 / 换装 / 表情 / 场景")
        # ⚠ 置顶 + 加大最小尺寸：
        #   ① 启动器是较大的不透明窗口，工坊被它盖住时用户会「看到启动器的内容，
        #      但要点的是下面的工坊」→ 表现为「显示的位置和实际点击的位置不一样」；
        #   ② 窗口太小会导致右侧控制列被挤掉/裁切，按钮位置随之错乱。
        self._want_size = (1320, 860)
        try:
            self.setMinimumSize(1200, 780)
        except Exception:
            pass
        try:
            from PyQt5.QtCore import Qt as _Qt2
            self.setWindowFlags(_Qt2.Window | _Qt2.FramelessWindowHint
                                | _Qt2.WindowStaysOnTopHint)
        except Exception:
            pass
        self.resize(*self._want_size)
        self._busy = False
        self._pending = False
        self._last_path = ""
        self._last_pixmap = None
        self._cur_set = "a"
        self._data = {}
        self._mode = "layers"          # layers / single（按角色立绘类型自适应）
        self._is_l2d_show = False
        self.preview_ready.connect(self._on_preview)
        self.options_ready.connect(self._on_options)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._refresh_preview)
        self._build_ui()
        threading.Thread(target=self._load_options, daemon=True).start()
        # 无边框窗口首次显示容易用最小尺寸 → 显示后强制重排一次
        try:
            QTimer.singleShot(0, self._force_size)
            QTimer.singleShot(150, self._force_size)
        except Exception as _e:
            print(f"[PortraitStudio] ⚠ 初始尺寸失败: {_e}")

    def _needed_size(self):
        """窗口至少要有这么大才装得下内容。

        ⚠ 这就是「看到的按钮位置 ≠ 能点到的位置」的根因：
        右侧控制列需要 ~916px 高，但窗口只给了 860px → 布局按 916 排（画在下面），
        窗口却按 860 收（命中区在上面）→ 用户得往上点约 60px 才点得到。
        这里让窗口尺寸 = 内容需要的最小尺寸，两者永远一致。
        """
        w, h = getattr(self, "_want_size", (1320, 860))
        try:
            c = getattr(self, "content", None)
            if c is not None:
                need_h = 46 + int(c.minimumSize().height()) + 6      # 46 = 标题栏
                need_w = int(c.minimumSize().width()) + 28
                w = max(int(w), need_w)
                h = max(int(h), need_h)
        except Exception as _e:
            print(f"[PortraitStudio] ⚠ 计算内容尺寸失败: {_e}")
        try:
            # 同时锁住最小尺寸：Windows 就不会把窗口缩到内容之外
            self.setMinimumSize(int(w), int(h))
        except Exception:
            pass
        return int(w), int(h)

    def _force_size(self):
        try:
            w, h = self._needed_size()
            from PyQt5.QtCore import Qt as _Qt
            self.setWindowState(self.windowState() & ~_Qt.WindowMinimized | _Qt.WindowActive)
            self.resize(w, h)
            self.show()
            self.raise_()
            self.activateWindow()
            # ⚠ 用 repaint()（同步重画）：resize 后只 update() 是异步的，
            #   用户可能先看到「旧尺寸那帧 + 新布局的命中区」→ 点击对不上。
            self.repaint()
            print(f"[PortraitStudio] 已按 {w}x{h} 重新布局（当前 {self.width()}x{self.height()}）")
        except Exception as e:
            print(f"[PortraitStudio] ⚠ 强制尺寸失败: {e}")

    # ── 子进程调用 ─────────────────────────────────────
    @staticmethod
    def _run_cli(args, timeout=90, pet_id=None):
        """跑 portrait_cli.py（**静态**方法：向导预览等地方不用实例也能调）。

        ⚠ 必须带上「要操作的角色」ID：
        以前只有 list/save 带了，合成/预览/切换显示方式都没带 → 子进程就按
        **活动角色**执行 → 「点别人的立绘工坊，看到的却是活动角色的立绘/Live2D」。
        实例内部调用请走 self._cli(...)（会自动带上本工坊的角色）。
        """
        try:
            py = _runtime_python()
            cli = os.path.join(_base_dir(), "tool", "portrait_cli.py")
            # ⚠ 子进程默认按系统编码（中文 Windows = GBK）写 stdout，
            #   父进程按 UTF-8 解码 → 表情名等中文变乱码。强制两边都用 UTF-8。
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            if pet_id:
                # 指定为哪个角色枚举/合成（不动全局活动角色）
                env["AIPET_PET_ID"] = str(pet_id)
            r = subprocess.run([py, cli] + [str(a) for a in args],
                               cwd=_base_dir(), capture_output=True,
                               encoding="utf-8", errors="replace", timeout=timeout,
                               env=env,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return (r.stdout or "").strip(), (r.stderr or "").strip()
        except Exception as e:
            return "", repr(e)

    @staticmethod
    def _result_path(out: str, since: float = 0.0) -> str:
        """从 CLI 结果里取「刚生成的那张预览图」。

        ⚠ 不能盲目取最后一行：CLI/底层库偶尔会往 stdout 打提示语
        （例如 [QQPortrait] ⚠ 合成结果为空），把提示语当路径 → 界面显示「合成失败」。
        所以两层判断：
        1) 倒着找像图片路径的行；
        2) 找不到时，看预览图的**修改时间**是否晚于本次调用（since）→ 与 stdout 噪声解耦。
        """
        try:
            lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
            for line in reversed(lines):
                low = line.lower()
                if low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    if os.path.isabs(line) and os.path.exists(line):
                        return line
                    for cand in (os.path.join(_base_dir(), "tmp", os.path.basename(line)),
                                 os.path.join(_base_dir(), os.path.basename(line))):
                        if os.path.exists(cand):
                            return cand
            if since:
                cand = os.path.join(_base_dir(), "tmp", "qq_portrait_studio.png")
                if os.path.exists(cand) and os.path.getmtime(cand) >= float(since):
                    return cand
        except Exception as _e:
            print(f"[PortraitStudio] ⚠ 结果解析失败: {_e}")
        return ""

    def _cli(self, args, timeout=90, pet_id=None):
        """实例内跑 CLI：默认带上「本工坊正在编辑的角色」"""
        if pet_id is None:
            pet_id = getattr(self, "_pet_id", None)
        return PortraitStudio._run_cli(args, timeout=timeout, pet_id=pet_id)

    def reload_for_pet(self, pet_id):
        """切换成「另一个角色」并重新加载它的素材/选项。

        ⚠ 复用同一个工坊窗口时，只改 _pet_id 是不够的：show() 对已显示的窗口不会
        再触发 showEvent → 选项不会重载 → 用户看到的是**上一个角色**的立绘/Live2D
        （反馈「点别的桌宠的立绘工坊，显示的还是活动角色的立绘」）。
        """
        try:
            self._pet_id = pet_id
            self._loaded_pet = None
            self._data = {}
            self._last_path = ""
            self._last_pixmap = None
            self._no_fg_warned = False
            try:
                from PyQt5.QtGui import QPixmap as _QP
                self.preview_lbl.setPixmap(_QP())
            except Exception:
                pass
            self.preview_lbl.setText("加载中…")
            self.status_lbl.setText("")
            for cb in list(getattr(self, "decor_boxes", [])):
                try:
                    self.g3.removeWidget(cb)
                    cb.setParent(None)
                except Exception:
                    pass
                cb.deleteLater()
            self.decor_boxes = []
            for combo in (getattr(self, "cloth_combo", None), getattr(self, "exp_combo", None),
                          getattr(self, "set_combo", None)):
                try:
                    combo.blockSignals(True)
                    combo.clear()
                    combo.blockSignals(False)
                except Exception:
                    pass
            threading.Thread(target=self._load_options, daemon=True).start()
            _studio_log(f"切换到角色 {pet_id}（重新加载选项）")
            print(f"[PortraitStudio] 已切换到角色 {pet_id} 并重新加载素材")
        except Exception as e:
            print(f"[PortraitStudio] ⚠ 切换角色失败: {e}")

    def _cli_ready(self) -> bool:
        """CLI 能不能跑（缺 runtime venv / 脚本时会给出明确提示，而不是含糊的“合成失败”）"""
        py = _runtime_python()
        if not os.path.exists(py):
            self.status_lbl.setText(
                "⚠ 这个运行环境没有 runtime venv（缺 Python），无法拼合立绘。\n"
                "用安装版，或先在项目根目录跑一次 install.bat 生成 .venv 再打开工坊。")
            print(f"[PortraitStudio] ⚠ runtime python 不存在: {py}")
            return False
        cli = os.path.join(_base_dir(), "tool", "portrait_cli.py")
        if not os.path.exists(cli):
            self.status_lbl.setText(f"⚠ 缺少合成脚本：{cli}")
            print(f"[PortraitStudio] ⚠ 缺少 portrait_cli.py: {cli}")
            return False
        return True

    def _load_options(self):
        out, err = self._cli(["list"], pet_id=getattr(self, "_pet_id", None))
        data = {}
        try:
            data = json.loads(out.splitlines()[-1]) if out else {}
        except Exception as e:
            print(f"[PortraitStudio] ⚠ 选项解析失败: {e} | err={err[:200]}")
        # 场景：新版本 CLI 的 list 里已经带上了 → 不再多起一个子进程（加载更快）
        if not (data or {}).get("scenes"):
            try:
                sout, _serr = self._cli(["scenes"], pet_id=getattr(self, "_pet_id", None))
                sdata = json.loads(sout.splitlines()[-1]) if sout else {}
                data["scenes"] = sdata.get("scenes") or []
                data["scene_dir"] = sdata.get("dir") or ""
            except Exception:
                data["scenes"] = []
        _act = str((data or {}).get("active") or "a")
        if not ((data or {}).get("clothes") or {}).get(_act):
            print("[PortraitStudio] ⚠ 活动角色没有可用的立绘素材（fgimages）")
        self.options_ready.emit(data or {})

    # ── UI ──────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout()
        self.content.addLayout(root, 1)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # 左：预览（尽量放大显示，不出现黑框）
        # 预览容器：2D 立绘用图片标签；Live2D 角色换成 OpenGL 实时预览（同一个位置切换）
        self.preview_lbl = QLabel("加载中…")
        self.preview_lbl.setAlignment(Qt.AlignCenter)
        self.preview_lbl.setMinimumSize(920, 517)
        self.preview_lbl.setStyleSheet(
            "background:#23232e; border-radius:10px; color:#9a9aa8; font-size:15px;")
        self.preview_box = QWidget()
        self._preview_stack = QStackedLayout(self.preview_box)
        self._preview_stack.setContentsMargins(0, 0, 0, 0)
        self._preview_stack.addWidget(self.preview_lbl)
        self._l2d = None
        root.addWidget(self.preview_box, 1)

        # 右：控制区
        right = QVBoxLayout()
        right.setSpacing(10)

        title = QLabel("立绘工坊")
        title.setStyleSheet("font-size:19px; font-weight:bold; color:#e8e8f0;")
        right.addWidget(title)
        self.tip_lbl = QLabel("a / b 是两套独立立绘素材，服装与装饰各自保存；\n"
                              "保存后 QQ 立绘与桌宠都用这一套。")
        self.tip_lbl.setStyleSheet("color:#9a9aa8; font-size:12px;")
        self.tip_lbl.setWordWrap(True)
        right.addWidget(self.tip_lbl)

        # 立绘类型（a / b）
        gb0 = QGroupBox("立绘类型（a / b 两套素材各自独立）")
        g0 = QVBoxLayout(gb0)
        self.set_combo = QComboBox()
        self.set_combo.setStyleSheet("padding:6px; font-size:13px;")
        self.set_combo.addItem("a 立绘（校服·多表情）", "a")
        self.set_combo.addItem("b 立绘（另一套立绘）", "b")
        self.set_combo.currentIndexChanged.connect(self._on_set_changed)
        g0.addWidget(self.set_combo)
        right.addWidget(gb0)

        # 服装
        gb1 = QGroupBox("服装")
        g1 = QVBoxLayout(gb1)
        self.cloth_combo = QComboBox()
        self.cloth_combo.setStyleSheet("padding:6px; font-size:13px;")
        self.cloth_combo.currentIndexChanged.connect(self._on_cloth_changed)
        g1.addWidget(self.cloth_combo)
        right.addWidget(gb1)

        # 动作（手臂姿势 = 素材里的「腕差分」）
        # ⚠ 这类层以前被当成「服装」列在下拉里（校服/校服·手臂替换件…），
        #   其实它们是同一件衣服的另一种手臂姿势 → 单独做成「动作」。
        self.gb_act = QGroupBox("动作（手臂姿势 · 随对话自动切换）")
        _gb_act_lay = QVBoxLayout(self.gb_act)
        self.act_combo = QComboBox()
        self.act_combo.setStyleSheet("padding:6px; font-size:13px;")
        self.act_combo.currentIndexChanged.connect(self._on_action_changed)
        _gb_act_lay.addWidget(self.act_combo)
        self._act_hint = QLabel("")
        self._act_hint.setWordWrap(True)
        self._act_hint.setStyleSheet("color:#888; font-size:11px;")
        _gb_act_lay.addWidget(self._act_hint)
        right.addWidget(self.gb_act)

        # 表情
        gb2 = QGroupBox("表情（保存后仍随对话情绪自动变化，这里用于预览）")
        g2 = QVBoxLayout(gb2)
        self.exp_combo = QComboBox()
        self.exp_combo.setStyleSheet("padding:6px; font-size:13px;")
        self.exp_combo.currentIndexChanged.connect(self._schedule)
        g2.addWidget(self.exp_combo)
        right.addWidget(gb2)

        # 装饰
        # ⚠ 装饰可能很多（例如芳乃 a 套 69 项）：以前直接堆进纵向布局 →
        #   窗口被撑到占满屏幕、内容还显示不全（要拖动窗口）。改为「固定高度 + 滚动」。
        self.gb3 = QGroupBox("附加装饰（可滚动，装饰多也不会撑大窗口）")
        _gb3_lay = QVBoxLayout(self.gb3)
        self._decor_scroll = QScrollArea()
        self._decor_scroll.setWidgetResizable(True)
        self._decor_scroll.setFrameShape(QScrollArea.NoFrame)
        self._decor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._decor_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollArea > QWidget > QWidget{background:transparent;}")
        _decor_holder = QWidget()
        self.g3 = QVBoxLayout(_decor_holder)
        self.g3.setContentsMargins(2, 2, 2, 2)
        self.g3.setSpacing(4)
        self._decor_scroll.setWidget(_decor_holder)
        try:
            self._decor_scroll.setMinimumHeight(110)
            self._decor_scroll.setMaximumHeight(180)     # 超出就在框内滚动，窗口尺寸不再变化
        except Exception:
            pass
        _gb3_lay.addWidget(self._decor_scroll)
        self.decor_boxes = []
        right.addWidget(self.gb3)

        # 场景（切换背景）
        gb4 = QGroupBox("背景场景（本地场景目录，放大裁剪不出黑边）")
        g4 = QVBoxLayout(gb4)
        self.scene_combo = QComboBox()
        self.scene_combo.setStyleSheet("padding:6px; font-size:13px;")
        self.scene_combo.addItem("🎲 随机场景", "")
        self.scene_combo.currentIndexChanged.connect(self._schedule)
        g4.addWidget(self.scene_combo)
        right.addWidget(gb4)

        right.addStretch(1)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color:#8fd18f; font-size:12px;")
        self.status_lbl.setWordWrap(True)
        right.addWidget(self.status_lbl)

        def _btn(text, slot, style=""):
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(38)
            b.setStyleSheet(style or (
                "QPushButton{background:#3a3a4a;color:#eee;border-radius:8px;font-size:13px;}"
                "QPushButton:hover{background:#4a4a5e;}"))
            b.clicked.connect(slot)
            return b

        row1 = QHBoxLayout()
        row1.addWidget(_btn("💾 保存为默认立绘", self._on_save, (
            "QPushButton{background:#c8506e;color:#fff;border-radius:8px;font-size:14px;font-weight:bold;}"
            "QPushButton:hover{background:#e0607e;}")))
        row1.addWidget(_btn("🎲 随机换装", self._on_random))
        right.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(_btn("📂 打开立绘素材位置", self._on_open_dir))
        row2.addWidget(_btn("🏞 打开场景文件夹", self._on_open_scene_dir))
        right.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(_btn("关闭", self.close))
        right.addLayout(row3)

        # ── 桌宠显示方式（2D 立绘 / Live2D 模型）——两种素材都有的角色可切换 ──
        self.gb_display = QGroupBox("桌宠显示方式（切换后重启桌宠生效）")
        gd = QVBoxLayout(self.gb_display)
        self.disp_combo = QComboBox()
        self.disp_combo.setStyleSheet("padding:6px; font-size:13px;")
        self.disp_combo.addItem("🖼 2D 立绘", "2d")
        self.disp_combo.addItem("🎭 Live2D 模型", "live2d")
        self.disp_combo.currentIndexChanged.connect(self._on_display_changed)
        gd.addWidget(self.disp_combo)
        right.addWidget(self.gb_display)

        # ── 单图模式（每个表情一张整图）：设默认表情 ──
        self.btn_def_emo = _btn("⭐ 把当前表情设为默认", self._on_set_default_emotion,
                                "QPushButton{background:#3f6f4f;color:#fff;border-radius:8px;"
                                "font-size:13px;font-weight:bold;}QPushButton:hover{background:#4f8f63;}")
        right.addWidget(self.btn_def_emo)

        holder = QWidget()
        holder.setLayout(right)
        # ⚠ 右侧控制列整体放进滚动区：装饰/表情等选项再多，也只在这条列里滚动，
        #   不会再被撑高到占满屏幕（用户反馈"拖一下窗口就变得特别大、还没法看全"）。
        self._right_scroll = QScrollArea()
        self._right_scroll.setWidgetResizable(True)
        self._right_scroll.setFrameShape(QScrollArea.NoFrame)
        self._right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._right_scroll.setWidget(holder)
        self._right_scroll.setFixedWidth(352)
        self._right_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollArea > QWidget > QWidget{background:transparent;}")
        root.addWidget(self._right_scroll)
        self._right_col = right          # 右侧控制栏（Live2D 按钮挂这里，不挤主布局）

    # ── 选项应用 ────────────────────────────────────────
    def _set_opts(self, key, set_name):
        """取某套的选项（兼容旧的单套格式）"""
        v = (self._data or {}).get(key)
        if isinstance(v, dict):
            return v.get(set_name) or []
        return v or []

    def _fill_actions(self, set_name, saved=None):
        """填「动作」下拉：当前服装的换臂姿势 + 默认姿势"""
        try:
            self.act_combo.blockSignals(True)
            self.act_combo.clear()
            cur_cid = int(self.cloth_combo.currentData() or 0)
            cur_name = str(self.cloth_combo.currentText() or "")
            acts = self._set_opts("actions", set_name)
            mine = [a for a in acts if int(a[2]) == cur_cid or not cur_cid]
            self.act_combo.addItem("（默认姿势）", 0)
            for nm, aid, base in mine:
                self.act_combo.addItem(str(nm), int(aid))
            want = str((saved or {}).get("action") or "")
            want_id = int((saved or {}).get("action_id") or 0)
            idx = 0
            for i in range(self.act_combo.count()):
                if want_id and int(self.act_combo.itemData(i) or 0) == want_id:
                    idx = i
                    break
                if want and want in self.act_combo.itemText(i):
                    idx = i
                    break
            self.act_combo.setCurrentIndex(idx)
            self.act_combo.blockSignals(False)
            if self.act_combo.count() > 1:
                self._act_hint.setText(f"「{cur_name}」有 {self.act_combo.count() - 1} 种手臂姿势；"
                                       f"桌宠会按对话情绪自动切换。")
            else:
                self._act_hint.setText("这套素材没有换臂姿势（半身立绘通常没有）。")
            self._relayout_right_col()
        except Exception as e:
            print(f"[PortraitStudio] ⚠ 填充动作失败: {e}")

    def _on_cloth_changed(self, *_):
        """换衣服：动作列表跟着换（动作是「某件衣服的手臂姿势」，不能跨衣服选）"""
        try:
            self._fill_actions(self._cur_set, {})
        except Exception:
            pass
        self._schedule()

    def _on_action_changed(self, *_):
        """换动作：立刻重排 + 重新预览"""
        try:
            self._relayout_right_col()
        except Exception:
            pass
        self._schedule()

    def _action_layer(self) -> int:
        """当前选中的动作层（0 = 默认姿势）"""
        try:
            return int(self.act_combo.currentData() or 0)
        except Exception:
            return 0

    def _saved_of(self, set_name):
        sv = (self._data or {}).get("saved") or {}
        if isinstance(sv, dict) and isinstance(sv.get(set_name), dict):
            return sv[set_name]
        if isinstance(sv, dict) and "cloth" in sv:      # 旧格式（a 套）
            return sv
        return {}

    def _apply_set_options(self, set_name):
        """按所选套装填充服装/表情/装饰下拉"""
        saved = self._saved_of(set_name)
        # 服装
        self.cloth_combo.blockSignals(True)
        self.cloth_combo.clear()
        self._clothes = self._set_opts("clothes", set_name)
        cur_idx = 0
        want_name = str(saved.get("cloth") or "")
        want_id = int(saved.get("cloth_id") or 0)
        for i, item in enumerate(self._clothes):
            name, cid = str(item[0]), int(item[1])
            self.cloth_combo.addItem(name, cid)
            if want_id and want_id == cid:
                cur_idx = i
            elif want_name and want_name == name:
                cur_idx = i
        self.cloth_combo.setCurrentIndex(cur_idx)
        self.cloth_combo.blockSignals(False)

        # 动作：只列当前这件衣服的换臂姿势（没选出服装时列全部）
        self._fill_actions(set_name, saved)

        # 表情
        self.exp_combo.blockSignals(True)
        self.exp_combo.clear()
        for item in self._set_opts("expressions", set_name):
            self.exp_combo.addItem(str(item[0]), int(item[1]))
        # 打开时优先还原「上次保存的那张表情」，其次角色自己的默认表情，
        # 都不行才退回列表第一项（往往是「泪水变体」，看着就像每次打开都换了张脸）
        _idx = -1
        _saved_emo = int((saved or {}).get("emotion") or 0)
        if _saved_emo:
            for i in range(self.exp_combo.count()):
                if int(self.exp_combo.itemData(i) or 0) == _saved_emo:
                    _idx = i
                    break
        if _idx < 0:
            _want = [str(((self._data or {}).get("portrait") or {}).get("default_emotion") or ""),
                     "平静", "普通", "基础", "平常", "微笑", "微笑 1"]
            for w in _want:
                if not w:
                    continue
                for i in range(self.exp_combo.count()):
                    txt = self.exp_combo.itemText(i)
                    if txt == w or (w.startswith("微笑") and txt.startswith("微笑")) or \
                            (w in ("基础", "平常") and txt.startswith(w)):
                        _idx = i
                        break
                if _idx >= 0:
                    break
        self.exp_combo.setCurrentIndex(_idx if _idx >= 0 else 0)
        self.exp_combo.blockSignals(False)

        # 装饰复选框
        # ⚠ 旧复选框必须「立刻」从布局里摘掉：deleteLater 是延迟的，
        #   而新复选框马上又加进同一个布局 → 新旧控件位置重叠、互相盖住
        #   → 出现「看到的是 A，点下去命中 B」的错位（切换 a/b 立绘后尤其明显）。
        for cb in list(self.decor_boxes):
            try:
                self.g3.removeWidget(cb)
                cb.setParent(None)
            except Exception:
                pass
            cb.deleteLater()
        self.decor_boxes = []
        for item in self._set_opts("decors", set_name):
            nm, did = str(item[0]), int(item[1])
            cb = QCheckBox(nm)
            cb.setProperty("layer_id", did)
            if did in (saved.get("decor") or []):
                cb.setChecked(True)
            cb.stateChanged.connect(self._schedule)
            self.g3.addWidget(cb)
            self.decor_boxes.append(cb)
        # 立刻重排分组框（否则它按旧数量留高/留窄，复选框会被裁掉 → 看着"点不到"）
        try:
            self.g3.invalidate()
            self.gb3.adjustSize()
            self.gb3.layout().activate()
            self._relayout_right_col()
        except Exception as _e:
            print(f"[PortraitStudio] ⚠ 装饰区重排失败: {_e}")

    def _relayout_right_col(self):
        """右侧控制列重排 + 清遮罩（改内容后按钮位置变了必须同步命中区域）"""
        try:
            c = getattr(self, "content", None)
            if c is not None:
                c.invalidate()
                c.activate()
            holder = None
            rc = getattr(self, "_right_col", None)
            if rc is not None:
                holder = rc.parentWidget()
            for w in (holder, getattr(self, "gb3", None), getattr(self, "gb_act", None),
                      getattr(self, "preview_box", None)):
                if w is not None:
                    w.updateGeometry()
                    w.update()
            self.clearMask()
            self.repaint()          # 同步重画：保证「画出来的」和「能点的」是同一帧
        except Exception as _e:
            print(f"[PortraitStudio] ⚠ 右侧列重排失败: {_e}")

    def _fallback_options(self) -> dict:
        """CLI 跑不起来时（缺 runtime venv / 子进程失败）直接从角色配置里取关键信息。

        ⚠ 这样界面照样能自适应：有 Live2D 模型就仍然显示「桌宠显示方式」切换，
        不会因为子进程失败而整个界面「少了一半选项」。
        """
        out = {"active": "a", "mode": "layers", "has_live2d": False, "has_fgimages": False,
               "default_display": "2d", "sets": ["a"], "live2d": {},
               "clothes": {}, "expressions": {}, "decors": {}, "scenes": [],
               "pet": {}, "portrait": {}}
        try:
            from pets.pet_registry import (get_active_pet_id, get_live2d_model_json,
                                           get_fgimages_dir, get_portrait_mode, get_pet_config)
            pid = getattr(self, "_pet_id", None) or get_active_pet_id()
            mj = ""
            try:
                mj = get_live2d_model_json(pid) or ""
            except Exception:
                pass
            fg = ""
            try:
                fg = get_fgimages_dir(pid) or ""
            except Exception:
                pass
            try:
                mode = get_portrait_mode(pid) or "layers"
            except Exception:
                mode = "layers"
            cfg = {}
            try:
                cfg = get_pet_config(pid) or {}
            except Exception:
                pass
            model = cfg.get("model") or {}
            portrait = cfg.get("portrait") or {}
            sets = model.get("fgimages_sets") or model.get("sets_available") or ["a"]
            if not isinstance(sets, (list, tuple)):
                sets = ["a"]
            out.update({
                "has_live2d": bool(mj), "has_fgimages": bool(fg), "mode": str(mode),
                "default_display": str(model.get("default")
                                       or ("live2d" if mj else "2d")).lower(),
                "sets": [str(s) for s in sets] or ["a"],
                "live2d": {"model_json": mj},
                "pet": {"id": pid, "name": cfg.get("name") or pid,
                        "display_name": cfg.get("display_name") or cfg.get("name") or pid},
                "portrait": portrait,
            })
            print(f"[PortraitStudio] 已用角色配置兜底：live2d={bool(mj)} 2d={bool(fg)} "
                  f"mode={mode} display={out['default_display']}")
        except Exception as e:
            print(f"[PortraitStudio] ⚠ 兜底读取角色配置失败: {e}")
        return out

    def _on_options(self, data):
        """选项加载完成（子进程返回）：填入套装/场景，并按角色立绘类型自适应界面"""
        try:
            if not (data or {}).get("clothes") and not (data or {}).get("live2d"):
                # 子进程没给出有效信息（缺 venv / 失败）→ 用角色配置兜底，
                # 保证「桌宠显示方式」等选项不会凭空消失
                data = self._fallback_options()
            self._data = data or {}
            sets = data.get("sets") or ["a", "b"]
            # 场景下拉：🎲 随机 + 每张场景图（按文件名）
            try:
                self.scene_combo.blockSignals(True)
                self.scene_combo.clear()
                self.scene_combo.addItem("🎲 随机场景", "")
                for sp in (data.get("scenes") or []):
                    self.scene_combo.addItem(os.path.basename(str(sp)), str(sp))
                # 打开就按「上次保存的那张场景」显示（以前默认随机 → 每次打开立绘都不一样）
                _sv = (data.get("saved") or {})
                _want_scene = ""
                for _s in (data.get("sets") or ("a", "b")):
                    _ent = _sv.get(_s) if isinstance(_sv, dict) else None
                    if isinstance(_ent, dict) and str(_ent.get("scene") or "").strip():
                        _want_scene = str(_ent["scene"]).strip()
                        break
                _si = 0
                if _want_scene:
                    _base = os.path.basename(_want_scene)
                    for i in range(self.scene_combo.count()):
                        _d = str(self.scene_combo.itemData(i) or "")
                        if _d == _want_scene or (_d and os.path.basename(_d) == _base):
                            _si = i
                            break
                elif self.scene_combo.count() > 1:
                    _si = 1          # 没存过 → 用第一张场景（固定），想随机要手动选
                self.scene_combo.setCurrentIndex(_si)
                self.scene_combo.blockSignals(False)
            except Exception:
                pass
            act = str(data.get("active") or "a").lower()
            if act not in sets:
                act = sets[0]
            self._cur_set = act
            self.set_combo.blockSignals(True)
            self.set_combo.clear()
            for s in sets:
                label = ("a 立绘（校服·多表情）" if s == "a"
                         else "b 立绘（另一套立绘）")
                self.set_combo.addItem(label, s)
            for i in range(self.set_combo.count()):
                if self.set_combo.itemData(i) == act:
                    self.set_combo.setCurrentIndex(i)
                    break
            self.set_combo.blockSignals(False)
            self._apply_set_options(act)
            self._apply_mode_ui()
            if not self._clothes and self._mode != "single":
                self.tip_lbl.setText("⚠ 未读取到立绘选项（runtime venv 或素材缺失？）")
            self._refresh_preview()
        except Exception as e:
            print(f"[PortraitStudio] ⚠ 应用选项失败: {e}")

    # ══════════ 按角色立绘类型自适应 ══════════
    def _apply_mode_ui(self):
        """三种角色三套界面：

        - layers：多图层立绘（丛雨/诺瓦）→ 服装 / 表情 / 装饰 / 场景
        - single：每个表情一张整图（新建向导创建）→ 只选表情（整图）+ 设默认表情 + 场景
        - Live2D 显示：换成 OpenGL 实时模型预览，不再有换装项
        """
        d = self._data or {}
        mode = str(d.get("mode") or "layers").lower()
        disp = str(d.get("default_display") or "2d").lower()
        self._mode = mode
        has_l2d = bool(d.get("has_live2d"))
        pet = (d.get("pet") or {})
        pname = pet.get("display_name") or pet.get("name") or pet.get("id") or "角色"
        is_l2d = (disp == "live2d" and has_l2d)
        self._is_l2d_show = is_l2d

        # 单图模式：表情下拉 = 角色自己的表情表
        if mode == "single":
            emo = (d.get("portrait") or {}).get("emotions") or {}
            dflt = str((d.get("portrait") or {}).get("default_emotion") or "")
            self.exp_combo.blockSignals(True)
            self.exp_combo.clear()
            for name, lid in emo.items():
                self.exp_combo.addItem(str(name), str(name))
            if dflt:
                i = self.exp_combo.findData(dflt)
                if i >= 0:
                    self.exp_combo.setCurrentIndex(i)
            self.exp_combo.blockSignals(False)

        # 显隐：立绘相关 / Live2D 相关
        try:
            self.gb_display.setVisible(has_l2d and bool(d.get("has_fgimages")))   # 两种素材都有才给切换
            self.btn_def_emo.setVisible(mode == "single" and not is_l2d)
            for w in (self.set_combo.parentWidget(), self.cloth_combo.parentWidget(),
                      self.gb3, getattr(self, "gb_act", None)):
                if w is not None:
                    w.setVisible(mode == "layers" and not is_l2d)
            self.exp_combo.parentWidget().setVisible(not is_l2d)
            self.scene_combo.parentWidget().setVisible(not is_l2d)
            # 单图模式下「随机换装」没意义（没有服装/装饰可随机）
            for _b in self.findChildren(QPushButton):
                if _b.text().startswith("🎲"):
                    _b.setVisible(mode == "layers" and not is_l2d)
        except Exception as e:
            print(f"[PortraitStudio] ⚠ 界面自适应失败: {e}")

        if has_l2d:
            try:
                self.disp_combo.blockSignals(True)
                self.disp_combo.setCurrentIndex(0 if disp != "live2d" else 1)
                self.disp_combo.blockSignals(False)
            except Exception:
                pass

        # 没有 Live2D 模型时把「为什么没有切换项」说清楚（免得以为功能丢了）
        _no_l2d_hint = ("" if has_l2d else
                        "\n（这个角色还没有 Live2D 模型，所以没有 2D / Live2D 切换项；"
                        "想用 Live2D 显示，请在「设置 → Live2D 模型」里给它加一个 *.model3.json）")
        if is_l2d:
            self.tip_lbl.setText(f"「{pname}」使用 Live2D 模型显示：\n"
                                 "点下面按钮在新窗口里看实时预览（和桌宠同一套渲染）。")
            self.status_lbl.setText("🎭 点「打开 Live2D 实时预览窗口」查看模型")
            try:
                from pets.pet_registry import get_live2d_model_json
                mj = get_live2d_model_json(getattr(self, "_pet_id", None)) if getattr(self, "_pet_id", None) else ""
                self._ensure_l2d_open_btn(mj)
            except Exception:
                self._ensure_l2d_open_btn()
        elif mode == "single":
            n = len((d.get("portrait") or {}).get("emotions") or {})
            self.tip_lbl.setText(f"「{pname}」的立绘是「每个表情一张整图」（共 {n} 张）：\n"
                                 "选表情即可预览；点「把当前表情设为默认」决定桌宠平时的样子。"
                                 + _no_l2d_hint)
            self._show_static_preview()
        else:
            self.tip_lbl.setText(f"「{pname}」是多图层立绘：\n"
                                 "服装与装饰各自保存，保存后 QQ 立绘与桌宠都用这一套。"
                                 + _no_l2d_hint)
            self._show_static_preview()

    def _show_static_preview(self):
        try:
            self._preview_stack.setCurrentWidget(self.preview_lbl)
        except Exception:
            pass

    def _live2d_probe_ok(self) -> bool:
        """子进程试跑 Live2D（GL 初始化在个别驱动下会把进程干掉；结果缓存 10 分钟）"""
        import time as _t
        if getattr(self, "_l2d_probe", None) is None or _t.time() - getattr(self, "_l2d_probe_ts", 0) > 600:
            ok = False
            try:
                import subprocess as _sp
                py = _runtime_python()
                code = ("import os,sys;"
                        "os.add_dll_directory(os.path.join(os.getcwd(),'Live2d'));"
                        "sys.path.insert(0,'.');"
                        "from PyQt5.QtGui import QSurfaceFormat;"
                        "from PyQt5.QtWidgets import QApplication;"
                        "f=QSurfaceFormat();f.setAlphaBufferSize(8);f.setSamples(0);"
                        "QSurfaceFormat.setDefaultFormat(f);"
                        "app=QApplication([]);"
                        "from Live2d.live2d_ui import Live2DWidget;"
                        "w=Live2DWidget();w.resize(320,420);w.show();"
                        "from PyQt5.QtCore import QTimer;QTimer.singleShot(2400,app.quit);"
                        "app.exec_();print('L2D_PROBE_OK')")
                _env = dict(os.environ)
                _env["PYTHONIOENCODING"] = "utf-8"
                r = _sp.run([py, "-c", code], cwd=_base_dir(), capture_output=True, timeout=22,
                            env=_env,
                            creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
                ok = b"L2D_PROBE_OK" in (r.stdout or b"")
            except Exception as e:
                print(f"[PortraitStudio] ⚠ Live2D 探测异常: {e}")
            self._l2d_probe = ok
            self._l2d_probe_ts = _t.time()
            print(f"[PortraitStudio] Live2D 兼容性探测: {'通过' if ok else '失败'}")
        return bool(self._l2d_probe)

    def _ensure_l2d_open_btn(self, model_json: str = ""):
        """在右侧放一个「打开 Live2D 实时预览窗口」按钮（不透明窗口里渲染，一定能显示）"""
        try:
            if getattr(self, "btn_l2d_open", None) is None:
                self.btn_l2d_open = QPushButton("🎭 打开 Live2D 实时预览窗口")
                self.btn_l2d_open.setMinimumHeight(34)
                self.btn_l2d_open.clicked.connect(
                    lambda: self._open_l2d_window(self._current_l2d_model()))
                _col = getattr(self, "_right_col", None)
                if _col is not None:
                    _col.insertWidget(max(0, _col.count() - 1), self.btn_l2d_open)
                else:
                    self.btn_l2d_open.setParent(self)
                    self.btn_l2d_open.show()
            self._btn_model_json = model_json
        except Exception as e:
            print(f"[PortraitStudio] ⚠ Live2D 按钮挂载失败: {e}")

    def _current_l2d_model(self) -> str:
        try:
            return str(((self._data or {}).get("live2d") or {}).get("model_json") or "")
        except Exception:
            return ""

    def _open_l2d_window(self, model_json: str = ""):
        try:
            from .live2d_preview import open_live2d_window
            mj = model_json or self._current_l2d_model()
            if not mj:
                self.status_lbl.setText("⚠ 该角色没有可用的 Live2D 模型文件")
                return
            w = open_live2d_window(mj, None)
            self.status_lbl.setText("🎭 已在新窗口打开 Live2D 实时预览（可拖动模型 / 缩放窗口）"
                                    if w else "⚠ 打开 Live2D 预览窗口失败（看日志）")
        except Exception as e:
            self.status_lbl.setText(f"⚠ 打开失败：{e}")

    def _model_texture_pixmap(self, model_json: str):
        """把 Live2D 模型目录里的贴图（texture *.png）拼成一张静态预览图。

        这样在这类「GL 初始化会崩」的机器上也能看到模型长什么样（不依赖 OpenGL）。"""
        try:
            import glob
            d = os.path.dirname(str(model_json))
            cands = []
            for pat in ("**/*.png", "**/*.jpg"):
                cands += glob.glob(os.path.join(d, pat), recursive=True)
            # 排除很小的图标/表情图，优先最大的几张（贴图通常最大）
            cands = [p_ for p_ in cands if os.path.getsize(p_) > 20 * 1024]
            cands.sort(key=lambda p_: -os.path.getsize(p_))
            if not cands:
                return None
            pm = QPixmap(cands[0])
            return pm if not pm.isNull() else None
        except Exception as e:
            print(f"[PortraitStudio] ⚠ 读取模型贴图失败: {e}")
            return None

    def _force_l2d(self):
        """用户主动要求：跳过自检直接加载 Live2D 预览"""
        try:
            self._l2d_force = True
            w = self._ensure_l2d_preview()
            self.status_lbl.setText("🎭 Live2D 预览已强制加载" if w else "⚠ 强制加载失败（看日志）")
        except Exception as e:
            self.status_lbl.setText(f"⚠ 强制加载失败：{e}")

    def _ensure_l2d_preview(self):
        """Live2D 实时预览（懒创建：只有 Live2D 角色才需要 OpenGL）"""
        if self._l2d is not None:
            try:
                self._preview_stack.setCurrentWidget(self._l2d)
                return self._l2d
            except Exception:
                return self._l2d
        try:
            from .live2d_preview import Live2DPreviewWidget
            mj = str(((self._data or {}).get("live2d") or {}).get("model_json") or "")
            if not mj:
                self.status_lbl.setText("⚠ 该角色没有可用的 Live2D 模型文件")
                return None
            # ⚠ 个别显卡驱动下 Live2D 的 GL 初始化会直接终止进程 → 先子进程试跑一次，
            #   失败就不在这里加载（否则会把整个启动器带崩）
            if not getattr(self, "_l2d_force", False):
                self.status_lbl.setText("⚠ Live2D 自检未通过（部分显卡驱动会崩，故默认跳过）。"
                                        "可点下面按钮强制试一次。")
                # 用「模型贴图」当预览（不需要 GL，任何机器都能显示）
                try:
                    img = self._model_texture_pixmap(mj)
                    if img is not None and not img.isNull():
                        self.preview_lbl.setPixmap(img.scaled(
                            self.preview_lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        self.preview_lbl.setText("")
                        self.status_lbl.setText("🖼 这是模型的贴图预览（静态，任何机器都能显示）。"
                                                "想看实时动起来，点「🎭 打开 Live2D 实时预览窗口」。")
                    else:
                        self.preview_lbl.setText("Live2D 预览不可用（驱动兼容问题）")
                except Exception as _e:
                    print(f"[PortraitStudio] ⚠ 贴图预览失败: {_e}")
                self._ensure_l2d_open_btn(mj)
                return None
            # ⚠ 关键：QOpenGLWidget 放在「透明窗口」里渲染不出来（旧版启动器是普通
            #   窗口所以正常）。预览 Live2D 时临时关掉窗口透明，退出预览再恢复。
            try:
                self.setAttribute(Qt.WA_TranslucentBackground, False)
                self.setStyleSheet("QDialog{background:#1e1e26;}")
                print("[PortraitStudio] 已切换为不透明窗口以渲染 Live2D")
            except Exception as _e:
                print(f"[PortraitStudio] ⚠ 关闭窗口透明失败: {_e}")
            w = Live2DPreviewWidget(mj, self.preview_box)
            self._l2d = w
            self._preview_stack.addWidget(w)
            self._preview_stack.setCurrentWidget(w)
            _studio_log(f"Live2D 预览已加载: {mj}")
            return w
        except Exception as e:
            print(f"[PortraitStudio] ⚠ Live2D 预览创建失败: {e}")
            self.status_lbl.setText(f"⚠ Live2D 预览失败：{e}")
            return None

    def _on_display_changed(self, *_):
        """切换桌宠显示方式（2D 立绘 / Live2D）→ 写 pet.json"""
        try:
            want = str(self.disp_combo.currentData() or "2d")
            out, err = self._cli(["set_display", want], timeout=30,
                                     pet_id=getattr(self, "_pet_id", None))
            ok = "OK" in (out or "")
            if ok:
                if self._data is not None:
                    self._data["default_display"] = want
                self.status_lbl.setText(
                    f"✅ 桌宠显示方式已切换为 {'Live2D 模型' if want == 'live2d' else '2D 立绘'}"
                    f"（重启桌宠生效）")
                self._apply_mode_ui()
            else:
                self.status_lbl.setText(f"⚠ 切换失败：{(out or err)[:120]}")
        except Exception as e:
            self.status_lbl.setText(f"⚠ 切换失败：{e}")

    def _on_set_default_emotion(self):
        """单图模式：把当前预览的表情设为角色默认表情（桌宠平时/搭话时显示的那张）"""
        try:
            emo = str(self.exp_combo.currentText() or "").strip()
            if not emo:
                return
            out, err = self._cli(["set_emotion", emo], timeout=30,
                                     pet_id=getattr(self, "_pet_id", None))
            if "OK" in (out or ""):
                if self._data is not None:
                    (self._data.setdefault("portrait", {}))["default_emotion"] = emo
                self.status_lbl.setText(f"✅ 默认表情已设为「{emo}」（重启桌宠生效）")
            else:
                self.status_lbl.setText(f"⚠ 设置失败：{(out or err)[:120]}")
        except Exception as e:
            self.status_lbl.setText(f"⚠ 设置失败：{e}")

    def _on_set_changed(self, *_):
        """切换立绘类型：重填选项 + 重新预览"""
        try:
            s = str(self.set_combo.currentData() or "a")
            self._cur_set = s
            self._apply_set_options(s)
            self.status_lbl.setText(f"当前预览：{s} 立绘")
            self._schedule()
        except Exception as e:
            print(f"[PortraitStudio] ⚠ 切换立绘类型失败: {e}")

    # ── 预览刷新（防抖 + 子进程合成）─────────────────
    def _schedule(self, *_):
        # 单图模式没有服装下拉 → 不能只看 cloth_combo 是否有内容
        if self.cloth_combo.count() or self._mode == "single":
            self._debounce.start(180)

    def _current(self):
        cloth = int(self.cloth_combo.currentData() or 1952)
        expr = int(self.exp_combo.currentData() or 1292)
        # 发型要按「服装层」查（动作层是换臂姿势，不在服装表里）——查错会拿到别的角色的发型
        hair = 0
        for item in getattr(self, "_clothes", []):
            if int(item[1]) == cloth:
                hair = int(item[2])
                break
        act = self._action_layer()
        if act:                      # 选了换臂姿势 → 用动作层当身体层
            cloth = act
        decors = [int(cb.property("layer_id")) for cb in self.decor_boxes if cb.isChecked()]
        try:
            scene = str(self.scene_combo.currentData() or "")
        except Exception:
            scene = ""
        return self._cur_set, cloth, hair, expr, decors, scene

    def _refresh_preview(self):
        # Live2D 角色：预览由 OpenGL 控件自己渲染，不走图片合成
        if getattr(self, "_is_l2d_show", False) and self._l2d is not None:
            return
        if self._busy:
            self._pending = True
            return
        # 环境自检：缺 runtime venv / 脚本时直接说清楚（否则只会看到含糊的“合成失败”）
        if not self._cli_ready():
            return
        if self._mode == "single":
            # 单图模式：一张整图就是一个完整立绘 → 用 preview_single 走 QQ 立绘同款合成
            emo = str(self.exp_combo.currentText() or "").strip()
            try:
                scene = str(self.scene_combo.currentData() or "")
            except Exception:
                scene = ""
            if not emo:
                self.status_lbl.setText("⚠ 这个角色还没有「每个表情一张整图」的表情素材：\n"
                                        "请在「设置 → 立绘素材」里添加表情图，保存后再回来预览。")
                return
            args = ["preview_single", emo, scene or ""]
        else:
            if not self.cloth_combo.count():
                # 以前这里直接 return → 界面停在“加载中…”什么都不说，像是坏了
                self.status_lbl.setText(
                    "⚠ 这个角色还没有可用的 2D 立绘素材（没有服装/图层选项），所以合成不出来。\n"
                    "· 想用 2D 显示：在「设置 → 立绘素材」里添加素材；\n"
                    "· 想用 Live2D 显示：在「设置 → Live2D 模型」里选一个 *.model3.json。")
                self.preview_lbl.setText("暂无 2D 立绘素材")
                return
            set_name, cloth, hair, expr, decors, scene = self._current()
            args = ["compose", set_name, cloth, hair, expr,
                    ",".join(str(d) for d in decors), "qq_portrait_studio.png", scene or ""]
        self._busy = True

        def _work():
            import time as _t
            t0 = _t.time()
            out, err = self._cli(args, pet_id=getattr(self, "_pet_id", None))
            path = self._result_path(out, since=t0)
            # 失败自动重试一次（偶发：预览图被占用 / 杀软扫描 / 目录刚创建）
            if not path and not getattr(self, "_no_fg_warned", False):
                # 没有 2D 立绘素材的角色（纯 Live2D）→ 明确说明，免得以为是 bug
                try:
                    from pets.pet_registry import get_fgimages_dir
                    if self._pet_id and not get_fgimages_dir(self._pet_id):
                        self._no_fg_warned = True
                        self.status_lbl.setText(
                            "⚠ 这个角色没有 2D 立绘素材（纯 Live2D 角色），无法拼合立绘。\n"
                            "想改它的显示：用上面的「桌宠显示方式」，或点「🎭 打开 Live2D 实时预览窗口」。")
                        print("[PortraitStudio] 该角色无 2D 立绘素材 → 不合成")
                        self.preview_ready.emit("")
                        self._busy = False
                        return
                except Exception:
                    pass
            if not path:
                _studio_log(f"合成失败(第1次) args={args} err={err[:400]}")
                _t.sleep(0.6)
                t1 = _t.time()
                out, err = self._cli(args, pet_id=getattr(self, "_pet_id", None))
                path = self._result_path(out, since=t1)
            if path:
                _studio_log(f"合成成功 args={args} → {path}")
            else:
                _studio_log(f"合成失败(重试后仍失败) err={err[:400]}")
                print(f"[PortraitStudio] ⚠ 合成失败: {err[:300]}")
            self.preview_ready.emit(path or "")
            self._busy = False

        threading.Thread(target=_work, daemon=True).start()

    def _show_pixmap(self):
        # 调参时保留上一帧（等新图回来再替换）→ 滑块拖动不闪、不空白
        try:
            if self._last_pixmap and not self._last_pixmap.isNull():
                self.preview_lbl.setPixmap(self._last_pixmap.scaled(
                    self.preview_lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            pass

    def _on_preview(self, path):
        try:
            if path and os.path.exists(path):
                self._last_path = path
                pm = QPixmap(path)
                if not pm.isNull():
                    self._last_pixmap = pm
                    self._show_pixmap()
                    return
            # 失败 → 状态栏给出可操作的原因（素材缺失 / 文件占用 / 角色无立绘…）
            try:
                logf = os.path.join(_base_dir(), "tmp", "portrait_studio.log")
                tail = ""
                if os.path.exists(logf):
                    with open(logf, encoding="utf-8", errors="replace") as f:
                        tail = f.read()[-400:]
                if "No such file" in tail or "未找到" in tail:
                    hint = "素材文件缺失：请检查 pets/<角色>/fgimages 是否完整"
                elif "Permission" in tail or "denied" in tail:
                    hint = "预览图被占用：关掉图片查看器/资源管理器预览后重试"
                else:
                    hint = "请查看 tmp/portrait_studio.log 末尾的原因"
                self.status_lbl.setText(f"❌ 合成失败 —— {hint}")
            except Exception:
                self.status_lbl.setText("合成失败（素材缺失？）")
            self.preview_lbl.setText("合成失败")
        except Exception:
            pass
        finally:
            if self._pending:
                self._pending = False
                QTimer.singleShot(80, self._refresh_preview)

    def showEvent(self, event):
        """窗口真正显示后再强制尺寸 + 重新拉选项。

        ⚠ 之前只在 __init__ 里 resize，但那一刻窗口还没 show → Qt 显示时按旧尺寸布局，
        于是表现为「要拖动一下窗口才变大」。
        """
        try:
            w, h = self._needed_size()
            self.resize(w, h)
            self._resync_input()
            from PyQt5.QtCore import QTimer as _QT
            try:
                from . import safety as _safety
                _cb = _safety.guard(self._resync_input, "studio.resync_input(定时)")
            except Exception:
                _cb = self._resync_input
            _QT.singleShot(0, _cb)
            _QT.singleShot(120, _cb)
        except Exception as _e:
            print(f"[PortraitStudio] ⚠ showEvent 尺寸失败: {_e}")
        super().showEvent(event)

    def _resync_input(self):
        """窗口尺寸/透明度变化后重排布局并清掉残留遮罩。

        ⚠ 无边框窗口在 resize 或切换 WA_TranslucentBackground 之后，可能留着旧的
        窗口遮罩/区域 → 表现为「按钮点了没反应，要往上/往旁边偏一点才点得到」。"""
        try:
            w, h = self._needed_size()
            self.resize(w, h)
            try:
                self.clearMask()
            except Exception:
                pass
            try:
                self.layout().activate()
            except Exception:
                pass
            c = getattr(self, "content", None)
            if c is not None:
                try:
                    c.invalidate()
                    c.updateGeometry()
                except Exception:
                    pass
            try:
                from . import silicon_ui as _sui
                _sui.apply_round_corners(self)
            except Exception:
                pass
            self.update()
        except Exception as _e:
            print(f"[PortraitStudio] ⚠ 重排/清遮罩失败: {_e}")

        try:
            from pets.pet_registry import get_active_pet_id
            act = get_active_pet_id()
            prev = getattr(self, "_loaded_pet", None)
            self._loaded_pet = act
            if prev != act or not getattr(self, "_data", None):
                _studio_log(f"重新加载选项（活动角色 {prev} → {act}）")
                threading.Thread(target=self._load_options, daemon=True).start()
        except Exception as e:
            _studio_log(f"showEvent 加载选项异常: {e!r}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._show_pixmap()

    # ── 动作 ────────────────────────────────────────────
    def _on_save(self):
        # 单图模式：没有服装可存，「保存」= 记住当前表情为默认表情
        if getattr(self, "_mode", "layers") == "single":
            self._on_set_default_emotion()
            return
        if getattr(self, "_is_l2d_show", False):
            # 纯 Live2D 角色没有 2D 立绘可存；丛雨这种「Live2D + 2D 都有」的要继续存 2D 装扮
            _has2d = False
            try:
                from pets.pet_registry import get_fgimages_dir
                _has2d = bool(self._pet_id and get_fgimages_dir(self._pet_id))
            except Exception:
                _has2d = False
            if not _has2d:
                self.status_lbl.setText("ℹ Live2D 角色不需要保存立绘装扮")
                return
        try:
            set_name, cloth, _hair, _expr, decors, _scene = self._current()
            name = self.cloth_combo.currentText()
            act_name = ""
            if self._action_layer():
                act_name = str(self.act_combo.currentText() or "")
            _scene = str(self.scene_combo.currentData() or "")
            _emo = int(self.exp_combo.currentData() or 0)
            out, err = self._cli(["save", set_name, name,
                                      ",".join(str(d) for d in decors),
                                      act_name or "-", _scene,
                                      str(_emo) if _emo else "-"],
                                     pet_id=getattr(self, "_pet_id", None))
            ok = (out.splitlines()[-1].strip() == "OK") if out else False
            if ok:
                if isinstance(self._data.get("saved"), dict):
                    self._data["saved"][set_name] = {
                        "cloth": name, "cloth_id": cloth, "decor": decors,
                        "action": act_name, "scene": _scene, "emotion": _emo}
                self._data["active"] = set_name
                _pose = act_name.split("（", 1)[1].rstrip("）") if "（" in act_name else act_name
                _msg = (f"✅ 已保存 {set_name} 立绘（{name}"
                        f"{'·' + _pose if _pose else '·默认姿势'}）——QQ 与桌宠都将使用该套装扮")
                self.status_lbl.setText(_msg)
                # 排队的刷新可能紧接着改写状态栏（Live2D 贴图提示等）→ 延迟再写一次，保证看得见
                QTimer.singleShot(600, lambda m=_msg: self.status_lbl.setText(m))
            else:
                self.status_lbl.setText(f"❌ 保存失败 {err[:80]}")
        except Exception as e:
            self.status_lbl.setText(f"❌ 保存失败: {e}")

    def _on_random(self):
        import random as _rnd
        try:
            if self.cloth_combo.count():
                self.cloth_combo.setCurrentIndex(_rnd.randrange(self.cloth_combo.count()))
            if self.exp_combo.count():
                self.exp_combo.setCurrentIndex(_rnd.randrange(self.exp_combo.count()))
            for cb in self.decor_boxes:
                cb.setChecked(_rnd.random() < 0.5)
        except Exception:
            pass

    def _on_open_dir(self):
        try:
            from pets.pet_registry import get_fgimages_dir
            d = get_fgimages_dir()
            if d and os.path.isdir(d):
                import subprocess as _sp
                _sp.Popen(["explorer", os.path.normpath(d)],
                          creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
        except Exception as e:
            print(f"[PortraitStudio] ⚠ 打开素材目录失败: {e}")

    def _on_open_scene_dir(self):
        """打开场景素材文件夹（立绘背景从这里取图：项目内「场景素材」）"""
        try:
            import json as _json
            d = os.path.join(_base_dir(), "场景素材")
            try:
                cfg = _json.load(open(os.path.join(_base_dir(), "config.json"), encoding="utf-8"))
                pd = str(cfg.get("portrait_scene_dir") or "").strip()
                if pd and os.path.isdir(pd):
                    d = pd
            except Exception:
                pass
            if not os.path.isdir(d):
                try:
                    os.makedirs(d, exist_ok=True)
                except Exception:
                    pass
            if os.path.isdir(d):
                import subprocess as _sp
                _sp.Popen(["explorer", os.path.normpath(d)],
                          creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
                try:
                    self.status_lbl.setText("🏞 已打开场景素材文件夹（放图片进去即可用于立绘背景）")
                except Exception:
                    pass
            else:
                self.status_lbl.setText(f"场景目录不存在：{d}（可在 config.json 设 portrait_scene_dir）")
        except Exception as e:
            print(f"[PortraitStudio] ⚠ 打开场景目录失败: {e}")
