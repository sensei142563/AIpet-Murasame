# -*- coding: utf-8 -*-
"""Live2D 动作 / 表情调试器（主题一致的正式版；原 `debug_live2d.py` 的"临时简陋版"）。

用途（一直没变）：逐个播/切模型的 **每个表情（*.exp3.json）与动作（*.motion3.json）**，
看清"这个文件到底是哪个表情/动作"，并**给它打个标签**，最后照着标签去配 pet.json 的
表情/动作映射。所以这里除了浏览，还提供：

  · 当前正在用的表情/动作会**高亮**（不然点完就分不清是哪个）
  · 每个文件可写「标签 + 备注」，存到 `tmp/live2d_labels_<角色>.json`
  · 一键**复制 / 导出对照表**（文件名 → 标签），直接能贴进 pet.json 或交给开发者
  · **动作时间轴**：先「🔴 录这段动作」把整段动作逐帧记下来，再**拖进度条定格到任意一帧**
    （否则动作只会从头播到尾，中间过程看不清）。录完还会列出这段动作真正在动的参数。

与桌宠用的是同一套渲染参数（scale / offset / 默认表情都读 pet.json），所以这里看到的
姿势/大小就是桌宠上的样子。

`debug_live2d.py` 现在只是本模块的命令行入口（`python debug_live2d.py --pet noir`），
立绘工坊的 Live2D 区也有按钮直接打开。
"""
import json
import os
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
                            QLabel, QPushButton, QComboBox, QSlider, QScrollArea,
                            QLineEdit, QOpenGLWidget, QSizePolicy, QPlainTextEdit)

from .colors import Color1, Color5, Color7, Gray2, Gray3, Color3, GreenDark
from .silicon_dialog import SiliconDialog, page_msg
from .silicon_ui import M

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


def short_name(fname):
    """按钮上只显示短名字（motion01 / exp1），文件名另有 tooltip 和标签表兜底"""
    for suf in (".motion3.json", ".exp3.json"):
        if fname.endswith(suf):
            return fname[:-len(suf)]
    return fname


def _base_dir() -> str:
    import sys as _sys
    if getattr(_sys, "frozen", False):
        return os.path.dirname(_sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scan_files(base_dir, suffix):
    """递归扫描目录下所有 suffix 结尾的文件，按文件名去重 → [(文件名, 绝对路径)]"""
    found = {}
    if not os.path.isdir(base_dir or ""):
        return []
    for root, _dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith(suffix):
                found.setdefault(f, os.path.join(root, f))
    return sorted(found.items())


# ══════════════ 打标签的存储（tmp/live2d_labels_<角色>.json）══════════════
class LabelStore:
    """某个角色的「文件名 → 标签/备注」记录（只是调试笔记，不进角色包）"""

    def __init__(self, pet_id):
        self.pet_id = pet_id or "pet"
        self.data = {}          # fname -> {"kind": "exp"/"mot", "label": str, "note": str}
        self.load()

    def _path(self):
        return os.path.join(_base_dir(), "tmp", "live2d_labels_%s.json" % self.pet_id)

    def load(self):
        try:
            with open(self._path(), encoding="utf-8") as f:
                d = json.load(f) or {}
            self.data = d if isinstance(d, dict) else {}
        except Exception:
            self.data = {}

    def get(self, fname):
        return self.data.get(fname) or {}

    def set(self, fname, kind, label, note):
        self.data[fname] = {"kind": kind, "label": label, "note": note}

    def save(self) -> str:
        p = self._path()
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2, sort_keys=True)
        except Exception as e:
            print(f"[L2DDebug] ⚠ 标签保存失败: {e}")
        return p

    def table(self, kind=None):
        """对照表：[(kind, 文件名, 标签, 备注)]（只列已打过标签的）"""
        rows = []
        for fname in sorted(self.data):
            d = self.data[fname] or {}
            if kind and d.get("kind") != kind:
                continue
            rows.append((d.get("kind", "?"), fname, d.get("label", ""), d.get("note", "")))
        return rows

    def export_text(self) -> str:
        rows = self.table()
        if not rows:
            return "（还没有打过标签 —— 选中一个表情/动作，填「标签」再点保存）"
        lines = ["# %s 的 Live2D 表情/动作对照表" % self.pet_id,
                 "# 表情文件 → 标签　　动作文件 → 标签", ""]
        for kind, fname, label, note in rows:
            tag = "表情" if kind == "exp" else ("动作" if kind == "mot" else kind)
            tail = ("　// %s" % note) if note else ""
            lines.append("[%s] %s → %s%s" % (tag, fname, label or "(未填)", tail))
        return "\n".join(lines)


