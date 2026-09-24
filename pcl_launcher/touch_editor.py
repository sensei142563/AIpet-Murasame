# -*- coding: utf-8 -*-
"""触摸区域编辑器 —— 在立绘上直接拖动 / 缩放「头 / 胸口 / 小腹 / 下体 / 大腿 /
小腿 / 脚 / 胳膊 / 手掌」的可触碰范围。

两种模式（按角色当前的显示方式自动选，也可手动切）：
- 2D：左侧显示拼合好的立绘（与桌宠同款合成），框画在图上；
- Live2D：按要求把框**画在 Live2D 实时预览窗口的上面**（半透明覆盖层），
  这样能一边看模型一边调框的位置大小。

坐标约定：归一化 0~1（相对立绘显示区），与桌宠运行时完全一致
（`tool/touch_areas.py`），所以编辑器里看到的位置就是桌宠身上生效的位置。
"""
import os
import sys

from PyQt5.QtCore import Qt, QRectF, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap, QFont
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGroupBox,
                             QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tool.touch_areas import (AREAS, AREA_KEYS, defaults as touch_defaults,  # noqa: E402
                              labels as touch_labels, get_pet_areas, touch_enabled,
                              save_pet_areas, norm_rect,
                              add_pet_area, remove_pet_area, custom_keys, get_disabled,
                              LABELS as LABELS_DEFAULT)
# 统一的主题输入框（替掉 QInputDialog.getText）
from .silicon_dialog import ask_text      # noqa: E402
# 文字色取主题（写死的 #e8e8f0 / #9a9aa8 是深色 UI 老值，浅色主题下看不清）
from .colors import Color1, Gray2, ok_text   # noqa: E402

HANDLE = 9            # 边缘/角命中半径（像素）
MIN_NORM = 0.02       # 最小归一化宽高（防止拖没了）


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ══════════════════════ 区域覆盖层（可拖动 / 缩放）══════════════════════
class RegionOverlay(QWidget):
    """半透明覆盖层：画所有区域框，支持选中 / 拖动 / 八向缩放。

    可以直接作为普通控件用（2D 模式，自带立绘背景），也可以挂到 Live2D 预览窗口
    上（此时背景透明，框叠在模型之上）。
    """

    changed = pyqtSignal()          # 任意区域被改动（用于实时回写）
    selected = pyqtSignal(str)      # 当前选中的区域键

    def __init__(self, parent=None, transparent_bg=False):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.areas = touch_defaults()
        self.labels = touch_labels()
        self.current = AREA_KEYS[0]
        self._bg = None                 # QPixmap（2D 模式）
        self._hint = ""                 # 空底图时的提示文字
        self.disabled = set()           # 被禁用的部位（不画、不可拖）
        self._transparent = bool(transparent_bg)
        self._mode = ""                 # ""=无操作 / "move" / "resize"
        self._edge = ""
        self._press = None
        self._orig = None
        if self._transparent:
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self._hint = "框显示在 Live2D 预览窗口上 →"
        self.setMinimumSize(320, 240)

    # ── 数据 ──
    def set_areas(self, areas: dict, current: str = None):
        self.areas = {k: norm_rect(v, touch_defaults().get(k)) for k, v in (areas or {}).items()}
        for k, v in touch_defaults().items():
            self.areas.setdefault(k, v)
        if current:
            self.current = current
        self.update()

    def areas_dict(self) -> dict:
        return {k: list(v) for k, v in self.areas.items()}

    def set_background(self, pm):
        self._bg = pm
        self.update()

    # ── 坐标换算：归一化 ↔ 本地像素（保持基图宽高比，避免框被拉伸）──
    def _view_rect(self) -> QRectF:
        """真正用来装立绘/模型的矩形（居中、按宽高比适配）"""
        w, h = max(1, self.width()), max(1, self.height())
        if self._bg is not None and not self._bg.isNull():
            iw, ih = self._bg.width(), self._bg.height()
            if iw > 0 and ih > 0:
                s = min(w / iw, h / ih)
                vw, vh = iw * s, ih * s
                return QRectF((w - vw) / 2.0, (h - vh) / 2.0, vw, vh)
        return QRectF(0, 0, w, h)

    def _to_px(self, rect) -> QRectF:
        v = self._view_rect()
        x, y, w, h = [float(t) for t in rect[:4]]
        return QRectF(v.x() + x * v.width(), v.y() + y * v.height(),
                      w * v.width(), h * v.height())

    def _to_norm(self, px_rect) -> list:
        v = self._view_rect()
        return norm_rect([(px_rect.x() - v.x()) / max(1.0, v.width()),
                          (px_rect.y() - v.y()) / max(1.0, v.height()),
                          px_rect.width() / max(1.0, v.width()),
                          px_rect.height() / max(1.0, v.height())])

    def _hit(self, pos):
        """返回 (区域键, 边/角) —— 先看当前区域的八个手柄，再看其它区域内部"""
        for key, edge in self._handles():
            if edge:
                pass
        for key, rect in self._visible_rects():
            px = self._to_px(rect)
            hx, hy = HANDLE / 2.0, HANDLE / 2.0
            corners = {"nw": (px.left(), px.top()), "ne": (px.right(), px.top()),
                       "sw": (px.left(), px.bottom()), "se": (px.right(), px.bottom())}
            for name, (cx, cy) in corners.items():
                if abs(pos.x() - cx) <= hx and abs(pos.y() - cy) <= hy:
                    return key, name
            if abs(pos.y() - px.top()) <= hy and px.left() - hx <= pos.x() <= px.right() + hx:
                return key, "n"
            if abs(pos.y() - px.bottom()) <= hy and px.left() - hx <= pos.x() <= px.right() + hx:
                return key, "s"
            if abs(pos.x() - px.left()) <= hx and px.top() - hy <= pos.y() <= px.bottom() + hy:
                return key, "w"
            if abs(pos.x() - px.right()) <= hx and px.top() - hy <= pos.y() <= px.bottom() + hy:
                return key, "e"
        for key, rect in self._visible_rects():
            if self._to_px(rect).contains(pos):
                return key, ""       # 内部 = 移动
        return "", ""

    def _handles(self):
        return []

    def _visible_rects(self):
        """当前区域排前面（便于优先命中）；已禁用的部位不参与拖动/命中"""
        dis = set(getattr(self, "disabled", set()) or set())
        items = [(self.current, self.areas.get(self.current))]
        for k, v in self.areas.items():
            if k != self.current:
                items.append((k, v))
        return [(k, v) for k, v in items if v and k not in dis]

    # ── 鼠标 ──
    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        key, edge = self._hit(e.pos())
        if not key:
            return
        self.current = key
        self.selected.emit(key)
        self._mode = "resize" if edge else "move"
        self._edge = edge
        self._press = e.pos()
        self._orig = list(self.areas.get(key) or [0, 0, 0.2, 0.1])
        self.setCursor(Qt.ClosedHandCursor if not edge else Qt.SizeFDiagCursor)
        self.update()

    def mouseMoveEvent(self, e):
        if self._mode and self._press is not None:
            v = self._view_rect()
            dxn = (e.x() - self._press.x()) / max(1.0, v.width())
            dyn = (e.y() - self._press.y()) / max(1.0, v.height())
            x, y, w, h = self._orig
            if self._mode == "move":
                x = min(max(0.0, x + dxn), 1.0 - w)
                y = min(max(0.0, y + dyn), 1.0 - h)
            else:
                if "w" in self._edge:
                    nx = min(max(0.0, x + dxn), x + w - MIN_NORM)
                    w += (x - nx); x = nx
                if "e" in self._edge:
                    w = min(max(MIN_NORM, w + dxn), 1.0 - x)
                if "n" in self._edge:
                    ny = min(max(0.0, y + dyn), y + h - MIN_NORM)
                    h += (y - ny); y = ny
                if "s" in self._edge:
                    h = min(max(MIN_NORM, h + dyn), 1.0 - y)
            self.areas[self.current] = norm_rect([x, y, w, h], self._orig)
            self.changed.emit()
            self.update()
            return
        # 悬停光标反馈
        key, edge = self._hit(e.pos())
        if edge in ("nw", "se"):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edge in ("ne", "sw"):
            self.setCursor(Qt.SizeBDiagCursor)
        elif edge in ("n", "s"):
            self.setCursor(Qt.SizeVerCursor)
        elif edge in ("e", "w"):
            self.setCursor(Qt.SizeHorCursor)
        elif key:
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if self._mode:
            self._mode = ""
            self._edge = ""
            self._press = None
            self._orig = None
            self.changed.emit()
            self.update()

    # ── 绘制 ──
    def paintEvent(self, e):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            if not self._transparent:
                p.fillRect(self.rect(), QColor(24, 24, 30))
            v = self._view_rect()
            if self._bg is not None and not self._bg.isNull():
                p.drawPixmap(v.toRect(), self._bg)
            elif not self._transparent:
                p.setPen(QColor(150, 150, 160))
                f = QFont(); f.setPointSize(11); p.setFont(f)
                p.drawText(self.rect(), Qt.AlignCenter,
                           self._hint or "（没有可显示的立绘，框仍可拖动调整）")

            for key, rect in self._visible_rects():
                px = self._to_px(rect)
                cur = (key == self.current)
                p.setPen(QPen(QColor(255, 90, 140) if cur else QColor(90, 170, 255),
                              2 if cur else 1))
                p.setBrush(QColor(255, 90, 140, 46) if cur else QColor(90, 170, 255, 26))
                p.drawRect(px)
                if cur:
                    # 八个缩放点
                    for c in (px.topLeft(), px.topRight(), px.bottomLeft(), px.bottomRight()):
                        p.setBrush(QColor(255, 255, 255))
                        p.drawRect(QRectF(c.x() - 4, c.y() - 4, 8, 8))
                f = QFont(); f.setPointSize(9 if not cur else 10); p.setFont(f)
                p.setPen(QColor(255, 255, 255) if cur else QColor(220, 230, 255))
                p.drawText(px.adjusted(3, -14, 0, 0), Qt.AlignLeft | Qt.AlignBottom,
                           self.labels.get(key, key))
            p.end()
        except Exception as _e:
            print(f"[TouchEditor] ⚠ 绘制失败: {_e}")


