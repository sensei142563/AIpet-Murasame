# -*- coding: utf-8 -*-
"""
Live2D 表情/动作调试器（临时简陋版）

用途：逐个查看角色模型的表情(exp3)/动作(motion3)文件效果，
      以便向开发者描述「哪个文件是什么表情/动作」，再据此配置 pet.json。

用法：
    python debug_live2d.py [--pet noir]
    （不带参数默认当前活动角色；右上角下拉可切换 4 个本地角色）

操作：
    - 左画面：Live2D 模型（显示参数沿用 pet.json 的调校值）
    - 表情按钮：点击立即切换；「复原表情」回到默认
    - 动作按钮：点击播放（播完自动回默认表情）
    - 参数滑块：拖动实时改参数（观察每个动作动了哪些参数）
"""
import os
import sys
import argparse

# ==== Live2D DLL 路径（复用 Live2d 模块顶部的设置）====
import Live2d.live2d_ui as _lui  # noqa: E402  （顶部已设置 PATH / add_dll_directory）

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QSlider, QScrollArea, QOpenGLWidget,
)
from PyQt5.QtGui import QGuiApplication

from pets.pet_registry import (
    get_pet_ids, get_pet_dir, get_live2d_model_json,
    get_live2d_display, get_live2d_params, get_active_pet_id,
)


def _scan_files(base_dir, suffix):
    """递归扫描 base_dir 下所有 suffix 结尾的文件，按文件名去重，返回 [(文件名, 绝对路径)]"""
    found = {}
    if not os.path.isdir(base_dir):
        return []
    for root, _dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith(suffix):
                found.setdefault(f, os.path.join(root, f))
    return sorted(found.items())


class ModelCanvas(QOpenGLWidget):
    """极简 Live2D 画布：加载模型 + 循环渲染 + 提供表情/动作/参数控制"""

    def __init__(self, model_json, model_dir, scale, offset_x, offset_y,
                 default_expression, parent=None):
        super().__init__(parent)
        self.model_json = model_json
        self.model_dir = model_dir
        self.scale = scale
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.default_expression = default_expression

        self.model = None
        self._ready = False
        self._failed = False

        # 表情：文件名 → 注册 ID
        self.expressions = {}          # id -> path
        self._cur_expression = None
        # 动作：文件名 → 组内序号（统一注册到 "emotion" 组）
        self.motions = {}              # 文件名 -> (组, 序号)
        self._motion_active = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.setInterval(16)
        self.timer.start()

    # ===== GL =====
    def initializeGL(self):
        if self._failed:
            return
        try:
            _lui._ensure_live2d()
            from OpenGL.GL import glEnable, GL_BLEND, glBlendFunc, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, glClearColor
            import live2d.v3 as l2d
            l2d.glInit()
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glClearColor(0.1, 0.12, 0.15, 1)   # 深色背景，方便看模型轮廓

            path = os.path.normpath(self.model_json).replace("\\", "/")
            self.model = l2d.LAppModel()
            self.model.LoadModelJson(path)
            if self.scale != 1.0 or self.offset_x or self.offset_y:
                try:
                    self.model.SetScale(self.scale)
                    self.model.SetOffset(self.offset_x, self.offset_y)
                except Exception:
                    pass

            # 注册表情（LoadExtraExpression 支持任意 exp3 文件）
            for fname, fpath in _scan_files(self.model_dir, ".exp3.json"):
                eid = fname
                try:
                    self.model.LoadExtraExpression(eid, fpath)
                    self.expressions[eid] = fpath
                except Exception as e:
                    print(f"[debug] 表情注册失败 {fname}: {e}")

            # 注册动作（全部归入 "emotion" 组，LoadExtraMotion 返回组内序号）
            for fname, fpath in _scan_files(self.model_dir, ".motion3.json"):
                try:
                    no = self.model.LoadExtraMotion("emotion", fpath)
                    self.motions[fname] = ("emotion", no)
                except Exception as e:
                    print(f"[debug] 动作注册失败 {fname}: {e}")

            if self.default_expression:
                self.apply_expression(self.default_expression)
            self._ready = True
            print(f"[debug] 模型加载完成: {path}")
            print(f"[debug] 表情 {len(self.expressions)} 个: {list(self.expressions)}")
            print(f"[debug] 动作 {len(self.motions)} 个: {list(self.motions)}")
        except Exception as e:
            self._failed = True
            import traceback
            traceback.print_exc()
            print(f"[debug] 模型加载失败: {e}")

    def paintGL(self):
        if not self._ready or self._failed:
            return
        try:
            from OpenGL.GL import glClear, GL_COLOR_BUFFER_BIT
            glClear(GL_COLOR_BUFFER_BIT)
            self.model.Update()
            self.model.Draw()
        except Exception:
            pass

    def resizeGL(self, w, h):
        if self.model and self._ready:
            try:
                self.model.Resize(w, h)
            except Exception:
                pass

    def _on_tick(self):
        if not self._ready or self._failed:
            return
        # 动作播完 → 恢复默认表情（与桌宠运行时行为一致）
        if self._motion_active:
            try:
                if self.model.IsMotionFinished():
                    self._motion_active = False
                    if self.default_expression:
                        self.apply_expression(self.default_expression)
                    else:
                        self.model.ResetExpressions()
                    print("[debug] 动作播完，已恢复默认表情")
            except Exception:
                pass
        self.update()

    # ===== 控制接口 =====
    def apply_expression(self, exp_id):
        try:
            self.model.SetExpression(exp_id)
            self._cur_expression = exp_id
            print(f"[debug] 应用表情: {exp_id}")
        except Exception as e:
            print(f"[debug] 表情失败 {exp_id}: {e}")

    def reset_expressions(self):
        try:
            self.model.ResetExpressions()
            self._cur_expression = None
            print("[debug] 已复原表情")
        except Exception:
            pass

    def play_motion(self, fname):
        if fname not in self.motions:
            print(f"[debug] 动作未注册: {fname}")
            return
        group, no = self.motions[fname]
        try:
            self.model.StopAllMotions()
            self.model.StartMotion(group, no, 3)
            self._motion_active = True
            print(f"[debug] 播放动作: {fname} (group={group}, no={no})")
        except Exception as e:
            print(f"[debug] 动作播放失败 {fname}: {e}")

    def set_param(self, param_id, value):
        try:
            self.model.SetParameterValue(param_id, value, 1.0)
        except Exception:
            pass

    def reset_params(self):
        try:
            self.model.ResetParameters()
            print("[debug] 已重置参数")
        except Exception:
            pass