# ══════════════ 画布 ══════════════
class ModelCanvas(QOpenGLWidget):
    """极简 Live2D 画布：加载模型 + 循环渲染 + 表情/动作/参数控制"""

    def __init__(self, model_json, model_dir, scale, offset_x, offset_y,
                 default_expression, on_status=None, on_recorded=None,
                 on_progress=None, parent=None):
        super().__init__(parent)
        self.model_json = model_json
        self.model_dir = model_dir
        self.scale = scale
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.default_expression = default_expression
        self.on_status = on_status            # 回调：把"加载中/失败"说给界面听
        self.on_recorded = on_recorded        # 回调：一段动作录完（帧数 + 变化参数）
        self.on_progress = on_progress        # 回调：录制中每帧报一次帧数

        self.model = None
        self._ready = False
        self._failed = False
        self.error = ""

        self.expressions = {}          # 文件名 -> 路径
        self._cur_expression = None
        self.motions = {}              # 文件名 -> (组, 序号)
        self._motion_active = False
        self._cur_motion = None

        # ── 动作时间轴（拖动进度条定格）──
        # Update() 不带 dt：动作靠真实时间推进，所以"录制"就是边播边逐帧快照参数，
        # 之后拖进度条 = 把某一帧的参数写回去（SetParameterValue）并只 Draw 不 Update。
        self._recording = None         # 正在录的动作名（None=没在录）
        self._rec_frames = []          # [{参数id: 值}, ...]
        self._rec_ids = []             # 本模型的参数 id（录之前取一次）
        self._rec_moving = []          # [(id, 最小, 最大)]：这段动作真正在动的参数
        self._frozen = False           # True=定格在某一帧（paintGL 不再 Update）
        self._auto_flags = None        # 录/定格前的自动眨眼呼吸开关，恢复用

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.setInterval(16)
        self.timer.start()

    # ===== 参数快照 / 时间轴 =====
    def snapshot(self):
        """当前所有参数的 {id: 值}（GetParameterValue 要 int 下标，所以走 GetParameter(i)）"""
        out = {}
        try:
            for i in range(self.model.GetParameterCount()):
                p = self.model.GetParameter(i)
                out[p.id] = p.value
        except Exception:
            pass
        return out

    def start_record(self, fname):
        """开始录一段动作（真实时间逐帧快照）。返回是否真的开始录。"""
        if not self._ready or self.model is None:
            self._say("⚠ 模型还没就绪，等它加载完再录")
            return False
        if fname not in self.motions:
            self._say("⚠ 这个动作还没注册（换个动作或等列表刷新）")
            return False
        self._restore_auto()
        try:
            self._auto_flags = (True, True)
            self.model.SetAutoBlinkEnable(False)     # 别让自动眨眼/呼吸混进时间轴
            self.model.SetAutoBreathEnable(False)
        except Exception:
            pass
        self._frozen = False
        self._rec_frames = []
        self._rec_ids = list(self.snapshot().keys())
        self._recording = fname
        group, no = self.motions[fname]
        try:
            self.model.StopAllMotions()
            self.model.StartMotion(group, no, 3)
        except Exception as e:
            self._recording = None
            self._say("⚠ 动作播放失败：%s" % e)
            return False
        self._say("🔴 正在录制「%s」…（跟着播完，约几秒）" % fname)
        return True

    def _finish_record(self):
        fname, frames = self._recording, self._rec_frames
        self._recording = None
        moving = []
        if frames:
            for pid in self._rec_ids:
                vals = [f.get(pid) for f in frames if pid in f]
                if vals and (max(vals) - min(vals)) > 0.01:
                    moving.append((pid, min(vals), max(vals)))
        self._rec_moving = moving
        self._say("✅ 「%s」录完：%d 帧，其中 %d 个参数在动" % (fname, len(frames), len(moving)))
        if self.on_recorded:
            try:
                self.on_recorded(fname, len(frames), moving)
            except Exception as e:
                print(f"[L2DDebug] on_recorded 回调失败: {e}")
        self._restore_auto()

    def hold_index(self, idx):
        """定格到第 idx 帧（0 基）：把那一帧的参数写回模型，之后只画不更新"""
        if not self._rec_frames:
            self._say("⚠ 还没录制：先点「录这段动作」")
            return False
        idx = max(0, min(int(idx), len(self._rec_frames) - 1))
        if not self._ready or self.model is None:
            return False
        try:
            self.model.SetAutoBlinkEnable(False)
            self.model.SetAutoBreathEnable(False)
            self.model.StopAllMotions()
        except Exception:
            pass
        fr = self._rec_frames[idx]
        ok = 0
        for i in range(self.model.GetParameterCount()):
            p = self.model.GetParameter(i)
            if p.id in fr:
                try:
                    self.model.SetParameterValue(p.id, fr[p.id], 1.0)
                    ok += 1
                except Exception:
                    pass
        self._frozen = True
        self.update()
        self._say("⏸ 定格在第 %d / %d 帧（写回 %d 个参数）" % (idx + 1, len(self._rec_frames), ok))
        return True

    def resume_live(self):
        """解除定格，回到实时渲染"""
        self._frozen = False
        try:
            self.model.StopAllMotions()
        except Exception:
            pass
        if self.default_expression and self.default_expression in self.expressions:
            self.apply_expression(self.default_expression)
        else:
            self.reset_expressions()
        self._restore_auto()
        self._say("▶ 已解除定格，回到实时预览")
        self.update()

    def _restore_auto(self):
        if not self._ready or self.model is None or self._frozen:
            return      # 定格中别把自动眨眼/呼吸打开（会跟定格抢参数）
        try:
            self.model.SetAutoBlinkEnable(True)
            self.model.SetAutoBreathEnable(True)
        except Exception:
            pass
        self._auto_flags = None

    def rec_count(self):
        return len(self._rec_frames)

    def rec_moving(self):
        return list(self._rec_moving)

    def _say(self, msg):
        if self.on_status:
            try:
                self.on_status(msg)
            except Exception:
                pass

    # ===== GL =====
    def initializeGL(self):
        if self._failed:
            return
        try:
            import Live2d.live2d_ui as _lui
            _lui._ensure_live2d()
            from OpenGL.GL import (glEnable, GL_BLEND, glBlendFunc,
                                   GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, glClearColor)
            import live2d.v3 as l2d
            l2d.glInit()
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glClearColor(0.09, 0.10, 0.13, 1)   # 深色背景，方便看模型轮廓（paintGL 里还会再设一次）

            path = os.path.normpath(self.model_json).replace("\\", "/")
            self.model = l2d.LAppModel()
            self.model.LoadModelJson(path)
            if self.scale != 1.0 or self.offset_x or self.offset_y:
                try:
                    self.model.SetScale(self.scale)
                    self.model.SetOffset(self.offset_x, self.offset_y)
                except Exception:
                    pass
            for fname, fpath in scan_files(self.model_dir, ".exp3.json"):
                try:
                    self.model.LoadExtraExpression(fname, fpath)
                    self.expressions[fname] = fpath
                except Exception as e:
                    print(f"[L2DDebug] 表情注册失败 {fname}: {e}")
            for fname, fpath in scan_files(self.model_dir, ".motion3.json"):
                try:
                    no = self.model.LoadExtraMotion("emotion", fpath)
                    self.motions[fname] = ("emotion", no)
                except Exception as e:
                    print(f"[L2DDebug] 动作注册失败 {fname}: {e}")
            if self.default_expression and self.default_expression in self.expressions:
                self.apply_expression(self.default_expression)
            self._ready = True
            self._say("✅ 模型已加载：表情 %d 个 / 动作 %d 个"
                      % (len(self.expressions), len(self.motions)))
            print(f"[L2DDebug] 模型加载完成: {path}")
        except Exception as e:
            self._failed = True
            self.error = str(e)
            import traceback
            traceback.print_exc()
            self._say("❌ 模型加载失败：%s（显卡驱动/OpenGL 兼容问题？）" % e)
            print(f"[L2DDebug] 模型加载失败: {e}")

    def paintGL(self):
        if not self._ready or self._failed:
            return
        try:
            from OpenGL.GL import (glClear, GL_COLOR_BUFFER_BIT, glClearColor)
            # 每帧都要重设清屏色：Qt 画 FBO 时会把它改回白色，只在 initializeGL 设一次不够
            glClearColor(0.09, 0.10, 0.13, 1.0)
            glClear(GL_COLOR_BUFFER_BIT)
            if not self._frozen:
                # 定格时不再 Update()，否则动作会继续往下走，参数白写
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
        if self._recording:
            # 录制中：这一帧画完（Update 在 paintGL 里）就存一份参数快照
            self.update()          # 先让 paintGL 跑一次，拿到最新参数
            try:
                self._rec_frames.append(self.snapshot())
                done = self.model.IsMotionFinished()
            except Exception as e:
                print(f"[L2DDebug] 录制采样失败: {e}")
                done = True
            if self.on_progress:
                try:
                    self.on_progress(len(self._rec_frames))
                except Exception:
                    pass
            if done or len(self._rec_frames) >= 900:   # 15 秒上限，防卡死
                self._finish_record()
            return
        if self._motion_active:
            try:
                if self.model.IsMotionFinished():
                    self._motion_active = False
                    self._cur_motion = None
                    if self.default_expression:
                        self.apply_expression(self.default_expression)
                    else:
                        self.model.ResetExpressions()
                    self._say("动作播完，已恢复默认表情")
            except Exception:
                pass
        self.update()

    # ===== 控制接口 =====
    def apply_expression(self, exp_id):
        if not self._ready or self.model is None:
            print(f"[L2DDebug] 模型还没就绪，暂时不能切换表情（{exp_id}）")
            return
        if self._frozen:
            self._frozen = False       # 换表情就解除定格，否则 Update 被挡住、表情看不出来
            self._restore_auto()
        try:
            self.model.SetExpression(exp_id)
            self._cur_expression = exp_id
            self._say("表情：%s" % exp_id)
        except Exception as e:
            print(f"[L2DDebug] 表情失败 {exp_id}: {e}")

    def reset_expressions(self):
        try:
            self.model.ResetExpressions()
            self._cur_expression = None
            self._say("已复原表情")
        except Exception:
            pass

    def play_motion(self, fname):
        if not self._ready or self.model is None:
            print(f"[L2DDebug] 模型还没就绪，暂时不能播放动作（{fname}）")
            return
        if fname not in self.motions:
            print(f"[L2DDebug] 动作未注册: {fname}")
            return
        if self._frozen:
            self._frozen = False       # 放动作前先解除定格，不然画布不更新
            self._restore_auto()
        group, no = self.motions[fname]
        try:
            self.model.StopAllMotions()
            self.model.StartMotion(group, no, 3)
            self._motion_active = True
            self._cur_motion = fname
            self._say("动作：%s" % fname)
        except Exception as e:
            print(f"[L2DDebug] 动作播放失败 {fname}: {e}")

    def set_param(self, param_id, value):
        if not self._ready or self.model is None:
            return
        try:
            self.model.SetParameterValue(param_id, value, 1.0)
        except Exception:
            pass

    def reset_params(self):
        try:
            self.model.ResetParameters()
            self._say("已重置参数")
        except Exception:
            pass

    def stop(self):
        try:
            self.timer.stop()
        except Exception:
            pass