# ══════════════════════ Live2D 预览窗口上的完整调节面板 ══════════════════════
class TouchControlPanel(QFrame):
    """在 Live2D 预览窗口里就能调：部位选择 / 增删 / 禁用 / 精确数值 / 保存。

    以前 Live2D 上只叠了「框」，改数值或增删部位得回编辑器窗口（看不到模型，调不准）。
    现在整块面板挂在预览窗口右侧，边看模型边调，数据只属于 Live2D 这一套。
    """

    def __init__(self, pet_id, overlay, parent=None, mode="live2d"):
        super().__init__(parent)
        self.pet_id = pet_id
        self.overlay = overlay
        self.mode = mode
        self._disabled = set(get_disabled(pet_id, mode))
        self.setFixedWidth(400)
        self.setStyleSheet("QFrame{background:rgba(18,18,24,238);border-radius:10px;}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        t = QLabel("Live2D 身体部位调节")
        t.setStyleSheet("font-size:15px;font-weight:bold;color:#e8e8f0;")
        lay.addWidget(t)
        tip = QLabel("· 拖框 = 移动，拖边/角 = 缩放；数值框可精确调\n"
                     "· 默认部位不能删但可以「🚫 禁用」（立绘上没这个部位时用）\n"
                     "· 这里的范围只属于 Live2D，和 2D 那套互不影响")
        tip.setStyleSheet("color:#9a9aa8;font-size:11px;")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        self.cmb_area = QComboBox()
        self.cmb_area.currentIndexChanged.connect(self._on_area)
        lay.addWidget(self.cmb_area)

        row = QHBoxLayout()
        b_add = QPushButton("添加")
        b_add.clicked.connect(self._add)
        row.addWidget(b_add)
        b_del = QPushButton("删除")
        b_del.clicked.connect(self._del)
        row.addWidget(b_del)
        self.btn_dis = QPushButton("禁用")
        self.btn_dis.clicked.connect(self._toggle_disabled)
        row.addWidget(self.btn_dis)
        lay.addLayout(row)

        self.spins = {}
        for key, lab in (("x", "左 X"), ("y", "上 Y"), ("w", "宽 W"), ("h", "高 H")):
            r = QHBoxLayout()
            r.addWidget(QLabel(lab))
            sp = QDoubleSpinBox()
            sp.setRange(0.0, 1.0)
            sp.setSingleStep(0.005)
            sp.setDecimals(3)
            sp.valueChanged.connect(self._on_spin)
            r.addWidget(sp)
            self.spins[key] = sp
            lay.addLayout(r)

        row2 = QHBoxLayout()
        b_reset = QPushButton("恢复默认")
        b_reset.clicked.connect(self._reset)
        row2.addWidget(b_reset)
        row2.addStretch()
        lay.addLayout(row2)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#8fd18f;font-size:11px;")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        b_save = QPushButton("保存到角色")
        b_save.setStyleSheet("QPushButton{background:#c8506e;color:#fff;border-radius:8px;"
                             "font-size:14px;font-weight:bold;padding:8px;}")
        b_save.clicked.connect(lambda: self._save())
        lay.addWidget(b_save)
        lay.addStretch(1)

        try:
            self.overlay.changed.connect(self._sync)
            self.overlay.selected.connect(self._on_selected)
        except Exception:
            pass
        self._rebuild()

    def _rebuild(self, keep=""):
        try:
            keep = keep or (self.cmb_area.currentData() if self.cmb_area.count() else "")
            labs = touch_labels(self.pet_id)
            self.cmb_area.blockSignals(True)
            self.cmb_area.clear()
            for k, _n, _d, _a, _b in AREAS:
                self.cmb_area.addItem(("（已禁用）" if k in self._disabled else "") + labs.get(k, k), k)
            for k in custom_keys(self.pet_id):
                self.cmb_area.addItem((""if k in self._disabled else "") + labs.get(k, k), k)
            i = self.cmb_area.findData(keep) if keep else -1
            self.cmb_area.setCurrentIndex(i if i >= 0 else 0)
            self.cmb_area.blockSignals(False)
            self.overlay.disabled = set(self._disabled)
            self._on_area()
        except Exception as e:
            print("[TouchPanel] 重建部位列表失败:", e)

    def _on_area(self, *_):
        key = self.cmb_area.currentData()
        self.overlay.current = key
        self.overlay.update()
        self.btn_dis.setText("启用该部位"if key in self._disabled else "禁用该部位")
        self._sync()

    def _on_selected(self, key):
        i = self.cmb_area.findData(key)
        if i >= 0 and i != self.cmb_area.currentIndex():
            self.cmb_area.blockSignals(True)
            self.cmb_area.setCurrentIndex(i)
            self.cmb_area.blockSignals(False)

    def _sync(self):
        r = self.overlay.areas.get(self.overlay.current) or [0, 0, 0.2, 0.1]
        vals = {"x": r[0], "y": r[1], "w": r[2], "h": r[3]}
        for k, sp in self.spins.items():
            sp.blockSignals(True)
            sp.setValue(float(vals[k]))
            sp.blockSignals(False)

    def _on_spin(self, *_):
        key = self.overlay.current
        self.overlay.areas[key] = norm_rect(
            [self.spins["x"].value(), self.spins["y"].value(),
             self.spins["w"].value(), self.spins["h"].value()],
            self.overlay.areas.get(key))
        self.overlay.update()

    def _reset(self):
        self.overlay.set_areas(touch_defaults(), self.overlay.current)
        self._sync()
        self.status.setText("已恢复默认（记得保存）")

    def _add(self):
        try:
            name, okk = ask_text(self, "添加部位", "部位名字", placeholder="例如：尾巴 / 耳朵 / 角")
            if not okk or not str(name).strip():
                return
            key = add_pet_area(self.pet_id, str(name).strip())
            if not key:
                self.status.setText("添加失败")
                return
            self.overlay.areas[key] = list(touch_defaults().get("chest"))
            self._rebuild(key)
            self.status.setText("已加「" + str(name).strip() + "」，拖到身上再保存")
        except Exception as e:
            self.status.setText("出错：" + str(e))

    def _del(self):
        key = self.cmb_area.currentData()
        if not key:
            return
        if key in LABELS_DEFAULT:
            self.status.setText("默认部位不能删（可用「 禁用」停用它）")
            return
        if remove_pet_area(self.pet_id, key):
            self.overlay.areas.pop(key, None)
            self._disabled.discard(key)
            self._rebuild()
            self._save(silent=True)
            self.status.setText("已删除该部位")

    def _toggle_disabled(self):
        key = self.cmb_area.currentData()
        if not key:
            return
        if key in self._disabled:
            self._disabled.discard(key)
            self.status.setText("已启用该部位")
        else:
            self._disabled.add(key)
            self.status.setText("已禁用该部位（桌宠摸到这里不再有反应）")
        self._rebuild(key)
        self._save(silent=True)

    def _save(self, silent=False):
        ok = save_pet_areas(self.pet_id, self.overlay.areas_dict(),
                            labels=touch_labels(self.pet_id), mode=self.mode,
                            disabled=sorted(self._disabled))
        if not silent:
            self.status.setText("已保存（Live2D 这套）；桌宠在运行会立刻刷新"
                                if ok else "保存失败，看日志")
        if ok:
            try:
                import json as _json
                import urllib.request as _u
                req = _u.Request("http://127.0.0.1:28565/control/reload_touch",
                                 data=_json.dumps({}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
                _u.urlopen(req, timeout=1.5).read()
            except Exception:
                pass


# ══════════════════════ 编辑器对话框 ══════════════════════
class TouchAreaEditor(QWidget):
    """独立窗口（不依赖启动器外壳，桌宠/向导里都能开）。

    左侧 = 立绘 + 框；右侧 = 区域列表、精确数值、模式切换、保存。
    """

    saved = pyqtSignal(str)          # 保存成功（pet_id）

    def __init__(self, pet_id: str = None, parent=None, force_mode: str = ""):
        super().__init__(parent, Qt.Window | Qt.WindowStaysOnTopHint)
        from pets.pet_registry import get_active_pet_id
        self.pet_id = pet_id or get_active_pet_id()
        self._force_mode = force_mode
        self.setWindowTitle(f"触摸区域调节 —— {self.pet_id}")
        self.resize(1320, 880)          # 加宽加大：部位增删 + 底图切换等按钮都在右侧列
        self._areas = get_pet_areas(self.pet_id)
        self._enabled = touch_enabled(self.pet_id)
        self._preview_pm = None
        self._build()
        self._select_default_base()
        QTimer.singleShot(60, self._load_preview)

    def _select_default_base(self):
        """默认选中合适的底图：多图拼合 / 单图 / Live2D（有 2D 素材就优先 2D）"""
        try:
            want = self._force_mode or self._pick_default_base()
            keys = {"2d": 0, "2d_single": 0, "live2d": 1}   # 2D 只有一项（自动识别单图/拼合）
            self.cmb_base.blockSignals(True)
            self.cmb_base.setCurrentIndex(keys.get(want, 0))
            self.cmb_base.blockSignals(False)
        except Exception as e:
            print(f"[TouchEditor] ⚠ 选择默认底图失败: {e}")

    # ── UI ──
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        self.overlay = RegionOverlay(self, transparent_bg=False)
        self.overlay.set_areas(self._areas, AREA_KEYS[0])
        self.overlay.changed.connect(self._on_overlay_changed)
        self.overlay.selected.connect(self._on_overlay_selected)
        root.addWidget(self.overlay, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        title = QLabel("触摸区域调节")
        title.setStyleSheet(f"font-size:17px;font-weight:bold;color:{Color1.name()};")
        right.addWidget(title)
        tip = QLabel("· 左键拖动 = 移动区域；拖框边/角 = 缩放\n"
                     "· 被摸到时桌宠会像「摸头」那样回应（轻点 / 按住抚摸两种）\n"
                     "· Live2D 角色：框会画在实时预览窗口的上面，边看模型边调")
        tip.setStyleSheet(f"color:{Gray2.name()};font-size:12px;")
        tip.setWordWrap(True)
        right.addWidget(tip)

        self.chk_enabled = QCheckBox("启用全身触摸互动")
        self.chk_enabled.setChecked(bool(self._enabled))
        right.addWidget(self.chk_enabled)

        gb = QGroupBox("部位（可自己增删：没有的部位可加、多余的可删）")
        gv = QVBoxLayout(gb)
        self.cmb_area = QComboBox()
        self.cmb_area.currentIndexChanged.connect(self._on_area_changed)
        gv.addWidget(self.cmb_area)
        row_add = QHBoxLayout()
        self.btn_add_area = QPushButton("添加部位")
        self.btn_add_area.clicked.connect(self._add_area)
        row_add.addWidget(self.btn_add_area)
        self.btn_del_area = QPushButton("删除该部位")
        self.btn_del_area.clicked.connect(self._del_area)
        row_add.addWidget(self.btn_del_area)
        self.btn_dis_area = QPushButton("禁用")
        self.btn_dis_area.clicked.connect(self._toggle_area_disabled)
        row_add.addWidget(self.btn_dis_area)
        gv.addLayout(row_add)
        self.lbl_area_hint = QLabel("默认 14 个部位不能删（可改位置/大小）；自定义部位可删")
        self.lbl_area_hint.setStyleSheet(f"color:{Gray2.name()};font-size:11px;")
        self.lbl_area_hint.setWordWrap(True)
        gv.addWidget(self.lbl_area_hint)
        right.addWidget(gb)
        self._rebuild_area_combo()

        gb2 = QGroupBox("精确数值（归一化 0~1，与桌宠窗口一致）")
        g2 = QVBoxLayout(gb2)
        self.spins = {}
        for key, lab, lo, hi, step in (("x", "左 (X)", 0.0, 1.0, 0.005),
                                       ("y", "上 (Y)", 0.0, 1.0, 0.005),
                                       ("w", "宽 (W)", 0.01, 1.0, 0.005),
                                       ("h", "高 (H)", 0.01, 1.0, 0.005)):
            row = QHBoxLayout()
            row.addWidget(QLabel(lab))
            sp = QDoubleSpinBox(); sp.setRange(lo, hi); sp.setSingleStep(step)
            sp.setDecimals(3); sp.valueChanged.connect(self._on_spin)
            row.addWidget(sp)
            self.spins[key] = sp
            g2.addLayout(row)
        right.addWidget(gb2)

        gb3 = QGroupBox("底图（2D 立绘 / Live2D 模型）")
        g3 = QVBoxLayout(gb3)
        self.cmb_base = QComboBox()
        # 2D 只有一种：自动识别该角色是「多图拼合」还是「每个表情一张整图」
        # （同一个角色不可能两种并存，所以不需要分成两个选项）
        self.cmb_base.addItem("2D 立绘（自动识别：多图拼合 / 单图整图）", "2d")
        self.cmb_base.addItem("Live2D 模型（框画在实时预览窗口上面）", "live2d")
        self.cmb_base.currentIndexChanged.connect(lambda *_: self._load_preview())
        g3.addWidget(self.cmb_base)
        self.cmb_emotion = QComboBox()
        self.cmb_emotion.currentIndexChanged.connect(lambda *_: self._load_preview())
        self.cmb_emotion.setVisible(False)
        g3.addWidget(self.cmb_emotion)
        b_reload = QPushButton("重新加载底图")
        b_reload.clicked.connect(self._load_preview)
        g3.addWidget(b_reload)
        right.addWidget(gb3)

        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{ok_text().name()};font-size:12px;")
        self.status.setWordWrap(True)
        right.addWidget(self.status)

        row = QHBoxLayout()
        b_def = QPushButton("恢复默认区域")
        b_def.clicked.connect(self._reset)
        row.addWidget(b_def)
        right.addLayout(row)

        row2 = QHBoxLayout()
        b_close = QPushButton("关闭")
        b_close.clicked.connect(self.close)
        row2.addWidget(b_close)
        b_save = QPushButton("保存到角色")
        b_save.setStyleSheet("QPushButton{background:#c8506e;color:#fff;border-radius:8px;"
                             "font-size:14px;font-weight:bold;padding:8px;}")
        b_save.clicked.connect(self._save)
        row2.addWidget(b_save)
        right.addLayout(row2)
        right.addStretch(1)

        holder = QWidget(); holder.setLayout(right); holder.setFixedWidth(420)
        root.addWidget(holder)
        self._sync_spins()

    # ── 动作 ──
    def _rebuild_area_combo(self, keep: str = ""):
        """按「默认部位 + 该角色自定义部位」重建下拉（增删后刷新）"""
        try:
            from tool.touch_areas import custom_keys
            keep = keep or (self.cmb_area.currentData() if self.cmb_area.count() else "")
            labs = touch_labels(self.pet_id)
            self.cmb_area.blockSignals(True)
            self.cmb_area.clear()
            _dis = set(getattr(self.overlay, "disabled", set()) or set())
            for k, _n, _d, _a, _b in AREAS:
                if k in (self._active().areas if hasattr(self, "overlay") else {}) or k in labs:
                    self.cmb_area.addItem(("（已禁用）" if k in _dis else "") + labs.get(k, k), k)
            for k in custom_keys(self.pet_id):
                self.cmb_area.addItem("（自定）" + labs.get(k, k) if str(k).startswith("custom") else labs.get(k, k), k)
            i = self.cmb_area.findData(keep) if keep else -1
            self.cmb_area.setCurrentIndex(i if i >= 0 else 0)
            self.cmb_area.blockSignals(False)
            self.lbl_area_hint.setText(
                f"共 {self.cmb_area.count()}个部位（默认 14 个不可删； 为自定义，可删）")
        except Exception as e:
            print(f"[TouchEditor] ⚠ 重建部位列表失败: {e}")

    def _add_area(self):
        """添加一个自定义部位（例如：尾巴、耳朵、角、翅膀…）"""
        try:
            from tool.touch_areas import add_pet_area
            name, okk = ask_text(self, "添加部位", "部位名字", placeholder="例如：尾巴 / 耳朵 / 角")
            if not okk or not str(name).strip():
                return
            key = add_pet_area(self.pet_id, str(name).strip())
            if not key:
                self.status.setText("添加失败，看控制台日志")
                return
            # 同步到两层框（默认给一个中间位置的小框，拖到身上即可）
            self.overlay.areas[key] = list(touch_defaults().get("chest"))
            ov = getattr(self, "_live_overlay", None)
            if ov is not None:
                ov.areas[key] = list(self.overlay.areas[key])
            self._rebuild_area_combo(key)
            self._on_area_changed()
            self.status.setText(f"已添加部位「{str(name).strip()}」——把它拖到身上对应位置，再点保存")
        except Exception as e:
            self.status.setText(f"添加部位失败:{e}")

    def _toggle_area_disabled(self):
        """禁用 / 启用当前部位（默认部位不能删，但可以禁用；每模式独立）"""
        try:
            key = self.cmb_area.currentData()
            if not key:
                return
            mode = self._cur_mode()
            dis = set(self.overlay.disabled or set())
            if key in dis:
                dis.discard(key)
            else:
                dis.add(key)
            self.overlay.disabled = dis
            ov = getattr(self, "_live_overlay", None)
            if ov is not None:
                ov.disabled = set(dis)
            if save_pet_areas(self.pet_id, self.overlay.areas_dict(), mode=mode,
                              labels=touch_labels(self.pet_id), disabled=sorted(dis)):
                self.status.setText(("已启用该部位"if key not in dis
                                     else "已禁用该部位（桌宠摸到这里不再有反应）"))
                self._rebuild_area_combo(key)
                self.overlay.update()
                try:
                    import json as _j, urllib.request as _u
                    _u.urlopen(_u.Request("http://127.0.0.1:28565/control/reload_touch",
                                          data=_j.dumps({}).encode("utf-8"),
                                          headers={"Content-Type": "application/json"}),
                               timeout=1.5).read()
                except Exception:
                    pass
        except Exception as e:
            self.status.setText(f"禁用/启用失败:{e}")

    def _del_area(self):
        """删除当前选中的自定义部位（默认部位不允许删）"""
        try:
            from tool.touch_areas import remove_pet_area, LABELS as _DEF
            key = self.cmb_area.currentData()
            if not key:
                return
            if key in _DEF:
                self.status.setText("默认部位不能删除（可以改位置/大小；不想要就把框拖到画面外的小角落）")
                return
            if remove_pet_area(self.pet_id, key):
                for ov in (self.overlay, getattr(self, "_live_overlay", None)):
                    if ov is not None:
                        ov.areas.pop(key, None)
                        ov.update()
                self._rebuild_area_combo()
                self._on_area_changed()
                self.status.setText("已删除该部位（已保存）")
        except Exception as e:
            self.status.setText(f"删除部位失败:{e}")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # 改尺寸后重排 + 同步重画（防止按钮命中区和画出来的位置不一致）
        try:
            lay = self.layout()
            if lay is not None:
                lay.activate()
            for ov in (self.overlay, getattr(self, "_live_overlay", None)):
                if ov is not None:
                    ov.updateGeometry()
                    ov.update()
            self.repaint()
        except Exception:
            pass
        self._refresh_live_overlay()

    def _on_area_changed(self, *_):
        key = self.cmb_area.currentData()
        for ov in (self.overlay, getattr(self, "_live_overlay", None)):
            if ov is None:
                continue
            ov.current = key
            ov.update()
        self._sync_spins()

    def _on_overlay_selected(self, key):
        i = self.cmb_area.findData(key)
        if i >= 0 and i != self.cmb_area.currentIndex():
            self.cmb_area.blockSignals(True)
            self.cmb_area.setCurrentIndex(i)
            self.cmb_area.blockSignals(False)
        self._sync_spins()

    def _sync_spins(self):
        """把当前选中区域的数值同步到右侧精确输入框"""
        ov = self._active()
        r = ov.areas.get(ov.current) or [0, 0, 0.2, 0.1]
        vals = {"x": r[0], "y": r[1], "w": r[2], "h": r[3]}
        for k, sp in self.spins.items():
            sp.blockSignals(True)
            sp.setValue(float(vals[k]))
            sp.blockSignals(False)

    def _on_spin(self, *_):
        ov = self._active()
        key = ov.current
        ov.areas[key] = norm_rect([self.spins["x"].value(), self.spins["y"].value(),
                                   self.spins["w"].value(), self.spins["h"].value()],
                                  ov.areas.get(key))
        self._mirror(ov)
        ov.update()

    def _reset(self):
        ov = self._active()
        ov.set_areas(touch_defaults(), ov.current)
        self._mirror(ov)
        self._sync_spins()
        self.status.setText("已恢复默认区域（记得点保存）")

    def _save(self):
        ov = self._active()
        _mode = self._cur_mode()
        ok = save_pet_areas(self.pet_id, ov.areas_dict(), mode=_mode,
                            labels=touch_labels(self.pet_id),
                            disabled=sorted(getattr(ov, "disabled", set()) or set()),
                            enabled=self.chk_enabled.isChecked())
        if ok:
            self.status.setText("已保存；桌宠在下次启动/重开后生效（正在运行的桌宠会立刻刷新）")
            self.saved.emit(self.pet_id)
            try:
                self._notify_pet()
            except Exception:
                pass
        else:
            self.status.setText("保存失败，看控制台日志")

    def _notify_pet(self):
        """通知正在运行的桌宠立刻刷新触摸区域（走它的 HTTP 接口）"""
        try:
            import json as _json
            import urllib.request as _u
            req = _u.Request("http://127.0.0.1:28565/control/reload_touch",
                             data=_json.dumps({}).encode("utf-8"),
                             headers={"Content-Type": "application/json"})
            _u.urlopen(req, timeout=1.5).read()
        except Exception:
            pass

    # ── 预览 ──
    # ── 预览 ──
    def _pick_default_base(self):
        """默认底图：**有 2D 素材就先用 2D**（多图拼合优先，单图模式用单图），
        只有纯 Live2D 角色才用 Live2D。

        ⚠ 以前是「角色默认显示方式=Live2D 就直接上 Live2D」→ 有 2D 素材的角色在编辑器里
        只能看到 Live2D（用户反馈"为什么不显示 2D 立绘，单图和多图合成都该支持"）。
        """
        try:
            from pets.pet_registry import get_fgimages_dir, get_live2d_model_json, get_portrait_mode
            has2d = bool(get_fgimages_dir(self.pet_id))
            has_l2d = bool(get_live2d_model_json(self.pet_id))
            mode = str(get_portrait_mode(self.pet_id) or "layers").lower()
            if has2d:
                return "2d"          # 2D 底图会自动识别是拼合还是单图（见 _load_2d_preview）
            if has_l2d:
                return "live2d"
        except Exception as e:
            print(f"[TouchEditor] ⚠ 判定默认底图失败: {e}")
        return "2d"

    def _fill_emotions(self):
        """单图模式：列出角色的表情供选择（每个表情一张整图的那种）"""
        try:
            from pets.pet_registry import get_pet_config
            cfg = get_pet_config(self.pet_id) or {}
            pt = cfg.get("portrait") or {}
            emos = list((pt.get("emotions") or {}).keys())
            dflt = str(pt.get("default_emotion") or "")
            if not emos:
                return False
            self.cmb_emotion.blockSignals(True)
            self.cmb_emotion.clear()
            for e in emos:
                self.cmb_emotion.addItem(e, e)
            if dflt:
                i = self.cmb_emotion.findData(dflt)
                if i >= 0:
                    self.cmb_emotion.setCurrentIndex(i)
            self.cmb_emotion.blockSignals(False)
            return True
        except Exception as e:
            print(f"[TouchEditor] ⚠ 读取表情失败: {e}")
            return False

    def _live_overlay_hide(self):
        ov = getattr(self, "_live_overlay", None)
        if ov is not None:
            try:
                ov.hide()
            except Exception:
                pass

    def _hide_live_overlay(self, hard=True):
        ov = getattr(self, "_live_overlay", None)
        if ov is not None:
            try:
                ov.hide()
            except Exception:
                pass
        panel = getattr(self, "_live_panel", None)
        if panel is not None:
            try:
                panel.hide()
            except Exception:
                pass

    def _detach_live2d(self):
        """切回 2D：把 Live2D 上的覆盖层收起来（窗口本身留着，方便再切回去）"""
        self._hide_live_overlay()
        self._preview_pm = None
        try:
            self.overlay.set_background(None)
        except Exception:
            pass
        self.status.setText("已切回 2D 立绘调框")

    def _detect_single_mode(self) -> bool:
        """该角色的 2D 立绘是不是「每个表情一张整图」那种（自动识别，不用用户选）"""
        try:
            from pets.pet_registry import get_portrait_mode, get_pet_config
            mode = str(get_portrait_mode(self.pet_id) or "").lower()
            if mode:
                return mode == "single"
            cfg = get_pet_config(self.pet_id) or {}
            pt = cfg.get("portrait") or {}
            # 没有显式 mode 时按素材判断：有表情整图表 → 单图模式
            if str(pt.get("mode") or "").lower() == "single":
                return True
            return bool(pt.get("emotions")) and not pt.get("layers")
        except Exception as e:
            print(f"[TouchEditor] ⚠ 识别 2D 类型失败（按拼合处理）: {e}")
            return False

    def _active(self):
        """当前真正在被操作的覆盖层。

        ⚠ 关键：在 Live2D 预览窗口上拖的是「挂到预览窗口的那个覆盖层」，
        而以前「保存 / 数值框 / 恢复默认」全都读编辑器自己那个覆盖层 →
        在预览窗口上调完再保存，等于保存了个没改过的旧数据（用户反馈"不会保存"）。
        """
        ov = getattr(self, "_live_overlay", None)
        try:
            if ov is not None and ov.isVisible():
                return ov
        except Exception:
            pass
        return self.overlay

    def _mirror(self, from_ov):
        """把改动同步到另一个覆盖层（两者始终看同一份数据）"""
        try:
            other = self.overlay if from_ov is not self.overlay else getattr(self, "_live_overlay", None)
            if other is None or other is from_ov:
                return
            other.areas = {k: list(v) for k, v in (from_ov.areas or {}).items()}
            other.current = from_ov.current
            other.update()
        except Exception as e:
            print(f"[TouchEditor] ⚠ 同步覆盖层失败: {e}")

    def _on_overlay_changed(self):
        self._mirror(self._active())
        self._sync_spins()

    def _cur_mode(self) -> str:
        """当前底图对应的数据模式（2D / Live2D 各自独立）"""
        try:
            return "live2d" if str(self.cmb_base.currentData()) == "live2d" else "2d"
        except Exception:
            return "2d"

    def _sync_mode_areas(self, mode: str):
        """把编辑器的框切换成该模式的独立数据（并从 pet.json 重新读一份）"""
        try:
            areas = get_pet_areas(self.pet_id, mode)
            dis = set(get_disabled(self.pet_id, mode))
            cur = self.overlay.current
            self.overlay.disabled = dis
            self.overlay.set_areas(areas, cur)
            self._rebuild_area_combo(cur)
            self._sync_spins()
            print(f"[TouchEditor] 已装载 {mode} 这套触摸区域（{len(areas)} 个，禁用 {len(dis)} 个）")
        except Exception as e:
            print(f"[TouchEditor] ⚠ 切换模式数据失败: {e}")

    def _load_preview(self):
        """按所选底图加载：2D(多图拼合) / 2D(单图) / Live2D"""
        try:
            self._live_overlay_hide()
        except Exception:
            pass
        want = str(self.cmb_base.currentData() or "2d")
        if want == "live2d":
            self.cmb_emotion.setVisible(False)
            self._attach_to_live2d()
            return
        # 2D：自动识别角色类型（单图整图 → 需要选表情；多图拼合 → 不需要）
        # 2D / Live2D 的触摸区域是两套独立数据：切换底图时换成对应那套
        try:
            self._sync_mode_areas("2d")
        except Exception:
            pass
        single = self._detect_single_mode()
        if single:
            self.cmb_emotion.setVisible(True)
            if not self.cmb_emotion.count() and not self._fill_emotions():
                self.status.setText("这个角色没有「每个表情一张整图」的表情素材")
                return
        else:
            self.cmb_emotion.setVisible(False)
        self._load_2d_preview(force_single=single)

    def _cli(self, args, timeout=90):
        """跑 portrait_cli.py（与「立绘工坊」同一套：子进程带 AIPET_PET_ID，不动活动角色）"""
        import subprocess
        from pcl_launcher.portrait_studio import _runtime_python, _base_dir
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
                   AIPET_PET_ID=str(self.pet_id))
        cli_path = os.path.join(_base_dir(), "tool", "portrait_cli.py")
        r = subprocess.run([_runtime_python(), cli_path] + [str(a) for a in args],
                           cwd=_base_dir(), capture_output=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return (r.stdout or "").strip(), (r.stderr or "").strip()

    def _load_2d_preview(self, force_single: bool = False):
        """2D 底图（与立绘工坊同款 CLI 合成）

        - 多图拼合（layers）：按角色保存的装扮 compose → 完整立绘
        - 每表情一张整图（single）：preview_single → 用当前选择的表情
        """
        try:
            from pcl_launcher.portrait_studio import _runtime_python, _base_dir
            import json as _json
            if not os.path.exists(_runtime_python()):
                self.status.setText("当前环境没有 runtime venv，无法合成立绘（框仍可调、保存可用）")
                return
            out, err = self._cli(["list"])
            data = {}
            try:
                data = _json.loads(out.splitlines()[-1]) if out else {}
            except Exception:
                data = {}
            mode = str(data.get("mode") or "layers").lower()
            out_name = "touch_preview.png"
            if force_single or mode == "single":
                pt = data.get("portrait") or {}
                emo = str(self.cmb_emotion.currentData() or "")
                if not emo:
                    emos = list((pt.get("emotions") or {}).keys())
                    emo = str(pt.get("default_emotion") or (emos[0] if emos else ""))
                if not emo:
                    self.status.setText("这个角色没有单图表情素材（没有可预览的整图）")
                    return
                # 套装名与下面「多图拼合」分支取同一来源（历史上前者漏了这句，
                # set_name 从未定义 → 单图角色点预览必报 NameError）
                set_name = str(data.get("active") or "a")
                args = ["preview_full", set_name or "a", emo]      # 全身 + 透明底
            else:
                act = str(data.get("active") or "a")
                sv = (data.get("saved") or {})
                sv = (sv.get(act) if isinstance(sv, dict) and isinstance(sv.get(act), dict) else sv) or {}
                cloth = int(sv.get("cloth_id") or 0)
                if not cloth:
                    cl = ((data.get("clothes") or {}).get(act) or [])
                    cloth = int(cl[0][1]) if cl else 0
                expr = 0
                for it in ((data.get("expressions") or {}).get(act) or []):
                    if str(it[0]) in ("平静", "普通"):
                        expr = int(it[1])
                        break
                if not expr:
                    ex = ((data.get("expressions") or {}).get(act) or [])
                    expr = int(ex[0][1]) if ex else 0
                hair = 0
                for it in ((data.get("clothes") or {}).get(act) or []):
                    if int(it[1]) == cloth:
                        hair = int(it[2])
                        break
                decors = ",".join(str(d) for d in (sv.get("decor") or []))
                args = ["preview_full", act, ""]                  # 全身 + 透明底（自动用该套保存的装扮）
            so, se = self._cli(args)
            path = ""
            for line in reversed((so or "").splitlines()):
                s = line.strip()
                if s.lower().endswith(".png"):
                    cand = s if os.path.isabs(s) else os.path.join(_base_dir(), "tmp",
                                                                   os.path.basename(s))
                    if os.path.exists(cand):
                        path = cand
                        break
            if not path:
                cand = os.path.join(_base_dir(), "tmp", out_name)
                if os.path.exists(cand):
                    path = cand
            if path and os.path.exists(path):
                pm = QPixmap(path)
                if not pm.isNull():
                    self._preview_pm = pm
                    self.overlay.set_background(pm)
                    how = "单张整图" if (force_single or mode == "single") else "多图拼合"
                    self.status.setText(f"2D 底图（{how}）：{os.path.basename(path)}"
                                        f"（把框拖到对应部位即可）")
                    return
            self.status.setText(f"没合成出预览图（框仍可调、保存可用）{se[:60]}")
        except Exception as e:
            self.status.setText(f"预览加载失败（框仍可调）:{e}")

    def _attach_to_live2d(self):
        """把框挂到 Live2D 实时预览窗口上（框在最上层 → 能边看模型边调）"""
        try:
            from pets.pet_registry import get_live2d_model_json
            from pcl_launcher.live2d_preview import open_live2d_window
            mj = get_live2d_model_json(self.pet_id) or ""
            if not mj:
                self.status.setText("该角色没有 Live2D 模型，已改用 2D 立绘调框")
                try:
                    self.cmb_base.blockSignals(True)
                    self.cmb_base.setCurrentIndex(0)
                    self.cmb_base.blockSignals(False)
                except Exception:
                    pass
                self._load_2d_preview()
                return
            win = open_live2d_window(mj, None, pet_id=getattr(self, "pet_id", None))
            if win is None:
                self.status.setText("打开 Live2D 预览失败（看 tmp/live2d_window.log）")
                return
            # 覆盖层：作为预览窗口的子控件，盖在 GL 控件上（半透明，模型可见）
            ov = getattr(win, "_touch_overlay", None)
            try:
                if ov is not None:
                    ov.isHidden()
            except Exception:
                ov = None
            if ov is None:
                ov = RegionOverlay(win, transparent_bg=True)
                win._touch_overlay = ov
            # 带上当前（可能刚在另一个覆盖层里改过的）数据，切底图不丢改动
            src_ov = self._active()
            ov.set_areas(src_ov.areas_dict(), src_ov.current)
            if src_ov is not ov:
                self.overlay.areas = {k: list(v) for k, v in ov.areas.items()}
            ov.changed.connect(self._on_overlay_changed)
            ov.selected.connect(self._on_overlay_selected)
            self._live_overlay = ov
            self._live_win = win
            ov.setGeometry(win.view.geometry())
            ov.show()
            ov.raise_()
            # ── 把「完整调节面板」也挂到预览窗口右侧（边看模型边调，不用回编辑器窗口）──
            panel = getattr(win, "_touch_panel", None)
            try:
                if panel is not None:
                    panel.isHidden()
            except Exception:
                panel = None
            if panel is None or getattr(panel, "pet_id", None) != str(self.pet_id):
                panel = TouchControlPanel(self.pet_id, ov, win, mode="live2d")
                win._touch_panel = panel
            panel.overlay = ov
            panel.pet_id = self.pet_id
            try:
                ov.changed.connect(panel._sync)
            except Exception:
                pass
            # ⚠ 面板要放在预览窗口右侧 → 窗口不够宽就先加大（模型区至少 600px + 面板 + 边距），
            #   否则面板会盖住模型，没法"边看模型边调"。
            try:
                panel.setFixedWidth(400)
            except Exception:
                pass
            pw = panel.width() or 400
            need_w = 600 + pw + 28
            need_h = max(760, win.height())
            if win.width() < need_w or win.height() < need_h:
                win.resize(need_w, need_h)
                print(f"[TouchEditor] 预览窗口已加大到 {need_w}x{need_h}（给调节面板留位置）")
            panel.setGeometry(max(0, win.width() - pw - 12), 8, pw, max(240, win.height() - 16))
            panel.show()
            panel.raise_()
            # 框的范围收窄到「模型区」= 预览窗口减去右侧面板，避免框被面板挡住
            try:
                g = win.view.geometry()
                ov.setGeometry(g.x(), g.y(), max(160, g.width() - pw - 20), g.height())
            except Exception:
                pass
            self._live_panel = panel
            ov._hint = "框显示在 Live2D 预览窗口上 →"
            self.status.setText("🎭 框已画在 Live2D 预览窗口上：直接拖框调位置/大小（模型可见）"
                                "；想用 2D 立绘调框点上面的按钮")
            # 窗口/布局稳定后再按「模型区」重算一次（必须用面板感知的刷新，
            # 直接 setGeometry(view) 会把框铺满整窗、盖到面板下面去）
            QTimer.singleShot(120, self._refresh_live_overlay)
            QTimer.singleShot(420, self._refresh_live_overlay)
        except Exception as e:
            self.status.setText(f"Live2D 调框失败:{e}")

    def _refresh_live_overlay(self):
        ov = getattr(self, "_live_overlay", None)
        win = getattr(self, "_live_win", None)
        if ov is None or win is None:
            return
        try:
            panel = getattr(self, "_live_panel", None)
            pw = panel.width() if panel is not None else 0
            if panel is not None:
                try:
                    need_w = 600 + pw + 28
                    if win.width() < need_w:
                        win.resize(need_w, max(760, win.height()))
                except Exception:
                    pass
                panel.setGeometry(max(0, win.width() - pw - 12), 8, pw,
                                  max(240, win.height() - 16))
                panel.raise_()
            g = win.view.geometry()
            ov.setGeometry(g.x(), g.y(), max(160, g.width() - pw - 20), g.height())
        except Exception:
            pass

    def closeEvent(self, e):
        ov = getattr(self, "_live_overlay", None)
        if ov is not None:
            try:
                ov.hide()
            except Exception:
                pass
        super().closeEvent(e)