# 参数滑块：参数名 → (最小值, 最大值)
PARAM_RANGES = [
    ("ParamAngleX", -30, 30),
    ("ParamAngleY", -30, 30),
    ("ParamAngleZ", -30, 30),
    ("ParamBodyAngleX", -10, 10),
    ("ParamBodyAngleY", -10, 10),
    ("ParamBodyAngleZ", -10, 10),
    ("ParamEyeLOpen", 0, 1),
    ("ParamEyeROpen", 0, 1),
    ("ParamMouthOpenY", 0, 1),
    ("ParamBreath", 0, 1),
]


class DebugWindow(QMainWindow):
    def __init__(self, initial_pet):
        super().__init__()
        self.setWindowTitle("Live2D 表情/动作调试器（临时）")
        self.pet_ids = [p for p in get_pet_ids()]
        if not self.pet_ids:
            print("没有发现任何桌宠角色包")
            sys.exit(1)

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)

        # ===== 左：画布 =====
        self.canvas_holder = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas_holder)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = None
        root_layout.addWidget(self.canvas_holder, 3)

        # ===== 右：控制面板 =====
        panel = QWidget()
        panel.setFixedWidth(360)
        pl = QVBoxLayout(panel)

        pl.addWidget(QLabel("角色："))
        self.pet_combo = QComboBox()
        for pid in self.pet_ids:
            self.pet_combo.addItem(pid, pid)
        self.pet_combo.currentIndexChanged.connect(self._on_pet_changed)
        pl.addWidget(self.pet_combo)

        pl.addWidget(QLabel("表情（点击切换）："))
        self.exp_container = QWidget()
        self.exp_grid = QGridLayout(self.exp_container)
        self.exp_scroll = QScrollArea()
        self.exp_scroll.setWidgetResizable(True)
        self.exp_scroll.setWidget(self.exp_container)
        pl.addWidget(self.exp_scroll, 1)

        pl.addWidget(QLabel("动作（点击播放，播完自动回默认）："))
        self.mot_container = QWidget()
        self.mot_grid = QGridLayout(self.mot_container)
        self.mot_scroll = QScrollArea()
        self.mot_scroll.setWidgetResizable(True)
        self.mot_scroll.setWidget(self.mot_container)
        pl.addWidget(self.mot_scroll, 2)

        pl.addWidget(QLabel("参数（拖动实时变化）："))
        self.sliders = {}
        for param_id, lo, hi in PARAM_RANGES:
            row = QHBoxLayout()
            lab = QLabel(param_id.replace("Param", ""))
            lab.setFixedWidth(90)
            row.addWidget(lab)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(0, 200)
            sl.setValue(100)
            sl.valueChanged.connect(lambda v, p=param_id, a=lo, b=hi: self._on_slider(p, v, a, b))
            row.addWidget(sl, 1)
            self.sliders[param_id] = sl
            pl.addLayout(row)

        btn_row = QHBoxLayout()
        b1 = QPushButton("重置参数")
        b1.clicked.connect(self._reset_params)
        b2 = QPushButton("复原表情")
        b2.clicked.connect(self._reset_expressions)
        btn_row.addWidget(b1)
        btn_row.addWidget(b2)
        pl.addLayout(btn_row)

        root_layout.addWidget(panel, 1)

        # 初始角色
        idx = self.pet_ids.index(initial_pet) if initial_pet in self.pet_ids else 0
        self.pet_combo.setCurrentIndex(idx)
        self._on_pet_changed(idx)

        self.resize(1280, 800)

    # ===== 角色切换 =====
    def _on_pet_changed(self, idx):
        pet_id = self.pet_combo.itemData(idx)
        model_json = get_live2d_model_json(pet_id)
        pet_dir = get_pet_dir(pet_id)
        disp = get_live2d_display(pet_id)
        params = get_live2d_params(pet_id)
        print(f"\n===== 加载角色 {pet_id} =====")
        print(f"模型: {model_json}")
        if not model_json or not os.path.exists(model_json):
            print(f"[debug] ⚠ 模型文件不存在: {model_json}")
            return
        # 重建画布（销毁旧的 GL 控件）
        if self.canvas is not None:
            self.canvas_layout.removeWidget(self.canvas)
            self.canvas.deleteLater()
            self.canvas = None
        self.canvas = ModelCanvas(
            model_json, pet_dir,
            disp.get("scale", 1.0), disp.get("offset_x", 0.0), disp.get("offset_y", 0.0),
            disp.get("default_expression", ""),
        )
        self.canvas_layout.addWidget(self.canvas)
        self._refresh_lists()
        # 表情/动作按钮在模型 initializeGL 完成后刷新（见 _refresh_lists 的兜底）
        QTimer.singleShot(800, self._refresh_lists)

    def _refresh_lists(self):
        if not self.canvas:
            return
        # 清空旧按钮
        for grid in (self.exp_grid, self.mot_grid):
            while grid.count():
                item = grid.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        # 表情按钮
        exp_names = sorted(self.canvas.expressions.keys()) if self.canvas.expressions else _scan_dummy()
        if not exp_names:
            exp_names = [f for f, _ in _scan_files(self.canvas.model_dir, ".exp3.json")]
        for i, fname in enumerate(exp_names):
            btn = QPushButton(fname)
            btn.setToolTip("点击切换表情")
            btn.clicked.connect(lambda _, f=fname: self.canvas.apply_expression(f))
            self.exp_grid.addWidget(btn, i // 3, i % 3)
        # 动作按钮
        mot_names = sorted(self.canvas.motions.keys()) if self.canvas.motions else [f for f, _ in _scan_files(self.canvas.model_dir, ".motion3.json")]
        if not mot_names:
            self.mot_grid.addWidget(QLabel("（该角色没有 motion3 动作文件）"), 0, 0)
        for i, fname in enumerate(mot_names):
            btn = QPushButton(fname)
            btn.setToolTip("点击播放动作")
            btn.clicked.connect(lambda _, f=fname: self.canvas.play_motion(f))
            self.mot_grid.addWidget(btn, i // 3, i % 3)

    # ===== 控件回调 =====
    def _on_slider(self, param_id, v, lo, hi):
        if not self.canvas or not self.canvas._ready:
            return
        value = lo + (hi - lo) * v / 200.0
        self.canvas.set_param(param_id, value)

    def _reset_params(self):
        if self.canvas:
            self.canvas.reset_params()

    def _reset_expressions(self):
        if self.canvas:
            self.canvas.reset_expressions()


def _scan_dummy():
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pet", default="", help="角色 ID（如 noir / murasame / arona / hiyori），默认当前活动角色")
    args = parser.parse_args()
    pet = args.pet or get_active_pet_id()

    app = QApplication(sys.argv)
    win = DebugWindow(pet)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