# ══════════════ 主题一致的调试器窗口 ══════════════
def _btn_qss(sel=False, small=True):
    fs = int(11 * 1.0)
    if sel:
        return (f"QPushButton {{ background: rgba({Color3.red()},{Color3.green()},{Color3.blue()},0.88);"
                f" color: white; border: 1px solid {Color3.name()}; border-radius: 6px;"
                f" padding: 3px 8px; font-size: {fs}px; font-weight: bold; }}")
    return (f"QPushButton {{ background: rgba(255,255,255,0.07); color: {Color1.name()};"
            f" border: 1px solid rgba(255,255,255,0.22); border-radius: 6px;"
            f" padding: 3px 8px; font-size: {fs}px; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.16); }}")


class Live2DDebuggerDialog(SiliconDialog):
    """Live2D 表情/动作调试器：看每个文件是什么效果 + 打标签（主题一致）。"""

    def __init__(self, pet_id=None, parent=None):
        from pets.pet_registry import (get_pet_ids, get_pet_config,
                                       get_live2d_model_json)
        self._get_pet_ids = get_pet_ids
        self._get_pet_config = get_pet_config
        self._get_model_json = get_live2d_model_json

        # 只列**有 Live2D 模型**的角色（没有模型的选进去只会是一片空白）
        self.pets = []
        for pid in get_pet_ids():
            try:
                mj = get_live2d_model_json(pid) or ""
            except Exception:
                mj = ""
            if mj and os.path.exists(mj):
                cfg = get_pet_config(pid) or {}
                self.pets.append((pid, str(cfg.get("display_name") or cfg.get("name") or pid)))
        want = pet_id or ""
        title = "Live2D 动作 / 表情调试器"
        super().__init__(title, parent, width=1180, height=760, opaque=True)

        self.canvas = None
        self._store = None
        self._sel = ("", "")            # (kind, fname)
        self._exp_btns, self._mot_btns = {}, {}

        lay = self.content
        lay.setContentsMargins(int(16 * M.scale if hasattr(M, "scale") else 16), 8, 16, 14)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.addWidget(QLabel("角色："))
        self.pet_combo = QComboBox()
        for pid, name in self.pets:
            self.pet_combo.addItem("%s（%s）" % (name, pid), pid)
        self.pet_combo.setMinimumWidth(220)
        self.pet_combo.currentIndexChanged.connect(self._on_pet_changed)
        head.addWidget(self.pet_combo)
        head.addStretch()
        tip = QLabel("点表情/动作即生效；选中后填「标签」并保存 → 生成对照表，照着配 pet.json")
        tip.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11 * 1.0)}px;")
        head.addWidget(tip)
        lay.addLayout(head)
        # 单独一行提示（不会被画布状态刷掉）：要求看的角色没有模型时用它说清楚
        self.warn_lbl = QLabel("")
        self.warn_lbl.setWordWrap(True)
        self.warn_lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11 * 1.0)}px;")
        self.warn_lbl.setVisible(False)
        lay.addWidget(self.warn_lbl)

        body = QHBoxLayout()
        body.setSpacing(10)

        # ── 左：画布 + 动作时间轴 ──
        self.canvas_holder = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas_holder)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas_layout.setSpacing(6)
        self.canvas_layout.addWidget(self._make_timeline())
        body.addWidget(self.canvas_holder, 3)

        # ── 右：控制面板（内容偏高：整块共用一个滚动条，任何字体/缩放下都不会被切掉。
        #     表情/动作列表不再各自套滚动条，否则会"滚动条套滚动条"）──
        panel = QWidget()
        panel.setMinimumWidth(300)      # 宽度跟着滚动区走（写死宽度会被滚动区切掉一列）
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(0, 0, 6, 0)
        pl.setSpacing(6)

        def _cap(text):
            lb = QLabel(text)
            lb.setWordWrap(True)          # 长标题换行，别压到下面的控件上
            lb.setStyleSheet(f"color: {Color1.name()}; font-size: {int(12 * 1.0)}px; font-weight: bold;")
            return lb

        pl.addWidget(_cap("表情（点击切换）"))
        self.exp_container = QWidget()
        self.exp_grid = QGridLayout(self.exp_container)
        self.exp_grid.setContentsMargins(0, 0, 0, 0)
        self.exp_grid.setSpacing(4)
        pl.addWidget(self.exp_container)

        pl.addWidget(_cap("动作（先选中，再录下来定格）"))
        self.mot_container = QWidget()
        self.mot_grid = QGridLayout(self.mot_container)
        self.mot_grid.setContentsMargins(0, 0, 0, 0)
        self.mot_grid.setSpacing(4)
        pl.addWidget(self.mot_container)

        # ── 打标签 ──
        pl.addWidget(_cap("给选中的那个打标签"))
        self.sel_lbl = QLabel("（先点上面任意一个表情或动作）")
        self.sel_lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11 * 1.0)}px;")
        self.sel_lbl.setWordWrap(True)
        pl.addWidget(self.sel_lbl)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("标签"))
        self.ed_label = QLineEdit()
        self.ed_label.setPlaceholderText("例如：高兴 / 打招呼")
        row1.addWidget(self.ed_label, 1)
        pl.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("备注"))
        self.ed_note = QLineEdit()
        self.ed_note.setPlaceholderText("可选：观察到什么动作/口型")
        row2.addWidget(self.ed_note, 1)
        pl.addLayout(row2)
        row3 = QGridLayout()
        b_save = QPushButton("💾 保存标签")
        b_save.clicked.connect(self._on_save_label)
        b_copy = QPushButton("📋 复制对照表")
        b_copy.clicked.connect(self._on_copy_table)
        b_exp = QPushButton("📄 导出对照表")
        b_exp.clicked.connect(self._on_export_table)
        for i, b in enumerate((b_save, b_copy, b_exp)):
            b.setStyleSheet(_btn_qss())
            b.setMinimumHeight(30)
            row3.addWidget(b, i // 2, i % 2)      # 两列排，字号大也不会被切掉
        pl.addLayout(row3)

        # ── 参数滑块 ──
        pl.addWidget(_cap("参数（拖动实时变化）"))
        self.sliders = {}
        pwrap = QWidget()
        pgrid = QGridLayout(pwrap)
        pgrid.setContentsMargins(0, 0, 0, 0)
        pgrid.setSpacing(2)
        for i, (param_id, lo, hi) in enumerate(PARAM_RANGES):
            lb = QLabel(param_id.replace("Param", ""))
            lb.setFixedWidth(96)
            lb.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11 * 1.0)}px;")
            sl = QSlider(Qt.Horizontal)
            sl.setRange(0, 200)
            sl.setValue(100)
            sl.valueChanged.connect(lambda v, p=param_id, a=lo, b=hi: self._on_slider(p, v, a, b))
            self.sliders[param_id] = sl
            pgrid.addWidget(lb, i, 0)
            pgrid.addWidget(sl, i, 1)
        pl.addWidget(pwrap)

        btns = QHBoxLayout()
        b_rp = QPushButton("重置参数")
        b_rp.clicked.connect(self._on_reset_params)
        b_re = QPushButton("复原表情")
        b_re.clicked.connect(lambda: self.canvas and self.canvas.reset_expressions())
        for b in (b_rp, b_re):
            b.setStyleSheet(_btn_qss())
            b.setMinimumHeight(30)
            btns.addWidget(b)
        pl.addLayout(btns)
        pl.addStretch(1)

        panel_scroll = QScrollArea()
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setFrameShape(QScrollArea.NoFrame)
        panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel_scroll.setFixedWidth(420)     # 固定右栏宽度（含滚动条），画布吃掉剩下的
        panel_scroll.setWidget(panel)
        body.addWidget(panel_scroll, 0)
        lay.addLayout(body)

        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11 * 1.0)}px;")
        lay.addWidget(self.status_lbl)

        # 初始角色
        idx = 0
        for i, (pid, _n) in enumerate(self.pets):
            if pid == want:
                idx = i
                break
        if self.pets:
            self.pet_combo.blockSignals(True)
            self.pet_combo.setCurrentIndex(idx)
            self.pet_combo.blockSignals(False)
            self._on_pet_changed(idx)
            # 要求看的角色没有模型 → 明说一句（否则会以为"点诺瓦却开了丛雨"）
            if want and want not in [pid for pid, _n in self.pets]:
                self.warn_lbl.setText(
                    "⚠ 角色「%s」没有 Live2D 模型（*.model3.json），下面显示的是「%s」的模型；"
                    "想调试它请先在「设置 → Live2D 模型」里给它选一个模型。"
                    % (want, self.pets[idx][1]))
                self.warn_lbl.setVisible(True)
        else:
            self.status_lbl.setText("")
            self.warn_lbl.setText("⚠ 没有任何角色带 Live2D 模型：先在「设置 → Live2D 模型」里"
                                  "给角色选一个 *.model3.json")
            self.warn_lbl.setVisible(True)

    # ── 动作时间轴（录一段 → 拖进度条定格） ──
    def _make_timeline(self):
        """画布下面那条时间轴：录一段动作，然后拖进度条定格到任意一帧。

        为什么要"录"：Live2D 的动作靠真实时间推进（Update 不带 dt），想停在中间某一帧，
        只能边播边把参数快照下来，再拖进度条把某一帧的参数写回去。
        """
        box = QWidget()
        tl = QVBoxLayout(box)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(4)

        row = QHBoxLayout()
        self.btn_rec = QPushButton("🔴 录这段动作")
        self.btn_rec.setToolTip("先点右边「动作」里的一个动作选中它，再点这里录；"
                                "录完拖下面的进度条就能定格到任意一帧")
        self.btn_rec.clicked.connect(self._on_record)
        self.btn_resume = QPushButton("▶ 解除定格")
        self.btn_resume.setToolTip("回到实时预览（自动眨眼/呼吸恢复）")
        self.btn_resume.clicked.connect(self._on_resume)
        for b in (self.btn_rec, self.btn_resume):
            b.setStyleSheet(_btn_qss())
            b.setMinimumHeight(30)
            row.addWidget(b)
        self.tl_lbl = QLabel("")
        self.tl_lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11 * 1.0)}px;")
        row.addWidget(self.tl_lbl, 1)
        tl.addLayout(row)

        self.tl_slider = QSlider(Qt.Horizontal)
        self.tl_slider.setRange(0, 0)
        self.tl_slider.setEnabled(False)
        self.tl_slider.setToolTip("拖动 = 定格到那一帧")
        self.tl_slider.valueChanged.connect(self._on_scrub)
        tl.addWidget(self.tl_slider)

        self.moving_view = QPlainTextEdit()
        self.moving_view.setReadOnly(True)
        self.moving_view.setMaximumHeight(96)
        self.moving_view.setPlaceholderText(
            "录完这段动作后，这里列出它真正在动的参数（名字 + 变化范围）")
        # ⚠ 别写死"黑底 + 深灰字"：浅色主题（经典 / 千恋万花）下那是"黑框里深灰字"，
        #   看不清（用户报的阴间配色）。改成用主题的输入框底色半透明 + 主题正文色。
        _c7 = Color7
        self.moving_view.setStyleSheet(
            f"QPlainTextEdit {{ background: rgba({_c7.red()},{_c7.green()},{_c7.blue()},150);"
            f" color: {Color1.name()};"
            f" border: 1px solid {Color5.name()}; border-radius: 6px;"
            f" font-size: {int(11 * 1.0)}px; }}")
        tl.addWidget(self.moving_view)
        self._timeline_reset()
        return box

    def _timeline_reset(self, tip=None):
        self._rec_name = ""
        self.tl_slider.blockSignals(True)
        self.tl_slider.setRange(0, 0)
        self.tl_slider.setValue(0)
        self.tl_slider.blockSignals(False)
        self.tl_slider.setEnabled(False)
        self.moving_view.setPlainText("")
        self.tl_lbl.setText(tip or "先在右边「动作」里点一个动作，再点「🔴 录这段动作」")

    def _on_record(self):
        if not self.canvas:
            return
        kind, fname = self._sel
        if kind != "mot" or not fname:
            self.status_lbl.setText("⚠ 先在右边「动作」里点一个要录的动作，再点「🔴 录这段动作」")
            self.tl_lbl.setText("⚠ 还没选动作：先点右边「动作」里的一个")
            return
        self.moving_view.setPlainText("")
        self._rec_name = fname
        self.tl_slider.blockSignals(True)
        self.tl_slider.setRange(0, 0)
        self.tl_slider.setValue(0)
        self.tl_slider.blockSignals(False)
        self.tl_slider.setEnabled(False)
        self.tl_lbl.setText("🔴 正在录「%s」…跟着它播完（几秒）" % fname)
        if not self.canvas.start_record(fname):
            self._rec_name = ""
            self.tl_lbl.setText("⚠ 没能开始录制：看下面状态栏的原因")

    def _on_progress(self, n):
        # 录制中让进度条自己涨，但别触发定格（所以 blockSignals）
        self.tl_slider.blockSignals(True)
        self.tl_slider.setRange(0, max(0, n - 1))
        self.tl_slider.setValue(max(0, n - 1))
        self.tl_slider.blockSignals(False)
        self.tl_lbl.setText("🔴 录制中… 已 %d 帧" % n)

    def _on_recorded(self, fname, n, moving):
        self._rec_name = fname
        self.tl_slider.setEnabled(n > 1)
        if n > 1:
            self.tl_slider.setValue(n - 1)      # 值变了会触发定格
            if not getattr(self.canvas, "_frozen", False):
                self.canvas.hold_index(n - 1)   # 值本来就在末帧时补一次
            self.tl_lbl.setText("已录「%s」共 %d 帧 · 已定格在末帧，拖进度条看中间" % (fname, n))
        else:
            self.tl_lbl.setText("⚠ 「%s」没采到帧（动作太短或没播起来）" % fname)
        if moving:
            lines = ["%s   %.2f → %.2f" % (pid, lo, hi) for pid, lo, hi in moving]
            self.moving_view.setPlainText("这段动作在动的参数（%d 个）：\n%s"
                                          % (len(moving), "\n".join(lines)))
        else:
            self.moving_view.setPlainText("这段动作没有明显变化的参数（可能是静态姿势）")

    def _on_scrub(self, v):
        if not self.canvas:
            return
        n = self.canvas.rec_count()
        if not n:
            return
        if self.canvas.hold_index(v):
            self.tl_lbl.setText("已录「%s」共 %d 帧 · 定格在第 %d 帧"
                                % (self._rec_name or "?", n, v + 1))

    def _on_resume(self):
        if not self.canvas:
            return
        if not self.canvas.rec_count():
            self.status_lbl.setText("ℹ 还没录过动作：先点「🔴 录这段动作」")
            return
        self.canvas.resume_live()
        self.tl_lbl.setText("▶ 已解除定格（已录「%s」共 %d 帧，拖进度条可再定格）"
                            % (self._rec_name or "?", self.canvas.rec_count()))

    def _on_reset_params(self):
        if not self.canvas:
            return
        self.canvas.resume_live()      # 定格中重置参数没意义，先回到实时
        self.canvas.reset_params()

    # ── 角色切换 ──
    def _on_pet_changed(self, idx):
        if not self.pets:
            return
        pet_id = self.pet_combo.itemData(idx)
        model_json = self._get_model_json(pet_id) or ""
        pet_dir = os.path.dirname(model_json) if model_json else ""
        try:
            from pets.pet_registry import get_live2d_display
            disp = get_live2d_display(pet_id) or {}
        except Exception:
            disp = {}
        self._store = LabelStore(pet_id)

        if self.canvas is not None:
            try:
                self.canvas.stop()
                self.canvas_layout.removeWidget(self.canvas)
                self.canvas.deleteLater()
            except Exception:
                pass
            self.canvas = None
        for k in (self._exp_btns, self._mot_btns):
            k.clear()
        self._sel = ("", "")
        self.sel_lbl.setText("（先点上面任意一个表情或动作）")
        self.ed_label.clear()
        self.ed_note.clear()
        self._timeline_reset()

        if not model_json or not os.path.exists(model_json):
            self.status_lbl.setText("⚠ 这个角色没有 Live2D 模型文件")
            return
        self.canvas = ModelCanvas(
            model_json, pet_dir,
            float(disp.get("scale") or 1.0), float(disp.get("offset_x") or 0.0),
            float(disp.get("offset_y") or 0.0), str(disp.get("default_expression") or ""),
            on_status=self.status_lbl.setText,
            on_recorded=self._on_recorded,
            on_progress=self._on_progress)
        self.canvas_layout.insertWidget(0, self.canvas, 1)   # 画布在上，时间轴在下
        self._refresh_lists()
        # 表情/动作列表要等 initializeGL 注册完才有（GL 是异步初始化的）
        QTimer.singleShot(600, self._refresh_lists)
        QTimer.singleShot(1600, self._refresh_lists)

    def _refresh_lists(self):
        if not self.canvas:
            return
        for grid, btns in ((self.exp_grid, self._exp_btns), (self.mot_grid, self._mot_btns)):
            while grid.count():
                item = grid.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        exps = sorted(self.canvas.expressions) or [f for f, _ in
                                                  scan_files(self.canvas.model_dir, ".exp3.json")]
        mots = sorted(self.canvas.motions) or [f for f, _ in
                                              scan_files(self.canvas.model_dir, ".motion3.json")]
        if not exps:
            self.exp_grid.addWidget(QLabel("（这个模型没有 .exp3.json 表情文件）"), 0, 0)
        if not mots:
            self.mot_grid.addWidget(QLabel("（这个模型没有 .motion3.json 动作文件）"), 0, 0)

        for i, fname in enumerate(exps):
            b = QPushButton(short_name(fname))
            b.setToolTip("文件：%s\n点击切换到这个表情" % fname)
            b.clicked.connect(lambda _=False, f=fname: self._pick("exp", f))
            b.setStyleSheet(_btn_qss())
            self.exp_grid.addWidget(b, i // 2, i % 2)
            self._exp_btns[fname] = b
        for i, fname in enumerate(mots):
            b = QPushButton(short_name(fname))
            b.setToolTip("文件：%s\n点击播放这个动作（播完自动回默认表情）；"
                         "选中后点「🔴 录这段动作」可录下来拖进度条定格" % fname)
            b.clicked.connect(lambda _=False, f=fname: self._pick("mot", f))
            b.setStyleSheet(_btn_qss())
            self.mot_grid.addWidget(b, i // 2, i % 2)
            self._mot_btns[fname] = b
        self._mark_selected()

    # ── 选中 / 打标签 ──
    def _pick(self, kind, fname):
        self._sel = (kind, fname)
        if self.canvas:
            if kind == "exp":
                self.canvas.apply_expression(fname)
            else:
                self.canvas.play_motion(fname)
        d = self._store.get(fname) if self._store else {}
        self.ed_label.setText(str(d.get("label") or ""))
        self.ed_note.setText(str(d.get("note") or ""))
        tag = "表情" if kind == "exp" else "动作"
        # 只显示短名，完整文件名放 tooltip / 对照表（长文件名在这个宽度下会被切掉）
        self.sel_lbl.setText("已选中%s：%s" % (tag, short_name(fname)))
        self.sel_lbl.setToolTip("文件：%s" % fname)
        self._mark_selected()

    def _mark_selected(self):
        kind, fname = self._sel
        for k, btns in (("exp", self._exp_btns), ("mot", self._mot_btns)):
            for name, b in btns.items():
                try:
                    want_sel = (k == kind and name == fname)
                    if bool(b.property("sel")) != want_sel:
                        b.setProperty("sel", want_sel)
                        b.setStyleSheet(_btn_qss(sel=want_sel))
                except Exception:
                    pass

    def _on_save_label(self):
        kind, fname = self._sel
        if not fname or not self._store:
            self.status_lbl.setText("⚠ 先在列表里点一个表情或动作，再保存标签")
            return
        self._store.set(fname, kind, self.ed_label.text().strip(), self.ed_note.text().strip())
        p = self._store.save()
        self.status_lbl.setText("✅ 已保存标签：%s → %s（%s）"
                                % (fname, self.ed_label.text().strip() or "(未填)",
                                   os.path.relpath(p, _base_dir()).replace("\\", "/")))
        # 保存后把按钮名字后面带上标签，一眼能对上
        b = (self._exp_btns if kind == "exp" else self._mot_btns).get(fname)
        if b is not None:
            label = self.ed_label.text().strip()
            b.setText("%s ← %s" % (short_name(fname), label) if label else short_name(fname))

    def _on_copy_table(self):
        if not self._store:
            return
        text = self._store.export_text()
        try:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
            self.status_lbl.setText("📋 对照表已复制到剪贴板（可直接贴给我）")
        except Exception as e:
            self.status_lbl.setText("⚠ 复制失败：%s" % e)

    def _on_export_table(self):
        if not self._store:
            return
        text = self._store.export_text()
        out = os.path.join(_base_dir(), "tmp", "live2d_labels_%s.txt" % self._store.pet_id)
        try:
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            self.status_lbl.setText("📄 已导出：%s" % os.path.relpath(out, _base_dir()).replace("\\", "/"))
        except Exception as e:
            page_msg(self, "导出失败", "写对照表失败。", str(e))

    def _on_slider(self, param_id, v, lo, hi):
        if not self.canvas or not self.canvas._ready:
            return
        self.canvas.set_param(param_id, lo + (hi - lo) * v / 200.0)


def open_debugger(pet_id=None, parent=None):
    """打开调试器（失败时给出主题一致的提示，绝不静默）

    ⚠ 以前这里会先关掉「Live2D 实时预览窗口」，理由是"Cubism 引擎是全局单例、两个画布
      会互相抢"→ 屏闪。**那个判断是错的**（真正的根因是各画布用了各自的 GL 上下文，
      入口用 silicon_ui.enable_shared_gl_contexts() 打开共享上下文后三个画布能并排渲染，
      实测见 _audit_fish9269/probe_l2d_two_canvases.py）。
      用户拍板：允许预览窗口与调试器同时开着（省得打个标签被顶掉），所以这里不再关任何窗口。
    """
    try:
        dlg = Live2DDebuggerDialog(pet_id=pet_id, parent=parent)
        dlg.setModal(False)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        return dlg
    except Exception as e:
        import traceback
        print(f"[L2DDebug] ⚠ 打开失败: {e}\n{traceback.format_exc()[:400]}")
        page_msg(parent, "打开 Live2D 调试器", "打开失败。", str(e))
        return None
